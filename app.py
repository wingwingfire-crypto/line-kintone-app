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

# ===== Kintoneアプリ番号 =====
KINTONE_APP_ID = 6

# ===== LINE設定 =====
LINE_TOKEN = os.environ.get("LINE_TOKEN")
LINE_URL = "https://api.line.me/v2/bot/message/push"
LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"

# ===== 日本時間 =====
JST = timezone(timedelta(hours=9))


# ===== 共通：Kintone値取得 =====
def get_value(record, field_code, default=""):
    try:
        value = record.get(field_code, {}).get("value", default)
        if value is None:
            return default
        return value
    except Exception:
        return default


# ===== 共通：金額表示 =====
def format_price(value):
    if value is None or value == "":
        return "未入力"

    try:
        return f"{int(float(value)):,}円"
    except Exception:
        return str(value) + "円"


# ===== 共通：日付表示 =====
def format_date(value):
    if value is None or value == "":
        return "未入力"
    return value


# ===== LINE送信 =====
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
    print("LINE送信:", res.text)

# ===== LINE返信 =====
def reply_line_message(reply_token, text):
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
        "replyToken": reply_token,
        "messages": [
            {
                "type": "text",
                "text": text
            }
        ]
    }

    res = requests.post(LINE_REPLY_URL, headers=headers, json=data)
    print("LINE返信:", res.text)

