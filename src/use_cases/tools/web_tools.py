"""
Tools "web.*" for fetching and scraping web pages using selectolax.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Any, Optional
from urllib.parse import urlparse

from selectolax.parser import HTMLParser

from src.exceptions import LLMError
from src.ports.llm.tools_port import ToolsHandlerPort, ToolSpec


class WebToolsHandler(ToolsHandlerPort):
    """Handler for simple web scraping using selectolax.

    Exposes one primary tool:
    - web.scrape: fetch a URL and extract content using a CSS selector
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger = logger or logging.getLogger(__name__)

    def available_tools(self) -> list[ToolSpec]:
        return [
            {
                "name": "web.scrape",
                "description": (
                    "Fetch a web page and extract content with a CSS selector using selectolax. "
                    "Return title and a list of extracted items."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Absolute URL to fetch",
                        },
                        "selector": {
                            "type": "string",
                            "description": "CSS selector (e.g., 'article', 'h1', 'div.content p')",
                        },
                        "attribute": {
                            "type": "string",
                            "description": (
                                "What to extract from selected nodes: 'text' (default), 'html', "
                                "or 'attr:<name>' (e.g., 'attr:href')."
                            ),
                        },
                        "max_nodes": {
                            "type": "integer",
                            "description": "Maximum nodes to extract (default: 20)",
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "HTTP timeout seconds (default: 12)",
                        },
                        "user_agent": {
                            "type": "string",
                            "description": "Override User-Agent header",
                        },
                        "max_html_bytes": {
                            "type": "integer",
                            "description": "Maximum bytes to read from response (default: 1000000)",
                        },
                        "strip_whitespace": {
                            "type": "boolean",
                            "description": "Strip and collapse whitespace for text (default: true)",
                        },
                    },
                    "required": ["url"],
                    "additionalProperties": False,
                },
            }
        ]

    # ---------------- private helpers ----------------
    def _validate_url(self, url: str) -> None:
        try:
            p = urlparse(url)
            if p.scheme not in ("http", "https"):
                raise LLMError("Only http/https URLs are supported")
            if not p.netloc:
                raise LLMError("Invalid URL: missing host")
        except Exception as e:
            raise LLMError(f"Invalid URL: {e}")

    def _fetch(
        self, url: str, timeout: int, user_agent: Optional[str], max_bytes: int
    ) -> str:
        headers = {
            "User-Agent": user_agent
            or "Mozilla/5.0 (compatible; HackCoder/1.0; +https://example.local)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
        }
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec - tool-controlled URL
                raw = resp.read(max_bytes + 1)
                if len(raw) > max_bytes:
                    raw = raw[:max_bytes]
                # Try to decode from HTTP headers, else fallback to utf-8
                charset = self._get_charset(resp.headers.get("Content-Type", ""))
                try:
                    return raw.decode(charset or "utf-8", errors="ignore")
                except Exception:
                    return raw.decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as e:
            raise LLMError(f"HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise LLMError(f"URL error: {e.reason}")
        except Exception as e:
            raise LLMError(f"Fetch failed: {e}")

    def _get_charset(self, content_type: str) -> Optional[str]:
        try:
            m = re.search(r"charset=([\w\-]+)", content_type, re.IGNORECASE)
            return m.group(1) if m else None
        except Exception:
            return None

    def _extract_title(self, tree: HTMLParser) -> Optional[str]:
        try:
            t = tree.css_first("title")
            if t and t.text():
                return t.text().strip()
        except Exception:
            pass
        try:
            h1 = tree.css_first("h1")
            if h1 and h1.text():
                return h1.text().strip()
        except Exception:
            pass
        return None

    # ---------------- dispatch ----------------
    def dispatch(self, name: str, arguments: dict[str, Any]) -> Any:
        try:
            if name != "web.scrape":
                raise ValueError(f"Unknown tool: {name}")

            url = str(arguments.get("url") or "").strip()
            if not url:
                raise LLMError("Field 'url' is required.")
            self._validate_url(url)

            selector = str(arguments.get("selector") or "").strip()
            attribute = str(arguments.get("attribute") or "text").strip().lower()
            max_nodes = int(arguments.get("max_nodes") or 20)
            max_nodes = max(1, min(max_nodes, 200))
            timeout = int(arguments.get("timeout") or 12)
            timeout = max(1, min(timeout, 30))
            user_agent = arguments.get("user_agent")
            if user_agent is not None:
                user_agent = str(user_agent)
            max_html_bytes = int(arguments.get("max_html_bytes") or 1_000_000)
            max_html_bytes = max(10_000, min(max_html_bytes, 5_000_000))
            strip_ws = bool(arguments.get("strip_whitespace", True))

            html = self._fetch(
                url, timeout=timeout, user_agent=user_agent, max_bytes=max_html_bytes
            )
            tree = HTMLParser(html)

            title = self._extract_title(tree)
            items: list[Any] = []
            if selector:
                try:
                    nodes = tree.css(selector)
                except Exception as e:
                    raise LLMError(f"Invalid CSS selector: {e}")
            else:
                # Default to body
                node = tree.css_first("body")
                nodes = [node] if node else []

            for node in nodes[:max_nodes]:
                if attribute == "html":
                    try:
                        items.append(node.html)
                    except Exception:
                        items.append("")
                elif attribute.startswith("attr:"):
                    attr_name = attribute.split(":", 1)[1].strip()
                    try:
                        items.append(node.attributes.get(attr_name, ""))
                    except Exception:
                        items.append("")
                else:
                    # text
                    try:
                        txt = node.text(separator=" ", strip=True)
                        if strip_ws:
                            txt = " ".join((txt or "").split())
                        items.append(txt)
                    except Exception:
                        items.append("")

            return json.dumps(
                {
                    "status": "ok",
                    "url": url,
                    "title": title,
                    "count": len(items),
                    "items": items,
                },
                ensure_ascii=False,
            )
        except ValueError:
            # Unknown tool for this handler
            raise
        except LLMError:
            raise
        except Exception as e:
            self._logger.error(f"Error in {name}: {e}")
            raise LLMError(f"Failed to execute tool {name}: {str(e)}")
