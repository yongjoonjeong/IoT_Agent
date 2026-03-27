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

print("[시스템] STT 모델 로딩 중...")
stt_model = WhisperModel("base", device="cpu", compute_type="int8")
print("[시스템] 초기화 완료!")

LOG_CHANNEL_ID = None 

# --- 2. 헬퍼 함수 정의 ---
def read_file(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

def get_stt_hints(file_path="whisper_hint.txt"):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().replace('\n', ', ') 
    return ""

def get_alias(agent_text):
    match = re.search(r"<별명>\s*:\s*(.+)", agent_text)
    if match:
        return match.group(1).strip()
    return "자비스" 

def handle_direct_command(user_text):
    """LLM을 거치지 않고 직접 제어하는 로직"""
    # 🌟 타겟에 전등, 라이트 추가
    targets = ["에어컨", "조명", "전등", "라이트", "환풍기"]
    found_target = None
    for t in targets:
        if t in user_text:
            found_target = t
            break
            
    if not found_target:
        return False, None
        
    print(f"[직접 제어 감지] 대상: {found_target}")
    
    # 1. 에어컨 제어 로직
    if found_target == "에어컨":
        try:
            result = subprocess.run(
                ["python3", "Aircon/aircon.py", user_text], 
                capture_output=True, 
                text=True
            )
            output = result.stdout.strip()
            try:
                data = json.loads(output)
                if data.get("status") == "incomplete":
                    return False, None
                speech = data.get("speech", "에어컨 제어 명령이 전송되었습니다.")
                return True, speech
            except json.JSONDecodeError:
                return True, "에어컨 제어 중 스크립트 오류가 발생했습니다."
        except Exception as e:
            print(f"[오류] 에어컨 스크립트 실행 실패: {e}")
            return True, "에어컨 스크립트를 실행할 수 없습니다."
            
    # 🌟 2. 조명(전등/라이트) 제어 완벽 매핑
    elif found_target in ["조명", "전등", "라이트"]:
        pwm_value = None
        action_text = ""
        
        # 단계 및 전원 상태 파악
        if "1단계" in user_text:
            pwm_value = 10
            action_text = "1단계(10%)로 조절했습니다."
        elif "2단계" in user_text:
            pwm_value = 50
            action_text = "2단계(50%)로 조절했습니다."
        elif "3단계" in user_text:
            pwm_value = 90
            action_text = "3단계(90%)로 조절했습니다."
        elif "꺼" in user_text:
            pwm_value = 0
            action_text = "껐습니다."
        elif "켜" in user_text:
            pwm_value = 100 # 기본 켜기는 100%로 설정
            action_text = "켰습니다."
            
        # 값이 지정되었으면 쉘 스크립트 실행
        if pwm_value is not None:
            try:
                print(f"[명령 실행] ./send_pwm.sh light {pwm_value}")
                subprocess.run(["./send_pwm.sh", "light", str(pwm_value)])
                return True, f"네, {found_target}을 {action_text}"
            except Exception as e:
                print(f"[오류] 조명 쉘 스크립트 실행 실패: {e}")
                return True, "조명 제어 중 시스템 오류가 발생했습니다."
        else:
            # "전등"이라는 말은 들렸는데 어떻게 하라는 건지 모를 경우 LLM에게 판단을 넘김
            return False, None

    # 3. 환풍기 임시 제어
    elif found_target == "환풍기":
        action = None
        if "켜" in user_text: action = "켜줘"
        elif "꺼" in user_text: action = "꺼줘"
        
        val_match = re.search(r"(\d+)(단)", user_text)
        value = val_match.group(1) if val_match else None
        
        if not action or (action == "켜줘" and not value):
            return False, None
            
        return True, f"{found_target}을 {value + '단으로 ' if value else ''}{action} 처리했습니다."

CONV_DIR = "@conversation"

def save_conversation(user_text, llm_reply):
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
        pass

async def get_relevant_context(user_text):
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
        extract_prompt = "다음 문장에서 중요한 단어나 개체명만 쉼표로 구분해서 말해. 부가 설명 절대 금지."
        resp = await AsyncClient().chat(model='llama3.2:3b', messages=[
            {'role': 'system', 'content': extract_prompt},
            {'role': 'user', 'content': user_text}
        ])
        keywords = [k.strip() for k in resp['message']['content'].split(',') if k.strip()]
        
        relevant_convs = []
        for conv in all_convs:
            conv_text = conv.get("user_input", "") + " " + conv.get("ai_response", "")
            if any(k in conv_text for k in keywords):
                relevant_convs.append(conv)
                
        relevant_convs = sorted(relevant_convs, key=lambda x: x.get("timestamp", ""), reverse=True)[:3]
        if not relevant_convs: return ""
            
        context_str = "\n[과거 연관 대화 기록]\n"
        for c in relevant_convs:
            context_str += f"User: {c.get('user_input')}\nAI: {c.get('ai_response')}\n---\n"
        return context_str
    except Exception:
        return ""

async def speak_text(text):
    audio_file = "reply.mp3"
    try:
        communicate = edge_tts.Communicate(text, "ko-KR-SunHiNeural")
        await communicate.save(audio_file)
    except Exception as e:
        print(f"[오류] TTS 재생 실패: {e}")

# --- 3. 핵심 AI 처리 파이프라인 ---
async def process_command(user_text, require_alias=False):
    agent_prompt = read_file("Agent.md")
    alias = get_alias(agent_prompt)
    
    if require_alias and alias not in user_text:
        return None, None 
        
    is_direct, direct_reply = handle_direct_command(user_text)
    if is_direct:
        return "direct", direct_reply
    
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
        
        if "action" not in llm_reply or "{" not in llm_reply:
             save_conversation(user_text, llm_reply)
        
        try:
            data = json.loads(llm_reply)
            action = data.get("action")
            target = data.get("target")
            val = data.get("value")
            speech = data.get("speech", "알겠습니다.")
            
            if action == "execute" and target == "에어컨":
                subprocess.run(["python3", "Aircon/aircon.py", str(val)])
            elif action == "execute" and target == "환풍기":
                pass 
                
            save_conversation(user_text, speech)
            return "llm", speech
            
        except json.JSONDecodeError:
            return "llm", llm_reply
            
    except Exception as e:
        return "error", f"처리 중 오류가 발생했습니다. {e}"

# --- 4. 백그라운드 마이크 대기 루프 ---
def listen_microphone():
    hints = get_stt_hints()
    recognizer = sr.Recognizer()
    microphone = sr.Microphone(device_index= 0, sample_rate=48000)
    
    with microphone as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        recognizer.energy_threshold = 300
        recognizer.pause_threshold = 1.2
        try:
            audio = recognizer.listen(source, timeout=2, phrase_time_limit=10)
            with open("temp.wav", "wb") as f:
                f.write(audio.get_wav_data())
                
            print("🎙️ [시스템] 목소리 감지 완료, 텍스트 변환(STT) 진행 중...")
            segments, _ = stt_model.transcribe("temp.wav", language="ko", initial_prompt=hints)
            text = "".join([s.text for s in segments]).strip()
            return text if text else None
            
        except sr.WaitTimeoutError:
            return None
        except Exception as e:
            print(f"❌ [마이크 인식 오류] {e}") 
            return None

async def voice_background_task():
    await client.wait_until_ready()
    print("[시스템] 마이크 상시 대기 모드 시작...")
    
    while not client.is_closed():
        user_text = await asyncio.to_thread(listen_microphone)
        
        if user_text:
            print(f"[음성 인식] {user_text}")
            source, reply_text = await process_command(user_text, require_alias=True)
            
            if reply_text:
                channel = client.get_channel(LOG_CHANNEL_ID)
                if channel:
                    await channel.send(f"**[음성 명령 수신]** {user_text}")
                    prefix = "**🤖 [로컬 하드웨어 봇] 엣지단 즉시 제어**" if source == "direct" else "**🧠 [로컬 LLM 답변] 문맥 추론**"
                    await channel.send(f"{prefix}\n{reply_text}")
                await speak_text(reply_text)

# --- 5. 디스코드 봇 이벤트 ---
@client.event
async def on_ready():
    global LOG_CHANNEL_ID
    print(f"[시스템] 디스코드 봇 [{client.user}] 온라인!")
    
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
    if message.author == client.user: 
        return

    user_command = message.content.strip()
    if not user_command:
        return
        
    status_msg = await message.channel.send("⏳ 명령을 처리 중입니다...")
    source, reply_text = await process_command(user_command, require_alias=False)
    
    if source == "direct":
        await status_msg.edit(content=f"**🤖 [로컬 하드웨어 봇] 엣지단 즉시 제어**\n{reply_text}")
    elif source == "llm":
        await status_msg.edit(content=f"**🧠 [로컬 LLM 답변] 문맥 추론**\n{reply_text}")
    else:
        await status_msg.edit(content=f"**[시스템 오류]**\n{reply_text}")

client.run(DISCORD_TOKEN)