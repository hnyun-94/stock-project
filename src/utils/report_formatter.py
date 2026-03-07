"""
리포트 렌더링 유틸리티.

Codex reading guide:
1. 현재 운영 경로는 `build_structured_markdown_report()`입니다.
2. payload는 builder가 가치 판단 구조를 만든 결과물이고, formatter는 동일한 읽기 패턴으로 렌더링합니다.
3. HTML 변환은 마지막 단계에서만 수행되며, 내부 표준 표현은 Markdown입니다.
"""

import markdown


def build_markdown_report(market_summary_md: str, theme_briefings_md: list) -> str:
    """리포트 재료들을 받아 하나의 통일된 마크다운 전문을 생성합니다."""
    overall_md = "🌤️ 오늘의 주식 인사이트 리포트\n\n"
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
    summary_label: str = "짧은 요약",
    outlook_label: str = "앞으로 예상",
) -> None:
    lines.append(f"### {heading}")
    lines.append("")

    stance = card.get("stance")
    if stance:
        lines.append(f"- 기본 판단: {stance}")

    summary = card.get("summary")
    if summary:
        lines.append(f"- {summary_label}: {summary}")

    for idx, detail in enumerate(card.get("details", []), 1):
        lines.append(f"- 근거 {idx}: {detail}")

    if card.get("positive_view"):
        lines.append(f"- 긍정 시각: {card['positive_view']}")
    if card.get("neutral_view"):
        lines.append(f"- 중립 시각: {card['neutral_view']}")
    if card.get("negative_view"):
        lines.append(f"- 부정 시각: {card['negative_view']}")
    if card.get("outlook"):
        lines.append(f"- {outlook_label}: {card['outlook']}")
    if card.get("action"):
        lines.append(f"- 실행 아이디어: {card['action']}")

    headers = card.get("table_headers") or []
    rows = card.get("table_rows") or []
    if headers and rows:
        lines.append("")
        lines.append("| " + " | ".join(str(header) for header in headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in rows:
            lines.append("| " + " | ".join(str(cell) for cell in row) + " |")

    lines.append("")


def build_structured_markdown_report(report_payload: dict) -> str:
    """구조화된 payload를 읽기 쉬운 Markdown 리포트로 렌더링합니다."""
    lines = [report_payload.get("title", "🌤️ 오늘의 주식 인사이트 리포트"), ""]

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

    headline_changes = report_payload.get("headline_changes", [])
    if headline_changes:
        lines.extend(["## 🧭 헤드라인 변화", ""])
        for item in headline_changes:
            lines.append(f"- {item}")
        lines.append("")

    quick_take = report_payload.get("quick_take")
    if quick_take:
        lines.extend(["## 📌 오늘 한눈에 보기", ""])
        _append_card(lines, heading="지금의 핵심 판단", card=quick_take)

    session_issue_section = report_payload.get("session_issue_section")
    if session_issue_section:
        lines.extend(["## 🔔 공통 이슈 브리핑", ""])
        _append_card(
            lines,
            heading=session_issue_section.get("title", "공통 이슈"),
            card=session_issue_section,
            outlook_label="지금 구간에서 볼 것",
        )

    time_windows = report_payload.get("time_windows", [])
    if time_windows:
        lines.extend(["## 🕒 타임 윈도우별 판단", ""])
        for window in time_windows:
            _append_card(
                lines,
                heading=f"{window.get('label', '')} | {window.get('title', '')}",
                card=window,
            )

    data_quality_section = report_payload.get("data_quality_section")
    if data_quality_section:
        lines.extend(["## 🛰 데이터 신뢰도", ""])
        _append_card(
            lines,
            heading="최근 7일 외부 데이터 품질",
            card=data_quality_section,
        )

    domain_signal_sections = report_payload.get("domain_signal_sections", [])
    if domain_signal_sections:
        lines.extend(["## 🧪 외부 지표 해석", ""])
        for section in domain_signal_sections:
            _append_card(
                lines,
                heading=section.get("title", "외부 지표"),
                card=section,
            )

    theme_sections = report_payload.get("theme_sections", [])
    if theme_sections:
        lines.extend(["## 🎯 관심 테마", ""])
        for section in theme_sections:
            _append_card(lines, heading=section.get("keyword", "테마"), card=section)

    holding_sections = report_payload.get("holding_sections", [])
    if holding_sections:
        lines.extend(["## 💼 보유 종목별 인사이트", ""])
        for section in holding_sections:
            _append_card(
                lines,
                heading=section.get("holding", "종목"),
                card=section,
                outlook_label="앞으로 예상",
            )

    long_term_section = report_payload.get("long_term_section")
    if long_term_section:
        lines.extend(["## 🗺️ 장기 플랜", ""])
        _append_card(lines, heading="중장기 판단", card=long_term_section)

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

    styled_html = f"""
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', Dotum, sans-serif; line-height: 1.6; color: #333; }}
        h1 {{ color: #1a73e8; border-bottom: 2px solid #1a73e8; padding-bottom: 5px; font-size: 20px; }}
        h2 {{ color: #202124; background-color: #f1f3f4; padding: 5px 10px; border-radius: 4px; font-size: 18px; }}
        h3 {{ color: #2c3e50; font-size: 16px; }}
        p {{ margin-bottom: 15px; font-size: 15px; }}
        a {{ color: #1a73e8; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
    </head>
    <body>
        <div style="max-width: 800px; margin: 0 auto; padding: 20px;">
            {html_body}
        </div>
    </body>
    </html>
    """
    return styled_html
