#!/bin/bash

# 1. 연결된 USB 포트 자동 찾기 (보통 ttyUSB0 또는 ttyACM0)
PORT=$(ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null | head -n 1)

if [ -z "$PORT" ]; then
    echo "USB에 연결된 ESP 보드를 찾을 수 없습니다."
    exit 1
fi
echo "보드 감지됨: $PORT"

# 2. arduino-cli로 컴파일 및 업로드 (ESP32-C3 기준 예시)
echo " 펌웨어 굽기를 시작합니다"
arduino-cli compile --fqbn esp32:esp32:esp32c3 MyIoT_Code
arduino-cli upload -p $PORT --fqbn esp32:esp32:esp32c3 MyIoT_Code

echo "펌웨어 업로드 완료!"

# 3. 라즈베리파이 방화벽 포트 열기 (라즈베리파이가 서버 역할을 할 경우)
# 예: 라즈베리파이에 8080 포트로 파이썬 서버를 열어둘 거라면
echo "🔓 라즈베리파이 방화벽(ufw) 8080 포트를 엽니다..."
sudo ufw allow 8080/tcp

# 4. 재부팅 및 와이파이 접속 대기
echo "⏳ 기기가 와이파이에 접속할 시간을 줍니다 (10초 대기)..."
sleep 30

# 5. IP 스캔 없이 mDNS 이름으로 바로 통신 테스트!
echo "📡 light1.local 기기에 통신을 시도합니다..."
RESPONSE=$(curl -s http://light1.local/on)

if [ "$RESPONSE" == "Light is ON" ]; then
    echo "🎉 성공적으로 세팅 및 통신이 완료되었습니다!"
else
    echo "⚠️ 통신 실패. 기기가 와이파이에 연결되지 않았을 수 있습니다."
fi