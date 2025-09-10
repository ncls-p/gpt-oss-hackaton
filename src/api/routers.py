"""
FastAPI router definitions for the API endpoints.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse

from src.api.dependencies import (
    get_generate_text_uc,
    get_list_files_uc,
    get_search_files_uc,
)
from src.api.schemas import (
    ErrorResponse,
    FileInfo,
    FileListResponse,
    GenerateTextRequest,
    GenerateTextResponse,
    ToolStep,
    ToolsRequest,
    ToolsResponse,
)
from src.container import container

router = APIRouter()


@router.get(
    "/files", response_model=FileListResponse, responses={400: {"model": ErrorResponse}}
)
def list_files(
    directory: str = Query(..., description="Directory path to list files from"),
):
    """
    List files in a directory.

    Args:
        directory: Path to the directory to list files from

    Returns:
        FileListResponse: List of files in the directory

    Raises:
        HTTPException: If listing files fails
    """
    try:
        files = get_list_files_uc().execute(directory)
        return FileListResponse(files=[FileInfo.from_entity(f) for f in files])
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/files/search",
    response_model=FileListResponse,
    responses={400: {"model": ErrorResponse}},
)
def search_files(
    directory: str = Query(..., description="Directory path to search in"),
    pattern: str = Query(..., description="Search pattern (e.g., '*.py')"),
    recursive: Optional[bool] = Query(
        False, description="Whether to search recursively"
    ),
):
    """
    Search for files matching a pattern in a directory.

    Args:
        directory: Path to the directory to search in
        pattern: Search pattern (e.g., "*.py", "test*")
        recursive: Whether to search recursively (default: False)

    Returns:
        FileListResponse: List of files matching the pattern

    Raises:
        HTTPException: If searching files fails
    """
    try:
        if recursive:
            files = get_search_files_uc().execute_recursive(directory, pattern)
        else:
            files = get_search_files_uc().execute(directory, pattern)
        return FileListResponse(files=[FileInfo.from_entity(f) for f in files])
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/generate-text",
    response_model=GenerateTextResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def generate_text(body: GenerateTextRequest):
    """
    Generate text using an LLM.

    Args:
        body: Request body containing prompt and optional parameters

    Returns:
        GenerateTextResponse: Generated text response

    Raises:
        HTTPException: If text generation fails
    """
    try:
        use_case = get_generate_text_uc()

        # Get model info for response
        llm_adapter = container.get_llm_adapter()
        model_info = {}
        try:
            model_info = llm_adapter.get_model_info()
        except Exception:
            # If we can't get model info, continue without it
            pass

        # Generate text
        if body.system_message:
            text = use_case.execute_with_system_message(
                prompt=body.prompt,
                system_message=body.system_message,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
            )
        else:
            text = use_case.execute(
                prompt=body.prompt,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
            )

        return GenerateTextResponse(
            text=text,
            model=model_info.get("model"),
            provider=model_info.get("provider"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/assistant/tools",
    response_model=ToolsResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def assistant_tools(body: ToolsRequest):
    """
    Run a tools-enabled assistant interaction and return the final text and a trace of tool calls.
    """
    try:
        # We specifically need the tools-enabled adapter
        from src.adapters.llm.openai_tools_adapter import OpenAIToolsAdapter

        llm_tools = container.get_llm_tools_adapter()
        if not isinstance(llm_tools, OpenAIToolsAdapter):
            raise RuntimeError("Tools-enabled LLM adapter is not available")

        def _confirm_tool(name: str, arguments: dict[str, object]):
            try:
                if name == "system.exec_custom" and not bool(body.allow_exec_custom):
                    import json as _json
                    payload = {
                        "status": "denied",
                        "message": "system.exec_custom denied by API (allow_exec_custom=false)",
                    }
                    return {"handled": True, "result": _json.dumps(payload, ensure_ascii=False)}
            except Exception:
                pass
            # Approve all other tools by default
            return True

        result = llm_tools.run_with_trace(
            prompt=body.prompt,
            system_message=body.system_message,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            tool_max_steps=body.tool_max_steps,
            require_final_tool=body.require_final_tool,
            allow_exec_custom=bool(body.allow_exec_custom),
            confirm_tool=_confirm_tool,
        )

        # Normalize steps into schema
        steps: list[ToolStep] = []
        for s in result.get("steps", []):
            name = s.get("name")
            arguments = s.get("arguments", {})
            res = s.get("result", "")
            steps.append(ToolStep(name=name, arguments=arguments, result=res))

        return ToolsResponse(text=result.get("text", ""), steps=steps)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/assistant/tools/stream")
def assistant_tools_stream(
    prompt: str = Query(...),
    system_message: Optional[str] = Query(None),
    temperature: float = Query(0.7),
    max_tokens: int = Query(800),
    tool_max_steps: int = Query(4),
    require_final_tool: bool = Query(True),
    allow_exec_custom: bool = Query(False),
):
    """Server-Sent Events (SSE)-style stream of tool steps and final text.

    Emits events:
    - event: step  data: {phase,name,arguments|result|error}
    - event: final data: {text, steps}
    """
    from queue import Queue, Empty
    from threading import Thread
    import json as _json

    # We specifically need the tools-enabled adapter
    from src.adapters.llm.openai_tools_adapter import OpenAIToolsAdapter

    llm_tools = container.get_llm_tools_adapter()
    if not isinstance(llm_tools, OpenAIToolsAdapter):
        raise HTTPException(status_code=500, detail="Tools-enabled LLM adapter is not available")

    q: Queue[str] = Queue()

    def on_step(ev: dict):
        try:
            q.put_nowait(f"event: step\n" + "data: " + _json.dumps(ev, ensure_ascii=False) + "\n\n")
        except Exception:
            pass

    def confirm_tool(name: str, arguments: dict[str, object]):
        try:
            if name == "system.exec_custom" and not bool(allow_exec_custom):
                payload = {
                    "status": "denied",
                    "message": "system.exec_custom denied by API (allow_exec_custom=false)",
                }
                return {"handled": True, "result": _json.dumps(payload, ensure_ascii=False)}
        except Exception:
            pass
        # Approve all other tools by default
        return True

    def worker():
        try:
            result = llm_tools.run_chat_turn_with_trace(
                messages=[],
                user_text=prompt,
                system_message=system_message,
                temperature=temperature,
                max_tokens=max_tokens,
                tool_max_steps=tool_max_steps,
                require_final_tool=require_final_tool,
                on_step=on_step,
                allow_exec_custom=bool(allow_exec_custom),
                confirm_tool=confirm_tool,
            )
            q.put_nowait(
                "event: final\n" + "data: " + _json.dumps({"text": result.get("text",""), "steps": result.get("steps", [])}, ensure_ascii=False) + "\n\n"
            )
        except Exception as e:
            try:
                q.put_nowait(
                    "event: error\n" + "data: " + _json.dumps({"error": str(e)}, ensure_ascii=False) + "\n\n"
                )
            except Exception:
                pass
        finally:
            try:
                q.put_nowait("event: done\n" + "data: {}\n\n")
            except Exception:
                pass

    Thread(target=worker, daemon=True).start()

    def gen():
        try:
            while True:
                try:
                    item = q.get(timeout=0.5)
                except Empty:
                    continue
                yield item
                if item.startswith("event: done"):
                    break
        except Exception:
            return

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/ui/tools", response_class=HTMLResponse)
def tools_ui():
    """Minimal web UI to interact with the tools-enabled assistant."""
    html = """
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>LLM Tools UI</title>
  <style>
    body { font: 14px system-ui, -apple-system, sans-serif; margin: 24px; }
    textarea { width: 100%; height: 120px; }
    input, button, select { font: inherit; }
    .row { margin: 8px 0; }
    pre { background: #f6f8fa; padding: 12px; overflow-x: auto; }
  </style>
  </head>
  <body>
    <h1>LLM Tools</h1>
    <div class=\"row\">
      <label>Prompt</label>
      <textarea id=\"prompt\" placeholder=\"Ex: Open the Terminal application and list files in the ~/ folder\"></textarea>
    </div>
    <div class=\"row\">
      <label>System message (optional)</label>
      <input id=\"system\" type=\"text\" style=\"width:100%\" placeholder=\"You are a computer assistant...\" />
    </div>
    <div class=\"row\">
      <label>Temperature</label>
      <input id=\"temp\" type=\"number\" step=\"0.1\" value=\"0.7\" />
      <label style=\"margin-left:12px\">Max tokens</label>
      <input id=\"max\" type=\"number\" value=\"800\" />
      <label style=\"margin-left:12px\">Tool steps</label>
      <input id=\"steps\" type=\"number\" value=\"2\" />
      <label style=\"margin-left:12px\">Require final tool</label>
      <input id=\"finalRequired\" type=\"checkbox\" checked />
    </div>
    <div class=\"row\">
      <label>Allow exec_custom</label>
      <input id=\"allowExec\" type=\"checkbox\" />
    </div>
    <div class=\"row\">
      <button id=\"run\">Run</button>
    </div>
    <div class=\"row\">
      <h3>Final Text</h3>
      <pre id=\"final\"></pre>
      <h3>Steps</h3>
      <pre id=\"trace\"></pre>
    </div>
    <script>
      async function run() {
        const prompt = document.getElementById('prompt').value;
        const system = document.getElementById('system').value || null;
        const temperature = parseFloat(document.getElementById('temp').value);
        const max_tokens = parseInt(document.getElementById('max').value, 10);
        const tool_max_steps = parseInt(document.getElementById('steps').value, 10);
        const res = await fetch('/assistant/tools', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt, system_message: system, temperature, max_tokens, tool_max_steps, require_final_tool: document.getElementById('finalRequired').checked, allow_exec_custom: document.getElementById('allowExec').checked })
        });
        const data = await res.json();
        if (!res.ok) {
          document.getElementById('final').textContent = 'Error: ' + (data.detail || JSON.stringify(data));
          document.getElementById('trace').textContent = '';
          return;
        }
        document.getElementById('final').textContent = data.text || '';
        document.getElementById('trace').textContent = JSON.stringify(data.steps, null, 2);
      }
      document.getElementById('run').addEventListener('click', run);
    </script>
  </body>
 </html>
    """
    return HTMLResponse(content=html, status_code=200)
