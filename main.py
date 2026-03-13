import discord
import asyncio
import os
import json
import subprocess
import speech_recognition as sr
from faster_whisper import WhisperModel
from ollama import AsyncClient
import edge_tts
import pygame
import re
import datetime


# os.environ["SDL_AUDIODRIVER"] = "dummy" # audio 부분 일단 주석 처리. 추후 오디오 연결하기 

# --- 1. 환경 설정 및 초기화 ---

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# pygame.mixer.init()

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

def get_stt_hints(file_path="whisper_hint.txt"):
    """STT 힌트 문자열 생성"""
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().replace('\n', ', ') 
    return ""

def get_alias(agent_text):
    """Agent.md에서 <별명> 파싱"""
    match = re.search(r"<별명>\s*:\s*(.+)", agent_text)
    if match:
        return match.group(1).strip()
    return "자비스" # 기본값

def handle_direct_command(user_text):
    """LLM을 거치지 않고 직접 제어하는 로직. 처리되었으면 (True, 응답음성), 아니면 (False, None) 반환"""
    targets = ["에어컨", "조명", "환풍기"]
    found_target = None
    for t in targets:
        if t in user_text:
            found_target = t
            break
            
    if not found_target:
        return False, None
        
    # 액션 및 값 파싱 (간단한 키워드 매칭)
    action = None
    if "켜" in user_text:
        action = "켜줘"
    elif "꺼" in user_text:
        action = "꺼줘"
        
    val_match = re.search(r"(\d+)(도|단)", user_text)
    value = val_match.group(1) if val_match else None
    
    # 파라미터 부족 시 되묻기
    if not action:
        return True, f"{found_target}을 켤까요, 아니면 끌까요?"
    if found_target == "에어컨" and action == "켜줘" and not value:
        return True, "에어컨 온도를 몇 도로 맞출까요?"
    elif found_target in ["조명", "환풍기"] and action == "켜줘" and not value:
        return True, f"{found_target}을 몇 단으로 켤까요?"
        
    # 실행 로직
    # 실제 하드웨어 제어 스크립트 연동 자리에 위치
    print(f"[직접 제어 실행] 대상: {found_target}, 명령: {action}, 값: {value}")
    if found_target == "에어컨":
        subprocess.run(["python3", "Aircon/aircon.py", str(value) if value else action])
        
    return True, f"{found_target}을 {value + ('도' if found_target == '에어컨' else '단') + '로 ' if value else ''}{action} 처리했습니다."

CONV_DIR = "@conversation"

def save_conversation(user_text, llm_reply):
    """대화 내용을 계층적 폴더에 저장"""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    daily_dir = os.path.join(CONV_DIR, today)
    os.makedirs(daily_dir, exist_ok=True)
    
    session_id = datetime.datetime.now().strftime("%H%M%S")
    file_path = os.path.join(daily_dir, f"{session_id}.json")
    
    data = {"timestamp": datetime.datetime.now().isoformat(), "user_input": user_text, "ai_response": llm_reply}
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[오류] 대화 기록 저장 실패: {e}")

async def get_relevant_context(user_text):
    """기존 대화 기록 중 연관성 있는 내용을 추출하여 반환 (llama 3b 활용)"""
    if not os.path.exists(CONV_DIR):
        return ""
        
    all_convs = []
    for root, _, files in os.walk(CONV_DIR):
        for file in files:
            if file.endswith(".json"):
                try:
                    with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                        all_convs.append(json.load(f))
                except:
                    pass
                    
    if not all_convs:
        return ""
        
    try:
        # 1. llama 1b로 키워드 추출
        extract_prompt = "다음 문장에서 중요한 단어나 개체명(예: 사람 이름, 장소, 사물 등)만 쉼표로 구분해서 말해. 부가 설명 절대 금지."
        resp = await AsyncClient().chat(model='llama3.2:3b', messages=[
            {'role': 'system', 'content': extract_prompt},
            {'role': 'user', 'content': user_text}
        ])
        keywords = [k.strip() for k in resp['message']['content'].split(',') if k.strip()]
        
        # 2. 키워드 기반 필터링
        relevant_convs = []
        for conv in all_convs:
            conv_text = conv.get("user_input", "") + " " + conv.get("ai_response", "")
            if any(k in conv_text for k in keywords):
                relevant_convs.append(conv)
                
        # 최근 3개만 반환
        relevant_convs = sorted(relevant_convs, key=lambda x: x.get("timestamp", ""), reverse=True)[:3]
        if not relevant_convs:
            return ""
            
        context_str = "\n[과거 연관 대화 기록]\n"
        for c in relevant_convs:
            context_str += f"User: {c.get('user_input')}\nAI: {c.get('ai_response')}\n---\n"
        return context_str
    except Exception as e:
        print(f"[오류] 컨텍스트 추출 실패: {e}")
        return ""

async def speak_text(text):
    """TTS로 스피커 출력"""
    audio_file = "reply.mp3"
    try:
        communicate = edge_tts.Communicate(text, "ko-KR-SunHiNeural")
        await communicate.save(audio_file)
        # pygame.mixer.music.load(audio_file)
        # pygame.mixer.music.play()
        # while pygame.mixer.music.get_busy():
        #     await asyncio.sleep(0.1)
        # pygame.mixer.music.unload()
        # if os.path.exists(audio_file): os.remove(audio_file)
    except Exception as e:
        print(f"[오류] TTS 재생 실패: {e}")

