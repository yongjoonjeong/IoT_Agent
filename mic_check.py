import speech_recognition as sr

print("🎤 파이썬이 인식한 마이크 목록:")
for index, name in enumerate(sr.Microphone.list_microphone_names()):
    print(f"[{index}] {name}")


    