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
    msg = request.args.get("msg", "Hello from Render!")
    if not BOT_TOKEN or not CHAT_ID:
        return "❌ Missing BOT_TOKEN or CHAT_ID environment variable", 500
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg}
    try:
        requests.post(url, json=payload)
        return f"✅ Message sent: {msg}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
