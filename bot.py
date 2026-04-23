import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, ImageMessage, FileMessage, TextSendMessage # เพิ่ม FileMessage
import os, datetime, base64, requests
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage, 
    VideoMessage, FileMessage, TextSendMessage
)

app = Flask(__name__)

# ดึงค่า Config จาก Railway
LINE_TOKEN = os.environ.get("LINE_TOKEN")
LINE_SECRET = os.environ.get("LINE_SECRET")
IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY")
# --- 1. ตั้งค่า LINE Credentials (แนะนำให้ใส่ใน Environment Variables) ---
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', 'YOUR_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', 'YOUR_SECRET')

line_bot_api = LineBotApi(LINE_TOKEN)
handler = WebhookHandler(LINE_SECRET)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

def upload_to_imgbb(image_data):
    """ฟังก์ชันอัปโหลดรูปภาพไปยัง ImgBB"""
    url = "https://api.imgbb.com/1/upload"
    base64_image = base64.b64encode(image_data)
    payload = {
        "key": IMGBB_API_KEY,
        "image": base64_image
    }
    try:
        response = requests.post(url, data=payload)
        result = response.json()
        if result["success"]:
            return result["data"]["url"]
# --- 2. ตั้งค่า Path สำหรับการจัดเก็บ (โครงสร้างตามที่ระบุ) ---
BASE_PATH = "/app/LineBackup"

def get_storage_info(event):
    """วิเคราะห์ Message และส่งคืน (ชื่อโฟลเดอร์ย่อย, ชื่อไฟล์)"""
    if isinstance(event.message, ImageMessage):
        return "BackupImages", f"img_{event.message.id}.jpg"
        
    elif isinstance(event.message, VideoMessage):
        return "BackupVideos", f"video_{event.message.id}.mp4"
        
    elif isinstance(event.message, FileMessage):
        file_name = event.message.file_name
        ext = os.path.splitext(file_name)[1].lower()
        
        # คัดแยก Archives กับ Documents
        archive_exts = ['.zip', '.rar', '.7z', '.tar', '.gz']
        if ext in archive_exts:
            return "BackupArchives", file_name
        else:
            print(f"ImgBB Error: {result['error']['message']}")
            return None
    except Exception as e:
        print(f"Connection Error: {e}")
        return None
            return "BackupDocments", file_name # สะกดตามความต้องการผู้ใช้
            
    return "Others", f"file_{event.message.id}"

@app.route("/callback", methods=["POST"])
# --- 3. Webhook Endpoint ---
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers["X-Line-Signature"]
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except Exception as e:
        print(f"Error: {e}")
    except InvalidSignatureError:
        abort(400)
    return "OK"
    return 'OK'

# --- ส่วนเดิมสำหรับรูปภาพ ---
@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    message_id = event.message.id
    content = line_bot_api.get_message_content(message_id)
    image_data = b"".join(content.iter_content())
    image_url = upload_to_imgbb(image_data)
    if image_url:
        print(f"บันทึกรูปสำเร็จ: {image_url}")
# --- 4. Handler สำหรับการ Backup ข้อมูล ---
@handler.add(MessageEvent, message=(ImageMessage, VideoMessage, FileMessage))
def handle_content_backup(event):
    try:
        # กำหนดโฟลเดอร์และชื่อไฟล์
        sub_folder, file_name = get_storage_info(event)
        target_dir = os.path.join(BASE_PATH, sub_folder)
        
        # สร้างโฟลเดอร์ถ้ายังไม่มี
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
            
        # ดึงเนื้อหาไฟล์จาก LINE Server
        message_content = line_bot_api.get_message_content(event.message.id)
        full_path = os.path.join(target_dir, file_name)
        
        # บันทึกไฟล์ (Binary Mode)
        with open(full_path, 'wb') as fd:
            for chunk in message_content.iter_content():
                fd.write(chunk)
                
        print(f">>> [SUCCESS] Saved: {full_path}")
        
        # ตอบกลับยืนยัน (สามารถเอาออกได้ถ้าไม่ต้องการให้บอทตอบ)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"สำรองข้อมูลเรียบร้อย!\n📂 หมวดหมู่: {sub_folder}\n📄 ชื่อไฟล์: {file_name}")
        )
        
    except Exception as e:
        print(f">>> [ERROR] {str(e)}")
        # ในกรณีใช้งานจริงอาจเลือกไม่ตอบกลับเมื่อ Error เพื่อความเงียบ

# --- ส่วนใหม่สำหรับไฟล์เอกสาร (PDF, Word, Excel, PPT) ---
@handler.add(MessageEvent, message=FileMessage)
def handle_file(event):
    message_id = event.message.id
    file_name = event.message.file_name # ชื่อไฟล์ต้นฉบับ
    
    # ดึงข้อมูลไฟล์จาก LINE
    content = line_bot_api.get_message_content(message_id)
    
    # หมายเหตุ: ImgBB ไม่สามารถเก็บไฟล์เอกสารได้ (เก็บได้เฉพาะรูปภาพ)
    # หากต้องการเก็บเอกสาร แนะนำให้บันทึกลงเครื่อง Server ชั่วคราว หรือใช้บริการอื่น
    
    # ตัวอย่างการบันทึกลงเครื่อง Server (Railway) ในโฟลเดอร์ downloads
    save_path = f"./downloads/{file_name}"
    os.makedirs("./downloads", exist_ok=True)
    
    with open(save_path, "wb") as f:
        for chunk in content.iter_content():
            f.write(chunk)
    
    print(f"บันทึกไฟล์เอกสารสำเร็จ: {save_path}")
# --- 5. คำสั่งพิเศษสำหรับเช็คไฟล์ผ่าน LINE (ทางเลือก) ---
@handler.add(MessageEvent, message=TextMessage)
def handle_text_command(event):
    user_text = event.message.text
    if user_text == "/status":
        status_msg = "สถานะการสำรองข้อมูล:\n"
        folders = ["BackupImages", "BackupVideos", "BackupArchives", "BackupDocments"]
        for f in folders:
            path = os.path.join(BASE_PATH, f)
            count = len(os.listdir(path)) if os.path.exists(path) else 0
            status_msg += f"- {f}: {count} ไฟล์\n"
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=status_msg)
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    # รันบนพอร์ตที่ Railway กำหนด
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)