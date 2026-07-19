from flask import Flask, request, send_from_directory
import requests
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs
import html

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
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
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


# ===== 共通：ボタン表示名作成 =====
def make_record_label(record):
    record_id = get_value(record, "$id", "")
    maker = get_value(record, "maker", "")
    model = get_value(record, "model", "")
    serial = get_value(record, "serial", "")

    if model:
        label = f"型番:{model}"
    elif maker:
        label = f"メーカー:{maker}"
    elif serial:
        label = f"機番:{serial}"
    else:
        label = f"修理品#{record_id}"

    if len(label) > 20:
        label = label[:20]

    return label


# ===== LINE Push送信 =====
def send_line_message(user_id, text, quick_reply_items=None):
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }

    message = {
        "type": "text",
        "text": text
    }

    if quick_reply_items:
        message["quickReply"] = {
            "items": quick_reply_items
        }

    data = {
        "to": user_id,
        "messages": [message]
    }

    res = requests.post(LINE_PUSH_URL, headers=headers, json=data)
    print("LINE送信:", res.text)


# ===== LINE Reply送信 =====
def reply_line_message(reply_token, text, quick_reply_items=None):
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }

    message = {
        "type": "text",
        "text": text
    }

    if quick_reply_items:
        message["quickReply"] = {
            "items": quick_reply_items
        }

    data = {
        "replyToken": reply_token,
        "messages": [message]
    }

    res = requests.post(LINE_REPLY_URL, headers=headers, json=data)
    print("LINE返信:", res.text)


# ===== LINE Reply送信：複数台選択 =====
def reply_line_quick_reply(reply_token, text, records):
    items = []

    for record in records[:10]:
        record_id = get_value(record, "$id", "")
        label = make_record_label(record)

        items.append({
            "type": "action",
            "action": {
                "type": "postback",
                "label": label,
                "data": f"action=check_status&record_id={record_id}",
                "displayText": label
            }
        })

    reply_line_message(reply_token, text, items)


# ===== Kintone：ユーザーIDから複数レコード取得 =====
def get_records_by_user(user_id):
    headers = {
        "X-Cybozu-API-Token": KINTONE_API_TOKEN
    }

    query = f'lineid = "{user_id}" order by $id desc limit 10'

    params = {
        "app": KINTONE_APP_ID,
        "query": query
    }

    res = requests.get(
        KINTONE_GET_URL,
        headers=headers,
        params=params
    )

    print("複数取得ステータス:", res.status_code)
    print("複数取得本文:", res.text)

    result = res.json()
    return result.get("records", [])


# ===== Kintone：レコードIDで1件取得 =====
def get_record_by_id(record_id):
    headers = {
        "X-Cybozu-API-Token": KINTONE_API_TOKEN
    }

    params = {
        "app": KINTONE_APP_ID,
        "id": record_id
    }

    res = requests.get(
        KINTONE_RECORD_URL,
        headers=headers,
        params=params
    )

    print("単体取得ステータス:", res.status_code)
    print("単体取得本文:", res.text)

    result = res.json()
    return result.get("record")


# ===== Kintone：修理可否回答を保存 =====
def update_repair_answer(record_id, answer_text):
    headers = {
        "X-Cybozu-API-Token": KINTONE_API_TOKEN,
        "Content-Type": "application/json"
    }

    data = {
        "app": KINTONE_APP_ID,
        "id": record_id,
        "record": {
            "shurikahikaito": {
                "value": answer_text
            }
        }
    }

    res = requests.put(
        KINTONE_RECORD_URL,
        headers=headers,
        json=data
    )

    print("修理可否回答更新:", res.text)


# ===== Kintone：キャンセル後対応を保存 =====
def update_cancel_action(record_id, cancel_text):
    headers = {
        "X-Cybozu-API-Token": KINTONE_API_TOKEN,
        "Content-Type": "application/json"
    }

    data = {
        "app": KINTONE_APP_ID,
        "id": record_id,
        "record": {
            "canceltaio": {
                "value": cancel_text
            }
        }
    }

    res = requests.put(
        KINTONE_RECORD_URL,
        headers=headers,
        json=data
    )

    print("キャンセル後対応更新:", res.text)


# ===== Kintone：位置情報を保存 =====
def update_location_info(record_id, shukabasho, ido, keido, mapurl):
    headers = {
        "X-Cybozu-API-Token": KINTONE_API_TOKEN,
        "Content-Type": "application/json"
    }

    data = {
        "app": KINTONE_APP_ID,
        "id": record_id,
        "record": {
            "shukabasho": {
                "value": shukabasho
            },
            "ido": {
                "value": str(ido)
            },
            "keido": {
                "value": str(keido)
            },
            "mapurl": {
                "value": mapurl
            }
        }
    }

    res = requests.put(
        KINTONE_RECORD_URL,
        headers=headers,
        json=data
    )

    print("位置情報更新:", res.text)


