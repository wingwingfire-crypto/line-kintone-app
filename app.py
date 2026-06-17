from flask import Flask, request, send_from_directory
import requests
import os

app = Flask(__name__)

# ===== Kintone設定 =====
KINTONE_BASE = "https://2zx7vnpprtja.cybozu.com"
KINTONE_RECORD_URL = KINTONE_BASE + "/k/v1/record.json"
KINTONE_GET_URL = KINTONE_BASE + "/k/v1/records.json"
KINTONE_API_TOKEN = os.environ.get("KINTONE_API_TOKEN")

HEADERS = {
    "X-Cybozu-API-Token": KINTONE_API_TOKEN,
    "Content-Type": "application/json"
}

# ===== LINE設定 =====
LINE_TOKEN = "oX7OXZ7IrZen3CMFYM7oFN0r6N6x/+wmC/LhAC3sm/v7VZoe3eK0AmvJ9pj97+wxohqrnFdgY1IzItZ5i1vqxbKmMc4Uh51bRAZQ6XNziPb1TD2giBBURVAslvv6uxN6vUIpXogs9N4s+2Ex0ScmnwdB04t89/1O/w1cDnyilFU="
LINE_URL = "https://api.line.me/v2/bot/message/push"


# ===== LINE送信 =====
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

    requests.post(LINE_URL, headers=headers, json=data)


# ===== フォーム表示 =====
@app.route("/form", methods=["GET"])
def form():
    return send_from_directory(".", "form.html")


# ===== 登録処理 =====
@app.route("/submit", methods=["POST"])
def submit():
    data = request.json

    try:
        name = data.get("name", "")
        phone = data.get("phone", "")
        maker = data.get("maker", "")
        model = data.get("model", "")
        issue = data.get("issue", "")
        line_user_id = data.get("line_user_id", "")

        # ✅ 通知リンク生成（重要）
        notify_url = f"https://line-kintone-app.onrender.com/notify?user={line_user_id}"

        record = {
            "app": 5,
            "record": {
                "customer_name": {"value": name},
                "phone": {"value": phone},
                "maker": {"value": maker},
                "model": {"value": model},
                "issue": {"value": issue},
                "lineid": {"value": line_user_id},
                "statuscode": {"value": "received"},
                "notifyurl": {"value": notify_url}
            }
        }

        # ✅ Kintoneへ登録
        res = requests.post(
            KINTONE_RECORD_URL,
            headers=HEADERS,
            json=record
        )

        print("Kintone登録:", res.text)

        # ✅ LINE受付通知
        if line_user_id:
            send_line_message(line_user_id, "📩 修理受付を受け付けました。")

        return {"status": "ok"}

    except Exception as e:
        print("エラー:", e)
        return {"status": "error"}


# ===== ✅ 通知処理（核心）=====
@app.route("/notify", methods=["GET"])
def notify():
    user_id = request.args.get("user")

    print("受信user:", user_id)

    # ✅ Kintoneから最新レコード取得
    query = f'lineid="{user_id}" order by record_id desc limit 1'

    params = {
        "app": 5,
        "query": query
    }

    res = requests.get(KINTONE_GET_URL, headers=HEADERS, params=params)
    result = res.json()

    print("取得結果:", result)

    if len(result.get("records", [])) == 0:
        return "レコードなし"

    record = result["records"][0]
    statuscode = record["statuscode"]["value"]

    print("statuscode:", statuscode)

    # ✅ 状態別メッセージ
    if statuscode == "received":
        message = "📩 修理受付を受け付けました。"

    elif statuscode == "pickup_requested":
        message = "🚚 集荷を依頼しました。"

    elif statuscode == "waiting_arrival":
        message = "📦 端末の到着をお待ちしています。"

    elif statuscode == "repairing":
        message = "🔧 修理作業を進めています。"

    elif statuscode == "estimating":
        message = "🟡 見積を作成中です。"

    elif statuscode == "quoted":
        message = "📄 見積をご確認ください。"

    elif statuscode == "waiting_parts":
        message = "📦 部品を手配中です。"

    elif statuscode == "completed":
        message = "✅ 修理が完了しました！ご来店お待ちしております。"

    elif statuscode == "cancel_return":
        message = "🔴 修理は中止となり返却対応となります。"

    elif statuscode == "cancel_disposal":
        message = "❌ 修理は中止となり処分対応となります。"

    else:
        message = "📢 状況が更新されました。"

    # ✅ LINE送信
    if user_id:
        send_line_message(user_id, message)

    return "通知送信OK"
