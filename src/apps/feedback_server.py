"""
피드백/별점 수집 서버 (사용자 피드백 루프) 모듈

FastAPI를 띄워 고객이 이메일/텔레그램 하단 링크를 눌렀을 때 
해당 파라미터(이름, 점수, 코멘트)를 수신하고 피드백 DB(user_feedback.json)에 기록합니다.
"""

import os
import sys
import hmac
import hashlib

# 프로젝트 최상단 디렉토리 경로 추가 (src 모듈을 찾을 수 있도록 함)
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import uvicorn

from src.services.feedback_manager import record_feedback
from src.utils.logger import global_logger

app = FastAPI(title="Stock Report Feedback API")

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
if not WEBHOOK_SECRET:
    raise RuntimeError(
        "⛔ 환경변수 WEBHOOK_SECRET이 설정되지 않았습니다. "
        "보안을 위해 피드백 서버를 시작할 수 없습니다. "
        ".env 파일 또는 docker-compose.yml에서 WEBHOOK_SECRET을 설정해 주세요."
    )

def verify_signature(user: str, score: int, signature: str) -> bool:
    """웹훅 파라미터에 대한 HMAC-SHA256 서명 검증"""
    try:
        payload = f"{user}:{score}".encode('utf-8')
        secret = WEBHOOK_SECRET.encode('utf-8')
        expected_sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_sig, signature)
    except Exception:
        return False

@app.get("/api/feedback", response_class=HTMLResponse)
async def submit_feedback(user: str, score: int, signature: str = "", comment: str = ""):
    """
    고객이 알림톡/이메일 하단의 URL 파라미터 링크를 클릭하였을 때 진입하는 라우트입니다.
    """
    if not verify_signature(user, score, signature):
        global_logger.warning(f"잘못된 서명 접근: user={user}, score={score}, sig={signature}")
        return HTMLResponse(content="<h1>잘못된 접근이거나 서명이 유효하지 않습니다.</h1>", status_code=403)

    try:
        # 안전한 별점 필터 (1~5점 제한)
        rating = max(1, min(5, score))
        record_feedback(user_name=user, score=rating, comment=comment)
        
        # 간단한 사용자 안내 웹 페이지 렌더링
        html_content = f"""
        <html>
            <head>
                <title>피드백 완료</title>
                <style>
                    body {{ font-family: sans-serif; text-align: center; margin-top: 50px; }}
                    h1 {{ color: #2E86C1; }}
                    .container {{ border: 1px solid #ddd; padding: 20px; border-radius: 10px; display: inline-block; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>소중한 의견 감사합니다! 💌</h1>
                    <p><b>{user}</b> 님이 남겨주신 <b>{rating}점</b> 피드백이 AI를 더 가치 있게 만듭니다.</p>
                </div>
            </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=200)
    
    except Exception as e:
        global_logger.error(f"피드백 서버 처리 에러: {e}")
        return HTMLResponse(content="<h1>서버 오류가 발생했습니다.</h1>", status_code=500)

def run_feedback_server(port: int = 8000):
    global_logger.info("🟢 피드백 루프 수집용 웹 서버(FastAPI)가 시작됩니다.")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    run_feedback_server()
