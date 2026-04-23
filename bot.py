import os
import time
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage, 
    VideoMessage, FileMessage, TextSendMessage
)

app = Flask(__name__)

# --- Configuration ---
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', 'YOUR_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', 'YOUR_SECRET')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# โครงสร้างโฟลเดอร์หลัก
BASE_PATH = "/app/LineBackup"

def get_storage_info(event):
    """แยกประเภทโฟลเดอร์ย่อยและชื่อไฟล์ตามประเภทข้อมูล"""
    if isinstance(event.message, ImageMessage):
        return "BackupImages", f"img_{event.message.id}.jpg"
        
    elif isinstance(event.message, VideoMessage):
        return "BackupVideos", f"video_{event.message.id}.mp4"
        
    elif isinstance(event.message, FileMessage):
        file_name = event.message.file_name
        ext = os.path.splitext(file_name)[1].lower()
        
        # แยก Archives และ Documents
        archive_exts = ['.zip', '.rar', '.7z', '.tar', '.gz']
        if ext in archive_exts:
            return "BackupArchives", file_name
        else:
            return "BackupDocments", file_name
            
    return "Others", f"file_{event.message.id}"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=(ImageMessage, VideoMessage, FileMessage))
def handle_content_backup(event):
    start_time = time.time()
    try:
        sub_folder, file_name = get_storage_info(event)
        target_dir = os.path.join(BASE_PATH, sub_folder)
        
        # Railway Log: เริ่มต้นการทำงาน
        print(f"\n[INFO] Incoming request: {file_name}")
        print(f"[INFO] Category: {sub_folder}")
        
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
            print(f"[INFO] Created directory: {target_dir}")

        # ดึงข้อมูลจาก LINE Server
        message_content = line_bot_api.get_message_content(event.message.id)
        full_path = os.path.join(target_dir, file_name)
        
        # บันทึกไฟล์และคำนวณขนาด
        file_size = 0
        with open(full_path, 'wb') as fd:
            for chunk in message_content.iter_content():
                fd.write(chunk)
                file_size += len(chunk)
        
        duration = round(time.time() - start_time, 2)
        size_mb = round(file_size / (1024 * 1024), 2)

        # Railway Log: รายงานความสำเร็จ
        print(f"[SUCCESS] Saved: {full_path}")
        print(f"[SUCCESS] Size: {size_mb} MB")
        print(f"[SUCCESS] Time: {duration} sec")
        print("-" * 30)
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"Backup Complete\nCategory: {sub_folder}\nFile: {file_name}\nSize: {size_mb} MB")
        )
        
    except Exception as e:
        # Railway Log: กรณีเกิดข้อผิดพลาด
        print(f"[ERROR] Process failed for {file_name if 'file_name' in locals() else 'Unknown'}")
        print(f"[ERROR] Message: {str(e)}")
        print("-" * 30)

@handler.add(MessageEvent, message=TextMessage)
def handle_text_command(event):
    user_text = event.message.text
    if user_text == "/status":
        status_msg = "Storage Status:\n"
        folders = ["BackupImages", "BackupVideos", "BackupArchives", "BackupDocments"]
        for f in folders:
            path = os.path.join(BASE_PATH, f)
            count = len(os.listdir(path)) if os.path.exists(path) else 0
            status_msg += f"- {f}: {count} files\n"
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=status_msg)
        )

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    print(f"\n--- System Ready ---")
    print(f"Server Port: {port}")
    print(f"Backup Path: {BASE_PATH}")
    print(f"--------------------\n")
    app.run(host='0.0.0.0', port=port)