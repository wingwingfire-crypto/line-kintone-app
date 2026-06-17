from flask import Flask, request, send_from_directory
import requests

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
            {"type": "text", "text": text}
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

        # 入力データ
        name = data.get("name", "")
        phone = data.get("phone", "")
        maker = data.get("maker", "")
        model = data.get("model", "")
        issue = data.get("issue", "")

        # LINEユーザーID
        line_user_id = data.get("line_user_id", "")

        # ✅ 初期ステータス
        status_code = "received"

        # ✅ 通知用URL（ここがポイント）
        notify_url = f"https://line-kintone-app.onrender.com/notify?user={line_user_id}&statuscode={status_code}"

        # Kintone登録
        record = {
            "app": 5,
            "record": {
                "customer_name": {"value": name},
                "phone": {"value": phone},
                "maker": {"value": maker},
                "model": {"value": model},
                "issue": {"value": issue},
                "lineid": {"value": line_user_id},
                "notifyurl": {"value": notify_url},
                "statuscode": {"value": status_code}
            }
        }

        print("保存データ:", record)

        res = requests.post(KINTONE_URL, headers=HEADERS, json=record)
        print("Kintone結果:", res.text)

        # ✅ 受付通知（自動）
        if line_user_id:
            send_line_message(
                line_user_id,
                "✅ 修理受付を受け付けました！"
            )

        return {"status": "ok"}

    except Exception as e:
        print("エラー:", e)
        return {"status": "error"}


# ===== ✅ 通知処理（ステータス連動）=====
@app.route("/notify", methods=["GET"])
def notify():
    user_id = request.args.get("user")
    statuscode = request.args.get("statuscode")

    print("受信ステータス:", statuscode)

    # ✅ ステータスごとのメッセージ
    if statuscode == "received":
        message = "📩 修理受付を受け付けました。"

    elif statuscode == "pickup_requested":
        message = "🚚 集荷を依頼しました。到着までお待ちください。"

    elif statuscode == "waiting_arrival":
        message = "📦 端末の到着をお待ちしています。"

    elif statuscode == "repairing":
        message = "🔧 修理作業を進めています。"

    elif statuscode == "estimating":
        message = "🟡 見積を作成中です。しばらくお待ちください。"

    elif statuscode == "quoted":
        message = "📄 見積をご確認ください。ご承認お待ちしています。"

    elif statuscode == "waiting_parts":
        message = "📦 部品を手配中です。到着までお待ちください。"

    elif statuscode == "completed":
        message = "✅ 修理が完了しました！ご来店お待ちしております。"

    elif statuscode == "cancel_return":
        message = "🔴 修理は中止となり、返却対応となります。"

    elif statuscode == "cancel_disposal":
        message = "❌ 修理は中止となり、処分対応となります。"

    else:
        message = "📢 状況が更新されました。"

    # LINE送信
    if user_id:
        send_line_message(user_id, message)

    return "通知送信OK"


# ===== Webhook（未使用）=====
@app.route("/callback", methods=["POST"])
def callback():
    return "OK"

