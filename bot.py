from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, ImageMessage
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account
import os, datetime, io, json

app = Flask(__name__)

LINE_TOKEN = os.environ.get("LINE_TOKEN")
LINE_SECRET = os.environ.get("LINE_SECRET")
FOLDER_ID = os.environ.get("FOLDER_ID")
GOOGLE_CREDS = os.environ.get("GOOGLE_CREDS")

line_bot_api = LineBotApi(LINE_TOKEN)
handler = WebhookHandler(LINE_SECRET)

# เชื่อมต่อ Google Drive
def get_drive_service():
    creds_dict = json.loads(GOOGLE_CREDS)
    creds = service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)

def upload_to_drive(image_data, filename):
    service = get_drive_service()
    media = MediaIoBaseUpload(
        io.BytesIO(image_data),
        mimetype="image/jpeg"
    )
    file_metadata = {
        "name": filename,
        "parents": [FOLDER_ID]
    }
    service.files().create(
        body=file_metadata,
        media_body=media,
        supportsAllDrives=True  # ⬅️ เพิ่มบรรทัดนี้
    ).execute()
    print(f"อัปโหลดไป Drive แล้ว: {filename}")

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
    content = line_bot_api.get_message_content(message_id)
    image_data = b"".join(content.iter_content())
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{message_id}.jpg"
    upload_to_drive(image_data, filename)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)