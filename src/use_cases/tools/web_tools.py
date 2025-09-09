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
            },
            {
                "name": "web.links",
                "description": "Extract (text, href) pairs from a page; hrefs resolved absolute.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "selector": {
                            "type": "string",
                            "description": "Anchor selector (default: 'a')",
                        },
                        "max_links": {"type": "integer", "description": "Default: 50"},
                        "timeout": {"type": "integer"},
                        "user_agent": {"type": "string"},
                        "max_html_bytes": {"type": "integer"},
                    },
                    "required": ["url"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "web.fetch_json",
                "description": "GET a JSON endpoint with optional query params and UA override.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "timeout": {"type": "integer"},
                        "user_agent": {"type": "string"},
                        "max_bytes": {"type": "integer"},
                    },
                    "required": ["url"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "web.readability",
                "description": "Extract main article-like content (heuristic) and title.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "timeout": {"type": "integer"},
                        "user_agent": {"type": "string"},
                        "max_html_bytes": {"type": "integer"},
                    },
                    "required": ["url"],
                    "additionalProperties": False,
                },
            },
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
            if name not in {
                "web.scrape",
                "web.links",
                "web.fetch_json",
                "web.readability",
            }:
                raise ValueError(f"Unknown tool: {name}")

            url = str(arguments.get("url") or "").strip()
            if not url:
                raise LLMError("Field 'url' is required.")
            self._validate_url(url)

            if name == "web.scrape":
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
                    url,
                    timeout=timeout,
                    user_agent=user_agent,
                    max_bytes=max_html_bytes,
                )
                tree = HTMLParser(html)
                title = self._extract_title(tree)
                scraped_items: list[Any] = []
                if selector:
                    try:
                        nodes = tree.css(selector)
                    except Exception as e:
                        raise LLMError(f"Invalid CSS selector: {e}")
                else:
                    node = tree.css_first("body")
                    nodes = [node] if node else []
                for node in nodes[:max_nodes]:
                    if attribute == "html":
                        try:
                            scraped_items.append(node.html)
                        except Exception:
                            scraped_items.append("")
                    elif attribute.startswith("attr:"):
                        attr_name = attribute.split(":", 1)[1].strip()
                        try:
                            scraped_items.append(node.attributes.get(attr_name, ""))
                        except Exception:
                            scraped_items.append("")
                    else:
                        try:
                            txt = node.text(separator=" ", strip=True)
                            if strip_ws:
                                txt = " ".join((txt or "").split())
                            scraped_items.append(txt)
                        except Exception:
                            scraped_items.append("")
                return json.dumps(
                    {
                        "status": "ok",
                        "url": url,
                        "title": title,
                        "count": len(scraped_items),
                        "items": scraped_items,
                    },
                    ensure_ascii=False,
                )

            if name == "web.links":
                from urllib.parse import urljoin

                selector = str(arguments.get("selector") or "a").strip() or "a"
                max_links = int(arguments.get("max_links") or 50)
                max_links = max(1, min(max_links, 500))
                timeout = int(arguments.get("timeout") or 12)
                user_agent = arguments.get("user_agent")
                if user_agent is not None:
                    user_agent = str(user_agent)
                max_html_bytes = int(arguments.get("max_html_bytes") or 1_000_000)

                html = self._fetch(
                    url,
                    timeout=timeout,
                    user_agent=user_agent,
                    max_bytes=max_html_bytes,
                )
                tree = HTMLParser(html)
                links: list[dict[str, str]] = []
                try:
                    nodes = tree.css(selector)
                except Exception as e:
                    raise LLMError(f"Invalid CSS selector: {e}")
                for n in nodes:
                    try:
                        href = (n.attributes.get("href") or "").strip()
                        if not href:
                            continue
                        abs_url = urljoin(url, href)
                        text = n.text(separator=" ", strip=True) or ""
                        links.append({"text": text, "url": abs_url})
                        if len(links) >= max_links:
                            break
                    except Exception:
                        continue
                return json.dumps(
                    {"status": "ok", "url": url, "links": links, "count": len(links)},
                    ensure_ascii=False,
                )

            if name == "web.fetch_json":
                timeout = int(arguments.get("timeout") or 12)
                user_agent = arguments.get("user_agent")
                if user_agent is not None:
                    user_agent = str(user_agent)
                max_bytes = int(arguments.get("max_bytes") or 1_000_000)
                headers = {
                    "User-Agent": user_agent
                    or "Mozilla/5.0 (compatible; HackCoder/1.0)",
                    "Accept": "application/json",
                }
                req = urllib.request.Request(url, headers=headers, method="GET")
                try:
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        raw = resp.read(max_bytes + 1)
                        if len(raw) > max_bytes:
                            raw = raw[:max_bytes]
                        try:
                            data = json.loads(raw.decode("utf-8", errors="ignore"))
                        except Exception:
                            data = None
                        return json.dumps(
                            {"status": "ok", "url": url, "json": data},
                            ensure_ascii=False,
                        )
                except Exception as e:
                    raise LLMError(f"Fetch JSON failed: {e}")

            if name == "web.readability":
                timeout = int(arguments.get("timeout") or 12)
                user_agent = arguments.get("user_agent")
                if user_agent is not None:
                    user_agent = str(user_agent)
                max_html_bytes = int(arguments.get("max_html_bytes") or 1_000_000)
                html = self._fetch(
                    url,
                    timeout=timeout,
                    user_agent=user_agent,
                    max_bytes=max_html_bytes,
                )
                tree = HTMLParser(html)
                title = self._extract_title(tree)
                # Simple heuristic: main, article, or largest text block of divs
                candidates = [
                    tree.css_first("main"),
                    tree.css_first("article"),
                    tree.css_first("div#content"),
                ]
                node = next((n for n in candidates if n), None)
                if not node:
                    # fallback: the longest <p>-text parent
                    ps = tree.css("p")
                    best_parent = None
                    best_len = 0
                for p in ps:
                    parent = p.parent
                    if parent is None:
                        continue
                    try:
                        txt = parent.text(separator=" ", strip=True)
                        length = len(txt or "")
                        if length > best_len:
                            best_len = length
                            best_parent = parent
                    except Exception:
                        continue
                    node = best_parent
                content = ""
                if node:
                    try:
                        content = node.text(separator="\n", strip=True)
                    except Exception:
                        content = ""
                return json.dumps(
                    {"status": "ok", "url": url, "title": title, "content": content},
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
