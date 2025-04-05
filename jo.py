import re
import os
import mysql.connector
from flask import Flask, request
from dotenv import load_dotenv
from datetime import datetime

from linebot.v3.webhook import WebhookHandler
from linebot.v3.messaging import MessagingApi, Configuration, ApiClient
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging.models import TextMessage as MessagingTextMessage
from linebot.v3.messaging.models import ReplyMessageRequest

# 載入環境變數
load_dotenv("pw.env")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE")

# 初始化 LINE SDK
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)
app = Flask(__name__)

# MySQL 資料庫連線
def get_db_connection():
    return mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE
    )

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INT AUTO_INCREMENT PRIMARY KEY,
            category VARCHAR(255),
            amount INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    print("✅ 資料表檢查 / 建立完成")

def save_to_db(category, amount):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO expenses (category, amount, created_at) VALUES (%s, %s, NOW())",
        (category, amount)
    )
    conn.commit()
    conn.close()

def load_from_db(today_only=False):
    conn = get_db_connection()
    cursor = conn.cursor()
    if today_only:
        cursor.execute("""
            SELECT category, amount, created_at
            FROM expenses
            WHERE DATE(created_at) = CURDATE()
        """)
    else:
        cursor.execute("SELECT category, amount, created_at FROM expenses")
    rows = cursor.fetchall()
    conn.close()
    return [{"category": r[0], "amount": r[1], "created_at": r[2]} for r in rows]

# 使用者確認狀態
confirmation_state = {}

@app.route("/ping", methods=["GET"])
def ping():
    return "OK", 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    print("[Webhook] 收到請求")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("❌ LINE 驗證失敗")
        return "Invalid signature", 400

    return "OK", 200

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_msg = event.message.text
    user_id = event.source.user_id

    print(f"✅ 收到訊息：{user_msg}（來自：{user_id}）")

    try:
        if user_id in confirmation_state:
            reply_msg = handle_confirmation(user_id, user_msg)
        else:
            reply_msg = handle_normal_message(user_msg, user_id)

        if not reply_msg:
            reply_msg = "⚠️ 發生未知錯誤，請稍後再試。"

    except Exception as e:
        print(f"❌ 發生錯誤：{e}")
        reply_msg = "⚠️ 系統錯誤，請稍後再試。"

    print(f"➡️ 將要回傳的訊息是：{reply_msg}")

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        # ✅ 正確方式建立回應
        text_msg = MessagingTextMessage(text=reply_msg)
        reply_req = ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[text_msg]
        )
        line_bot_api.reply_message(reply_message_request=reply_req)

def handle_confirmation(user_id, user_msg):
    if user_msg == "是":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM expenses")
        conn.commit()
        conn.close()
        reply = "✅ 所有記錄已清除。"
    else:
        reply = "取消清除紀錄。"
    del confirmation_state[user_id]
    return reply

def handle_normal_message(user_msg, user_id):
    if user_msg == "查看紀錄":
        return view_records()
    elif user_msg == "今日記錄":
        return view_records(today_only=True)
    elif user_msg == "清除紀錄":
        confirmation_state[user_id] = True
        return "❓ 確定要清除所有記錄嗎？請輸入「是」來確認。"
    else:
        return save_expense(user_msg)

def view_records(today_only=False):
    expenses = load_from_db(today_only=today_only)
    if not expenses:
        return "📭 沒有記錄。"
    return "\n".join([
        f"📌 類別：{x['category']}，金額：{x['amount']}，時間：{x['created_at'].strftime('%H:%M')}"
        for x in expenses
    ])

def save_expense(msg):
    print(f"[save_expense] 處理：{msg}")
    match = re.match(r"(\S+)\s+(\d+)", msg)
    if not match:
        return "⚠️ 格式錯誤，請輸入：分類 金額，例如 早餐 60"
    category, amount = match.group(1), int(match.group(2))
    save_to_db(category, amount)
    return f"✅ 已記錄：\n類別：{category}\n金額：{amount}"

if __name__ == "__main__":
    init_db()  # 啟動時自動建立資料表
    app.run(host="0.0.0.0", port=5000, debug=True)
