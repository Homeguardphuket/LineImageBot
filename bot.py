from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, ImageMessage, TextSendMessage
import os, datetime, base64, requests

app = Flask(__name__)

# ดึงค่า Config ต่างๆ จาก Environment Variables ใน Railway
LINE_TOKEN = os.environ.get("LINE_TOKEN")
LINE_SECRET = os.environ.get("LINE_SECRET")
IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY")

line_bot_api = LineBotApi(LINE_TOKEN)
handler = WebhookHandler(LINE_SECRET)

def upload_to_imgbb(image_data):
    """ฟังก์ชันอัปโหลดรูปภาพไปยัง ImgBB API"""
    url = "https://api.imgbb.com/1/upload"
    
    # แปลง Binary Data ของรูปภาพเป็น Base64
    base64_image = base64.b64encode(image_data)
    
    payload = {
        "key": IMGBB_API_KEY,
        "image": base64_image
    }
    
    try:
        response = requests.post(url, data=payload)
        result = response.json()
        
        if result["success"]:
            # คืนค่า URL ของรูปภาพที่อัปโหลดสำเร็จ
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

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    message_id = event.message.id
    
    # 1. ดึงข้อมูลรูปภาพจาก LINE
    content = line_bot_api.get_message_content(message_id)
    image_data = b"".join(content.iter_content())
    
    # 2. อัปโหลดไปยัง ImgBB
    image_url = upload_to_imgbb(image_data)
    
    # 3. จัดการเรื่องการแจ้งเตือน
    if image_url:
        # พิมพ์ลง Log ของ Railway แทนการส่งข้อความเข้าไลน์
        print(f"บันทึกรูปสำเร็จ: {image_url}")
    else:
        print("เกิดข้อผิดพลาดในการอัปโหลดไป ImgBB")

    # --- ลบหรือคอมเมนต์ส่วนด้านล่างนี้ออก เพื่อไม่ให้บอทตอบกลับในไลน์ ---
    # line_bot_api.reply_message(
    #     event.reply_token,
    #     TextSendMessage(text=f"บันทึกเรียบร้อย: {image_url}")
    # )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)