import os
import vosk
import pyaudio
import pyttsx3
import json
import requests
import asyncio
import websockets
import threading

# 模型路径
model_path = "vosk-model-small-cn-0.22"
if not os.path.exists(model_path):
    print(f"模型文件夹 {model_path} 不存在！")
    exit()

# 当前是否正在播放语音的标志
is_speaking = False
speech_thread = None  # 用来控制语音播放线程

# 调用大模型接口获取回复
def get_model_reply(prompt):
    url = "http://x.x.x.x:xxxx/api/generate"
    headers = {
        "Host": "127.0.0.1",
        "Content-Type": "application/json"
    }
    data = {
        "model": "qwen2.5",
        "prompt": prompt,
        "stream": False
    }
    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            response_data = response.json()
            return response_data.get("response", "抱歉，未能生成回复。")
        else:
            return f"请求失败，状态码: {response.status_code}"
    except Exception as e:
        return f"请求发生错误: {str(e)}"

# 语音合成并播放
def speak(text):
    global is_speaking, speech_thread
    is_speaking = True  # 设置为正在播放语音

    def run_speech():
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)
        engine.setProperty('volume', 1.0)
        voices = engine.getProperty('voices')
        male_voice = next((v for v in voices if "male" in v.name.lower()), None)
        if male_voice:
            engine.setProperty('voice', male_voice.id)
        engine.say(text)
        engine.runAndWait()
        global is_speaking
        is_speaking = False  # 播放完成后设置为未播放

    # 创建一个线程来处理语音播放，这样就能在播放期间不阻塞其他操作
    speech_thread = threading.Thread(target=run_speech)
    speech_thread.start()

# WebSocket 发送消息
async def send_message(websocket, message):
    try:
        await websocket.send(json.dumps(message))
    except Exception as e:
        print(f"WebSocket发送消息失败: {e}")

# 启动语音识别和通信
async def recognize_and_communicate():
    uri = "ws://127.0.0.1:8888"  # Unity 的 WebSocket 地址

    # 初始化 PyAudio 和 Vosk
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000,
                    input=True, frames_per_buffer=4000)
    model = vosk.Model(model_path)
    rec = vosk.KaldiRecognizer(model, 16000)

    print("语音识别启动，等待连接到 Unity...")

    # 保持 WebSocket 连接
    async with websockets.connect(uri) as websocket:
        print("已连接到 Unity")

        while True:  # 持续识别并发送消息
            try:
                # 读取音频数据
                data = stream.read(4000, exception_on_overflow=False)
                
                # 如果正在播放语音，跳过本次语音识别
                if is_speaking:
                    await asyncio.sleep(0.1)  # 稍微延时，避免占用过多的 CPU 资源
                    continue

                if rec.AcceptWaveform(data):
                    result = rec.Result()
                    result_json = json.loads(result)
                    user_input = result_json.get('text', "").strip()

                    if user_input:
                        print(f"用户说: {user_input}")

                        # 获取模型回复
                        reply_text = get_model_reply(user_input)
                        print(f"模型回复: {reply_text}")

                        # 将结果发送到 Unity
                        message = {
                            "user_input": user_input,
                            "reply_text": reply_text
                        }
                        await send_message(websocket, message)

                        # 语音播放回复
                        speak(reply_text)

                await asyncio.sleep(0.1)  # 稍微延时，确保持续读取
            except Exception as e:
                print(f"语音识别或消息处理出错: {e}")
                await asyncio.sleep(1)  # 防止出错时死循环

# 主函数
if __name__ == "__main__":
    try:
        asyncio.run(recognize_and_communicate())
    except KeyboardInterrupt:
        print("程序已终止")
