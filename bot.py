import os
import time
import requests
from requests.auth import HTTPBasicAuth
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, ImageMessage, VideoMessage, FileMessage

app = Flask(__name__)

# ดึงค่า Config (ต้องตั้งค่าใน Railway Variables)
LINE_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_SECRET = os.getenv('LINE_CHANNEL_SECRET')
NAS_USER = os.getenv('NAS_USER')
NAS_PASS = os.getenv('NAS_PASS')
NAS_URL = os.getenv('NAS_URL')

line_bot_api = LineBotApi(LINE_TOKEN)
handler = WebhookHandler(LINE_SECRET)

def get_storage_info(event):
    """วิเคราะห์ประเภทไฟล์และเลือกโฟลเดอร์ใน NAS"""
    if isinstance(event.message, ImageMessage):
        return "BackupImages", f"img_{event.message.id}.jpg"
    elif isinstance(event.message, VideoMessage):
        return "BackupVideos", f"video_{event.message.id}.mp4"
    elif isinstance(event.message, FileMessage):
        f_name = event.message.file_name
        ext = os.path.splitext(f_name)[1].lower()
        if ext in ['.zip', '.rar', '.7z', '.tar', '.gz']:
            return "BackupArchives", f_name
        return "BackupDocments", f_name
    return "Others", f"file_{event.message.id}"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=(ImageMessage, VideoMessage, FileMessage))
def handle_content_backup(event):
    try:
        sub_folder, file_name = get_storage_info(event)
        target_url = f"{NAS_URL}/LineBackup/{sub_folder}/{file_name}"
        
        # ดึงไฟล์จาก LINE และอัปโหลดเข้า NAS ทันที (Streaming)
        message_content = line_bot_api.get_message_content(event.message.id)
        
        response = requests.put(
            target_url,
            data=message_content.content,
            auth=HTTPBasicAuth(NAS_USER, NAS_PASS),
            timeout=120
        )

        if response.status_code in [201, 204]:
            print(f"[SUCCESS] {file_name} saved to NAS", flush=True)
        else:
            print(f"[ERROR] NAS Status: {response.status_code}", flush=True)

    except Exception as e:
        print(f"[ERROR] {str(e)}", flush=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)