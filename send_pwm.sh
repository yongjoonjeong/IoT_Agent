#!/bin/bash

# 입력값이 2개가 아니면 안내 메시지 출력
if [ "$#" -ne 2 ]; then
  echo "사용법: ./send_pwm.sh [보드이름] [0-100 사이의 숫자]"
  echo "예시: ./send_pwm.sh light 50"
  exit 1
fi

TARGET_BOARD=$1
VALUE=$2

# 입력값이 0~100 사이의 숫자인지 확인
if [ "$VALUE" -ge 0 ] && [ "$VALUE" -le 100 ]; then
  echo "🚀 [${TARGET_BOARD}.local] 보드로 PWM $VALUE% 전송 시도 중..."
  
  # 입력받은 보드 이름으로 주소를 동적 생성하여 신호 전송
  curl -s "http://${TARGET_BOARD}.local/pwm?val=$VALUE"
  echo ""
else
  echo "❌ 오류: PWM 값은 0에서 100 사이의 숫자를 입력하세요."
fi