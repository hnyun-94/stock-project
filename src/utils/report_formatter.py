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
