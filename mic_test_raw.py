import pyaudio
import wave

# Test parameters
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 1024
RECORD_SECONDS = 5
WAVE_OUTPUT_FILENAME = "test_mic.wav"
DEVICE_INDEX = 0 # Based on previous arecord -l output

audio = pyaudio.PyAudio()

print("Testing PyAudio with device_index =", DEVICE_INDEX)

try:
    # start Recording
    stream = audio.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    input_device_index=DEVICE_INDEX,
                    frames_per_buffer=CHUNK)
                    
    print("Recording for 5 seconds...")
    frames = []
    
    for i in range(0, int(RATE / CHANNELS / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)
        
    print("Finished recording.")
    
    # stop Recording
    stream.stop_stream()
    stream.close()
    audio.terminate()
    
    # save to file
    waveFile = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
    waveFile.setnchannels(CHANNELS)
    waveFile.setsampwidth(audio.get_sample_size(FORMAT))
    waveFile.setframerate(RATE)
    waveFile.writeframes(b''.join(frames))
    waveFile.close()
    print(f"Saved to {WAVE_OUTPUT_FILENAME}")
    
except Exception as e:
    print(f"Error initializing PyAudio stream: {e}")
    
finally:
    audio.terminate()
