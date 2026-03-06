"""
Prompt cache manager.

Loads prompt templates from Notion DB into in-memory cache and provides
runtime-safe formatting for template variables.
"""

import os
import string
from typing import Any, Dict, Optional

from src.utils.logger import global_logger

# In-memory prompt cache.
# cache_key -> {"content": str, "model": str, "temperature": float, ...}
_PROMPT_CACHE: Dict[str, Dict[str, Any]] = {}

_PROMPT_PROPERTY_ALIASES = {
    "title": ["Title", "제목", "이름", "PromptTitle"],
    "content": ["Content", "본문", "프롬프트", "Prompt", "Template"],
    "is_active": ["IsActive", "활성", "활성화", "Enabled", "Status", "수신여부"],
    "model": ["Model", "모델"],
    "temperature": ["Temperature", "온도"],
    "prompt_key": ["PromptKey", "Key", "키", "Slug", "Type", "PromptType"],
    "version": ["Version", "버전"],
}
_ACTIVE_VALUE_SET = {
    "o",
    "y",
    "yes",
    "true",
    "enabled",
    "active",
    "활성",
    "사용",
    "on",
    "1",
}


def _normalize_key(value: str) -> str:
    """Normalizes cache keys for robust lookup."""
    if not value:
        return ""
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized


def _extract_plain_text(prop: Dict[str, Any]) -> str:
    """Extracts plain text from Notion property payload."""
    if not prop:
        return ""

    prop_type = prop.get("type")
    if prop_type == "title":
        return "".join(item.get("plain_text", "") for item in prop.get("title", []))
    if prop_type == "rich_text":
        return "".join(
            item.get("plain_text", "") for item in prop.get("rich_text", [])
        )
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


def _resolve_property_name(
    properties: Dict[str, Dict[str, Any]],
    aliases: list[str],
    fallback_type: Optional[str] = None,
) -> Optional[str]:
    """Resolves a property name by alias, then by fallback Notion property type."""
    for alias in aliases:
        if alias in properties:
            return alias

    normalized_aliases = {_normalize_key(alias) for alias in aliases}
    for prop_name in properties:
        if _normalize_key(prop_name) in normalized_aliases:
            return prop_name

    if fallback_type:
        for prop_name, prop in properties.items():
            if prop.get("type") == fallback_type:
                return prop_name

    return None


def _is_prompt_active(properties: Dict[str, Dict[str, Any]]) -> bool:
    """Evaluates whether prompt row is active. Missing flag means active by default."""
    active_name = _resolve_property_name(
        properties, _PROMPT_PROPERTY_ALIASES["is_active"]
    )
    if not active_name:
        return True

    prop = properties.get(active_name, {})
    prop_type = prop.get("type")
    if prop_type == "checkbox":
        return bool(prop.get("checkbox"))

    text_value = _extract_plain_text(prop).strip().lower()
    if not text_value:
        return True

    return text_value in _ACTIVE_VALUE_SET


def _safe_format_template(template: str, values: Dict[str, Any]) -> str:
    """Formats template while tolerating missing keys for operational resilience."""

    class DefaultFormatDict(dict):
        def __missing__(self, key: str) -> str:
            return ""

    required_fields = {
        field_name
        for _, field_name, _, _ in string.Formatter().parse(template)
        if field_name
    }
    missing_fields = sorted(
        field_name
        for field_name in required_fields
        if field_name not in values and "." not in field_name and "[" not in field_name
    )
    if missing_fields:
        global_logger.warning(
            f"프롬프트 변수 일부 누락({', '.join(missing_fields)}). 빈 문자열로 치환합니다."
        )

    return template.format_map(DefaultFormatDict(values))


def _register_prompt(prompt_data: Dict[str, Any]) -> None:
    """Registers prompt into cache using multiple lookup keys."""
    prompt_title = prompt_data.get("title", "")
    prompt_key = prompt_data.get("prompt_key", "")
    normalized_title = _normalize_key(prompt_title)
    normalized_key = _normalize_key(prompt_key)
    base_payload = {
        "content": prompt_data["content"],
        "model": prompt_data["model"],
        "temperature": prompt_data["temperature"],
        "title": prompt_title,
        "prompt_key": prompt_key,
        "version": prompt_data.get("version", ""),
    }

    cache_keys = {
        prompt_title,
        prompt_key,
        normalized_title,
        normalized_key,
    }
    for cache_key in [key for key in cache_keys if key]:
        _PROMPT_CACHE[cache_key] = base_payload


