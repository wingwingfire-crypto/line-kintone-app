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

        # ✅ Kintone登録
        record = {
            "app": 5,
            "record": {
                "customer_name": {"value": name},
                "phone": {"value": phone},
                "maker": {"value": maker},
                "model": {"value": model},
                "issue": {"value": issue}
            }
        }

        res = requests.post(KINTONE_URL, headers=HEADERS, json=record)

        print("Kintone結果:", res.text)

        return {"status": "ok"}

    except Exception as e:
        print("エラー:", e)
        return {"status": "error"}

    
# ===== LINE Webhook（将来用）=====
@app.route("/callback", methods=["POST"])
def callback():
    return "OK"
