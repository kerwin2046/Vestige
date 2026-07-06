from __future__ import annotations

import asyncio
import json
import shutil
import subprocess

from search.web._filter import filter_by_domains
from search.web.exa import exa_query_params


def _exa_dict_snippet(item: dict) -> str:
    highlights = item.get("highlights") or []
    if highlights:
        first = highlights[0]
        return first if isinstance(first, str) else str(first)
    summary = item.get("summary") or ""
    if summary:
        return summary
    text = item.get("text") or ""
    return text[:500] if text else ""


def _extract_exa_results(data) -> list:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []

    if isinstance(data.get("results"), list):
        return data["results"]

    structured = data.get("structuredContent")
    if isinstance(structured, dict) and isinstance(structured.get("results"), list):
        return structured["results"]

    nested = data.get("raw")
    if isinstance(nested, dict):
        found = _extract_exa_results(nested)
        if found:
            return found

    content = data.get("content")
    if isinstance(content, list):
        for entry in content:
            if not isinstance(entry, dict):
                continue
            if entry.get("type") == "json":
                payload = entry.get("json")
                if payload is not None:
                    found = _extract_exa_results(payload)
                    if found:
                        return found
            text = entry.get("text") if entry.get("type") == "text" else None
            if not text:
                continue
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                continue
            found = _extract_exa_results(parsed)
            if found:
                return found
    return []


def parse_mcporter_exa_response(raw_text: str) -> list[dict]:
    data = json.loads(raw_text)
    if isinstance(data, dict) and data.get("issue"):
        issue = data.get("issue")
        server = data.get("server", "exa")
        tool = data.get("tool", "web_search_exa")
        raise RuntimeError(f"mcporter 调用失败 ({server}.{tool}): {issue}")

    out = []
    for item in _extract_exa_results(data)[:100]:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not url:
            continue
        out.append(
            {
                "url": url,
                "title": item.get("title") or "",
                "snippet": _exa_dict_snippet(item),
                "engine": "exa-mcp",
            }
        )
    return out


def build_mcporter_exa_args(query: str, max_results: int) -> dict:
    clean_query, include_domains = exa_query_params(query)
    args: dict = {
        "query": clean_query,
        "numResults": min(max(max_results, 1), 100),
    }
    if include_domains:
        args["includeDomains"] = include_domains
    return args


async def search(
    query: str,
    count: int,
    *,
    filter_list: list[str] | None = None,
) -> list[dict]:
    from config import EXA_MCP_TIMEOUT_SEC, MCPORTER_BIN

    mcporter_bin = MCPORTER_BIN
    if not shutil.which(mcporter_bin):
        raise RuntimeError(
            f"未找到 {mcporter_bin!r}。请先安装: npm install -g mcporter，"
            "并运行: mcporter config add exa https://mcp.exa.ai/mcp"
        )

    args = build_mcporter_exa_args(query, count)
    cmd = [
        mcporter_bin,
        "call",
        "exa.web_search_exa",
        "--args",
        json.dumps(args, ensure_ascii=False),
        "--output",
        "json",
    ]

    def _sync() -> str:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=EXA_MCP_TIMEOUT_SEC,
            check=False,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            hint = "若尚未配置 Exa MCP，请运行: mcporter config add exa https://mcp.exa.ai/mcp"
            raise RuntimeError(err or f"mcporter 退出码 {proc.returncode}。{hint}")
        return proc.stdout

    raw = await asyncio.to_thread(_sync)
    out = parse_mcporter_exa_response(raw)
    return filter_by_domains(out, filter_list)
