from flask import Flask, request
import requests
import os

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

@app.route('/')
def home():
    return "✅ BadMeet Bot is running on Render!"

@app.route('/send')
def send_message():
    msg = request.args.get('msg', 'No message provided')
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg}
    requests.post(url, data=data)
    return f"Message sent: {msg}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
