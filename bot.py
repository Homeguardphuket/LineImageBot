import os
import time
import requests
import re
from requests.auth import HTTPBasicAuth
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
NAS_USER = os.getenv('NAS_USER')
NAS_PASS = os.getenv('NAS_PASS')
NAS_URL = os.getenv('NAS_URL')

line_bot_api = LineBotApi(LINE_TOKEN)
handler = WebhookHandler(LINE_SECRET)

# --- 2. ฟังก์ชันช่วยงาน (Helper Functions) ---

def clean_folder_name(name):
    """ลบอักขระพิเศษเพื่อให้ชื่อโฟลเดอร์ใน NAS ไม่พัง"""
    # อนุญาตภาษาไทย อังกฤษ ตัวเลข และช่องว่าง (ซึ่งจะเปลี่ยนเป็น _)
    clean_name = re.sub(r'[^\u0E00-\u0E7Fa-zA-Z0-9\s]', '', name)
    return clean_name.strip().replace(' ', '_')

def get_group_name(event):
    """ดึงชื่อกลุ่ม (ทำงานเฉพาะประเภท group เท่านั้น)"""
    if event.source.type == 'group':
        try:
            group_id = event.source.group_id
            group_summary = line_bot_api.get_group_summary(group_id)
            return clean_folder_name(group_summary.group_name)
        except:
            # กรณีดึงชื่อไม่ได้ ให้ใช้ Group ID แทน
            return event.source.group_id
    return None

def get_storage_info(event, group_folder):
    """กำหนดโครงสร้างโฟลเดอร์ย่อยใน NAS"""
    if isinstance(event.message, ImageMessage): # ไฟล์รูปภาพ
        sub_folder = "BackupImages"
        file_name = f"img_{event.message.id}.jpg"
    elif isinstance(event.message, VideoMessage): # ไฟล์วิดีโอ
        sub_folder = "BackupVideos"
        file_name = f"video_{event.message.id}.mp4"
    elif isinstance(event.message, FileMessage): # ไฟล์เอกสารและอื่นๆ
        file_name = event.message.file_name
        ext = os.path.splitext(file_name)[1].lower()
        
        if ext in ['.zip', '.rar', '.7z', '.tar', '.gz']: # ไฟล์ archive
            sub_folder = "BackupArchives"
        elif ext in ['.dwg', '.dxf', '.dwt']: # ไฟล์ออกแบบ CAD
            sub_folder = "BackupCAD"
        else: # ไฟล์เอกสารทั่วไป
            sub_folder = "BackupDocuments"
    else:
        sub_folder = "Others"
        file_name = f"file_{event.message.id}"
            
    return f"{group_folder}/{sub_folder}", file_name

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

# --- 4. Main Backup Handler (เฉพาะแชทกลุ่มเท่านั้น) ---

@handler.add(MessageEvent, message=(ImageMessage, VideoMessage, FileMessage))
def handle_content_backup(event):
    # ตรวจสอบว่าเป็นกลุ่มหรือไม่ (ถ้าไม่ใช่จะคืนค่า None)
    group_folder = get_group_name(event)
    
    if not group_folder:
        return

    try:
        rel_path, file_name = get_storage_info(event, group_folder)
        # โครงสร้าง URL สำหรับ WebDAV: NAS_URL/LineBackup/ชื่อกลุ่ม/ประเภทไฟล์/ไฟล์
        target_url = f"{NAS_URL}/LineBackup/{rel_path}/{file_name}"
        
        print(f"[GROUP] {group_folder} | Saving: {file_name}", flush=True)

        message_content = line_bot_api.get_message_content(event.message.id)
        
        # ส่งข้อมูลเข้า NAS ผ่าน WebDAV PUT
        response = requests.put(
            target_url,
            data=message_content.content,
            auth=HTTPBasicAuth(NAS_USER, NAS_PASS),
            timeout=120 
        )

        if response.status_code in [201, 204]:
            print(f"[SUCCESS] Saved to {rel_path}", flush=True)
        else:
            print(f"[ERROR] HTTP {response.status_code} - ตรวจสอบโฟลเดอร์ {rel_path} ใน NAS", flush=True)
            
    except Exception as e:
        print(f"[ERROR] {str(e)}", flush=True)

# --- 5. Status Command ---

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    if event.message.text == "/status":
        group_name = get_group_name(event)
        if group_name:
            msg = f"Group Backup: Active\nFolder: {group_name}"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)