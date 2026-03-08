"""
리포트 렌더링 유틸리티.

Codex reading guide:
1. 현재 운영 경로는 `build_structured_markdown_report()`입니다.
2. payload는 builder가 가치 판단 구조를 만든 결과물이고, formatter는 동일한 읽기 패턴으로 렌더링합니다.
3. HTML 변환은 마지막 단계에서만 수행되며, 내부 표준 표현은 Markdown입니다.
"""

import re
from typing import Optional

import markdown

_PRIMARY_COLOR = "#AEBDCA"
_PRIMARY_DARK = "#5F6D7A"
_PRIMARY_TINT = "#F3F6F8"
_ACCENT_COLOR = "#E8DFCA"
_ACCENT_TINT = "#FBF8F1"
_CARD_BORDER = "#D9E1E7"
_TEXT_COLOR = "#33424F"
_MUTED_TEXT = "#6E7B86"
_BODY_BACKGROUND = "#F6F4EE"
_TABLE_HEADER_ALIASES = {
    "구분": "체크 대상",
    "내용": "현재 판단",
    "왜 보나": "읽는 이유",
    "항목": "체크 대상",
    "현재 값": "오늘 숫자",
    "읽는 법": "읽는 포인트",
    "구간": "기간",
    "한줄 판단": "핵심 요약",
    "지금 볼 것": "바로 볼 점",
    "긍정 시각": "좋게 보면",
    "중립 시각": "중립적으로 보면",
    "부정 시각": "조심해서 보면",
    "날짜": "기준일",
    "소스": "데이터 출처",
    "성공률": "정상 수집 비율",
    "평균 지연": "응답 속도",
    "판단": "읽는 포인트",
    "지표": "체크 지표",
    "최근값": "지금 수치",
    "1D 변화": "하루 변화",
    "7D 변화": "일주일 변화",
}
_EMPHASIS_TERMS = (
    "원/달러 환율",
    "외국인·기관 수급",
    "리포트 신뢰도",
    "인공지능(AI)",
    "AI",
    "HBM",
    "GPU",
    "KOSPI",
    "KOSDAQ",
    "중립",
    "관찰",
    "유지",
    "경계",
    "공격적",
    "방어적",
    "관망",
    "성장형",
    "실적형",
    "혼조형",
    "방어형",
    "경제 온도",
    "자금 흐름",
    "시장 화제",
)


def _emphasize_text(text: str) -> str:
    if not text:
        return text

    pattern = "|".join(re.escape(term) for term in sorted(_EMPHASIS_TERMS, key=len, reverse=True))
    return re.sub(rf"(?<!\*)({pattern})(?!\*)", r"**\1**", text)


def build_markdown_report(market_summary_md: str, theme_briefings_md: list) -> str:
    """리포트 재료들을 받아 하나의 통일된 마크다운 전문을 생성합니다."""
    overall_md = "# 🌤️ 오늘의 주식 인사이트 리포트\n\n"
    overall_md += "---\n\n"
    overall_md += market_summary_md + "\n\n"
    overall_md += "---\n\n"

    if theme_briefings_md:
        overall_md += "## 🎯 사용자 맞춤관심 테마 분석\n\n"
        for brief in theme_briefings_md:
            overall_md += brief + "\n\n"

    overall_md += "---\n\n*본 리포트는 자동화된 AI 및 스크래핑 시스템에 의해 수집/편집되었습니다.*"
    return overall_md


