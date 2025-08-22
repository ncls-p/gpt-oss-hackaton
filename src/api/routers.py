"""
FastAPI router definitions for the API endpoints.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.container import container
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
)

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
