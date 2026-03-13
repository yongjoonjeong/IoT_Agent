import sys
import time
import re
import json
# 향후 실제 IR 제어를 위해 lirc나 gpiozero 등의 라이브러리를 import 할 자리

def send_ir_signal(command):
    # 여기에 실제 IR 발신 코드가 들어갑니다.
    # print(f"📡 [IR 송신] 에어컨으로 '{command}' 신호를 쏩니다...")
    time.sleep(1) # 신호 전송 대기 시간 시뮬레이션
    # print("✅ [IR 송신] 완료!")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # main.py에서 전달받은 사용자의 원본 문장 전체
        user_text = sys.argv[1]
        
        # 기본 동작 우선순위 파악
        action = None
        if "꺼" in user_text:
            action = "OFF"
        elif "켜" in user_text:
            action = "ON"
            
        # 온도 숫자 추출 (18도 ~ 30도)
        val_match = re.search(r"(\d+)\s*도", user_text)
        temp_val = val_match.group(1) if val_match else None
        
        # 1. 온도가 명시되었지만 '켜/꺼'가 없는 경우 -> '켜기'로 간주
        # "에어컨 25도로 맞춰줘"
        if temp_val and not action:
            action = "ON"
            
        # 2. 결과 처리 및 응답 메시지 생성
        if not action and not temp_val:
            # 에어컨이라고만 하고 어떻게 할지 안 말한 경우
            result = {"status": "incomplete", "speech": "에어컨을 켤까요, 아니면 끌까요?"}
        
        elif action == "ON" and not temp_val:
            # 켜달라고는 했는데 온도가 없는 경우
            result = {"status": "incomplete", "speech": "에어컨 온도를 몇 도로 맞출까요?"}
            
        elif action == "OFF":
            send_ir_signal("POWER_OFF")
            result = {"status": "success", "speech": "네, 에어컨을 껐습니다."}
            
        else:
            # ON 이고 온도가 있는 경우
            send_ir_signal(f"TEMP_{temp_val}")
            result = {"status": "success", "speech": f"에어컨을 켜고 {temp_val}도로 설정했습니다."}
            
        # main.py가 읽을 수 있도록 JSON 형태로 출력
        print(json.dumps(result, ensure_ascii=False))
        
    else:
        err = {"status": "error", "speech": "에어컨 명령어가 전달되지 않았습니다."}
        print(json.dumps(err, ensure_ascii=False))