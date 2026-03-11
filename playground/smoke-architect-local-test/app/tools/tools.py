from importlib import import_module
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Callable
from urllib.parse import quote_plus

import httpx
from app.config.settings import settings
from app.plugins.loader import load_plugin_tools


def search_tool(query: str) -> str:
    text = query.strip()
    if not text:
        return "empty query"

    try:
        return _wikipedia_search(text)
    except Exception:
        return _local_knowledge_search(text)


def calculator_tool(expression: str) -> str:
    try:
        return str(eval(expression, {"__builtins__": {}}))
    except Exception:
        return "invalid expression"


def database_query(query: str) -> str:
    statement = query.strip()
    if not statement:
        return "empty query"
    if not _is_read_only_query(statement):
        return "blocked: only read-only SQL statements are allowed"

    try:
        with _connect_db() as conn:
            cursor = conn.execute(statement)
            rows = cursor.fetchmany(max(1, settings.app_db_max_rows))
            columns = [item[0] for item in (cursor.description or [])]
    except sqlite3.Error as exc:
        return f"sql_error: {exc}"

    if not rows:
        return json.dumps({"columns": columns, "rows": []}, ensure_ascii=False)

    payload_rows: list[dict[str, str]] = []
    for row in rows:
        payload_rows.append({key: str(row[key]) if row[key] is not None else "" for key in row.keys()})
    return json.dumps({"columns": columns, "rows": payload_rows}, ensure_ascii=False)


BUILTIN_TOOLS: dict[str, Callable[[str], str]] = {
    "search_tool": search_tool,
    "calculator_tool": calculator_tool,
    "database_query": database_query,
}


def contract_parser(input_text: str) -> str:
    return _run_named_tool("contract_parser", input_text)


def clause_risk_analyzer(input_text: str) -> str:
    return _run_named_tool("clause_risk_analyzer", input_text)


def legal_search(input_text: str) -> str:
    return _run_named_tool("legal_search", input_text)



def _load_external_tools() -> dict[str, Callable[[str], str]]:
    discovered: dict[str, Callable[[str], str]] = {}
    for file in Path(__file__).parent.glob("*_tool.py"):
        module = import_module(f"app.tools.{file.stem}")
        fn = getattr(module, "tool", None)
        if callable(fn):
            discovered[file.stem] = fn
    return discovered


def get_tools() -> dict[str, Callable[[str], str]]:
    tools = dict(BUILTIN_TOOLS)
    tools["contract_parser"] = contract_parser
    tools["clause_risk_analyzer"] = clause_risk_analyzer
    tools["legal_search"] = legal_search
    tools.update(_load_external_tools())
    tools.update(load_plugin_tools())
    return tools


def _run_named_tool(tool_name: str, input_text: str) -> str:
    normalized = tool_name.strip().lower()
    text = input_text.strip()
    if not text:
        return "empty input"

    if "search" in normalized:
        return search_tool(text)
    if any(token in normalized for token in ("calc", "math")):
        return calculator_tool(text)
    if any(token in normalized for token in ("db", "sql", "query")):
        return database_query(text)
    if any(token in normalized for token in ("parser", "extract")):
        return _parse_text_payload(tool_name, text)
    if any(token in normalized for token in ("analyzer", "analysis", "classifier", "risk", "score")):
        return _analyze_text_payload(tool_name, text)
    return _transform_text_payload(tool_name, text)


def _is_read_only_query(statement: str) -> bool:
    normalized = " ".join(statement.strip().split())
    if not normalized:
        return False
    head = normalized.split(" ", 1)[0].lower()
    if head not in {"select", "with", "pragma"}:
        return False
    body = normalized[:-1] if normalized.endswith(";") else normalized
    return ";" not in body


def _connect_db() -> sqlite3.Connection:
    db_path = Path(settings.app_db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _bootstrap_db(conn)
    return conn


def _bootstrap_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()


def _wikipedia_search(query: str) -> str:
    limit = min(max(1, settings.app_db_max_rows), 10)
    url = (
        "https://en.wikipedia.org/w/api.php?action=query&list=search&format=json"
        f"&srlimit={limit}&srsearch={quote_plus(query)}"
    )
    response = httpx.get(url, timeout=max(1.0, settings.llm_request_timeout))
    response.raise_for_status()
    data = response.json()
    payload = data.get("query", {}).get("search", [])
    if not isinstance(payload, list):
        return json.dumps({"query": query, "source": "wikipedia", "results": []}, ensure_ascii=False)

    results: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        snippet = _strip_html(str(item.get("snippet", "")).strip())
        pageid = item.get("pageid")
        if not title:
            continue
        results.append(
            {
                "title": title,
                "snippet": snippet,
                "url": f"https://en.wikipedia.org/?curid={pageid}" if pageid else "",
            }
        )

    return json.dumps({"query": query, "source": "wikipedia", "results": results}, ensure_ascii=False)


def _local_knowledge_search(query: str) -> str:
    wildcard = f"%{query}%"
    try:
        with _connect_db() as conn:
            rows = conn.execute(
                """
                SELECT title, content, created_at
                FROM knowledge
                WHERE title LIKE ? OR content LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (wildcard, wildcard, max(1, settings.app_db_max_rows)),
            ).fetchall()
    except sqlite3.Error as exc:
        return f"sql_error: {exc}"

    results: list[dict[str, str]] = []
    for row in rows:
        results.append(
            {
                "title": str(row["title"]),
                "content": str(row["content"]),
                "created_at": str(row["created_at"]),
            }
        )
    return json.dumps({"query": query, "source": "local_knowledge", "results": results}, ensure_ascii=False)


def _strip_html(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", text)
    return " ".join(cleaned.split())


def _parse_text_payload(tool_name: str, text: str) -> str:
    sentences = [item.strip() for item in re.split(r"[.!?]+", text) if item.strip()]
    tokens = [item for item in re.split(r"\W+", text.lower()) if item]
    payload = {
        "tool": tool_name,
        "char_count": len(text),
        "word_count": len(tokens),
        "sentence_count": len(sentences),
        "sentences": sentences[: min(8, len(sentences))],
    }
    return json.dumps(payload, ensure_ascii=False)


def _analyze_text_payload(tool_name: str, text: str) -> str:
    tokens = [item for item in re.split(r"\W+", text.lower()) if item]
    risk_terms = {"penalty", "breach", "liability", "termination", "fine", "risk", "default"}
    matched = sorted({token for token in tokens if token in risk_terms})
    risk_score = min(1.0, round(len(matched) / 5.0, 3))
    payload = {
        "tool": tool_name,
        "word_count": len(tokens),
        "risk_score": risk_score,
        "risk_terms": matched,
    }
    return json.dumps(payload, ensure_ascii=False)


def _transform_text_payload(tool_name: str, text: str) -> str:
    payload = {
        "tool": tool_name,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "char_count": len(text),
        "preview": text[:200],
    }
    return json.dumps(payload, ensure_ascii=False)
