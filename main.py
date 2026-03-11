import discord
import asyncio
import os
import json
import subprocess
import speech_recognition as sr
from faster_whisper import WhisperModel
from ollama import AsyncClient
from dotenv import load_dotenv
import edge_tts
import pygame

# --- 1. 환경 설정 및 초기화 ---
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

pygame.mixer.init()

print("[시스템] STT 모델 로딩 중...")
stt_model = WhisperModel("base", device="cpu", compute_type="int8")
print("[시스템] 초기화 완료!")

# 디스코드 음성 로그를 출력할 채널 ID를 저장할 변수
LOG_CHANNEL_ID = None 

# --- 2. 헬퍼 함수 정의 ---
def read_file(file_path):
    """파일을 읽어오는 함수"""
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

async def speak_text(text):
    """TTS로 스피커 출력"""
    audio_file = "reply.mp3"
    try:
        communicate = edge_tts.Communicate(text, "ko-KR-SunHiNeural")
        await communicate.save(audio_file)
        pygame.mixer.music.load(audio_file)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.1)
        pygame.mixer.music.unload()
        if os.path.exists(audio_file): os.remove(audio_file)
    except Exception as e:
        print(f"[오류] TTS 재생 실패: {e}")

# --- 3. 핵심 AI 처리 파이프라인 ---
async def process_command(user_text):
    """사용자의 입력을 분석하고 스크립트를 실행한 뒤 대답을 반환합니다."""
    
    agent_prompt = read_file("Agent.md")
    
    # 키워드 검사 및 스킬 문서 추가
    skill_context = ""
    if "에어컨" in user_text:
        skill_context = read_file("Aircon/Aircon.md")
    elif "환풍기" in user_text:
        skill_context = read_file("Fan/fan.md")
        
    system_prompt = f"{agent_prompt}\n\n[관련 스킬 및 상태]\n{skill_context}"
    
    try:
        response = await AsyncClient().chat(model='llama3.1', messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_text}
        ], keep_alive=-1)
        
        llm_reply = response['message']['content'].strip()
        
        # JSON 파싱 및 파이썬 파일 실행
        try:
            data = json.loads(llm_reply)
            action = data.get("action")
            target = data.get("target")
            val = data.get("value")
            speech = data.get("speech", "알겠습니다.")
            
            # 하드웨어 제어 분기
            if action == "execute" and target == "에어컨":
                print(f"[실행] 에어컨 제어: {val}")
                subprocess.run(["python3", "Aircon/aircon.py", str(val)])
                
            elif action == "execute" and target == "환풍기":
                # 추후 환풍기 제어 파이썬 스크립트 연결
                pass 
                
            return speech
            
        except json.JSONDecodeError:
            # JSON 포맷이 아닐 경우(일반 대화) 그대로 반환
            return llm_reply
            
    except Exception as e:
        return f"처리 중 오류가 발생했습니다. {e}"

# --- 4. 백그라운드 마이크 대기 루프 ---
def listen_microphone():
    """마이크 입력을 처리하는 동기 함수 (스레드에서 실행됨)"""
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()
    with microphone as source:
        recognizer.adjust_for_ambient_noise(source, duration=1.0)
        recognizer.pause_threshold = 1.2
        try:
            audio = recognizer.listen(source, timeout=2, phrase_time_limit=10)
            with open("temp.wav", "wb") as f:
                f.write(audio.get_wav_data())
            segments, _ = stt_model.transcribe("temp.wav", language="ko")
            text = "".join([s.text for s in segments]).strip()
            return text if text else None
        except sr.WaitTimeoutError:
            return None
        except Exception:
            return None

async def voice_background_task():
    """디스코드 봇과 겹치지 않게 비동기로 마이크를 계속 감시합니다."""
    await client.wait_until_ready()
    print("[시스템] 마이크 상시 대기 모드 시작...")
    
    while not client.is_closed():
        user_text = await asyncio.to_thread(listen_microphone)
        
        if user_text:
            print(f"[음성 인식] {user_text}")
            
            channel = client.get_channel(LOG_CHANNEL_ID)
            if channel:
                await channel.send(f"**[음성 명령 수신]** {user_text}")
            
            reply_text = await process_command(user_text)
            
            if channel:
                await channel.send(f"**[AI 실행/응답]** {reply_text}")
                
            await speak_text(reply_text)

# --- 5. 디스코드 봇 이벤트 ---
@client.event
async def on_ready():
    global LOG_CHANNEL_ID
    print(f"[시스템] 디스코드 봇 [{client.user}] 온라인!")
    
    # 봇이 참여 중인 서버의 첫 번째 텍스트 채널을 로그 채널로 자동 설정
    for guild in client.guilds:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                LOG_CHANNEL_ID = channel.id
                print(f"[시스템] 로그 채널 설정됨: {channel.name}")
                break
        if LOG_CHANNEL_ID: break

    client.loop.create_task(voice_background_task())

@client.event
async def on_message(message):
    # 봇 자신이 보낸 메시지는 무한 루프 방지를 위해 무시
    if message.author == client.user: 
        return

    # '!제어' 확인 로직을 없애고 모든 메시지를 명령어로 받아들입니다.
    user_command = message.content.strip()
    
    # 아무 내용도 없는 빈 메시지라면 무시
    if not user_command:
        return
        
    status_msg = await message.channel.send("LLM이 명령을 분석 중입니다...")
    
    reply_text = await process_command(user_command)
    
    await status_msg.edit(content=f"**[실행 결과]** {reply_text}")

# 봇 실행
client.run(DISCORD_TOKEN)