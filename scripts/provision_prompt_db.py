"""
Provision and sync Notion prompt database for runtime prompt loading.

This script:
1. Ensures required prompt schema exists in NOTION_PROMPT_DB_ID.
2. Upserts local prompt templates into the prompt database.
3. Keeps the DB ready for dynamic prompt operations in production.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import dotenv_values


NOTION_BASE_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
RICH_TEXT_CHUNK_SIZE = 1900


@dataclass
class PromptDefinition:
    """Local prompt definition to sync into Notion."""

    key: str
    title: str
    file_path: str
    model: str
    temperature: float
    version: str = "v1"


def load_env_from_dotenv() -> None:
    """Loads .env values into process environment."""
    env = dotenv_values(".env")
    for key, value in env.items():
        if value is not None and key not in os.environ:
            os.environ[key] = value


def build_headers(token: str) -> Dict[str, str]:
    """Builds Notion API headers."""
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def split_to_rich_text(content: str) -> List[Dict[str, Any]]:
    """Splits long text into Notion rich_text blocks."""
    chunks = [
        content[index : index + RICH_TEXT_CHUNK_SIZE]
        for index in range(0, len(content), RICH_TEXT_CHUNK_SIZE)
    ]
    if not chunks:
        chunks = [""]
    return [
        {
            "type": "text",
            "text": {"content": chunk},
        }
        for chunk in chunks
    ]


def extract_plain_text(prop: Dict[str, Any]) -> str:
    """Extracts plain text from a Notion property payload."""
    if not prop:
        return ""
    prop_type = prop.get("type")
    if prop_type == "title":
        return "".join(item.get("plain_text", "") for item in prop.get("title", []))
    if prop_type == "rich_text":
        return "".join(item.get("plain_text", "") for item in prop.get("rich_text", []))
    if prop_type == "select":
        selected = prop.get("select")
        return (selected or {}).get("name", "")
    if prop_type == "status":
        selected = prop.get("status")
        return (selected or {}).get("name", "")
    if prop_type == "number":
        number = prop.get("number")
        return "" if number is None else str(number)
    if prop_type == "checkbox":
        return str(bool(prop.get("checkbox")))
    return ""


def get_title_property_name(properties: Dict[str, Dict[str, Any]]) -> str:
    """Returns title property name from DB schema."""
    for name, prop in properties.items():
        if prop.get("type") == "title":
            return name
    raise RuntimeError("Prompt DB에 title 타입 컬럼이 없습니다.")


def find_property_name(
    properties: Dict[str, Dict[str, Any]],
    candidates: List[str],
    expected_type: Optional[str] = None,
) -> Optional[str]:
    """Finds property name by candidates first, then by type fallback."""
    for candidate in candidates:
        if candidate in properties:
            return candidate
    if expected_type:
        for name, prop in properties.items():
            if prop.get("type") == expected_type:
                return name
    return None


def build_required_schema_patch(
    title_property_name: str,
    existing_property_names: List[str],
    cleanup_legacy: bool,
) -> Dict[str, Any]:
    """Builds schema patch payload for prompt DB."""
    patch: Dict[str, Any] = {
        "properties": {
            "Content": {"rich_text": {}},
            "IsActive": {"checkbox": {}},
            "Model": {
                "select": {
                    "options": [
                        {"name": "gemini-2.5-flash", "color": "blue"},
                        {"name": "gemini-2.5-flash-lite", "color": "green"},
                        {"name": "gemini-2.0-flash", "color": "orange"},
                        {"name": "gemini-2.0-flash-lite", "color": "gray"},
                    ]
                }
            },
            "Temperature": {"number": {"format": "number"}},
            "PromptKey": {"rich_text": {}},
            "Version": {"rich_text": {}},
        }
    }

    if title_property_name != "Title":
        patch["properties"][title_property_name] = {"name": "Title"}

    if cleanup_legacy:
        existing_set = set(existing_property_names)
        for legacy_column in [
            "이메일",
            "관심키워드",
            "수신여부",
            "보유종목",
            "긴급알림 임계치",
            "수신 채널",
            "텔레그램ID",
        ]:
            if legacy_column in existing_set and legacy_column != title_property_name:
                patch["properties"][legacy_column] = None

    return patch


def load_local_prompts(default_model: str) -> List[PromptDefinition]:
    """Loads local prompt files to sync."""
    return [
        PromptDefinition(
            key="market_summary",
            title="market_summary",
            file_path="src/prompts/market_summary.md",
            model=default_model,
            temperature=0.5,
        ),
        PromptDefinition(
            key="theme_briefing",
            title="theme_briefing",
            file_path="src/prompts/theme_briefing.md",
            model=default_model,
            temperature=0.5,
        ),
        PromptDefinition(
            key="portfolio_analysis",
            title="portfolio_analysis",
            file_path="src/prompts/portfolio_analysis.md",
            model=default_model,
            temperature=0.5,
        ),
    ]


def fetch_database(client: httpx.Client, db_id: str, headers: Dict[str, str]) -> Dict[str, Any]:
    """Retrieves Notion database metadata."""
    response = client.get(
        f"{NOTION_BASE_URL}/databases/{db_id}",
        headers=headers,
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


def query_all_pages(
    client: httpx.Client, db_id: str, headers: Dict[str, str]
) -> List[Dict[str, Any]]:
    """Queries all pages in the database with cursor pagination."""
    pages: List[Dict[str, Any]] = []
    next_cursor: Optional[str] = None
    while True:
        payload: Dict[str, Any] = {}
        if next_cursor:
            payload["start_cursor"] = next_cursor
        response = client.post(
            f"{NOTION_BASE_URL}/databases/{db_id}/query",
            headers=headers,
            json=payload,
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        pages.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        next_cursor = data.get("next_cursor")
    return pages


def resolve_schema_names(properties: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    """Resolves canonical property names after schema provisioning."""
    title_name = get_title_property_name(properties)
    content_name = find_property_name(properties, ["Content", "본문"], "rich_text")
    active_name = find_property_name(properties, ["IsActive", "활성"], "checkbox")
    model_name = find_property_name(properties, ["Model", "모델"], "select")
    temperature_name = find_property_name(
        properties, ["Temperature", "온도"], "number"
    )
    prompt_key_name = find_property_name(
        properties, ["PromptKey", "Key", "키"], "rich_text"
    )
    version_name = find_property_name(properties, ["Version", "버전"], "rich_text")

    if not all(
        [title_name, content_name, active_name, model_name, temperature_name, prompt_key_name]
    ):
        raise RuntimeError("Prompt DB 스키마 해석 실패: 필수 컬럼이 누락되었습니다.")

    resolved: Dict[str, str] = {
        "title": title_name,
        "content": content_name,  # type: ignore[assignment]
        "is_active": active_name,  # type: ignore[assignment]
        "model": model_name,  # type: ignore[assignment]
        "temperature": temperature_name,  # type: ignore[assignment]
        "prompt_key": prompt_key_name,  # type: ignore[assignment]
    }
    if version_name:
        resolved["version"] = version_name
    return resolved


def build_page_properties_payload(
    prompt_def: PromptDefinition,
    prompt_text: str,
    schema: Dict[str, str],
) -> Dict[str, Any]:
    """Builds Notion page properties payload for a single prompt."""
    payload: Dict[str, Any] = {
        schema["title"]: {
            "title": [
                {
                    "type": "text",
                    "text": {"content": prompt_def.title[:2000]},
                }
            ]
        },
        schema["prompt_key"]: {
            "rich_text": split_to_rich_text(prompt_def.key),
        },
        schema["content"]: {
            "rich_text": split_to_rich_text(prompt_text),
        },
        schema["is_active"]: {"checkbox": True},
        schema["model"]: {"select": {"name": prompt_def.model}},
        schema["temperature"]: {"number": prompt_def.temperature},
    }
    if "version" in schema:
        payload[schema["version"]] = {
            "rich_text": split_to_rich_text(prompt_def.version),
        }
    return payload


def build_existing_page_map(
    pages: List[Dict[str, Any]], schema: Dict[str, str]
) -> Dict[str, str]:
    """Builds key->page_id map for upsert."""
    page_map: Dict[str, str] = {}
    for page in pages:
        properties = page.get("properties", {})
        key = extract_plain_text(properties.get(schema["prompt_key"], {})).strip()
        title = extract_plain_text(properties.get(schema["title"], {})).strip()
        page_id = page.get("id")
        if not page_id:
            continue
        if key:
            page_map[key] = page_id
        if title and title not in page_map:
            page_map[title] = page_id
    return page_map


def read_prompt_file(file_path: str) -> str:
    """Reads local prompt file content."""
    content = Path(file_path).read_text(encoding="utf-8").strip()
    if not content:
        raise RuntimeError(f"프롬프트 파일이 비어있습니다: {file_path}")
    return content


def upsert_prompts(
    client: httpx.Client,
    db_id: str,
    headers: Dict[str, str],
    schema: Dict[str, str],
    prompt_defs: List[PromptDefinition],
    archive_empty_rows: bool,
    dry_run: bool,
) -> Dict[str, int]:
    """Upserts prompt rows into Notion prompt DB."""
    pages = query_all_pages(client, db_id, headers)
    archived = 0
    if archive_empty_rows:
        filtered_pages: List[Dict[str, Any]] = []
        for page in pages:
            props = page.get("properties", {})
            title = extract_plain_text(props.get(schema["title"], {})).strip()
            key = extract_plain_text(props.get(schema["prompt_key"], {})).strip()
            content = extract_plain_text(props.get(schema["content"], {})).strip()
            if title or key or content:
                filtered_pages.append(page)
                continue

            page_id = page.get("id")
            if not page_id:
                continue
            if dry_run:
                print(f"[DRY-RUN] ARCHIVE empty row page_id={page_id}")
            else:
                response = client.patch(
                    f"{NOTION_BASE_URL}/pages/{page_id}",
                    headers=headers,
                    json={"archived": True},
                    timeout=30.0,
                )
                response.raise_for_status()
                print(f"[ARCHIVED] empty row page_id={page_id}")
            archived += 1
        pages = filtered_pages

    existing_map = build_existing_page_map(pages, schema)

    created = 0
    updated = 0
    for prompt_def in prompt_defs:
        prompt_text = read_prompt_file(prompt_def.file_path)
        properties_payload = build_page_properties_payload(prompt_def, prompt_text, schema)
        page_id = existing_map.get(prompt_def.key) or existing_map.get(prompt_def.title)

        if dry_run:
            action = "UPDATE" if page_id else "CREATE"
            print(f"[DRY-RUN] {action}: {prompt_def.key}")
            continue

        if page_id:
            response = client.patch(
                f"{NOTION_BASE_URL}/pages/{page_id}",
                headers=headers,
                json={"properties": properties_payload},
                timeout=30.0,
            )
            response.raise_for_status()
            updated += 1
            print(f"[UPDATED] {prompt_def.key} -> {page_id}")
        else:
            response = client.post(
                f"{NOTION_BASE_URL}/pages",
                headers=headers,
                json={
                    "parent": {"database_id": db_id},
                    "properties": properties_payload,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            created += 1
            created_page_id = response.json().get("id", "<unknown>")
            print(f"[CREATED] {prompt_def.key} -> {created_page_id}")

    return {"created": created, "updated": updated, "archived": archived}


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Provision and sync Notion prompt database schema/data."
    )
    parser.add_argument(
        "--cleanup-legacy",
        action="store_true",
        help="Remove legacy user columns from prompt DB schema.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned changes without applying writes.",
    )
    parser.add_argument(
        "--archive-empty-rows",
        action="store_true",
        help="Archive DB rows that have empty Title/PromptKey/Content.",
    )
    args = parser.parse_args()

    load_env_from_dotenv()
    notion_token = os.getenv("NOTION_TOKEN", "").strip()
    prompt_db_id = os.getenv("NOTION_PROMPT_DB_ID", "").strip()
    default_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

    if not notion_token or not prompt_db_id:
        raise RuntimeError(
            "NOTION_TOKEN 또는 NOTION_PROMPT_DB_ID가 설정되지 않았습니다."
        )

    headers = build_headers(notion_token)
    prompt_defs = load_local_prompts(default_model)

    with httpx.Client() as client:
        db = fetch_database(client, prompt_db_id, headers)
        title_property_name = get_title_property_name(db.get("properties", {}))
        schema_patch = build_required_schema_patch(
            title_property_name=title_property_name,
            existing_property_names=list(db.get("properties", {}).keys()),
            cleanup_legacy=args.cleanup_legacy,
        )

        if args.dry_run:
            print("[DRY-RUN] Schema patch to apply:")
            print(schema_patch)
            for prompt_def in prompt_defs:
                print(
                    f"[DRY-RUN] UPSERT prompt key={prompt_def.key} file={prompt_def.file_path}"
                )
            print("[DRY-RUN] No write operation executed.")
            return
        else:
            response = client.patch(
                f"{NOTION_BASE_URL}/databases/{prompt_db_id}",
                headers=headers,
                json=schema_patch,
                timeout=30.0,
            )
            response.raise_for_status()
            print("[OK] Prompt DB schema patched.")

        refreshed_db = fetch_database(client, prompt_db_id, headers)
        schema = resolve_schema_names(refreshed_db.get("properties", {}))
        result = upsert_prompts(
            client=client,
            db_id=prompt_db_id,
            headers=headers,
            schema=schema,
            prompt_defs=prompt_defs,
            archive_empty_rows=args.archive_empty_rows,
            dry_run=args.dry_run,
        )

    print(
        "[DONE] Prompt sync completed. "
        f"created={result['created']}, updated={result['updated']}, archived={result['archived']}"
    )


if __name__ == "__main__":
    main()
