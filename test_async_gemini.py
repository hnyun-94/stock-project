"""
이 모듈은 Google Gemini GenAI API와의 비동기 상호작용을 테스트하는 기능을 제공합니다.
환경 변수에서 API 키를 로드하여 Gemini 모델에 요청을 보내고 응답을 출력하는 예제를 포함합니다.
주로 비동기 API 호출 설정을 확인하고 GenAI 클라이언트의 사용법을 시연하는 데 사용됩니다.
"""

import asyncio
import os
from dotenv import load_dotenv
from google import genai

async def test_genai_async():
    """
    비동기적으로 Google Gemini GenAI API와 통신하여 콘텐츠를 생성하는 기능을 테스트합니다.

    역할:
        환경 변수에서 Gemini API 키를 로드하고, `gemini-2.5-flash` 모델을 사용하여
        "what is 1+1? answer concisely"라는 질문에 대한 응답을 비동기적으로 요청합니다.
        응답을 콘솔에 출력하여 비동기 API 호출의 성공 여부를 확인합니다.

    입력:
        없음 (None): 이 함수는 직접적인 입력 매개변수를 받지 않습니다.
                      필요한 GEMINI_API_KEY는 `.env` 파일 또는 시스템 환경 변수에서 로드됩니다.

    반환값:
        없음 (None): 이 함수는 명시적인 값을 반환하지 않습니다.
                      대신, AI 모델로부터 받은 응답 텍스트를 표준 출력(콘솔)에 직접 출력합니다.
                      예시 출력: "Async AI response: 2"
    """
    load_dotenv()
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    res = await client.aio.models.generate_content(
        model='gemini-2.5-flash',
        contents='what is 1+1? answer concisely'
    )
    print("Async AI response:", res.text)

if __name__ == "__main__":
    asyncio.run(test_genai_async())
