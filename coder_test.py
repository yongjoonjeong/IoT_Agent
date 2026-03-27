import discord
from discord.ext import commands
import os
import re
import asyncio
from ollama import AsyncClient

# --- 설정 ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
MODEL_NAME = "qwen2.5-coder:3b"
SANDBOX_DIR = "@coder_sandbox"
MAX_RETRIES = 3  # 🌟 최대 재시도 횟수 설정

if not os.path.exists(SANDBOX_DIR):
    os.makedirs(SANDBOX_DIR)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
client = AsyncClient()

# --- 프롬프트 설정 ---
SYSTEM_PROMPT = (
    "당신은 파이썬 개발자입니다. 반드시 아래의 '구분자' 형식을 지켜 응답하세요.\n"
    "코드 블록(```python) 안에는 '오직 파이썬 코드'만 넣으세요. 라벨을 넣지 마세요.\n\n"
    "###FILENAME: [파일이름.py]\n"
    "###DESCRIPTION: [설명]\n"
    "###CODE:\n"
    "```python\n"
    "(여기에 순수 코드만 작성)\n"
    "```"
)

@bot.command(name="코딩")
async def coding(ctx, *, prompt: str):
    status_msg = await ctx.send(f"🧠 `{MODEL_NAME}` 모델이 코드를 생성 중입니다...")
    
    # AI에게 보낼 메시지 히스토리 초기화
    messages = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {'role': 'user', 'content': f"기능 요청: {prompt}"}
    ]

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if attempt > 1:
                await status_msg.edit(content=f"🔄 형식 인식 실패... 재시도 중입니다 ({attempt}/{MAX_RETRIES})")

            response = await client.chat(model=MODEL_NAME, messages=messages)
            content = response['message']['content'].strip()
            
            # 데이터 추출 시도
            filename_match = re.search(r"###FILENAME:\s*\[?(.*?)\]?\n", content)
            desc_match = re.search(r"###DESCRIPTION:\s*\[?(.*?)\]?\n", content)
            code_match = re.search(r"```python\n(.*?)```", content, re.DOTALL)

            # 🌟 성공적으로 모든 데이터를 찾았을 때
            if filename_match and code_match:
                filename = filename_match.group(1).strip()
                description = desc_match.group(1).strip() if desc_match else "설명 없음"
                raw_code = code_match.group(1).strip()

                # 코드 내부 불필요 라벨 제거
                clean_code = re.sub(r"(###FILENAME|###DESCRIPTION|###CODE|FILENAME|DESCRIPTION|CODE|###).*?\n", "", raw_code).strip()

                # 파일 저장
                file_path = os.path.join(SANDBOX_DIR, filename)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(clean_code)

                # 결과 임베드
                embed = discord.Embed(title="✅ 코드 생성 완료", color=0x00ff00)
                embed.add_field(name="📁 파일명", value=f"`{filename}`", inline=True)
                embed.add_field(name="📝 설명", value=description, inline=False)
                if attempt > 1:
                    embed.set_footer(text=f"{attempt}번의 시도 끝에 성공했습니다!")
                
                await status_msg.edit(content=None, embed=embed)
                
                if len(clean_code) < 1800:
                    await ctx.send(f"```python\n{clean_code}\n```")
                return # 성공했으므로 루프 탈출

            # 🌟 실패했을 때: 모델에게 피드백 추가 후 다시 요청
            messages.append({'role': 'assistant', 'content': content})
            messages.append({'role': 'user', 'content': "형식이 잘못되었습니다. 다시 한 번 ###FILENAME, ###DESCRIPTION, ###CODE 형식을 엄격히 지켜서 코드 블록과 함께 응답해주세요."})

        except Exception as e:
            await status_msg.edit(content=f"❌ 시스템 오류: {str(e)}")
            return

    # 모든 재시도가 실패했을 때
    await status_msg.edit(content=f"❌ {MAX_RETRIES}번 시도했지만 형식 인식에 실패했습니다. 요청을 구체적으로 다시 입력해보세요.")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)