# --- 3. 핵심 AI 처리 파이프라인 ---
async def process_command(user_text, require_alias=False):
    """사용자의 입력을 분석하고 스크립트를 실행한 뒤 대답을 반환합니다."""
    
    agent_prompt = read_file("Agent.md")
    alias = get_alias(agent_prompt)
    
    if require_alias and alias not in user_text:
        return None # 별명이 불리지 않으면 무시
        
    # 직접 제어 가능한지 확인 (LLM 생략)
    is_direct, direct_reply = handle_direct_command(user_text)
    if is_direct:
        return direct_reply
    
    # 키워드 검사 및 스킬 문서 추가
    skill_context = ""
    if "에어컨" in user_text:
        skill_context = read_file("Aircon/Aircon.md")
    elif "환풍기" in user_text:
        skill_context = read_file("Fan/fan.md")
        
    past_logic = await get_relevant_context(user_text)
    system_prompt = f"{agent_prompt}\n\n[관련 스킬 및 상태]\n{skill_context}\n{past_logic}"
    
    try:
        response = await AsyncClient().chat(model='llama3.2:3b', messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_text}
        ], keep_alive=-1)
        
        llm_reply = response['message']['content'].strip()
        
        # 일반 대화일 경우 저장
        if "action" not in llm_reply or "{" not in llm_reply:
             save_conversation(user_text, llm_reply)
        
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
                
            save_conversation(user_text, speech)
            return speech
            
        except json.JSONDecodeError:
            # JSON 포맷이 아닐 경우(일반 대화) 그대로 반환
            return llm_reply
            
    except Exception as e:
        return f"처리 중 오류가 발생했습니다. {e}"

# --- 4. 백그라운드 마이크 대기 루프 ---
def listen_microphone():
    """마이크 입력을 처리하는 동기 함수 (스레드에서 실행됨)"""
    hints = get_stt_hints()
    
    # # 1. 자동 마이크 인식 로직 (USB 마이크 찾기)
    # mic_index = None
    # mic_list = sr.Microphone.list_microphone_names()
    # for index, name in enumerate(mic_list):
    #     if "USB" in name or "hw:2" in name:
    #         mic_index = index
    #         break
            
    # if mic_index is None and len(mic_list) > 0:
    #     mic_index = 0 # 못찾으면 첫 번째 장치 사용
        
    recognizer = sr.Recognizer()
    
    # 2. USB 마이크의 경우 sample_rate를 48000 또는 44100으로 명시해야 ALSA 오류/튕김이 잡힙니다.
    # 인덱스 0번이 안 되었던 이유는 샘플레이트 문제일 확률이 높습니다.
    microphone = sr.Microphone(device_index= 0, sample_rate=48000)
    
    with microphone as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        recognizer.energy_threshold = 300
        recognizer.pause_threshold = 1.2
        try:
            audio = recognizer.listen(source, timeout=2, phrase_time_limit=10)
            with open("temp.wav", "wb") as f:
                f.write(audio.get_wav_data())
            segments, _ = stt_model.transcribe("temp.wav", language="ko", initial_prompt=hints)
            text = "".join([s.text for s in segments]).strip()
            return text if text else None
            
        except sr.WaitTimeoutError:
            return None
        except Exception as e:
            # 🚨 [수정 2] 문제가 생기면 조용히 멈추지 않고 터미널에 에러를 띄워주게 변경
            print(f"❌ [마이크 인식 오류] {e}") 
            return None

async def voice_background_task():
    """디스코드 봇과 겹치지 않게 비동기로 마이크를 계속 감시합니다."""
    await client.wait_until_ready()
    print("[시스템] 마이크 상시 대기 모드 시작...")
    
    while not client.is_closed():
        user_text = await asyncio.to_thread(listen_microphone)
        
        if user_text:
            print(f"[음성 인식] {user_text}")
            
            # 음성 입력은 별명 필수
            reply_text = await process_command(user_text, require_alias=True)
            
            if reply_text:
                channel = client.get_channel(LOG_CHANNEL_ID)
                if channel:
                    await channel.send(f"**[음성 명령 수신]** {user_text}")
                    await channel.send(f"**[AI 로컬 제어/응답]** {reply_text}")
                    
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
        
    # 1. 우선 직접 제어 가능한 명령인지 확인 (별명 체크 없이 바로 실행)
    is_direct, direct_reply = handle_direct_command(user_command)
    
    if is_direct:
        # 직접 제어인 경우 LLM을 거치지 않고 피드백 전송
        await message.channel.send(f"**[로컬 직접 제어]** {direct_reply}")
        return

    # 2. 직접 제어가 아닌 경우에만 LLM 분석 진행
    status_msg = await message.channel.send("⏳ 로컬 LLM이 명령을 분석 중입니다...")
    
    reply_text = await process_command(user_command, require_alias=False)
    
    await status_msg.edit(content=f"**[AI 실행 결과]** {reply_text}")

# 봇 실행
client.run(DISCORD_TOKEN)