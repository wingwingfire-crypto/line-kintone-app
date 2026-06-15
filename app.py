from flask import Flask, request
import requests
import os

app = Flask(__name__)

# ===== Kintone設定 =====
KINTONE_URL = "https://2zx7vnpprtja.cybozu.com/k/v1/record.json"
API_TOKEN = os.environ.get("KINTONE_API_TOKEN")

HEADERS = {
    "X-Cybozu-API-Token": API_TOKEN,
    "Content-Type": "application/json"
}

# ===== 動作確認用 =====
@app.route("/", methods=["GET"])
def home():
    return "OK"


# ===== LINE Webhook受信 =====
@app.route("/callback", methods=["POST"])
def callback():
    data = request.json

    # ✅ 先に即レスポンス（超重要：タイムアウト防止）
    response = "OK"

    try:
        events = data.get("events", [])

        for event in events:
            if event["type"] == "message":

                # ユーザーID
                user_id = event["source"]["userId"]

                # テキスト
                text = event["message"].get("text", "")

                print("受信:", text)

                # ✅ Kintone登録
                record = {
                    "app": 5,
                    "record": {
                        "customer_name": {"value": text},
                        "line_user_id": {"value": user_id}
                    }
                }

                res = requests.post(
                    KINTONE_URL,
                    headers=HEADERS,
                    json=record,
                    timeout=5  # ← 念のため
                )

                print("Kintone:", res.text)

    except Exception as e:
        print("エラー:", e)

    return response
