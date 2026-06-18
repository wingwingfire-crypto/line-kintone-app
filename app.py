from flask import Flask, request, send_from_directory
import requests
import os

app = Flask(__name__)

# ===== Kintone設定 =====
KINTONE_BASE = "https://2zx7vnpprtja.cybozu.com"
KINTONE_RECORD_URL = KINTONE_BASE + "/k/v1/record.json"
KINTONE_GET_URL = KINTONE_BASE + "/k/v1/records.json"
KINTONE_API_TOKEN = os.environ.get("KINTONE_API_TOKEN")

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
                "進捗状況": {"value": "修理受付中"},
                "notifyurl": {"value": notify_url}
            }
        }

        headers = {
            "X-Cybozu-API-Token": KINTONE_API_TOKEN,
            "Content-Type": "application/json"
        }

        res = requests.post(KINTONE_RECORD_URL, headers=headers, json=record)
        print("Kintone登録:", res.text)

        send_line_message(line_user_id, "📩 修理受付を受け付けました。")

        return {"status": "ok"}

    except Exception as e:
        print("登録エラー:", e)
        return {"status": "error"}


# ===== ✅ 通知（日本語→英語変換版）=====
@app.route("/notify", methods=["GET"])
def notify():
    user_id = request.args.get("user")

    print("受信user:", user_id)

    try:
        # ✅ Kintoneからレコード取得
        url = f'{KINTONE_GET_URL}?app=5&query=lineid="{user_id}" limit 1'

        headers = {
            "X-Cybozu-API-Token": KINTONE_API_TOKEN
        }

        res = requests.get(url, headers=headers)
        result = res.json()

        print("取得結果:", result)

        if "records" not in result:
            return f"APIエラー: {result}"

        if len(result["records"]) == 0:
            return "レコードなし"

        record = result["records"][0]

        # ✅ 日本語ステータス取得
        status_jp = record["進捗状況"]["value"]

        # ✅ 日本語 → 英語変換（あなたの画面に完全合わせ）
        status_map = {
            "修理受付中": "received",
            "集荷依頼済": "pickup_requested",
            "荷受待（店舗持込待ち）": "waiting_arrival",
            "見積中": "estimating",
            "見積提示済": "quoted",
            "受注（部品待ち）": "waiting_parts",
            "中止（返却）": "cancel_return",
            "中止（処分）": "cancel_disposal"
        }

        statuscode = status_map.get(status_jp, "received")

        print("変換後statuscode:", statuscode)

        # ===== LINEメッセージ =====
        if statuscode == "received":
            message = "📩 修理受付を受け付けました。"

        elif statuscode == "pickup_requested":
            message = "🚚 集荷を依頼しました。"

        elif statuscode == "waiting_arrival":
            message = "📦 端末の到着をお待ちしています。"

        elif statuscode == "estimating":
            message = "🟡 見積を作成中です。"

        elif statuscode == "quoted":
            message = "📄 見積をご確認ください。"

        elif statuscode == "waiting_parts":
            message = "📦 部品を手配中です。"

        elif statuscode == "repairing":
            message = "🔧 修理中です。"

        elif statuscode == "completed":
            message = "✅ 修理が完了しました！"

        elif statuscode == "cancel_return":
            message = "🔴 修理は中止となり返却となります。"

        elif statuscode == "cancel_disposal":
            message = "❌ 修理は中止となり処分となります。"

        else:
            message = "📢 状況が更新されました。"

        send_line_message(user_id, message)

        return f"送信完了: {status_jp}"

    except Exception as e:
        print("通知エラー:", e)
        return "通知処理エラー"