# ===== フォーム表示 =====
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
            "app": KINTONE_APP_ID,
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

        res = requests.post(
            KINTONE_RECORD_URL,
            headers=headers,
            json=record
        )

        print("Kintone登録:", res.text)

        if line_user_id:
            send_line_message(
                line_user_id,
                "📩 修理受付を受け付けました。"
            )

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
        # ===== 最新レコード取得 =====
        headers = {
            "X-Cybozu-API-Token": KINTONE_API_TOKEN
        }

        query = f'lineid = "{user_id}" order by $id desc limit 1'

        params = {
            "app": KINTONE_APP_ID,
            "query": query
        }

        res = requests.get(
            KINTONE_GET_URL,
            headers=headers,
            params=params
        )

        print("Kintone取得ステータス:", res.status_code)
        print("Kintone取得本文:", res.text)

        try:
            result = res.json()
        except Exception as e:
            print("JSON変換エラー:", e)
            return f"Kintone取得エラー: {res.status_code}"

        if "records" not in result or len(result["records"]) == 0:
            return "レコードなし"

        record = result["records"][0]

        # ===== 基本情報 =====
        record_id = record["$id"]["value"]

        name = get_value(record, "customer_name", "")
        maker = get_value(record, "maker", "")
        model = get_value(record, "model", "")
        serial = get_value(record, "serial", "")
        issue = get_value(record, "issue", "")

        # ===== 見積・修理情報 =====
        mitsumorikingaku = get_value(record, "mitsumorikingaku", "")
        mitsumorinaiyo = get_value(record, "mitsumorinaiyo", "")
        kanryoyoteibi = get_value(record, "kanryoyoteibi", "")

        price_text = format_price(mitsumorikingaku)
        date_text = format_date(kanryoyoteibi)

        # ===== 発送情報 =====
        okurijobango = get_value(record, "okurijobango", "")

        # ===== 進捗状況取得 =====
        status_jp = get_value(record, "ドロップダウン", "").strip()
        print("取得ステータス:", status_jp)

        # ===== 進捗状況マップ =====
        status_map = {
            "⚪修理受付中": "received",
            "📩集荷依頼済": "pickup_requested",
            "🚚荷受待(店舗持込待ち)": "waiting_arrival",
            "🟡見積中": "estimating",
            "📄見積提出済": "quoted",
            "📦受注(部品待ち)": "waiting_parts",
            "✅修理完了連絡済": "repair_completed",
            "🚚発送完了": "shipped",
            "🔴中止(返却)": "cancel_return",
            "❌中止(処分)": "cancel_disposal"
        }

        statuscode = status_map.get(status_jp, "unknown")
        print("変換後:", statuscode)

        # ===== メッセージ作成 =====
        if statuscode == "received":
            message = f"""{name}様

【修理受付中】

この度は修理のご依頼ありがとうございます。

順次対応しております。
今しばらくお待ちください。
"""

        elif statuscode == "pickup_requested":
            message = f"""{name}様

【集荷依頼済】

集荷手配が完了しております。
出荷の準備をしてお待ちください。
"""

        elif statuscode == "waiting_arrival":
            message = f"""{name}様

【荷受待】

修理品の到着をお待ちしております。
到着次第、確認を進めさせていただきます。
"""

        elif statuscode == "estimating":
            message = f"""{name}様

【見積中】

現在お預かり品の状態を確認し、
お見積りを作成しております。

もうしばらくお待ちください。
"""

        elif statuscode == "quoted":
            message = f"""{name}様

【見積提出済】

お預かりしている修理品のお見積りが完了しました。

■ 修理品情報
メーカー：{maker}
型番：{model}
機番：{serial}

■ 故障内容
{issue}

■ お見積り金額
{price_text}

■ お見積り内容
{mitsumorinaiyo if mitsumorinaiyo else "未入力"}

■ 修理完了予定日
{date_text}

内容をご確認ください。
修理を進めるか、キャンセルされるかにつきましては、担当者までご連絡ください。
"""

        elif statuscode == "waiting_parts":
            message = f"""{name}様

【受注・部品待ち】

修理のご依頼を承りました。

現在、必要部品を手配しております。
部品入荷後、修理作業を進めさせていただきます。

■ 修理完了予定日
{date_text}
"""

        elif statuscode == "repair_completed":
            message = f"""{name}様

【修理完了】

お預かりしておりました修理品の修理が完了しました。

■ 修理品情報
メーカー：{maker}
型番：{model}
機番：{serial}

■ 故障内容
{issue}

■ 修理金額
{price_text}

■ 修理内容
{mitsumorinaiyo if mitsumorinaiyo else "未入力"}

お手すきの際にご来店をお願いいたします。

国本刃物 上中野店
〒700-0972
岡山県岡山市北区上中野2丁目27-12
電話番号：086-230-6551
"""

        elif statuscode == "shipped":
            message = f"""{name}様

【発送完了】

お預かりしておりました修理品を発送いたしました。

■ 修理品情報
メーカー：{maker}
型番：{model}
機番：{serial}

■ 修理金額
{price_text}

■ 送り状番号
{okurijobango if okurijobango else "未入力"}

配送状況は以下よりご確認ください。
https://toi.kuronekoyamato.co.jp/cgi-bin/tneko

よろしくお願いいたします。
"""

        elif statuscode == "cancel_return":
            message = f"""{name}様

【中止（返却）】

修理は中止となり、返却対応となります。

詳細につきましては、別途ご案内いたします。
"""

        elif statuscode == "cancel_disposal":
            message = f"""{name}様

【中止（処分）】

修理は中止となり、処分対応となります。

何卒ご了承ください。
"""

        else:
            message = f"""{name}様

ステータス不一致：
{status_jp}
"""

        # ===== LINE送信 =====
        send_line_message(user_id, message)

        # ===== 日本時間 =====
        now_time = datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S%z")

        # ===== 通知履歴保存 =====
        update_data = {
            "app": KINTONE_APP_ID,
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

        res = requests.put(
            KINTONE_RECORD_URL,
            headers=update_headers,
            json=update_data
        )

        print("履歴更新:", res.text)

        return f"送信完了: {status_jp}"

    except Exception as e:
        print("通知エラー:", e)
        return "通知処理エラー"

# ===== LINE Webhook：問い合わせ受付 =====
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        body = request.json
        print("Webhook受信:", body)

        events = body.get("events", [])

        for event in events:
            event_type = event.get("type")

            # メッセージ以外は無視
            if event_type != "message":
                continue

            message = event.get("message", {})
            message_type = message.get("type")

            # テキスト以外は無視
            if message_type != "text":
                continue

            user_message = message.get("text", "").strip()
            reply_token = event.get("replyToken")
            user_id = event.get("source", {}).get("userId")

            print("受信メッセージ:", user_message)
            print("受信userId:", user_id)

            # 「修理問い合わせ」だけ反応
            if user_message not in ["修理問い合わせ", "問い合わせ", "状況確認"]:
                reply_line_message(
                    reply_token,
                    "修理状況を確認する場合は「修理問い合わせ」と送信してください。"
                )
                continue

            # ===== Kintoneから最新レコード取得 =====
            headers = {
                "X-Cybozu-API-Token": KINTONE_API_TOKEN
            }

            query = f'lineid = "{user_id}" order by $id desc limit 1'

            params = {
                "app": KINTONE_APP_ID,
                "query": query
            }

            res = requests.get(
                KINTONE_GET_URL,
                headers=headers,
                params=params
            )

            print("問い合わせKintone取得ステータス:", res.status_code)
            print("問い合わせKintone取得本文:", res.text)

            result = res.json()

            if "records" not in result or len(result["records"]) == 0:
                reply_line_message(
                    reply_token,
                    "現在、修理受付情報が見つかりませんでした。"
                )
                continue

            record = result["records"][0]

            # ===== 必要情報取得 =====
            name = get_value(record, "customer_name", "")
            maker = get_value(record, "maker", "")
            model = get_value(record, "model", "")
            serial = get_value(record, "serial", "")
            issue = get_value(record, "issue", "")

            status_jp = get_value(record, "ドロップダウン", "").strip()

            mitsumorikingaku = get_value(record, "mitsumorikingaku", "")
            mitsumorinaiyo = get_value(record, "mitsumorinaiyo", "")
            kanryoyoteibi = get_value(record, "kanryoyoteibi", "")

            price_text = format_price(mitsumorikingaku)
            date_text = format_date(kanryoyoteibi)

            # ===== 進捗ごとの問い合わせ返信 =====
            if status_jp in ["⚪修理受付中", "📩集荷依頼済", "🚚荷受待(店舗持込待ち)"]:
                reply_message = f"""{name}様

現在の修理状況は

【受付完了・修理品荷受け待ち】

です。

修理品の到着、または確認作業をお待ちしております。
"""

            elif status_jp == "🟡見積中":
                reply_message = f"""{name}様

現在の修理状況は

【見積中】

です。

ただいま修理内容を確認し、お見積りを作成しております。
もうしばらくお待ちください。
"""

            elif status_jp == "📄見積提出済":
                reply_message = f"""{name}様

現在の修理状況は

【見積提出済】

です。

■ 修理品情報
メーカー：{maker}
型番：{model}
機番：{serial}

■ お見積り金額
{price_text}

■ お見積り内容
{mitsumorinaiyo if mitsumorinaiyo else "未入力"}

■ 修理完了予定日
{date_text}

修理を進めるか、キャンセルされるかをご確認ください。
"""

            elif status_jp == "📦受注(部品待ち)":
                reply_message = f"""{name}様

現在の修理状況は

【受注・部品待ち】

です。

現在、修理作業または部品手配を進めております。

■ 修理完了予定日
{date_text}
"""

            elif status_jp == "✅修理完了連絡済":
                reply_message = f"""{name}様

現在の修理状況は

【修理完了】

です。

修理が完了しております。
お手すきの際にご来店をお願いいたします。

■ 修理金額
{price_text}
"""

            elif status_jp == "🚚発送完了":
                okurijobango = get_value(record, "okurijobango", "")

                reply_message = f"""{name}様

現在の修理状況は

【発送完了】

です。

修理品は発送済みです。

■ 送り状番号
{okurijobango if okurijobango else "未入力"}

配送状況はこちらからご確認ください。
https://toi.kuronekoyamato.co.jp/cgi-bin/tneko
"""

            elif status_jp == "🔴中止(返却)":
                reply_message = f"""{name}様

現在の修理状況は

【中止・返却】

です。

修理は中止となり、返却対応となります。
"""

            elif status_jp == "❌中止(処分)":
                reply_message = f"""{name}様

現在の修理状況は

【中止・処分】

です。

修理は中止となり、処分対応となります。
"""

            else:
                reply_message = f"""{name}様

現在の修理状況は

【{status_jp}】

です。
"""

            # ===== LINEに返信 =====
            reply_line_message(reply_token, reply_message)

        return "OK"

    except Exception as e:
        print("Webhookエラー:", e)
        return "OK"
