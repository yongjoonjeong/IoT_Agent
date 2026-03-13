import discord
from ollama import AsyncClient
import json
import subprocess
from dotenv import load_dotenv
import os
# 1. 디스코드 봇 권한 설정 (메시지 읽기 권한 필수)
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")  # discord token 받아오기


@client.event
async def on_ready():
    print(f'디스코드 봇 [{client.user}] 라즈베리파이에서 구동 완료!')
    print('--------------------------------------------------')

@client.event
async def on_message(message):
    # 봇 자신이 보낸 메시지는 무시
    if message.author == client.user:
        return

    # '!제어 ' 라는 명령어로 시작하는 채팅만 인식하도록 설정
    if message.content.startswith('!제어 '):
        # '!제어 ' 이후의 실제 명령어 부분만 추출
        user_command = message.content[4:].strip()
        
        # 디스코드 채널에 '처리 중' 피드백 전송
        status_msg = await message.channel.send("⏳ 로컬 LLM 이 명령을 분석하고 있습니다...")

        try:
            # 2. Ollama 비동기 호출 (Qwen 3.5 4B 모델 사용
            response = await AsyncClient().chat(model='llama3.2:3b', messages=[ #model : llama3.2:3b 고정
                {
                    'role': 'system', 
                    'content': '너는 라즈베리파이 IoT 제어 AI야. 사용자의 요청을 분석해서 반드시 {"action": "execute", "target": "장치명", "value": "값"} 형태의 순수 JSON으로만 대답해. 부가 설명이나 마크다운은 절대 쓰지 마.'
                },
                {
                    'role': 'user', 
                    'content': user_command
                }
            ])

            # LLM이 뱉어낸 텍스트 (JSON 형태일 것으로 기대)
            llm_reply = response['message']['content'].strip()
            
            # 3. 디스코드에 LLM의 분석 결과 전송
            await status_msg.edit(content=f"**LLM 분석 결과:**\n```json\n{llm_reply}\n```")

            # 4. (선택) JSON 파싱 및 실제 파이썬 코드 실행 로직
            # 추후 실제 하드웨어 제어 코드를 연결할 자리
            try:
                command_data = json.loads(llm_reply)
                action = command_data.get('action')
                target = command_data.get('target')
                value = command_data.get('value')
                
                # 가상의 실행 결과 피드백 출력
                await message.channel.send(f"시스템: `{target}` 장치에 대해 `{action}` 명령(설정값: `{value}`)을 실행할 준비가 되었습니다.")
                
            except json.JSONDecodeError:
                await message.channel.send("경고: LLM이 올바른 JSON 형태를 반환하지 않아 명령을 실행할 수 없습니다.")

        except Exception as e:
            await status_msg.edit(content=f"시스템 오류 발생: {e}")

# 봇 실행
client.run(DISCORD_TOKEN)