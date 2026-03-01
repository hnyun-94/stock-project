import os
from google import genai

client = genai.Client()
print("Client created")

import asyncio
async def main():
    print("calling gemini")
    res = await client.aio.models.generate_content(
        model='gemini-2.5-flash',
        contents="Hello"
    )
    print("Response:", res.text)

asyncio.run(main())
