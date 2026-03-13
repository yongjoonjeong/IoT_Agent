#include <WiFi.h>
#include <ESPmDNS.h>
#include <WebServer.h>

#include "secrets.h" 

const char* ssid = SECRET_SSID;
const char* password = SECRET_PASS;

WebServer server(80);

void setup() {
  Serial.begin(115200);
  
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) { 
    delay(500); 
  }
  
  if (!MDNS.begin("light1")) {
    while(1) { delay(1000); }
  }
  
  server.on("/on", []() {
    server.send(200, "text/plain", "Light is ON");
  });
  
  server.begin();
}

void loop() { 
  server.handleClient(); 
}