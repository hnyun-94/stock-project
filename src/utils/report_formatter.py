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
        lines.append(f"> {summary_label}: {summary}")
        lines.append("")

    details = card.get("details", [])
    if details:
        lines.append("**핵심 근거**")
        for idx, detail in enumerate(details, 1):
            lines.append(f"{idx}. {detail}")
        lines.append("")

    why_it_matters = card.get("why_it_matters")
    if why_it_matters:
        lines.append("**왜 중요한가**")
        lines.append(f"- {why_it_matters}")
        lines.append("")

    watch_points = card.get("watch_points", [])
    if watch_points:
        lines.append("**지금 볼 것**")
        for item in watch_points:
            lines.append(f"- {item}")
        lines.append("")

    lines.append("**세 가지 시각**")
    if card.get("positive_view"):
        lines.append(f"- 긍정: {card['positive_view']}")
    if card.get("neutral_view"):
        lines.append(f"- 중립: {card['neutral_view']}")
    if card.get("negative_view"):
        lines.append(f"- 부정: {card['negative_view']}")
    lines.append("")

    if card.get("outlook"):
        lines.append(f"**{outlook_label}**")
        lines.append(f"- {card['outlook']}")
        lines.append("")
    if card.get("action"):
        lines.append("**실행 아이디어**")
        lines.append(f"- {card['action']}")
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
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
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
        lines.append(f"> {summary}")
        lines.append("")

    details = card.get("details", [])
    if details:
        lines.append(f"- 핵심 근거: {' / '.join(details[:2])}")
    if card.get("why_it_matters"):
        lines.append(f"- 왜 중요한가: {card['why_it_matters']}")
    if card.get("watch_points"):
        lines.append(f"- 지금 볼 것: {', '.join(card['watch_points'][:3])}")
    if card.get("outlook"):
        lines.append(f"- 다음 체크포인트: {card['outlook']}")
    if card.get("action"):
        lines.append(f"- 실행 아이디어: {card['action']}")
    lines.append("")

    _append_three_view_table(lines, card)


def _append_decision_section(lines: list[str], report_payload: dict) -> None:
    lines.extend(["## 📍 지금 결론", ""])

    headline_changes = report_payload.get("headline_changes", [])
    if headline_changes:
        lines.extend(["### 헤드라인 변화", ""])
        for item in headline_changes:
            lines.append(f"- {item}")
        lines.append("")

    quick_take = report_payload.get("quick_take")
    if quick_take:
        lines.append(f"> 한줄 결론: {quick_take.get('summary', '')}")
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

    lines.extend(["## 🧱 오늘 판단을 만드는 세 가지 축", ""])
    for lens in insight_lenses:
        lines.append(f"### {lens.get('title', '판단 축')}")
        lines.append("")
        if lens.get("summary"):
            lines.append(f"> {lens['summary']}")
            lines.append("")
        if lens.get("details"):
            lines.append(f"- 핵심 근거: {' / '.join(lens['details'][:2])}")
        if lens.get("why_it_matters"):
            lines.append(f"- 왜 중요한가: {lens['why_it_matters']}")
        if lens.get("watch_points"):
            lines.append(f"- 지금 볼 것: {', '.join(lens['watch_points'][:3])}")
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
            f"> 지금 구간 공통 이슈: {session_issue_section.get('summary', '')}"
        )
        lines.append("")


def build_structured_markdown_report(report_payload: dict) -> str:
    """구조화된 payload를 읽기 쉬운 Markdown 리포트로 렌더링합니다."""
    lines = [f"# {report_payload.get('title', '🌤️ 오늘의 주식 인사이트 리포트')}", ""]

    subtitle = report_payload.get("subtitle")
    if subtitle:
        lines.extend([f"> {subtitle}", ""])

    reliability_badge = report_payload.get("reliability_badge")
    if reliability_badge:
        lines.extend(
            [
                (
                    f"> 리포트 신뢰도: {reliability_badge.get('label', '보통')} "
                    f"({reliability_badge.get('score', 0)}/100) - {reliability_badge.get('reason', '')}"
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
            '<h1 style="color:#6a4f2b;border-bottom:2px solid #ddc7a4;padding-bottom:8px;margin:0 0 16px;font-size:24px;line-height:1.4;">',
        ),
        (
            r"<h2>",
            '<h2 style="color:#3b2f24;background:#f2eadb;padding:9px 12px;border-radius:10px;font-size:18px;margin:26px 0 12px;line-height:1.45;">',
        ),
        (
            r"<h3>",
            '<h3 style="color:#5b4630;font-size:16px;margin:18px 0 10px;line-height:1.45;">',
        ),
        (
            r"<p>",
            '<p style="margin:0 0 14px;font-size:14px;line-height:1.68;color:#2b241d;">',
        ),
        (
            r"<ul>",
            '<ul style="margin:0 0 16px;padding-left:20px;">',
        ),
        (
            r"<li>",
            '<li style="margin:0 0 8px;font-size:14px;line-height:1.65;color:#2b241d;">',
        ),
        (
            r"<blockquote>",
            '<blockquote style="margin:14px 0;padding:12px 14px;background:#fbf6ea;border-left:4px solid #d7a94b;color:#58452e;border-radius:8px;">',
        ),
        (
            r"<table>",
            '<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="width:100%;border-collapse:collapse;margin:12px 0 16px;table-layout:fixed;">',
        ),
        (
            r"<th>",
            '<th style="background:#efe4d2;color:#4f3f2f;font-weight:700;font-size:13px;padding:10px 8px;border:1px solid #e3d5bf;text-align:left;vertical-align:top;">',
        ),
        (
            r"<td>",
            '<td style="background:#fffdfa;font-size:13px;padding:10px 8px;border:1px solid #eadfcd;vertical-align:top;word-break:keep-all;line-height:1.55;">',
        ),
        (
            r"<hr ?/?>",
            '<hr style="border:0;border-top:1px solid #e7dccd;margin:28px 0 18px;">',
        ),
        (
            r"<a href=",
            '<a style="color:#8a5b22;text-decoration:none;" href=',
        ),
        (
            r"<em>",
            '<em style="color:#6f6253;">',
        ),
    ]
    for pattern, replacement in replacements:
        html_body = re.sub(pattern, replacement, html_body)

    styled_html = f"""
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        body {{ margin: 0; background: #f6f1e8; font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', Dotum, sans-serif; color: #2b241d; }}
    </style>
    </head>
    <body style="margin:0;background:#f6f1e8;">
        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="width:100%;background:#f6f1e8;">
            <tr>
                <td align="center" style="padding:24px 12px 40px;">
                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="max-width:860px;width:100%;background:#fffdfa;border:1px solid #e7dccd;border-radius:18px;">
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
