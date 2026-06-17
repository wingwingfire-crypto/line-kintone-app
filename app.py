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

    res = requests.post(LINE_URL, headers=headers, json=data)
    print("LINE送信:", res.text)


# ===== フォーム =====
@app.route("/form", methods=["GET"])
def form():
    return send_from_directory(".", "form.html")


# ===== 登録 =====
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

        # ✅ 通知URL生成
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

        res = requests.post(
            KINTONE_RECORD_URL,
            headers=HEADERS,
            json=record
        )

        print("Kintone登録:", res.text)

        if line_user_id:
            send_line_message(line_user_id, "📩 修理受付を受け付けました。")

        return {"status": "ok"}

    except Exception as e:
        print("登録エラー:", e)
        return {"status": "error"}


# ===== ✅ 通知（完全修正版）=====
@app.route("/notify", methods=["GET"])
def notify():
    user_id = request.args.get("user")

    print("受信user:", user_id)

    try:
        # ✅ 正しいクエリ（重要）
        query = f'lineid = "{user_id}" order by $id desc limit 1'

        params = {
            "app": 5,
            "query": query
        }

        # ✅ GETで取得（最重要）
        res = requests.get(KINTONE_GET_URL, headers=HEADERS, params=params)
        result = res.json()

        print("取得結果:", result)

        # ✅ エラー表示（これで原因見える）
        if "records" not in result:
            return f"APIエラー: {result}"

        if len(result["records"]) == 0:
            return "レコードなし（検索ヒット0件）"

        record = result["records"][0]
        statuscode = record["statuscode"]["value"]

        print("取得statuscode:", statuscode)

        # ===== メッセージ分岐 =====
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

        if user_id:
            send_line_message(user_id, message)

        return f"送信完了: {statuscode}"

    except Exception as e:
        print("通知エラー:", e)
        return "通知処理エラー"
