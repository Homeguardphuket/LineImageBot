from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, ImageMessage, FileMessage, TextSendMessage # เพิ่ม FileMessage
import os, datetime, base64, requests

app = Flask(__name__)

# ดึงค่า Config จาก Railway
LINE_TOKEN = os.environ.get("LINE_TOKEN")
LINE_SECRET = os.environ.get("LINE_SECRET")
IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY")

line_bot_api = LineBotApi(LINE_TOKEN)
handler = WebhookHandler(LINE_SECRET)

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
        else:
            print(f"ImgBB Error: {result['error']['message']}")
            return None
    except Exception as e:
        print(f"Connection Error: {e}")
        return None

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except Exception as e:
        print(f"Error: {e}")
        abort(400)
    return "OK"

# --- ส่วนเดิมสำหรับรูปภาพ ---
@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    message_id = event.message.id
    content = line_bot_api.get_message_content(message_id)
    image_data = b"".join(content.iter_content())
    image_url = upload_to_imgbb(image_data)
    if image_url:
        print(f"บันทึกรูปสำเร็จ: {image_url}")

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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)