# ===== 位置情報保存対象レコードを取得 =====
def get_latest_active_record(user_id):
    records = get_records_by_user(user_id)

    if len(records) == 0:
        return None

    closed_statuses = [
        "●完了(精算済)",
        "🔴中止(返却)",
        "❌中止(処分)"
    ]

    for record in records:
        status = get_value(record, "ドロップダウン", "").strip()
        if status not in closed_statuses:
            return record

    return records[0]


# ===== 問い合わせ返信文作成 =====
def build_status_message(record):
    name = get_value(record, "customer_name", "")
    maker = get_value(record, "maker", "")
    model = get_value(record, "model", "")
    serial = get_value(record, "serial", "")
    issue = get_value(record, "issue", "")

    status_jp = get_value(record, "ドロップダウン", "").strip()

    mitsumorikingaku = get_value(record, "mitsumorikingaku", "")
    mitsumorinaiyo = get_value(record, "mitsumorinaiyo", "")
    kanryoyoteibi = get_value(record, "kanryoyoteibi", "")
    okurijobango = get_value(record, "okurijobango", "")
    shukabasho = get_value(record, "shukabasho", "")
    mapurl = get_value(record, "mapurl", "")

    price_text = format_price(mitsumorikingaku)
    date_text = format_date(kanryoyoteibi)

    base_info = f"""■ 修理品情報
メーカー：{maker}
型番：{model}
機番：{serial}

"""

    if status_jp in ["⚪修理受付中", "📩集荷依頼済", "🚚荷受待(店舗持込待ち)", "🚶荷受待(店舗持込待ち)"]:
        return f"""{name}様

以下の修理品の状況です。

{base_info}■ 現在の進捗
【受付完了・修理品荷受け待ち】

修理品の到着、または確認作業をお待ちしております。

■ 集荷場所
{shukabasho if shukabasho else "未登録"}

■ 地図URL
{mapurl if mapurl else "未登録"}
"""

    elif status_jp == "🟡見積中":
        return f"""{name}様

以下の修理品の状況です。

{base_info}■ 現在の進捗
【見積中】

ただいま修理内容を確認し、お見積りを作成しております。
もうしばらくお待ちください。
"""

    elif status_jp == "📄見積提出済":
        return f"""{name}様

以下の修理品の状況です。

{base_info}■ 現在の進捗
【見積提出済】

■ 故障内容
{issue}

■ お見積り金額
{price_text}

■ お見積り内容
{mitsumorinaiyo if mitsumorinaiyo else "未入力"}

■ 修理完了予定日
{date_text}

修理を進めるか、キャンセルされるかをご確認ください。
"""

    elif status_jp == "📦受注(部品待ち)":
        return f"""{name}様

以下の修理品の状況です。

{base_info}■ 現在の進捗
【受注・部品待ち】

現在、修理作業または部品手配を進めております。

■ 修理完了予定日
{date_text}
"""

    elif status_jp == "✅修理完了連絡済":
        return f"""{name}様

以下の修理品の状況です。

{base_info}■ 現在の進捗
【修理完了】

修理が完了しております。
お手すきの際にご来店をお願いいたします。

■ 修理金額
{price_text}
"""

    elif status_jp == "🚚発送完了":
        return f"""{name}様

以下の修理品の状況です。

{base_info}■ 現在の進捗
【発送完了】

修理品は発送済みです。

■ 送り状番号
{okurijobango if okurijobango else "未入力"}

配送状況はこちらからご確認ください。
https://toi.kuronekoyamato.co.jp/cgi-bin/tneko
"""

    elif status_jp == "🔴中止(返却)":
        return f"""{name}様

以下の修理品の状況です。

{base_info}■ 現在の進捗
【中止・返却】

修理は中止となり、返却対応となります。
"""

    elif status_jp == "❌中止(処分)":
        return f"""{name}様

以下の修理品の状況です。

{base_info}■ 現在の進捗
【中止・処分】

修理は中止となり、処分対応となります。
"""

    else:
        return f"""{name}様

以下の修理品の状況です。

{base_info}■ 現在の進捗
【{status_jp}】

です。
"""


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