def fetch_prompts_from_notion() -> None:
    """
    Loads active prompts from Notion DB and caches them in memory.

    Supports both canonical schema (Title/Content/IsActive/Model/Temperature/PromptKey)
    and commonly used Korean aliases to keep runtime robust.
    """
    notion_token = os.getenv("NOTION_TOKEN")
    db_id = os.getenv("NOTION_PROMPT_DB_ID")

    if not notion_token or not db_id:
        global_logger.warning(
            "NOTION_PROMPT_DB_ID 또는 TOKEN이 설정되지 않았습니다. 기본 로컬 프롬프트를 사용합니다."
        )
        return

    default_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    loaded_prompts: Dict[str, Dict[str, Any]] = {}

    try:
        import httpx

        next_cursor = None
        while True:
            payload: Dict[str, Any] = {}
            if next_cursor:
                payload["start_cursor"] = next_cursor

            response = httpx.post(
                f"https://api.notion.com/v1/databases/{db_id}/query",
                headers={
                    "Authorization": f"Bearer {notion_token}",
                    "Notion-Version": "2022-06-28",
                },
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])

            for row in results:
                props = row.get("properties", {})
                if not _is_prompt_active(props):
                    continue

                title_name = _resolve_property_name(
                    props, _PROMPT_PROPERTY_ALIASES["title"], fallback_type="title"
                )
                content_name = _resolve_property_name(
                    props,
                    _PROMPT_PROPERTY_ALIASES["content"],
                    fallback_type="rich_text",
                )
                if not title_name or not content_name:
                    continue

                title = _extract_plain_text(props.get(title_name, {})).strip()
                content = _extract_plain_text(props.get(content_name, {})).strip()
                if not title or not content:
                    continue

                key_name = _resolve_property_name(
                    props, _PROMPT_PROPERTY_ALIASES["prompt_key"]
                )
                prompt_key = _extract_plain_text(props.get(key_name, {})).strip()
                if not prompt_key:
                    prompt_key = title

                model_name = _resolve_property_name(
                    props, _PROMPT_PROPERTY_ALIASES["model"]
                )
                model = _extract_plain_text(props.get(model_name, {})).strip()
                if not model:
                    model = default_model

                temp_name = _resolve_property_name(
                    props, _PROMPT_PROPERTY_ALIASES["temperature"]
                )
                raw_temperature = _extract_plain_text(props.get(temp_name, {})).strip()
                try:
                    temperature = (
                        float(raw_temperature) if raw_temperature else 0.5
                    )
                except (TypeError, ValueError):
                    temperature = 0.5

                version_name = _resolve_property_name(
                    props, _PROMPT_PROPERTY_ALIASES["version"]
                )
                version = _extract_plain_text(props.get(version_name, {})).strip()

                normalized_primary_key = _normalize_key(prompt_key or title)
                loaded_prompts[normalized_primary_key] = {
                    "title": title,
                    "prompt_key": prompt_key,
                    "content": content,
                    "model": model,
                    "temperature": temperature,
                    "version": version,
                }

            if not data.get("has_more"):
                break
            next_cursor = data.get("next_cursor")

        _PROMPT_CACHE.clear()
        for prompt in loaded_prompts.values():
            _register_prompt(prompt)

        loaded_count = len(loaded_prompts)
        if loaded_count == 0:
            global_logger.warning("Notion 프롬프트 DB에서 로드된 활성 프롬프트가 없습니다.")
        else:
            global_logger.info(
                f"✨ Notion에서 {loaded_count}개의 동적 프롬프트를 성공적으로 로드했습니다."
            )

    except Exception as e:
        global_logger.error(f"Notion 프롬프트 DB 연동 실패 (로컬 Fallback을 사용합니다): {e}")


def get_cached_prompt(title: str, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Returns a formatted prompt payload from cache.

    If no matching prompt exists, returns None so callers can use local fallback.
    """
    lookup_keys = [title, _normalize_key(title)]
    prompt_data = None
    for key in lookup_keys:
        prompt_data = _PROMPT_CACHE.get(key)
        if prompt_data:
            break

    if not prompt_data:
        return None

    payload = prompt_data.copy()
    template = payload.get("content", "")
    try:
        payload["content"] = _safe_format_template(template, kwargs)
        return payload
    except Exception as e:
        global_logger.warning(
            f"프롬프트 '{title}' 변수 포매팅 실패. 로컬 폴백으로 전환합니다: {e}"
        )
        return None
