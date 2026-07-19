from flask import Flask, request, send_from_directory
import requests
import os
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

# ===== Kintone設定 =====
KINTONE_BASE = "https://2r2oficviuff.cybozu.com"
KINTONE_RECORD_URL = KINTONE_BASE + "/k/v1/record.json"
KINTONE_GET_URL = KINTONE_BASE + "/k/v1/records.json"
KINTONE_API_TOKEN = os.environ.get("KINTONE_API_TOKEN")

# ===== LINE設定 =====
LINE_TOKEN = "oX7OXZ7IrZen3CMFYM7oFN0r6N6x/+wmC/LhAC3sm/v7VZoe3eK0AmvJ9pj97+wxohqrnFdgY1IzItZ5i1vqxbKmMc4Uh51bRAZQ6XNziPb1TD2giBBURVAslvv6uxN6vUIpXogs9N4s+2Ex0ScmnwdB04t89/1O/w1cDnyilFU="
LINE_URL = "https://api.line.me/v2/bot/message/push"

# ===== 日本時間 =====
JST = timezone(timedelta(hours=9))


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
@.route("/submit", methods=["POST"])
def submit():
    data = request.json

    try:
        name = data.get("name", "")
        phone = data.get("phone", "")
        maker = data.get("maker", "")
        model = data.get("model", "")
        issue = data.get("issue", "")
        line_user_id = data.get("line_user_id", "")

        notify_url = f"https://line-kintone-.onrender.com/notify?user={line_user_id}"

        record = {
            "app": 6,
            "record": {
                "customer_name": {"value": name},
                "phone": {"value": phone},
                "maker": {"value": maker},
                "model": {"value": model},
                "issue": {"value": issue},
                "lineid": {"value": line_user_id},
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


# ===== 通知 =====
@app.route("/notify", methods=["GET"])
def notify():
    user_id = request.args.get("user")

    print("受信user:", user_id)

    try:
        # ===== レコード取得 =====
        url = f'{KINTONE_GET_URL}?app=5&query=lineid="{user_id}" order by $id desc limit 1'

        headers = {
            "X-Cybozu-API-Token": KINTONE_API_TOKEN
        }

        res = requests.get(url, headers=headers)
        result = res.json()

        if "records" not in result or len(result["records"]) == 0:
            return "レコードなし"

        record = result["records"][0]

        # ===== 基本情報 =====
        record_id = record["$id"]["value"]
        name = record["customer_name"]["value"]

        # ✅ ステータス取得（ズレ防止）
        status_jp = record["ドロップダウン"]["value"].strip()
        print("取得ステータス:", status_jp)

        # ===== マップ（Kintoneと完全一致させる）=====
        status_map = {
            "⚪修理受付中": "received",
            "📩集荷依頼済": "pickup_requested",
            "🚚荷受待(店舗持込待ち)": "waiting_arrival",
            "🟡見積中": "estimating",
            "📄見積提出済": "quoted",
            "📦受注(部品待ち)": "waiting_parts",
            "🔴中止(返却)": "cancel_return",
            "❌中止(処分)": "cancel_disposal"
        }

        statuscode = status_map.get(status_jp, "unknown")
        print("変換後:", statuscode)

        # ===== メッセージ =====
        if statuscode == "received":
            message = f"""{name}様

【修理受付中】

順次対応しております。
今しばらくお待ちください。
"""

        elif statuscode == "pickup_requested":
            message = f"""{name}様

【集荷依頼済】

集荷手配が完了しております。
到着までお待ちください。
"""

        elif statuscode == "waiting_arrival":
            message = f"""{name}様

【荷受待】

端末の到着をお待ちしております。
"""

        elif statuscode == "estimating":
            message = f"""{name}様

【見積中】

現在お見積りを作成しております。
もうしばらくお待ちください。
"""

        elif statuscode == "quoted":
            message = f"""{name}様

【見積提示済】

お見積りが完了しております。
内容をご確認ください。
"""

        elif statuscode == "waiting_parts":
            message = f"""{name}様

【部品待ち】

部品の手配を行っております。
入荷までお待ちください。
"""

        elif statuscode == "cancel_return":
            message = f"""{name}様

【修理中止（返却）】

修理不可のため返却となります。
詳細は別途ご案内いたします。
"""

        elif statuscode == "cancel_disposal":
            message = f"""{name}様

【修理中止（処分）】

修理不可のため処分対応となります。
何卒ご了承ください。
"""

        else:
            # 👇 デバッグしやすくする
            message = f"""{name}様

ステータス不一致：
{status_jp}
"""

        # ===== LINE送信 =====
        send_line_message(user_id, message)

        # ===== 日本時間 =====
        now_time = datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S%z")

        # ===== Kintone更新 =====
        update_url = KINTONE_BASE + "/k/v1/record.json"

        update_data = {
            "app": 6,
            "id": record_id,
            "record": {
                "lastnotify": {"value": now_time},
                "notifymessage": {"value": message}
            }
        }

        update_headers = {
            "X-Cybozu-API-Token": KINTONE_API_TOKEN,
            "Content-Type": "application/json"
        }

        res = requests.put(update_url, headers=update_headers, json=update_data)
        print("履歴更新:", res.text)

        return f"送信完了: {status_jp}"

    except Exception as e:
        print("通知エラー:", e)
        return "通知処理エラー"
