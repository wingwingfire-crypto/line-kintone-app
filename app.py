from flask import Flask, request, send_from_directory
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

# ===== LINE設定 =====
LINE_TOKEN = "oX7OXZ7IrZen3CMFYM7oFN0r6N6x/+wmC/LhAC3sm/v7VZoe3eK0AmvJ9pj97+wxohqrnFdgY1IzItZ5i1vqxbKmMc4Uh51bRAZQ6XNziPb1TD2giBBURVAslvv6uxN6vUIpXogs9N4s+2Ex0ScmnwdB04t89/1O/w1cDnyilFU="
LINE_URL = "https://api.line.me/v2/bot/message/push"


# ===== LINE送信関数 =====
def send_line_message(user_id, text):
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
        "to": user_id,
        "messages": [
            {
                "type": "text",
                "text": text
            }
        ]
    }

    res = requests.post(LINE_URL, headers=headers, json=data)
    print("LINE送信結果:", res.text)


# ===== 動作確認 =====
@app.route("/", methods=["GET"])
def home():
    return "OK"


# ===== フォーム表示 =====
@app.route("/form", methods=["GET"])
def form():
    return send_from_directory(".", "form.html")


# ===== フォーム送信処理 =====
@app.route("/submit", methods=["POST"])
def submit():
    data = request.json

    try:
        print("受信データ:", data)

        name = data.get("name", "")
        phone = data.get("phone", "")
        maker = data.get("maker", "")
        model = data.get("model", "")
        issue = data.get("issue", "")

        # ✅ LINEユーザーID取得
        line_user_id = data.get("line_user_id", "")

        # ✅ Kintone登録
        record = {
            "app": 5,
            "record": {
                "customer_name": {"value": name},
                "phone": {"value": phone},
                "maker": {"value": maker},
                "model": {"value": model},
                "issue": {"value": issue},
                "lineid": {"value": line_user_id}  # ←あなたの成功パターン
            }
        }

        print("保存データ:", record)

        res = requests.post(
            KINTONE_URL,
            headers=HEADERS,
            json=record
        )

        print("Kintone結果:", res.text)

        # ✅ ✅ ✅ LINE通知（ここが今回のゴール）
        if line_user_id:
            send_line_message(
                line_user_id,
                "✅ 修理受付を受け付けました！担当よりご連絡します。"
            )

        return {"status": "ok"}

    except Exception as e:
        print("エラー:", e)
        return {"status": "error"}


# ===== テスト通知用 =====
@app.route("/notify_test", methods=["GET"])
def notify_test():
    user_id = "Ue90610c9001350129a502f1a7eda69da"

    send_line_message(user_id, "✅ テスト通知成功！")

    return "OK"


# ===== LINE Webhook（将来用）=====
@app.route("/callback", methods=["POST"])
def callback():
    return "OK"
