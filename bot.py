import os
import time
import base64
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage, 
    VideoMessage, FileMessage, TextSendMessage
)

app = Flask(__name__)

# --- 1. การตั้งค่า Config (ดึงจาก Railway Variables) ---
LINE_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_SECRET = os.getenv('LINE_CHANNEL_SECRET')
IMGBB_KEY = os.getenv('IMGBB_API_KEY')

line_bot_api = LineBotApi(LINE_TOKEN)
handler = WebhookHandler(LINE_SECRET)

# พาธหลักสำหรับเก็บไฟล์ใน Railway
BASE_PATH = "/app/LineBackup"

# --- 2. ฟังก์ชันช่วยงาน (Helper Functions) ---

def get_storage_info(event):
    """วิเคราะห์ประเภทไฟล์และกำหนดโฟลเดอร์ปลายทาง"""
    if isinstance(event.message, ImageMessage):
        return "BackupImages", f"img_{event.message.id}.jpg"
        
    elif isinstance(event.message, VideoMessage):
        return "BackupVideos", f"video_{event.message.id}.mp4"
        
    elif isinstance(event.message, FileMessage):
        f_name = event.message.file_name
        ext = os.path.splitext(f_name)[1].lower()
        
        # คัดแยกกลุ่ม Archives
        archive_exts = ['.zip', '.rar', '.7z', '.tar', '.gz']
        if ext in archive_exts:
            return "BackupArchives", f_name
        else:
            return "BackupDocments", f_name
            
    return "Others", f"file_{event.message.id}"

# --- 3. Webhook Route ---

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# --- 4. Main Backup Handler (ไม่มีการแจ้งเตือนใน LINE) ---

@handler.add(MessageEvent, message=(ImageMessage, VideoMessage, FileMessage))
def handle_content_backup(event):
    start_time = time.time()
    try:
        # 1. ระบุตำแหน่งจัดเก็บ
        sub_folder, file_name = get_storage_info(event)
        target_dir = os.path.join(BASE_PATH, sub_folder)
        
        # Log แจ้งเตือนใน Railway ว่าได้รับไฟล์แล้ว
        print(f"[INFO] Received: {file_name} for {sub_folder}", flush=True)

        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        # 2. ดาวน์โหลดข้อมูลจาก LINE
        message_content = line_bot_api.get_message_content(event.message.id)
        full_path = os.path.join(target_dir, file_name)
        
        file_size = 0
        with open(full_path, 'wb') as fd:
            for chunk in message_content.iter_content():
                fd.write(chunk)
                file_size += len(chunk)
        
        size_mb = round(file_size / (1024 * 1024), 2)
        
        # Log แจ้งเตือนใน Railway เมื่อบันทึกสำเร็จ
        print(f"[SUCCESS] Saved: {full_path} ({size_mb} MB)", flush=True)
        print(f"[SUCCESS] Time taken: {round(time.time() - start_time, 2)} sec", flush=True)
        print("-" * 30, flush=True)

        # --- ลบส่วน line_bot_api.reply_message ออกแล้ว ---

    except Exception as e:
        # Log แจ้งเตือนใน Railway เมื่อเกิดข้อผิดพลาด
        print(f"[ERROR] {str(e)}", flush=True)
        print("-" * 30, flush=True)

# --- 5. Status Command (คงไว้เผื่อคุณต้องการเช็คยอดไฟล์ด้วยตัวเอง) ---

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    if event.message.text == "/status":
        msg = "Storage Status:\n"
        folders = ["BackupImages", "BackupVideos", "BackupArchives", "BackupDocments"]
        for f in folders:
            path = os.path.join(BASE_PATH, f)
            count = len(os.listdir(path)) if os.path.exists(path) else 0
            msg += f"- {f}: {count} files\n"
        
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"[SYSTEM] Bot started on port {port}", flush=True)
    print(f"[SYSTEM] Backup Path: {BASE_PATH}", flush=True)
    app.run(host="0.0.0.0", port=port)