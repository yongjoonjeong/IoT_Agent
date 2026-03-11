import sys
import time
# 향후 실제 IR 제어를 위해 lirc나 gpiozero 등의 라이브러리를 import 할 자리

def send_ir_signal(command):
    # 여기에 실제 IR 발신 코드가 들어갑니다.
    print(f"📡 [IR 송신] 에어컨으로 '{command}' 신호를 쏩니다...")
    time.sleep(1) # 신호 전송 대기 시간 시뮬레이션
    print("✅ [IR 송신] 완료!")

if __name__ == "__main__":
    # 메인 봇에서 인자(명령어)를 제대로 넘겨주었는지 확인
    if len(sys.argv) > 1:
        target_value = sys.argv[1]
        
        if target_value.lower() == "on":
            send_ir_signal("POWER_ON")
        elif target_value.lower() == "off":
            send_ir_signal("POWER_OFF")
        else:
            send_ir_signal(f"TEMP_{target_value}")
    else:
        print("❌ 오류: 전달된 에어컨 설정 값이 없습니다.")