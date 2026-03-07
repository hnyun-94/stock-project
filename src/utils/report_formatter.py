"""
마크다운 리포트 포매팅 유틸리티.

AI 모델과 데이터 크롤러가 수집/생성한 마크다운 형태의 텍스트들을
HTML 구조로 매핑하여 이메일 본문이나 메신저 포맷으로 변환합니다.
"""

import markdown


def build_markdown_report(market_summary_md: str, theme_briefings_md: list) -> str:
    """리포트 재료들을 받아 하나의 통일된 마크다운 전문을 생성합니다.

    Args:
        market_summary_md (str): 시황 요약 마크다운
        theme_briefings_md (list): 테마별 브리핑 마크다운 리스트

    Returns:
        str: 통합된 마크다운 문자열
    """
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


def build_structured_markdown_report(report_payload: dict) -> str:
    """구조화된 payload를 읽기 쉬운 Markdown 리포트로 렌더링합니다."""
    lines = [report_payload.get("title", "🌤️ 오늘의 주식 인사이트 리포트"), ""]

    subtitle = report_payload.get("subtitle")
    if subtitle:
        lines.extend([f"> {subtitle}", ""])

    headline_changes = report_payload.get("headline_changes", [])
    if headline_changes:
        lines.extend(["## 🧭 헤드라인 변화", ""])
        for item in headline_changes:
            lines.append(f"- {item}")
        lines.append("")

    recent_focus = report_payload.get("recent_focus", [])
    if recent_focus:
        lines.extend(["## 📌 지금 바로 볼 것", ""])
        for item in recent_focus:
            lines.append(f"- {item}")
        lines.append("")

    time_windows = report_payload.get("time_windows", [])
    if time_windows:
        lines.extend(["## 🕒 타임 윈도우", ""])
        for window in time_windows:
            lines.append(f"### {window.get('label', '')} | {window.get('title', '')}")
            lines.append("")
            for item in window.get("bullets", []):
                lines.append(f"- {item}")
            lines.append("")

    theme_sections = report_payload.get("theme_sections", [])
    if theme_sections:
        lines.extend(["## 🎯 관심 테마 요약", ""])
        for section in theme_sections:
            lines.append(f"### {section.get('keyword', '테마')}")
            lines.append("")
            for point in section.get("points", []):
                lines.append(f"- {point}")
            lines.append("")

    holding_sections = report_payload.get("holding_sections", [])
    if holding_sections:
        lines.extend(["## 💼 보유 종목별 인사이트", ""])
        for section in holding_sections:
            lines.append(f"### {section.get('holding', '종목')}")
            lines.append("")
            lines.append(f"- 상태: {section.get('stance', '관찰')}")
            summary = section.get("summary")
            if summary:
                lines.append(f"- 근거: {summary}")
            action = section.get("action")
            if action:
                lines.append(f"- 액션: {action}")
            lines.append("")

    long_term_plan = report_payload.get("long_term_plan", [])
    if long_term_plan:
        lines.extend(["## 🗺️ 장기 플랜", ""])
        for item in long_term_plan:
            lines.append(f"- {item}")
        lines.append("")

    footer_note = report_payload.get("footer_note")
    if footer_note:
        lines.extend(["---", "", f"*{footer_note}*"])

    return "\n".join(lines).strip() + "\n"

def markdown_to_html(markdown_str: str) -> str:
    """제공된 마크다운을 이메일 발송용 CSS가 입혀진 HTML로 변환합니다."""
    html_body = markdown.markdown(markdown_str, extensions=['tables'])
    
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