# ===== 通知URLクリック用 =====
@app.route("/notify", methods=["GET"])
def notify():
    user_id = request.args.get("user")

    print("受信user:", user_id)

    try:
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

        result = res.json()

        if "records" not in result or len(result["records"]) == 0:
            return "レコードなし"

        record = result["records"][0]
        record_id = record["$id"]["value"]

        name = get_value(record, "customer_name", "")
        maker = get_value(record, "maker", "")
        model = get_value(record, "model", "")
        serial = get_value(record, "serial", "")
        issue = get_value(record, "issue", "")

        mitsumorikingaku = get_value(record, "mitsumorikingaku", "")
        mitsumorinaiyo = get_value(record, "mitsumorinaiyo", "")
        kanryoyoteibi = get_value(record, "kanryoyoteibi", "")
        okurijobango = get_value(record, "okurijobango", "")

        price_text = format_price(mitsumorikingaku)
        date_text = format_date(kanryoyoteibi)

        status_jp = get_value(record, "ドロップダウン", "").strip()
        print("取得ステータス:", status_jp)

        status_map = {
            "⚪修理受付中": "received",
            "📩集荷依頼済": "pickup_requested",
            "🚚荷受待(店舗持込待ち)": "waiting_arrival",
            "🚶荷受待(店舗持込待ち)": "waiting_arrival",
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
            quick_reply_items = [
                {
                    "type": "action",
                    "action": {
                        "type": "postback",
                        "label": "修理を依頼する",
                        "data": f"action=repair_accept&record_id={record_id}",
                        "displayText": "修理を依頼する"
                    }
                },
                {
                    "type": "action",
                    "action": {
                        "type": "postback",
                        "label": "キャンセルする",
                        "data": f"action=repair_cancel&record_id={record_id}",
                        "displayText": "キャンセルする"
                    }
                }
            ]

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

修理を進めるか、キャンセルされるかをご回答ください。
"""

            send_line_message(user_id, message, quick_reply_items)

            now_time = datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S%z")

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

            update_res = requests.put(
                KINTONE_RECORD_URL,
                headers=update_headers,
                json=update_data
            )

            print("履歴更新:", update_res.text)

            return f"送信完了: {status_jp}"

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

        send_line_message(user_id, message)

        now_time = datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S%z")

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

        update_res = requests.put(
            KINTONE_RECORD_URL,
            headers=update_headers,
            json=update_data
        )

        print("履歴更新:", update_res.text)

        return f"送信完了: {status_jp}"

    except Exception as e:
        print("通知エラー:", e)
        return "通知処理エラー"


# ===== LINE Webhook：問い合わせ・複数台対応・修理可否回答・キャンセル後対応・位置情報 =====
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        body = request.json
        print("Webhook受信:", body)

        events = body.get("events", [])

        for event in events:
            event_type = event.get("type")
            reply_token = event.get("replyToken")
            user_id = event.get("source", {}).get("userId")

            # ===== ボタン選択された場合 =====
            if event_type == "postback":
                postback_data = event.get("postback", {}).get("data", "")
                postback_data = html.unescape(postback_data)

                print("Postback受信:", postback_data)

                parsed = parse_qs(postback_data)
                action = parsed.get("action", [""])[0]
                record_id = parsed.get("record_id", [""])[0]

                if action == "check_status" and record_id:
                    record = get_record_by_id(record_id)

                    if not record:
                        reply_line_message(
                            reply_token,
                            "選択された修理情報が見つかりませんでした。"
                        )
                        continue

                    reply_message = build_status_message(record)
                    reply_line_message(reply_token, reply_message)
                    continue

                if action == "repair_accept" and record_id:
                    update_repair_answer(record_id, "修理する")

                    record = get_record_by_id(record_id)

                    if record:
                        maker = get_value(record, "maker", "")
                        model = get_value(record, "model", "")
                        serial = get_value(record, "serial", "")
                    else:
                        maker = ""
                        model = ""
                        serial = ""

                    reply_message = f"""【修理受付完了】

ご依頼ありがとうございます。
これより修理作業に入らせていただきます。

完了次第、こちらのLINEにてご連絡いたします。

■ 修理品情報
メーカー：{maker}
型番：{model}
機番：{serial}
"""

                    reply_line_message(reply_token, reply_message)
                    continue

                if action == "repair_cancel" and record_id:
                    update_repair_answer(record_id, "キャンセル")

                    record = get_record_by_id(record_id)

                    if record:
                        maker = get_value(record, "maker", "")
                        model = get_value(record, "model", "")
                        serial = get_value(record, "serial", "")
                    else:
                        maker = ""
                        model = ""
                        serial = ""

                    quick_reply_items = [
                        {
                            "type": "action",
                            "action": {
                                "type": "postback",
                                "label": "店舗で受け取る",
                                "data": f"action=cancel_pickup&record_id={record_id}",
                                "displayText": "店舗で受け取る"
                            }
                        },
                        {
                            "type": "action",
                            "action": {
                                "type": "postback",
                                "label": "店舗で処分する",
                                "data": f"action=cancel_disposal&record_id={record_id}",
                                "displayText": "店舗で処分する"
                            }
                        }
                    ]

                    reply_message = f"""【キャンセル受付】

修理キャンセルを承りました。

■ 修理品情報
メーカー：{maker}
型番：{model}
機番：{serial}

返却方法をお選びください。
"""

                    reply_line_message(reply_token, reply_message, quick_reply_items)
                    continue

                if action == "cancel_pickup" and record_id:
                    update_cancel_action(record_id, "店舗引取")

                    record = get_record_by_id(record_id)

                    if record:
                        maker = get_value(record, "maker", "")
                        model = get_value(record, "model", "")
                        serial = get_value(record, "serial", "")
                    else:
                        maker = ""
                        model = ""
                        serial = ""

                    reply_message = f"""【返却受付完了】

修理品の店舗引取を承りました。

■ 修理品情報
メーカー：{maker}
型番：{model}
機番：{serial}

キャンセル料が発生する場合は、
商品返却時にお支払いください。

ご来店をお待ちしております。
"""

                    reply_line_message(reply_token, reply_message)
                    continue

                if action == "cancel_disposal" and record_id:
                    update_cancel_action(record_id, "処分")

                    record = get_record_by_id(record_id)

                    if record:
                        maker = get_value(record, "maker", "")
                        model = get_value(record, "model", "")
                        serial = get_value(record, "serial", "")
                    else:
                        maker = ""
                        model = ""
                        serial = ""

                    reply_message = f"""【処分受付完了】

お預かり品を処分いたします。

■ 修理品情報
メーカー：{maker}
型番：{model}
機番：{serial}

キャンセル料が発生する場合は、
ご来店時または別途ご案内の方法にてお支払いください。
"""

                    reply_line_message(reply_token, reply_message)
                    continue

            # ===== メッセージの場合 =====
            if event_type != "message":
                continue

            message = event.get("message", {})
            message_type = message.get("type")

            # ===== 位置情報メッセージの場合 =====
            if message_type == "location":
                title = message.get("title", "")
                address = message.get("address", "")
                latitude = message.get("latitude", "")
                longitude = message.get("longitude", "")

                print("位置情報受信 title:", title)
                print("位置情報受信 address:", address)
                print("位置情報受信 latitude:", latitude)
                print("位置情報受信 longitude:", longitude)

                record = get_latest_active_record(user_id)

                if not record:
                    reply_line_message(
                        reply_token,
                        "修理受付情報が見つかりませんでした。先に修理受付フォームをご入力ください。"
                    )
                    continue

                record_id = get_value(record, "$id", "")
                maker = get_value(record, "maker", "")
                model = get_value(record, "model", "")
                serial = get_value(record, "serial", "")

                mapurl = f"https://www.google.com/maps?q={latitude},{longitude}"

                if title and address:
                    shukabasho = f"{title}\n{address}"
                elif address:
                    shukabasho = address
                elif title:
                    shukabasho = title
                else:
                    shukabasho = "位置情報"

                update_location_info(
                    record_id,
                    shukabasho,
                    latitude,
                    longitude,
                    mapurl
                )

                reply_message = f"""【位置情報受付完了】

集荷場所を受け付けました。

■ 修理品情報
メーカー：{maker}
型番：{model}
機番：{serial}

■ 集荷場所
{shukabasho}

■ 地図URL
{mapurl}
"""

                reply_line_message(reply_token, reply_message)
                continue

            # ===== テキストメッセージの場合 =====
            if message_type != "text":
                continue

            user_message = message.get("text", "").strip()

            print("受信メッセージ:", user_message)
            print("受信userId:", user_id)

            if user_message not in ["修理問い合わせ", "問い合わせ", "状況確認"]:
                reply_line_message(
                    reply_token,
                    "修理状況を確認する場合は「修理問い合わせ」と送信してください。\n集荷場所を送る場合は、LINEの位置情報送信をご利用ください。"
                )
                continue

            records = get_records_by_user(user_id)

            if len(records) == 0:
                reply_line_message(
                    reply_token,
                    "現在、修理受付情報が見つかりませんでした。"
                )
                continue

            closed_statuses = [
                "●完了(精算済)",
                "🔴中止(返却)",
                "❌中止(処分)"
            ]

            active_records = []

            for record in records:
                status = get_value(record, "ドロップダウン", "").strip()

                if status not in closed_statuses:
                    active_records.append(record)

            if len(active_records) == 0:
                reply_line_message(
                    reply_token,
                    "現在、進行中の修理受付情報はありません。"
                )
                continue

            if len(active_records) == 1:
                reply_message = build_status_message(active_records[0])
                reply_line_message(reply_token, reply_message)
                continue

            reply_line_quick_reply(
                reply_token,
                "現在、複数の修理品をお預かりしています。\n確認したい修理品を選択してください。",
                active_records
            )

        return "OK"

    except Exception as e:
        print("Webhookエラー:", e)
        return "OK"
