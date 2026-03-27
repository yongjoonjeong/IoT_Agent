import sys
import os
import subprocess
import re
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = SCRIPT_DIR

def detect_devices():
    tx_dev, rx_dev = "/dev/lirc0", "/dev/lirc1"
    try:
        res = subprocess.run(["ir-ctl", "-d", "/dev/lirc0", "-f"], capture_output=True, text=True)
        # 🌟 "Receive" 단어 하나가 아니라, "수신 가능"이라는 정확한 문장을 찾도록 변경!
        if "Device can receive raw IR" in res.stdout:  
            tx_dev, rx_dev = "/dev/lirc1", "/dev/lirc0"
        else:
            tx_dev, rx_dev = "/dev/lirc0", "/dev/lirc1"
    except Exception:
        pass
    return tx_dev, rx_dev

TX_DEVICE, RX_DEVICE = detect_devices()

def parse_and_send(cmd):
    if cmd == "on":
        filename = "25degree.txt"
    elif cmd == "off":
        filename = "off.txt"
    else:
        filename = f"{cmd}degree.txt"

    filepath = os.path.join(DATA_DIR, filename)

    if not os.path.exists(filepath):
        print(f"❌ 파일을 찾을 수 없습니다: {filepath}")
        return

    with open(filepath, 'r') as f:
        content = f.read()

    matches = re.findall(r'[-+]\s*\d+', content)
    if not matches:
        print("❌ 유효한 IR 신호를 찾을 수 없습니다.")
        return

    conf_path = os.path.join(SCRIPT_DIR, "temp_ir.txt")
    
    print("-" * 30)
    print(f"🛠️ [디버깅] 원본 파일에서 찾은 총 신호 개수: {len(matches)}개")
    
    # 송신용으로 변환된 신호를 임시 저장할 리스트
    debug_signals = []
    
    with open(conf_path, 'w') as f:
        f.write("carrier 38000\n")
        started = False
        for m in matches:
            val = int(m.replace(' ', '').replace('+', ''))
            
            if not started:
                if val < 0:
                    continue
                else:
                    started = True
            
            if val < 0:
                line = f"space {abs(val)}"
            else:
                line = f"pulse {val}"
                
            f.write(line + "\n")
            debug_signals.append(line)

    # 🌟 추가된 디버깅 출력 부분
    print(f"🛠️ [디버깅] 하드웨어로 실제 전송될 신호 (앞부분 10줄만 출력):")
    for line in debug_signals[:10]:
        print("  > " + line)
    print(f"  > ... (총 {len(debug_signals)} 줄의 신호가 전송 대기 중)")
    print("-" * 30)

    print(f"🔍 장치 자동 세팅: 송신기({TX_DEVICE}), 수신기({RX_DEVICE})")
    print(f"👂 수신 대기 중...")
    
    recv_proc = subprocess.Popen(
        ["ir-ctl", "-d", RX_DEVICE, "-r"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    time.sleep(0.5)

    print(f"📡 IR 신호 송신 중... ({filename})")
    send_result = subprocess.run(["ir-ctl", "-d", TX_DEVICE, "--send", conf_path], capture_output=True, text=True)

    # 신호가 충분히 날아가고 수신될 수 있도록 대기 시간을 조금 늘렸습니다
    time.sleep(1.0)

    recv_proc.terminate()
    rx_out, rx_err = recv_proc.communicate()

    if send_result.returncode == 0:
        print("✅ 송신 완료!\n")
        print("-" * 30)
        print("📥 [수신된 데이터 확인]")
        
        if "pulse" in rx_out or "space" in rx_out:
            print("🎉 루프백 테스트 성공! 내가 쏜 신호를 되돌려 받았습니다!")
            lines = rx_out.strip().split('\n')
            for line in lines[:15]:
                print("  " + line)
            if len(lines) > 15:
                print("  ... (이하 생략)")
        else:
            print("⚠️ 송신 명령은 정상적으로 들어갔으나, 수신된 빛(신호)이 없습니다.")
            print("1. 송신기의 LED 전구가 고장났을 확률 (새 모듈로 교체 필요)")
            print("2. 송신기와 수신기의 센서가 서로 마주보고 있지 않음")
            if rx_err:
                print(f"RX 에러 로그: {rx_err}")
        print("-" * 30)
    else:
        print(f"❌ 송신 실패 (ir-ctl 하드웨어 에러):")
        print(send_result.stderr)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("사용법: python3 test_aircon.py [온도]")
        sys.exit(1)

    command_input = sys.argv[1].lower()
    
    if command_input.isdigit() and (18 <= int(command_input) <= 28):
        parse_and_send(command_input)
    elif command_input in ["on", "off"]:
        parse_and_send(command_input)
    else:
        print("❌ 온도는 18에서 28도 사이여야 합니다.")