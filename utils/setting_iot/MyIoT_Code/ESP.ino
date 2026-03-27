#include <WiFi.h>
#include <ESPmDNS.h>
#include <WebServer.h>

// 🌟 여기에 사용하시는 와이파이 정보를 입력하세요!
const char* ssid = "Jws";
const char* password = "11111112";

WebServer server(80);
const int pwmPin = 3; // 제어할 3번 핀

void handlePWM() {
  // 라즈베리파이가 "?val=숫자" 형태로 보낸 값을 확인합니다.
  if (server.hasArg("val")) {
    int val = server.arg("val").toInt();
    
    // 0~100 사이의 값인지 검증
    if (val >= 0 && val <= 100) {
      // 0~100을 ESP32의 8비트 PWM 해상도인 0~255로 변환
      int mappedVal = map(val, 0, 100, 0, 255);
      
      // 3번 핀에 PWM 신호 출력
      analogWrite(pwmPin, mappedVal); 
      
      String msg = "✅ PWM이 " + String(val) + "% 로 설정되었습니다.";
      server.send(200, "text/plain; charset=utf-8", msg);
      Serial.println(msg);
    } else {
      server.send(400, "text/plain; charset=utf-8", "❌ 값은 0에서 100 사이여야 합니다.");
    }
  } else {
    server.send(400, "text/plain; charset=utf-8", "❌ 'val' 값이 전달되지 않았습니다.");
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(pwmPin, OUTPUT);
  analogWrite(pwmPin, 0); // 초기 상태는 0(꺼짐)

  Serial.println("\nWiFi 연결 중...");
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n✅ WiFi 연결 성공!");

  // 🌟 mDNS 설정 (IP 주소 대신 esp32c3.local 로 접속 가능하게 함)
  if (!MDNS.begin("light")) {
    Serial.println("❌ mDNS 설정 실패!");
    while(1) { delay(1000); }
  }
  Serial.println("✅ mDNS 시작됨: http://light.local");

  // /pwm 경로로 요청이 오면 handlePWM 함수를 실행
  server.on("/pwm", HTTP_GET, handlePWM);
  server.begin();
  Serial.println("✅ 웹 서버 실행 중!");
}

void loop() {
  // 라즈베리파이의 요청을 계속 기다림
  server.handleClient();
  delay(2);
}