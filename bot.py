import os
import time
import sys # เพิ่มตัวนี้เพื่อใช้ flush
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage, 
    VideoMessage, FileMessage, TextSendMessage
)

app = Flask(__name__)

# --- Configuration ---
LINE_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_SECRET = os.getenv('LINE_CHANNEL_SECRET')

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_SECRET)
BASE_PATH = "/app/LineBackup"

# --- ส่วนเช็คสถานะ Server (เข้าชมผ่าน Browser ได้) ---
@app.route("/", methods=['GET'])
def index():
    # ถ้าเปิดหน้าเว็บ Railway แล้วเจอข้อความนี้ แสดงว่า Server ทำงานปกติครับ
    return "Line Backup Bot is Running!", 200

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    
    # พิมพ์ Log ทุกครั้งที่มีคนเรียก Webhook (เพื่อเช็คว่า LINE ส่งมาถึงไหม)
    print(f"[DEBUG] Webhook received from LINE", flush=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("[ERROR] Invalid Signature. Check your Channel Secret.", flush=True)
        abort(400)
    return 'OK'

def get_storage_info(event):
    if isinstance(event.message, ImageMessage):
        return "BackupImages", f"img_{event.message.id}.jpg"
    elif isinstance(event.message, VideoMessage):
        return "BackupVideos", f"video_{event.message.id}.mp4"
    elif isinstance(event.message, FileMessage):
        file_name = event.message.file_name
        ext = os.path.splitext(file_name)[1].lower()
        archive_exts = ['.zip', '.rar', '.7z']
        if ext in archive_exts:
            return "BackupArchives", file_name
        else:
            return "BackupDocments", file_name
    return "Others", f"file_{event.message.id}"

@handler.add(MessageEvent, message=(ImageMessage, VideoMessage, FileMessage))
def handle_content_backup(event):
    start_time = time.time()
    try:
        sub_folder, file_name = get_storage_info(event)
        target_dir = os.path.join(BASE_PATH, sub_folder)
        
        # ใส่ flush=True เพื่อให้ Log ออกทันที
        print(f"[INFO] Start downloading: {file_name}", flush=True)
        
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
            print(f"[INFO] Folder created: {target_dir}", flush=True)

        message_content = line_bot_api.get_message_content(event.message.id)
        full_path = os.path.join(target_dir, file_name)
        
        file_size = 0
        with open(full_path, 'wb') as fd:
            for chunk in message_content.iter_content():
                fd.write(chunk)
                file_size += len(chunk)
        
        size_mb = round(file_size / (1024 * 1024), 2)
        print(f"[SUCCESS] Saved to: {full_path} ({size_mb} MB)", flush=True)
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"Backup Complete\nCategory: {sub_folder}\nFile: {file_name}")
        )
        
    except Exception as e:
        print(f"[ERROR] Fail: {str(e)}", flush=True)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    # Log ตอนเริ่มระบบ
    print(f"--- Starting System ---", flush=True)
    print(f"Port: {port}", flush=True)
    print(f"Path: {BASE_PATH}", flush=True)
    app.run(host='0.0.0.0', port=port)