def _append_card(
    lines: list[str],
    *,
    heading: str,
    card: dict,
    summary_label: str = "한줄 판단",
    outlook_label: str = "다음 체크포인트",
) -> None:
    lines.append(f"### {heading}")
    lines.append("")

    stance = card.get("stance")
    if stance:
        lines.append(f"`기본 판단: {stance}`")
        lines.append("")

    summary = card.get("summary")
    if summary:
        lines.append(f"> {summary_label}: {_emphasize_text(summary)}")
        lines.append("")

    details = card.get("details", [])
    if details:
        lines.append("**핵심 근거**")
        for idx, detail in enumerate(details, 1):
            lines.append(f"{idx}. {_emphasize_text(detail)}")
        lines.append("")

    why_it_matters = card.get("why_it_matters")
    if why_it_matters:
        lines.append("**왜 중요한가**")
        lines.append(f"- {_emphasize_text(why_it_matters)}")
        lines.append("")

    watch_points = card.get("watch_points", [])
    if watch_points:
        lines.append("**지금 볼 것**")
        for item in watch_points:
            lines.append(f"- {_emphasize_text(item)}")
        lines.append("")

    related_links = card.get("related_links", [])
    if related_links:
        lines.append("**관련 기사**")
        for link in related_links:
            lines.append(f"- [{link.get('label', '관련 기사')}]({link.get('url', '#')})")
        lines.append("")

    lines.append("**세 가지 시각**")
    if card.get("positive_view"):
        lines.append(f"- 긍정: {_emphasize_text(card['positive_view'])}")
    if card.get("neutral_view"):
        lines.append(f"- 중립: {_emphasize_text(card['neutral_view'])}")
    if card.get("negative_view"):
        lines.append(f"- 부정: {_emphasize_text(card['negative_view'])}")
    lines.append("")

    if card.get("outlook"):
        lines.append(f"**{outlook_label}**")
        lines.append(f"- {_emphasize_text(card['outlook'])}")
        lines.append("")
    if card.get("action"):
        lines.append("**실행 아이디어**")
        lines.append(f"- {_emphasize_text(card['action'])}")
        lines.append("")

    headers = card.get("table_headers") or []
    rows = card.get("table_rows") or []
    if headers and rows:
        lines.append("**참고 데이터**")
        lines.append("| " + " | ".join(str(header) for header in headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in rows:
            lines.append("| " + " | ".join(str(cell) for cell in row) + " |")

    lines.append("")


def _append_markdown_table(
    lines: list[str],
    *,
    headers: list[str],
    rows: list[list[str]],
) -> None:
    if not headers or not rows:
        return
    aliased_headers = [_TABLE_HEADER_ALIASES.get(header, header) for header in headers]
    lines.append("| " + " | ".join(aliased_headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(aliased_headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(_emphasize_text(str(cell)) for cell in row) + " |")
    lines.append("")


def _append_three_view_table(lines: list[str], card: dict) -> None:
    rows = [[
        card.get("positive_view", "-") or "-",
        card.get("neutral_view", "-") or "-",
        card.get("negative_view", "-") or "-",
    ]]
    _append_markdown_table(
        lines,
        headers=["긍정 시각", "중립 시각", "부정 시각"],
        rows=rows,
    )


def _append_compact_brief(
    lines: list[str],
    *,
    heading: str,
    card: dict,
    stance_label: str = "기본 판단",
) -> None:
    lines.append(f"### {heading}")
    lines.append("")

    stance = card.get("stance")
    if stance:
        lines.append(f"**{stance_label}:** {stance}")
        lines.append("")

    summary = card.get("summary")
    if summary:
        lines.append(f"> {_emphasize_text(summary)}")
        lines.append("")

    details = card.get("details", [])
    if details:
        for idx, detail in enumerate(details[:4], 1):
            lines.append(f"- 핵심 근거 {idx}: {_emphasize_text(detail)}")
    if card.get("why_it_matters"):
        lines.append(f"- 왜 중요한가: {_emphasize_text(card['why_it_matters'])}")
    if card.get("watch_points"):
        for idx, item in enumerate(card["watch_points"][:4], 1):
            lines.append(f"- 지금 볼 것 {idx}: {_emphasize_text(item)}")
    if card.get("related_links"):
        for idx, link in enumerate(card["related_links"][:4], 1):
            lines.append(
                f"- 관련 기사 {idx}: "
                f"[{link.get('label', '관련 기사')}]({link.get('url', '#')})"
            )
    if card.get("outlook"):
        lines.append(f"- 다음 체크포인트: {_emphasize_text(card['outlook'])}")
    if card.get("action"):
        lines.append(f"- 실행 아이디어: {_emphasize_text(card['action'])}")
    lines.append("")

    _append_three_view_table(lines, card)


def _append_decision_section(lines: list[str], report_payload: dict) -> None:
    lines.extend(["## 📍 지금 결론", ""])

    headline_changes = report_payload.get("headline_changes", [])
    if headline_changes:
        lines.extend(["### 헤드라인 변화", ""])
        for item in headline_changes:
            lines.append(f"- {_emphasize_text(item)}")
        lines.append("")

    quick_take = report_payload.get("quick_take")
    if quick_take:
        lines.append(f"> 한줄 결론: {_emphasize_text(quick_take.get('summary', ''))}")
        lines.append("")
        if quick_take.get("related_links"):
            lines.append("**관련 기사**")
            for link in quick_take["related_links"][:2]:
                lines.append(f"- [{link.get('label', '관련 기사')}]({link.get('url', '#')})")
            lines.append("")

    decision_tiles = report_payload.get("decision_tiles", [])
    if decision_tiles:
        lines.extend(["### 빠르게 보는 판단표", ""])
        _append_markdown_table(
            lines,
            headers=["구분", "내용", "왜 보나"],
            rows=[
                [
                    tile.get("label", ""),
                    tile.get("value", ""),
                    tile.get("detail", ""),
                ]
                for tile in decision_tiles
            ],
        )

    scoreboard = report_payload.get("market_scoreboard")
    if scoreboard:
        lines.extend(["### 오늘 바로 볼 숫자", ""])
        _append_markdown_table(
            lines,
            headers=scoreboard.get("headers", []),
            rows=scoreboard.get("rows", []),
        )


def _append_lens_section(lines: list[str], insight_lenses: list[dict]) -> None:
    if not insight_lenses:
        return

    lines.extend(["## 🌍 경제 상황과 트렌드", ""])
    for lens in insight_lenses:
        lines.append(f"### {lens.get('title', '판단 축')}")
        lines.append("")
        if lens.get("summary"):
            lines.append(f"> {_emphasize_text(lens['summary'])}")
            lines.append("")
        if lens.get("details"):
            for idx, detail in enumerate(lens["details"][:4], 1):
                lines.append(f"- 핵심 근거 {idx}: {_emphasize_text(detail)}")
        if lens.get("why_it_matters"):
            lines.append(f"- 왜 중요한가: {_emphasize_text(lens['why_it_matters'])}")
        if lens.get("watch_points"):
            for idx, item in enumerate(lens["watch_points"][:4], 1):
                lines.append(f"- 지금 볼 것 {idx}: {_emphasize_text(item)}")
        if lens.get("related_links"):
            for idx, link in enumerate(lens["related_links"][:3], 1):
                lines.append(
                    f"- 관련 기사 {idx}: "
                    f"[{link.get('label', '관련 기사')}]({link.get('url', '#')})"
                )
        lines.append("")
        _append_three_view_table(lines, lens)


def _append_time_window_digest(lines: list[str], time_windows: list[dict], session_issue_section: Optional[dict]) -> None:
    if not time_windows:
        return

    lines.extend(["## 🕒 시간대 압축판", ""])
    _append_markdown_table(
        lines,
        headers=["구간", "한줄 판단", "지금 볼 것"],
        rows=[
            [
                f"{window.get('label', '')} {window.get('title', '')}".strip(),
                window.get("summary", ""),
                ", ".join(window.get("watch_points", [])[:2]) or "후속 수급 확인",
            ]
            for window in time_windows
        ],
    )

    if session_issue_section:
        lines.append(
            f"> 지금 구간 공통 이슈: {_emphasize_text(session_issue_section.get('summary', ''))}"
        )
        lines.append("")
        if session_issue_section.get("related_links"):
            lines.append("**관련 기사**")
            for link in session_issue_section["related_links"][:2]:
                lines.append(f"- [{link.get('label', '관련 기사')}]({link.get('url', '#')})")
            lines.append("")


def build_structured_markdown_report(report_payload: dict) -> str:
    """구조화된 payload를 읽기 쉬운 Markdown 리포트로 렌더링합니다."""
    lines = [f"# {report_payload.get('title', '🌤️ 오늘의 주식 인사이트 리포트')}", ""]

    subtitle = report_payload.get("subtitle")
    if subtitle:
        lines.extend([f"> {_emphasize_text(subtitle)}", ""])

    reliability_badge = report_payload.get("reliability_badge")
    if reliability_badge:
        gauge = str(reliability_badge.get("gauge", "")).strip()
        gauge_text = f" · {gauge}" if gauge else ""
        lines.extend(
            [
                _emphasize_text(
                    f"> 리포트 신뢰도: {reliability_badge.get('label', '보통')} "
                    f"({reliability_badge.get('score', 0)}/100){gauge_text} - {reliability_badge.get('reason', '')}"
                ),
                "",
            ]
        )

    _append_decision_section(lines, report_payload)
    _append_lens_section(lines, report_payload.get("insight_lenses", []))
    _append_time_window_digest(
        lines,
        report_payload.get("time_windows", []),
        report_payload.get("session_issue_section"),
    )

    theme_sections = report_payload.get("theme_sections", [])
    if theme_sections:
        lines.extend(["## 🎯 관심 테마", ""])
        for section in theme_sections:
            _append_compact_brief(
                lines,
                heading=section.get("keyword", "테마"),
                card=section,
                stance_label="현재 톤",
            )

    holding_sections = report_payload.get("holding_sections", [])
    if holding_sections:
        lines.extend(["## 💼 보유 종목별 인사이트", ""])
        for section in holding_sections:
            _append_compact_brief(
                lines,
                heading=section.get("holding", "종목"),
                card=section,
            )

    domain_signal_sections = report_payload.get("domain_signal_sections", [])
    if domain_signal_sections:
        lines.extend(["## 🧪 보조 지표 해석", ""])
        for section in domain_signal_sections:
            _append_compact_brief(
                lines,
                heading=section.get("title", "외부 지표"),
                card=section,
                stance_label="해석 포인트",
            )
            headers = section.get("table_headers") or []
            rows = section.get("table_rows") or []
            if headers and rows:
                _append_markdown_table(lines, headers=headers, rows=rows)

    long_term_section = report_payload.get("long_term_section")
    if long_term_section:
        lines.extend(["## 🗺️ 장기 플랜", ""])
        _append_compact_brief(lines, heading="중장기 판단", card=long_term_section)

    learning_card = report_payload.get("learning_card")
    if learning_card:
        lines.extend(["## 📘 오늘의 경제 상식", ""])
        lines.append(f"### {learning_card.get('term', '경제 상식')}")
        lines.append("")
        lines.append(f"> {_emphasize_text(learning_card.get('summary', ''))}")
        lines.append("")
        lines.append(f"- 오늘 왜 중요했나: {_emphasize_text(learning_card.get('why_today', ''))}")
        lines.append(f"- 이렇게 읽으면 됩니다: {_emphasize_text(learning_card.get('how_to_read', ''))}")
        lines.append("")

    data_quality_section = report_payload.get("data_quality_section")
    if data_quality_section:
        lines.extend(["## 🛰 데이터 신뢰도", ""])
        _append_compact_brief(
            lines,
            heading="최근 7일 외부 데이터 품질",
            card=data_quality_section,
            stance_label="운영 해석",
        )
        headers = data_quality_section.get("table_headers") or []
        rows = data_quality_section.get("table_rows") or []
        if headers and rows:
            _append_markdown_table(lines, headers=headers, rows=rows)

    glossary = report_payload.get("glossary", [])
    if glossary:
        lines.extend(["## 🧩 용어 풀이", ""])
        for item in glossary:
            lines.append(f"- {item.get('term', '용어')}: {item.get('definition', '')}")
        lines.append("")

    footer_note = report_payload.get("footer_note")
    if footer_note:
        lines.extend(["---", "", f"*{footer_note}*"])

    return "\n".join(lines).strip() + "\n"


def markdown_to_html(markdown_str: str) -> str:
    """제공된 마크다운을 이메일 발송용 CSS가 입혀진 HTML로 변환합니다."""
    html_body = markdown.markdown(markdown_str, extensions=["tables"])
    replacements = [
        (
            r"<h1>",
            (
                f'<h1 style="color:{_PRIMARY_DARK};border-bottom:3px solid {_ACCENT_COLOR};'
                f'padding-bottom:10px;margin:0 0 18px;font-size:24px;line-height:1.4;">'
            ),
        ),
        (
            r"<h2>",
            (
                f'<h2 style="color:{_PRIMARY_DARK};background:{_PRIMARY_TINT};padding:10px 12px;'
                f'border-left:5px solid {_ACCENT_COLOR};border-radius:12px;font-size:18px;'
                f'margin:26px 0 12px;line-height:1.45;">'
            ),
        ),
        (
            r"<h3>",
            f'<h3 style="color:{_PRIMARY_DARK};font-size:16px;margin:18px 0 10px;line-height:1.45;">',
        ),
        (
            r"<p>",
            f'<p style="margin:0 0 14px;font-size:14px;line-height:1.68;color:{_TEXT_COLOR};">',
        ),
        (
            r"<ul>",
            '<ul style="margin:0 0 16px;padding-left:20px;">',
        ),
        (
            r"<li>",
            f'<li style="margin:0 0 8px;font-size:14px;line-height:1.65;color:{_TEXT_COLOR};">',
        ),
        (
            r"<blockquote>",
            (
                f'<blockquote style="margin:14px 0;padding:12px 14px;background:{_ACCENT_TINT};'
                f'border-left:4px solid {_ACCENT_COLOR};color:{_PRIMARY_DARK};border-radius:10px;">'
            ),
        ),
        (
            r"<table>",
            (
                '<table role="presentation" cellspacing="0" cellpadding="0" border="0" '
                'style="width:100%;border-collapse:collapse;margin:12px 0 16px;table-layout:fixed;">'
            ),
        ),
        (
            r"<th>",
            (
                f'<th style="background:{_PRIMARY_COLOR};color:{_PRIMARY_DARK};font-weight:700;font-size:13px;'
                f'padding:10px 8px;border:1px solid {_CARD_BORDER};text-align:left;vertical-align:top;">'
            ),
        ),
        (
            r"<td>",
            (
                f'<td style="background:#ffffff;font-size:13px;padding:10px 8px;border:1px solid {_CARD_BORDER};'
                f'vertical-align:top;word-break:keep-all;line-height:1.55;color:{_TEXT_COLOR};">'
            ),
        ),
        (
            r"<hr ?/?>",
            f'<hr style="border:0;border-top:1px solid {_CARD_BORDER};margin:28px 0 18px;">',
        ),
        (
            r"<a href=",
            f'<a style="color:{_PRIMARY_DARK};text-decoration:underline;text-decoration-color:{_ACCENT_COLOR};font-weight:600;" href=',
        ),
        (
            r"<em>",
            f'<em style="color:{_MUTED_TEXT};">',
        ),
        (
            r"<strong>",
            f'<strong style="color:{_PRIMARY_DARK};">',
        ),
    ]
    for pattern, replacement in replacements:
        html_body = re.sub(pattern, replacement, html_body)

    styled_html = f"""
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        body {{ margin: 0; background: {_BODY_BACKGROUND}; font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', Dotum, sans-serif; color: {_TEXT_COLOR}; }}
    </style>
    </head>
    <body style="margin:0;background:{_BODY_BACKGROUND};">
        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="width:100%;background:{_BODY_BACKGROUND};">
            <tr>
                <td align="center" style="padding:24px 12px 40px;">
                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="max-width:860px;width:100%;background:#ffffff;border:1px solid {_CARD_BORDER};border-radius:18px;">
                        <tr>
                            <td style="padding:28px 24px;">
                                {html_body}
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    return styled_html
