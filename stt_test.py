import speech_recognition as sr
from faster_whisper import WhisperModel
import ollama
import edge_tts
import pygame
import asyncio
import os


os.environ["SDL_AUDIODRIVER"] = "dummy"


# --- 1. 초기 세팅 ---
print("🚀 [시스템] 시스템 초기화 중...")
# TTS 재생을 위한 pygame 믹서 초기화
pygame.mixer.init()

# STT 모델 로딩 (최초 1회)
print("📥 [시스템] STT 모델(faster-whisper) 로딩 중...")
stt_model = WhisperModel("base", device="cpu", compute_type="int8")
print("✅ [시스템] 준비 완료!\n" + "="*50)

# --- 2. 핵심 함수 정의 ---

def get_stt_hints(file_path="whisper_hint.txt"):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            # 줄바꿈을 쉼표로 바꿔서 한 줄의 프롬프트로 만듭니다.
            return f.read().replace('\n', ', ') 
    return ""



def read_agent_md():
    """Agent.md 파일을 읽어와서 시스템 프롬프트로 사용할 문자열 반환"""
    file_path = "Agent.md"
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception as e:
        print(f"Agent.md 파일 읽기 오류: {e}")
    

def listen_to_user():
    """마이크를 열어 사용자의 음성을 녹음하고 텍스트로 변환"""
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()
    
    # 🚨 [수정 1] 위에서 만든 함수를 불러와서 hints 변수에 확실히 넣어줍니다!
    hints = get_stt_hints()

    with microphone as source:
        print("\n🎧 주변 소음 적응 중...")
        # 🚨 [수정 2] 적응 시간을 0.5초로 줄이고, 강제로 귀를 아주 밝게(300) 만듭니다!
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        recognizer.energy_threshold = 300  
        recognizer.pause_threshold = 1.2 
        
        print("🟢 말씀해 주세요! (듣는 중...)")
        try:
            audio_data = recognizer.listen(source, timeout=5, phrase_time_limit=15)
            print("🔄 음성 인식 중...")
            
            # 임시 파일로 저장 후 faster-whisper로 변환
            temp_wav = "temp_voice.wav"
            with open(temp_wav, "wb") as f:
                f.write(audio_data.get_wav_data())
            
            # 여기서 hints 변수를 무사히 사용하게 됩니다.
            segments, _ = stt_model.transcribe(temp_wav, beam_size=5, language="ko", initial_prompt=hints)
            text = "".join([segment.text for segment in segments])
            
            if os.path.exists(temp_wav): os.remove(temp_wav)
            return text.strip()

        except sr.WaitTimeoutError:
            print("💤 (입력 없음)")
            return None
        except Exception as e:
            # 에러가 나면 화면에 빨간색으로 확실하게 보여주도록 수정
            print(f"❌ 음성 인식 오류 발생: {e}") 
            return None

def think_llm(user_text, agent_prompt):
    """Ollama를 통해 LLM에게 질문하고 답변을 받아옴"""
    print("🧠 LLM 생각 중...")
    try:
        # 모델명은 qwen3.5:4b 또는 llama3.2:3b 로 상황에 맞게 변경하세요.
        response = ollama.chat(model='llama3.2:3b', messages=[
            {'role': 'system', 'content': agent_prompt},
            {'role': 'user', 'content': user_text}
        ])
        return response['message']['content'].strip()
    except Exception as e:
        print(f" LLM 처리 오류: {e}")
        return "죄송해요, 생각이 중간에 엉켰어요."

async def speak_text(text):
    """텍스트를 edge-tts로 음성 변환 후 스피커로 출력"""
    print(f"🗣️ AI 답변 낭독 중: {text}")
    audio_file = "reply.mp3"
    
    try:
        # 한국어 여성 아나운서 톤 (SunHi)
        communicate = edge_tts.Communicate(text, "ko-KR-SunHiNeural")
        await communicate.save(audio_file)
        
        # 스피커 재생
        pygame.mixer.music.load(audio_file)
        pygame.mixer.music.play()
        
        # 말이 끝날 때까지 대기
        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.1)
            
        pygame.mixer.music.unload()
        if os.path.exists(audio_file): os.remove(audio_file)
            
    except Exception as e:
        print(f"TTS 재생 오류: {e}")

# --- 3. 메인 실행 루프 ---
def main():
    while True:
        try:
            # 1. 마이크로 듣기
            user_input = listen_to_user()
            
            if user_input:
                print("-" * 40)
                print(f" 사용자: {user_input}")
                
                # 2. Agent.md 읽어오기
                agent_context = read_agent_md()
                
                # 3. LLM에게 답변 구하기
                llm_reply = think_llm(user_input, agent_context)
                
                # 4. 스피커로 말하기 (asyncio.run으로 비동기 함수 실행)
                asyncio.run(speak_text(llm_reply))
                print("-" * 40)
                
        except KeyboardInterrupt:
            print("\n 프로그램을 종료합니다.")
            break

if __name__ == "__main__":
    main()





