import asyncio
from dotenv import load_dotenv
load_dotenv()
from src.services.ai_summarizer import safe_gemini_call

async def main():
    print("calling gemini")
    res = await safe_gemini_call("Hello")
    print("response:", res)

asyncio.run(main())
