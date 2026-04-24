import os
import time
import requests
import re
from datetime import datetime # เพิ่มสำหรับจัดการวันที่
from requests.auth import HTTPBasicAuth
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage, 
    VideoMessage, FileMessage, TextSendMessage
)

app = Flask(__name__)

# --- 1. การตั้งค่า Config ---
LINE_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_SECRET = os.getenv('LINE_CHANNEL_SECRET')
NAS_USER = os.getenv('NAS_USER')
NAS_PASS = os.getenv('NAS_PASS')
NAS_URL = os.getenv('NAS_URL')

line_bot_api = LineBotApi(LINE_TOKEN)
handler = WebhookHandler(LINE_SECRET)

# --- 2. ฟังก์ชันช่วยงาน (Helper Functions) ---

def clean_folder_name(name):
    """ลบอักขระพิเศษเพื่อให้ชื่อโฟลเดอร์ใน NAS ไม่พัง"""
    clean_name = re.sub(r'[^\u0E00-\u0E7Fa-zA-Z0-9\s]', '', name)
    return clean_name.strip().replace(' ', '_')

def ensure_nas_folder(full_path):
    """ตรวจสอบและสร้างโฟลเดอร์ใน NAS หากยังไม่มี (WebDAV MKCOL)"""
    # แยก path เป็นส่วนๆ เพื่อสร้างทีละระดับ
    parts = full_path.strip('/').split('/')
    current_path = f"{NAS_URL}"
    for part in parts:
        current_path += f"/{part}"
        # ลองสร้างโฟลเดอร์ (ถ้ามีอยู่แล้วจะตอบกลับ 405 Method Not Allowed)
        requests.request(
            'MKCOL', 
            current_path, 
            auth=HTTPBasicAuth(NAS_USER, NAS_PASS)
        )

def get_group_name(event):
    if event.source.type == 'group':
        try:
            group_id = event.source.group_id
            group_summary = line_bot_api.get_group_summary(group_id)
            return clean_folder_name(group_summary.group_name)
        except:
            return event.source.group_id
    return None

def get_storage_info(event, group_folder):
    """กำหนดโครงสร้างโฟลเดอร์: ชื่อกลุ่ม/ประเภทไฟล์/ปปปป-ดด-วว/ไฟล์"""
    # ดึงวันที่ปัจจุบัน (รูปแบบ 2024-04-24)
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    if isinstance(event.message, ImageMessage):
        sub_folder = "BackupImages"
        file_name = f"img_{event.message.id}.jpg"
    elif isinstance(event.message, VideoMessage):
        sub_folder = "BackupVideos"
        file_name = f"video_{event.message.id}.mp4"
    elif isinstance(event.message, FileMessage):
        file_name = event.message.file_name
        ext = os.path.splitext(file_name)[1].lower()
        if ext in ['.zip', '.rar', '.7z', '.tar', '.gz']:
            sub_folder = "BackupArchives"
        elif ext in ['.dwg', '.dxf', '.dwt']:
            sub_folder = "BackupCAD"
        else:
            sub_folder = "BackupDocuments"
    else:
        sub_folder = "Others"
        file_name = f"file_{event.message.id}"
            
    # โครงสร้างใหม่: ชื่อกลุ่ม/ประเภทไฟล์/วันที่
    rel_path = f"{group_folder}/{sub_folder}/{today_str}"
    return rel_path, file_name

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

# --- 4. Main Backup Handler ---
@handler.add(MessageEvent, message=(ImageMessage, VideoMessage, FileMessage))
def handle_content_backup(event):
    group_folder = get_group_name(event)
    if not group_folder:
        return

    try:
        rel_path, file_name = get_storage_info(event, group_folder)
        
        # 1. ตรวจสอบและสร้างโฟลเดอร์ LineBackup และโฟลเดอร์ย่อย
        ensure_nas_folder(f"LineBackup/{rel_path}")
        
        target_url = f"{NAS_URL}/LineBackup/{rel_path}/{file_name}"
        print(f"[GROUP] {group_folder} | Folder: {rel_path} | Saving: {file_name}", flush=True)

        message_content = line_bot_api.get_message_content(event.message.id)
        
        # 2. ส่งข้อมูลเข้า NAS
        response = requests.put(
            target_url,
            data=message_content.content,
            auth=HTTPBasicAuth(NAS_USER, NAS_PASS),
            timeout=120 
        )

        if response.status_code in [201, 204]:
            print(f"[SUCCESS] Saved to {rel_path}", flush=True)
        else:
            print(f"[ERROR] HTTP {response.status_code}", flush=True)
            
    except Exception as e:
        print(f"[ERROR] {str(e)}", flush=True)

# --- 5. Status Command ---
@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    if event.message.text == "/status":
        group_name = get_group_name(event)
        if group_name:
            today = datetime.now().strftime('%Y-%m-%d')
            msg = f"Group Backup: Active\nGroup: {group_name}\nDate Folder: {today}"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)