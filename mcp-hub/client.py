import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


HUB_DIR = Path(__file__).resolve().parent


def _server_env() -> Dict[str, str]:
    env = os.environ.copy()
    python_path = str(HUB_DIR)
    if env.get("PYTHONPATH"):
        python_path = python_path + os.pathsep + env["PYTHONPATH"]
    env["PYTHONPATH"] = python_path
    return env


def _extract_text_content(content: Any) -> Optional[str]:
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return content.get("text")
    return getattr(content, "text", None)


def _normalize_tool_result(result: Any) -> Dict[str, Any]:
    if isinstance(result, dict):
        if isinstance(result.get("result"), dict):
            return result["result"]
        return result

    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        if isinstance(structured.get("result"), dict):
            return structured["result"]
        return structured

    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        if isinstance(structured.get("result"), dict):
            return structured["result"]
        return structured

    content_items = getattr(result, "content", None) or []
    for item in content_items:
        text = _extract_text_content(item)
        if not text:
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            if isinstance(parsed.get("result"), dict):
                return parsed["result"]
            return parsed

    return {
        "ok": False,
        "error": {
            "code": "INVALID_MCP_RESPONSE",
            "message": "A tool MCP retornou uma resposta em formato inesperado.",
            "details": repr(result),
        },
    }


class FinanceMCPClient:
    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        result = await self._session.call_tool(name, arguments)
        return _normalize_tool_result(result)


@asynccontextmanager
async def finance_client() -> AsyncIterator[FinanceMCPClient]:
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "servers.finance"],
        env=_server_env(),
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield FinanceMCPClient(session)
