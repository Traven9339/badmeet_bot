import os
import requests
from flask import Flask, request

app = Flask(__name__)

# 从 Replit 的 Secrets 中读取变量
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# 发送测试消息
def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    requests.post(url, data=payload)

@app.route('/')
def home():
    return "✅ Bot is running!"

@app.route('/send', methods=['GET'])
def send():
    message = request.args.get("msg", "Hello from Replit!")
    send_message(message)
    return f"Message sent: {message}"

if __name__ == '__main__':
    send_message("🚀 BadMeet Bot 已经在 Replit 启动！")
    app.run(host='0.0.0.0', port=8080)
