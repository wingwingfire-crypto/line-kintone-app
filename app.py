import os
import json
import html
import requests
from datetime import datetime, timezone
from urllib.parse import parse_qs

from flask import Flask, request, render_template

app = Flask(__name__)


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "https://9oh3c.cybozu.com"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


LINE_CHANNEL_ACCESS_TOKEN = (
    os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    or os.environ.get("LINE_TOKEN")
)

KINTONE_API_TOKEN = os.environ.get("KINTONE_API_TOKEN")

KINTONE_BASE = "https://9oh3c.cybozu.com"
KINTONE_APP_ID = 6

PUBLIC_BASE_URL = os.environ.get(
    "PUBLIC_BASE_URL",
    "https://line-kintone-app.onrender.com"
)

KINTONE_RECORD_URL = f"{KINTONE_BASE}/k/v1/record.json"
KINTONE_RECORDS_URL = f"{KINTONE_BASE}/k/v1/records.json"

LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"

STATUS_RECEIVED = "⚪修理受付中"
STATUS_PICKUP_REQUESTED = "🚚集荷依頼済"
STATUS_ESTIMATE = "📄見積提出済"
STATUS_ORDERED = "📦受注"
STATUS_DONE_STORE = "✉️修理完了連絡済(店頭受取)"
STATUS_DONE_SHIP = "✉️修理完了連絡済(発送)"
STATUS_COMPLETE = "🟢完了・出荷済"
STATUS_CANCEL_STORE = "🔴中止(店舗引取)"
STATUS_CANCEL_RETURN = "🔴中止(返送)"
STATUS_CANCEL_DISPOSE = "❌中止(店舗処分)"

OLD_STATUS_ORDERED = "📦受注(部品待ち)"
OLD_STATUS_DONE = "✉️修理完了連絡済"
OLD_STATUS_COMPLETE = "🟢完了(精算済)"
OLD_STATUS_CANCEL_RETURN = "🔴中止(返却)"
OLD_STATUS_CANCEL_DISPOSE = "❌中止(処分)"


# =========================
# 共通ヘルパー
# =========================

def now_utc_for_kintone():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def kintone_headers():
    return {
        "X-Cybozu-API-Token": KINTONE_API_TOKEN,
        "Content-Type": "application/json"
    }


def line_headers():
    return {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }


def getvalue(record, field_code, default=""):
    try:
        field = record.get(field_code)
        if not field:
            return default
        value = field.get("value")
        if value is None:
            return default
        return value
    except Exception:
        return default


def escape_kintone_query_value(value):
    if value is None:
        return ""
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def make_field(value):
    return {"value": value if value is not None else ""}


def format_yen(value):
    if value is None or value == "":
        return "未入力"
    try:
        return f"{int(float(value)):,}円"
    except Exception:
        return str(value)


def shorten_text(value, limit=80):
    if not value:
        return "未入力"
    if len(value) > limit:
        return value[:limit] + "..."
    return value


def make_repair_item_text(record):
    maker = getvalue(record, "maker", "")
    model = getvalue(record, "model", "")
    serial = getvalue(record, "serial", "")

    parts = []

    if maker:
        parts.append(maker)

    if model:
        parts.append(model)

    if serial:
        parts.append(f"機番:{serial}")

    if not parts:
        return "修理品情報 未入力"

    return " / ".join(parts)


def is_ordered_status(status):
    return status in [STATUS_ORDERED, OLD_STATUS_ORDERED] or "受注" in status


def is_done_status(status):
    return status in [STATUS_DONE_STORE, STATUS_DONE_SHIP, OLD_STATUS_DONE] or "修理完了連絡済" in status


def is_complete_status(status):
    return status in [STATUS_COMPLETE, OLD_STATUS_COMPLETE] or "完了" in status


def is_cancel_status(status):
    return status in [
        STATUS_CANCEL_STORE,
        STATUS_CANCEL_RETURN,
        STATUS_CANCEL_DISPOSE,
        OLD_STATUS_CANCEL_RETURN,
        OLD_STATUS_CANCEL_DISPOSE
    ] or "中止" in status


# =========================
# LINE送信
# =========================

def send_line_reply(reply_token, text, quick_reply_items=None):
    message = {
        "type": "text",
        "text": text
    }

    if quick_reply_items:
        message["quickReply"] = {
            "items": quick_reply_items
        }

    payload = {
        "replyToken": reply_token,
        "messages": [message]
    }

    res = requests.post(
        LINE_REPLY_URL,
        headers=line_headers(),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8")
    )

    print("LINE返信:", res.text)
    return res


def send_line_reply_messages(reply_token, messages):
    payload = {
        "replyToken": reply_token,
        "messages": messages
    }

    res = requests.post(
        LINE_REPLY_URL,
        headers=line_headers(),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8")
    )

    print("LINE複数返信:", res.text)
    return res


def send_line_push(user_id, text, quick_reply_items=None):
    message = {
        "type": "text",
        "text": text
    }

    if quick_reply_items:
        message["quickReply"] = {
            "items": quick_reply_items
        }

    payload = {
        "to": user_id,
        "messages": [message]
    }

    res = requests.post(
        LINE_PUSH_URL,
        headers=line_headers(),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8")
    )

    print("LINE送信:", res.text)
    return res


def send_line_push_messages(user_id, messages):
    payload = {
        "to": user_id,
        "messages": messages
    }

    res = requests.post(
        LINE_PUSH_URL,
        headers=line_headers(),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8")
    )

    print("LINE複数送信:", res.text)
    return res


def quick_reply_location(label="📍 位置情報を送る"):
    return {
        "type": "action",
        "action": {
            "type": "location",
            "label": label
        }
    }


def quick_reply_postback(label, data, display_text=None):
    action = {
        "type": "postback",
        "label": label,
        "data": data
    }

    if display_text:
        action["displayText"] = display_text

    return {
        "type": "action",
        "action": action
    }


# =========================
# Kintone操作
# =========================

def add_kintone_record(record):
    payload = {
        "app": KINTONE_APP_ID,
        "record": record
    }

    res = requests.post(
        KINTONE_RECORD_URL,
        headers=kintone_headers(),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8")
    )

    print("Kintone登録:", res.text)
    return res


def get_kintone_record(record_id):
    params = {
        "app": KINTONE_APP_ID,
        "id": record_id
    }

    res = requests.get(
        KINTONE_RECORD_URL,
        headers={"X-Cybozu-API-Token": KINTONE_API_TOKEN},
        params=params
    )

    print("単体取得ステータス:", res.status_code)
    print("単体取得本文:", res.text)

    if not res.ok:
        return None

    return res.json().get("record")


def get_records_by_lineid(line_user_id, limit=10):
    safe_user_id = escape_kintone_query_value(line_user_id)

    params = {
        "app": KINTONE_APP_ID,
        "query": f'lineid = "{safe_user_id}" order by $id desc limit {limit}'
    }

    res = requests.get(
        KINTONE_RECORDS_URL,
        headers={"X-Cybozu-API-Token": KINTONE_API_TOKEN},
        params=params
    )

    print("複数取得ステータス:", res.status_code)
    print("複数取得本文:", res.text)

    if not res.ok:
        return []

    return res.json().get("records", [])


def update_kintone_record(record_id, fields):
    payload = {
        "app": KINTONE_APP_ID,
        "id": record_id,
        "record": fields
    }

    res = requests.put(
        KINTONE_RECORD_URL,
        headers=kintone_headers(),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8")
    )

    print("Kintone更新:", res.text)
    return res


def update_location_pickup(record_id, address, latitude, longitude):
    map_url = f"https://www.google.com/maps?q={latitude},{longitude}"

    fields = {
        "shukabasho": make_field(address),
        "ido": make_field(str(latitude)),
        "keido": make_field(str(longitude)),
        "mapurl": make_field(map_url)
    }

    record = get_kintone_record(record_id)

    if record:
        sameaddress = getvalue(record, "sameaddress", "")
        henkyakuhouhou = getvalue(record, "henkyakuhouhou", "")

        if sameaddress == "はい" or henkyakuhouhou == "集荷場所と同じ":
            fields.update({
                "henkyakubasho": make_field(address),
                "henkyakuido": make_field(str(latitude)),
                "henkyakukeido": make_field(str(longitude)),
                "henkyakumapurl": make_field(map_url)
            })

            if not getvalue(record, "henkyakujusho", ""):
                fields["henkyakujusho"] = make_field("集荷場所と同じ")

    return update_kintone_record(record_id, fields)


def update_location_return(record_id, address, latitude, longitude):
    map_url = f"https://www.google.com/maps?q={latitude},{longitude}"

    fields = {
        "henkyakubasho": make_field(address),
        "henkyakuido": make_field(str(latitude)),
        "henkyakukeido": make_field(str(longitude)),
        "henkyakumapurl": make_field(map_url)
    }

    return update_kintone_record(record_id, fields)


def update_notify_history(record_id, message):
    fields = {
        "lastnotify": make_field(now_utc_for_kintone()),
        "notifymessage": make_field(message)
    }

    res = update_kintone_record(record_id, fields)
    print("履歴更新:", res.text)
    return res


def update_repair_answer(record_id, answer):
    fields = {
        "shurikahikaito": make_field(answer)
    }

    if answer == "修理する":
        fields["ドロップダウン"] = make_field(STATUS_ORDERED)

    return update_kintone_record(record_id, fields)


def update_cancel_action(record_id, action):
    fields = {
        "canceltaio": make_field(action)
    }

    if action == "店舗引取":
        fields["ドロップダウン"] = make_field(STATUS_CANCEL_STORE)

    if action == "返送":
        fields["ドロップダウン"] = make_field(STATUS_CANCEL_RETURN)

    if action == "処分":
        fields["ドロップダウン"] = make_field(STATUS_CANCEL_DISPOSE)

    return update_kintone_record(record_id, fields)


# =========================
# 誤操作防止ヘルパー
# =========================

def already_decided_text(current_answer, current_cancel_action):
    if current_cancel_action:
        return f"この修理受付は、すでに「{current_cancel_action}」で登録済みです。\n変更が必要な場合は店舗までご連絡ください。"

    if current_answer == "修理する":
        return "この修理受付は、すでに「修理する」で受付済みです。\n変更が必要な場合は店舗までご連絡ください。"

    if current_answer == "キャンセル":
        return "この修理受付は、すでに「キャンセル」で受付済みです。\n変更が必要な場合は店舗までご連絡ください。"

    return "この修理受付は、すでに対応済みです。\n変更が必要な場合は店舗までご連絡ください。"


# =========================
# LINE通知テキスト
# =========================

def build_status_text(record):
    record_id = getvalue(record, "$id", "")
    status = getvalue(record, "ドロップダウン", "未設定")
    name = getvalue(record, "customer_name", "")
    maker = getvalue(record, "maker", "")
    model = getvalue(record, "model", "")
    serial = getvalue(record, "serial", "")
    issue = getvalue(record, "issue", "")
    estimate = getvalue(record, "mitsumorikingaku", "")
    estimate_detail = getvalue(record, "mitsumorinaiyo", "")
    due_date = getvalue(record, "kanryoyoteibi", "")
    tracking = getvalue(record, "okurijobango", "")
    uketorihouhou = getvalue(record, "uketorihouhou", "")
    shukajusho = getvalue(record, "shukajusho", "")
    shukabasho = getvalue(record, "shukabasho", "")
    mapurl = getvalue(record, "mapurl", "")
    sameaddress = getvalue(record, "sameaddress", "")
    henkyakuhouhou = getvalue(record, "henkyakuhouhou", "")
    henkyakujusho = getvalue(record, "henkyakujusho", "")
    henkyakubasho = getvalue(record, "henkyakubasho", "")
    henkyakumapurl = getvalue(record, "henkyakumapurl", "")

    text = f"""【修理進捗状況のご案内】

受付番号：{record_id}
現在のステータス：{status}

■ お客様名
{name}

■ 修理品情報
メーカー：{maker or "未入力"}
型番：{model or "未入力"}
機番：{serial or "未入力"}

■ 故障内容
{issue or "未入力"}

■ 受け渡し方法
{uketorihouhou or "未入力"}
"""

    if shukajusho or shukabasho:
        text += "\n■ 集荷場所\n"
        if shukajusho:
            text += f"{shukajusho}\n"
        if shukabasho:
            text += f"{shukabasho}\n"
        if mapurl:
            text += f"{mapurl}\n"

    if sameaddress or henkyakuhouhou or henkyakujusho or henkyakubasho:
        text += "\n■ 返却場所\n"
        if sameaddress:
            text += f"集荷場所と同じ：{sameaddress}\n"
        if henkyakuhouhou:
            text += f"指定方法：{henkyakuhouhou}\n"
        if henkyakujusho:
            text += f"{henkyakujusho}\n"
        if henkyakubasho:
            text += f"{henkyakubasho}\n"
        if henkyakumapurl:
            text += f"{henkyakumapurl}\n"

    if "見積" in status:
        text += f"""
■ お見積り金額
{estimate or "未入力"}

■ お見積り内容
{estimate_detail or "未入力"}

修理を進めるか、キャンセルされるかをご回答ください。
"""

    if tracking:
        text += f"""
■ お問い合わせ送り状番号
{tracking}
"""

    if due_date:
        text += f"""
■ 修理完了予定日
{due_date}
"""

    return text


def build_notify_message(record):
    record_id = getvalue(record, "$id", "")
    status = getvalue(record, "ドロップダウン", "")
    name = getvalue(record, "customer_name", "")
    maker = getvalue(record, "maker", "")
    model = getvalue(record, "model", "")
    serial = getvalue(record, "serial", "")
    issue = getvalue(record, "issue", "")
    estimate = getvalue(record, "mitsumorikingaku", "")
    estimate_detail = getvalue(record, "mitsumorinaiyo", "")
    tracking = getvalue(record, "okurijobango", "")

    if status == STATUS_RECEIVED:
        return f"""修理のお申込みを受け付けました

受付番号：{record_id}

{name}様

お申し込みありがとうございます。
ただいま内容を確認しております。

確認・準備が整い次第、次のご案内をお送りいたしますので少々お待ちください。"""

    if status == STATUS_PICKUP_REQUESTED:
        return f"""修理品の集荷手配が完了しました

受付番号：{record_id}

指定の日時に配送業者が伺いますので、修理品のご準備をお願いいたします。"""

    if status == STATUS_ESTIMATE or "見積" in status:
        return f"""修理のお見積りが届きました

受付番号：{record_id}

お預かりしている修理品のお見積りが完了しました。
以下の見積より金額をご確認いただき、ご判断をお知らせください。

■ 修理品情報
メーカー：{maker or "未入力"}
型番：{model or "未入力"}
機番：{serial or "未入力"}

■ 故障内容
{issue or "未入力"}

■ お見積り金額
{estimate or "未入力"}

■ お見積り内容
{estimate_detail or "未入力"}

◎修理を進めるか、キャンセルされるかをご回答ください。"""

    if status == STATUS_ORDERED or "受注" in status:
        return f"""修理作業を開始いたします

受付番号：{record_id}

修理実行のご連絡ありがとうございます。
これより修理作業に入らせていただきます。

完了まで今しばらくお待ちください。

受取方法やお届け先の変更がある場合は、店舗へお電話にてご連絡ください。

上中野店 TEL：086-230-6551
受付時間：7:00〜19:00"""

    if status == STATUS_DONE_SHIP:
        return f"""修理品を発送しました

受付番号：{record_id}

大変お待たせいたしました。
修理作業が完了し、修理品を発送いたしました。

■ お問い合わせ送り状番号
{tracking or "未入力"}

到着までもうしばらくお待ちください。
この度は修理サービスをご利用いただき、誠にありがとうございました。"""

    if status == STATUS_DONE_STORE:
        return f"""修理が完了いたしました

受付番号：{record_id}

大変お待たせいたしました。
修理作業が完了し、店頭でのお渡し準備が整っております。

ご来店時に、このLINE画面または受付番号をスタッフへお見せください。"""

    if status == STATUS_COMPLETE:
        return f"""修理対応が完了しました

受付番号：{record_id}

この度は修理サービスをご利用いただき、誠にありがとうございました。"""

    if status == STATUS_CANCEL_STORE:
        return f"""修理キャンセル後の店舗引取について

受付番号：{record_id}

修理中止のご連絡を承りました。
お預かりした修理品は店舗引取として進めます。"""

    if status == STATUS_CANCEL_RETURN:
        return f"""修理キャンセル後の返送対応について

受付番号：{record_id}

修理中止のご連絡を承りました。
お預かりした修理品は返送対応として進めます。"""

    if status == STATUS_CANCEL_DISPOSE:
        return f"""修理キャンセル後の店舗処分について

受付番号：{record_id}

修理中止のご連絡を承りました。
お預かりした修理品は当店にて処分対応として進めます。"""

    return build_status_text(record)


# =========================
# Flex Messageカード作成
# =========================

def text_component(text, size="sm", weight=None, color=None, wrap=True, margin=None):
    item = {
        "type": "text",
        "text": text,
        "size": size,
        "wrap": wrap
    }

    if weight:
        item["weight"] = weight

    if color:
        item["color"] = color

    if margin:
        item["margin"] = margin

    return item


def separator(margin="md"):
    return {
        "type": "separator",
        "margin": margin
    }


def info_box(title, value, color, bg):
    return {
        "type": "box",
        "layout": "vertical",
        "backgroundColor": bg,
        "cornerRadius": "12px",
        "paddingAll": "14px",
        "margin": "md",
        "contents": [
            text_component(title, size="sm", weight="bold", color=color),
            text_component(value, size="lg", weight="bold", margin="sm")
        ]
    }


def make_flex_card(title, record_id, header_color, sub_color, body_contents, footer_contents=None, alt_text=None, quick_reply_items=None):
    message = {
        "type": "flex",
        "altText": alt_text or title,
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": header_color,
                "paddingAll": "16px",
                "contents": [
                    text_component(title, size="lg", weight="bold", color="#FFFFFF"),
                    text_component(f"受付番号：{record_id}", size="sm", color=sub_color, margin="sm")
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": body_contents
            }
        }
    }

    if footer_contents:
        message["contents"]["footer"] = {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": footer_contents
        }

    if quick_reply_items:
        message["quickReply"] = {
            "items": quick_reply_items
        }

    return message


def build_receipt_flex_message(record_id, name):
    body = [
        text_component(f"{name or 'お客様'} 様", size="md", weight="bold"),
        text_component("修理のお申し込みありがとうございます。内容を確認し、準備が整い次第ご案内いたします。", color="#555555"),
        separator(),
        info_box("現在の状態", STATUS_RECEIVED, "#06C755", "#F3FFF7")
    ]

    return make_flex_card(
        "✅ 修理受付を完了しました",
        record_id,
        "#06C755",
        "#E8F5E9",
        body,
        alt_text="修理受付を完了しました"
    )


def build_pickup_location_request_flex_message(record_id, name):
    body = [
        text_component(f"{name or 'お客様'} 様", size="md", weight="bold"),
        text_component("集荷場所の位置情報が必要です。", color="#555555"),
        separator(),
        {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#F2F8FF",
            "cornerRadius": "12px",
            "paddingAll": "14px",
            "contents": [
                text_component("次にやること", size="sm", weight="bold", color="#1976D2"),
                text_component("下の「📍 集荷場所を送る」ボタンを押してください。", margin="sm"),
                text_component("位置情報画面が開いたら、場所を選んで緑の✅を押してください。", margin="sm")
            ]
        }
    ]

    return make_flex_card(
        "📍 集荷場所を登録してください",
        record_id,
        "#1976D2",
        "#E3F2FD",
        body,
        alt_text="集荷場所を送信してください",
        quick_reply_items=[quick_reply_location("📍 集荷場所を送る")]
    )


def build_return_location_request_flex_message(record):
    record_id = getvalue(record, "$id", "")
    name = getvalue(record, "customer_name", "")

    body = [
        text_component(f"{name or 'お客様'} 様", size="md", weight="bold"),
        text_component("集荷場所を登録しました。続いて返却場所の位置情報を送ってください。", color="#555555"),
        separator(),
        {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#FAF2FF",
            "cornerRadius": "12px",
            "paddingAll": "14px",
            "contents": [
                text_component("次にやること", size="sm", weight="bold", color="#6A1B9A"),
                text_component("下の「📍 返却場所を送る」ボタンを押してください。", margin="sm"),
                text_component("位置情報画面が開いたら、場所を選んで緑の✅を押してください。", margin="sm")
            ]
        }
    ]

    return make_flex_card(
        "📦 返却場所を登録してください",
        record_id,
        "#6A1B9A",
        "#F3E5F5",
        body,
        alt_text="返却場所を送信してください",
        quick_reply_items=[quick_reply_location("📍 返却場所を送る")]
    )


def build_estimate_flex_message(record):
    record_id = getvalue(record, "$id", "")
    name = getvalue(record, "customer_name", "")
    maker = getvalue(record, "maker", "")
    model = getvalue(record, "model", "")
    serial = getvalue(record, "serial", "")
    issue = shorten_text(getvalue(record, "issue", ""), 70)
    estimate = getvalue(record, "mitsumorikingaku", "")
    estimate_detail = shorten_text(getvalue(record, "mitsumorinaiyo", ""), 80)

    body = [
        text_component(f"{name or 'お客様'} 様", size="md", weight="bold", color="#222222"),
        text_component("修理品のお見積りが完了しました。", color="#666666"),
        separator(),
        text_component("修理品情報", weight="bold", color="#06C755"),
        text_component(f"メーカー：{maker or '未入力'}"),
        text_component(f"型番：{model or '未入力'}"),
        text_component(f"機番：{serial or '未入力'}"),
        text_component("故障内容", weight="bold", color="#06C755", margin="md"),
        text_component(issue),
        {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#F3FFF7",
            "cornerRadius": "12px",
            "paddingAll": "14px",
            "margin": "md",
            "contents": [
                text_component("お見積り金額", weight="bold", color="#06C755"),
                text_component(format_yen(estimate), size="xxl", weight="bold", color="#111111", margin="sm")
            ]
        },
        text_component("お見積り内容", weight="bold", color="#06C755", margin="md"),
        text_component(estimate_detail)
    ]

    footer = [
        {
            "type": "button",
            "style": "primary",
            "height": "sm",
            "color": "#06C755",
            "action": {
                "type": "postback",
                "label": "修理する",
                "data": f"action=repair&recordid={record_id}",
                "displayText": "修理する"
            }
        },
        {
            "type": "button",
            "style": "secondary",
            "height": "sm",
            "action": {
                "type": "postback",
                "label": "キャンセルする",
                "data": f"action=cancel&recordid={record_id}",
                "displayText": "キャンセルする"
            }
        }
    ]

    return make_flex_card(
        "📄 修理見積が届きました",
        record_id,
        "#06C755",
        "#E8F5E9",
        body,
        footer,
        alt_text="修理のお見積りが届きました"
    )


def build_repair_accept_flex_message(record):
    record_id = getvalue(record, "$id", "")
    name = getvalue(record, "customer_name", "")
    repair_item = make_repair_item_text(record)

    body = [
        text_component(f"{name or 'お客様'} 様", size="md", weight="bold"),
        text_component("修理進行のご回答ありがとうございます。これより修理作業を進めます。", color="#555555"),
        separator(),
        text_component("対象修理品", weight="bold", color="#06C755"),
        text_component(repair_item),
        info_box("現在の状態", STATUS_ORDERED, "#06C755", "#F3FFF7"),
        text_component("完了予定日が決まり次第、LINEでご案内いたします。", color="#555555", margin="md")
    ]

    return make_flex_card(
        "✅ 修理進行を受け付けました",
        record_id,
        "#06C755",
        "#E8F5E9",
        body,
        alt_text="修理進行を受け付けました"
    )


def build_cancel_action_flex_message(record):
    record_id = getvalue(record, "$id", "")
    name = getvalue(record, "customer_name", "")
    repair_item = make_repair_item_text(record)

    body = [
        text_component(f"{name or 'お客様'} 様", size="md", weight="bold"),
        text_component("修理キャンセルのご回答を受け付けました。", color="#555555"),
        separator(),
        text_component("対象修理品", weight="bold", color="#D32F2F"),
        text_component(repair_item),
        {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#FFF5F5",
            "cornerRadius": "12px",
            "paddingAll": "14px",
            "margin": "md",
            "contents": [
                text_component("今後の対応を選択してください", weight="bold", color="#D32F2F"),
                text_component("お預かりしている修理品について、店舗引取・返送・処分のいずれかを選択してください。", margin="sm")
            ]
        }
    ]

    footer = [
        {
            "type": "button",
            "style": "primary",
            "height": "sm",
            "color": "#1565C0",
            "action": {
                "type": "postback",
                "label": "店舗引取",
                "data": f"action=cancel_store&recordid={record_id}",
                "displayText": "店舗引取"
            }
        },
        {
            "type": "button",
            "style": "secondary",
            "height": "sm",
            "action": {
                "type": "postback",
                "label": "返送",
                "data": f"action=cancel_return&recordid={record_id}",
                "displayText": "返送"
            }
        },
        {
            "type": "button",
            "style": "secondary",
            "height": "sm",
            "action": {
                "type": "postback",
                "label": "処分",
                "data": f"action=cancel_dispose&recordid={record_id}",
                "displayText": "処分"
            }
        }
    ]

    return make_flex_card(
        "❌ キャンセルを受け付けました",
        record_id,
        "#D32F2F",
        "#FFEBEE",
        body,
        footer,
        alt_text="キャンセル後の対応を選択してください"
    )


def build_store_pickup_flex_message(record):
    record_id = getvalue(record, "$id", "")
    name = getvalue(record, "customer_name", "")
    repair_item = make_repair_item_text(record)

    body = [
        text_component(f"{name or 'お客様'} 様", size="md", weight="bold"),
        text_component("大変お待たせいたしました。修理品のお渡し準備が整いました。", color="#555555"),
        separator(),
        text_component("対象修理品", weight="bold", color="#1976D2"),
        text_component(repair_item),
        {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#F2F8FF",
            "cornerRadius": "12px",
            "paddingAll": "14px",
            "margin": "md",
            "contents": [
                text_component("ご来店時のお願い", weight="bold", color="#1976D2"),
                text_component("このLINE画面、または受付番号をスタッフへお見せください。", margin="sm")
            ]
        }
    ]

    return make_flex_card(
        "✅ 修理が完了しました",
        record_id,
        "#1976D2",
        "#E3F2FD",
        body,
        alt_text="修理が完了しました"
    )


def build_shipping_flex_message(record):
    record_id = getvalue(record, "$id", "")
    name = getvalue(record, "customer_name", "")
    tracking = getvalue(record, "okurijobango", "")
    repair_item = make_repair_item_text(record)

    body = [
        text_component(f"{name or 'お客様'} 様", size="md", weight="bold"),
        text_component("修理作業が完了し、修理品を発送いたしました。", color="#555555"),
        separator(),
        text_component("対象修理品", weight="bold", color="#6A1B9A"),
        text_component(repair_item),
        info_box("お問い合わせ送り状番号", tracking or "未入力", "#6A1B9A", "#FAF2FF"),
        text_component("到着までもうしばらくお待ちください。", color="#555555", margin="md")
    ]

    return make_flex_card(
        "🚚 修理品を発送しました",
        record_id,
        "#6A1B9A",
        "#F3E5F5",
        body,
        alt_text="修理品を発送しました"
    )


def build_cancel_store_action_done_flex_message(record, action_label):
    record_id = getvalue(record, "$id", "")
    name = getvalue(record, "customer_name", "")
    repair_item = make_repair_item_text(record)

    if action_label == "処分":
        title = "❌ 店舗処分で承りました"
        color = "#D32F2F"
        bg = "#FFF5F5"
        body_text = "お預かりしている修理品は、当店にて適切に処分いたします。"
        status_text = STATUS_CANCEL_DISPOSE
    elif action_label == "返送":
        title = "🚚 返送で承りました"
        color = "#6A1B9A"
        bg = "#FAF2FF"
        body_text = "お預かりしている修理品は、返送対応として進めます。"
        status_text = STATUS_CANCEL_RETURN
    else:
        title = "🏬 店舗引取で承りました"
        color = "#1565C0"
        bg = "#F2F8FF"
        body_text = "お預かりしている修理品は、店舗引取としてお渡し準備を進めます。"
        status_text = STATUS_CANCEL_STORE

    body = [
        text_component(f"{name or 'お客様'} 様", size="md", weight="bold"),
        text_component(body_text, color="#555555"),
        separator(),
        text_component("対象修理品", weight="bold", color=color),
        text_component(repair_item),
        info_box("現在の状態", status_text, color, bg)
    ]

    return make_flex_card(
        title,
        record_id,
        color,
        "#FFFFFF",
        body,
        alt_text=f"{action_label}で承りました"
    )


def build_notify_quick_replies(record_id, status):
    items = []

    if status == STATUS_ESTIMATE or "見積" in status:
        items.append(
            quick_reply_postback(
                "修理する",
                f"action=repair&recordid={record_id}",
                "修理する"
            )
        )
        items.append(
            quick_reply_postback(
                "キャンセル",
                f"action=cancel&recordid={record_id}",
                "キャンセル"
            )
        )

    return items


# =========================
# ルーティング
# =========================

@app.route("/")
def index():
    return "LINE Kintone App is running."


@app.route("/form")
def form():
    return render_template("form.html")


@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json(force=True)

    lineuserid = data.get("lineuserid", "")
    name = data.get("name", "")
    phone = data.get("phone", "")

    maker = data.get("maker", "")
    makerother = data.get("makerother", "")
    model = data.get("model", "")
    serial = data.get("serial", "")

    issue = data.get("issue", "")
    issueother = data.get("issueother", "")
    symptomother = data.get("symptomother", "")

    uketorihouhou = data.get("uketorihouhou", "")
    shukajusho = data.get("shukajusho", "")
    shukakiboubi = data.get("shukakiboubi", "")
    shukakiboujikan = data.get("shukakiboujikan", "")

    sameaddress = data.get("sameaddress", "")
    henkyakuhouhou = data.get("henkyakuhouhou", "")
    henkyakujusho = data.get("henkyakujusho", "")

    coupon = data.get("coupon", "")
    kiyakuagree = data.get("kiyakuagree", "")

    notify_url = f"{PUBLIC_BASE_URL}/notify?user={lineuserid}"

    record = {
        "lineid": make_field(lineuserid),
        "customer_name": make_field(name),
        "phone": make_field(phone),

        "maker": make_field(maker),
        "makerother": make_field(makerother),
        "model": make_field(model),
        "serial": make_field(serial),

        "issue": make_field(issue),
        "issueother": make_field(issueother),
        "symptomother": make_field(symptomother),

        "uketorihouhou": make_field(uketorihouhou),
        "shukajusho": make_field(shukajusho),
        "shukakiboubi": make_field(shukakiboubi),
        "shukakiboujikan": make_field(shukakiboujikan),

        "sameaddress": make_field(sameaddress),
        "henkyakuhouhou": make_field(henkyakuhouhou),
        "henkyakujusho": make_field(henkyakujusho),

        "coupon": make_field(coupon),
        "kiyakuagree": make_field(kiyakuagree),

        "notifyurl": make_field(notify_url),
        "ドロップダウン": make_field(STATUS_RECEIVED)
    }

    res = add_kintone_record(record)

    if not res.ok:
        return res.text, 500

    result = res.json()
    record_id = result.get("id", "")

    receipt_card = build_receipt_flex_message(record_id, name)

    if uketorihouhou == "集荷依頼・LINEで位置情報を送る":
        pickup_card = build_pickup_location_request_flex_message(record_id, name)
        send_line_push_messages(lineuserid, [receipt_card, pickup_card])
    else:
        send_line_push_messages(lineuserid, [receipt_card])

    return "OK", 200


@app.route("/notify", methods=["GET", "OPTIONS"])
def notify():
    if request.method == "OPTIONS":
        return "", 204

    user_id = request.args.get("user", "")
    record_id = request.args.get("recordid", "") or request.args.get("id", "")

    if not user_id and not record_id:
        return "user または recordid が必要です", 400

    record = None

    if record_id:
        record = get_kintone_record(record_id)
    else:
        records = get_records_by_lineid(user_id, limit=1)
        if records:
            record = records[0]
            record_id = getvalue(record, "$id", "")

    if not record:
        return "対象レコードが見つかりません", 404

    if not user_id:
        user_id = getvalue(record, "lineid", "")

    if not user_id:
        return "LINEユーザーIDがありません", 400

    status = getvalue(record, "ドロップダウン", "")
    message = build_notify_message(record)
    past_message = getvalue(record, "notifymessage", "")

    if past_message.strip() == message.strip():
        print("重複通知スキップ:", status)
        return f"既に同じ内容を通知済み: {status}", 200

    if status == STATUS_ESTIMATE or "見積" in status:
        flex_message = build_estimate_flex_message(record)
        line_res = send_line_push_messages(user_id, [flex_message])

    elif status == STATUS_DONE_SHIP:
        flex_message = build_shipping_flex_message(record)
        line_res = send_line_push_messages(user_id, [flex_message])

    elif status == STATUS_DONE_STORE:
        flex_message = build_store_pickup_flex_message(record)
        line_res = send_line_push_messages(user_id, [flex_message])

    else:
        quick_reply_items = build_notify_quick_replies(record_id, status)
        line_res = send_line_push(
            user_id,
            message,
            quick_reply_items if quick_reply_items else None
        )

    if not line_res.ok:
        return line_res.text, 500

    update_notify_history(record_id, message)

    return f"送信完了: {status}", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_json(force=True)
    print("Webhook受信:", body)

    events = body.get("events", [])

    for event in events:
        event_type = event.get("type")
        source = event.get("source", {})
        user_id = source.get("userId", "")
        reply_token = event.get("replyToken", "")

        if event_type == "message":
            message = event.get("message", {})
            message_type = message.get("type")

            if message_type == "text":
                text = message.get("text", "").strip()
                print("受信メッセージ:", text)
                print("受信userId:", user_id)

                if text == "修理問い合わせ":
                    handle_repair_inquiry(user_id, reply_token)
                elif text.isdigit():
                    handle_record_number_inquiry(text, reply_token)
                else:
                    send_line_reply(
                        reply_token,
                        "メッセージありがとうございます。\n修理状況を確認する場合は「修理問い合わせ」と送信してください。"
                    )

            elif message_type == "location":
                handle_location_message(user_id, reply_token, message)

        elif event_type == "postback":
            postback = event.get("postback", {})
            data = html.unescape(postback.get("data", ""))
            print("Postback受信:", data)
            handle_postback(user_id, reply_token, data)

    return "OK", 200


# =========================
# Webhook処理
# =========================

def handle_repair_inquiry(user_id, reply_token):
    records = get_records_by_lineid(user_id, limit=10)

    if not records:
        send_line_reply(
            reply_token,
            "現在、このLINEアカウントに紐づく修理受付は見つかりませんでした。"
        )
        return

    if len(records) == 1:
        text = build_status_text(records[0])
        send_line_reply(reply_token, text)
        return

    text = "複数の修理受付があります。\n確認したい受付を選んでください。"

    quick_items = []

    for record in records[:10]:
        record_id = getvalue(record, "$id", "")
        maker = getvalue(record, "maker", "")
        model = getvalue(record, "model", "")
        label = f"{record_id} {maker} {model}".strip()

        if not label:
            label = f"受付番号 {record_id}"

        if len(label) > 20:
            label = label[:20]

        quick_items.append(
            quick_reply_postback(
                label,
                f"action=checkstatus&recordid={record_id}",
                label
            )
        )

    send_line_reply(reply_token, text, quick_items)


def handle_record_number_inquiry(record_number, reply_token):
    record = get_kintone_record(record_number)

    if not record:
        send_line_reply(
            reply_token,
            "指定された受付番号の修理受付が見つかりませんでした。"
        )
        return

    text = build_status_text(record)
    send_line_reply(reply_token, text)


def handle_location_message(user_id, reply_token, message):
    address = message.get("address", "")
    title = message.get("title", "")
    latitude = message.get("latitude", "")
    longitude = message.get("longitude", "")

    print("位置情報受信 title:", title)
    print("位置情報受信 address:", address)
    print("位置情報受信 latitude:", latitude)
    print("位置情報受信 longitude:", longitude)

    location_text = address or title or "位置情報"

    records = get_records_by_lineid(user_id, limit=5)

    if not records:
        send_line_reply(
            reply_token,
            "位置情報を受信しましたが、紐づく修理受付が見つかりませんでした。先に修理受付フォームを送信してください。"
        )
        return

    target_record = records[0]
    record_id = getvalue(target_record, "$id", "")

    shukabasho = getvalue(target_record, "shukabasho", "")
    henkyakuhouhou = getvalue(target_record, "henkyakuhouhou", "")
    henkyakubasho = getvalue(target_record, "henkyakubasho", "")
    sameaddress = getvalue(target_record, "sameaddress", "")

    if not shukabasho:
        res = update_location_pickup(record_id, location_text, latitude, longitude)

        if res.ok:
            if sameaddress == "はい" or henkyakuhouhou == "集荷場所と同じ":
                send_line_reply(
                    reply_token,
                    "集荷場所を登録しました。\n返却場所は集荷場所と同じとして登録しています。"
                )
            elif henkyakuhouhou == "LINEで位置情報を送る":
                updated_record = get_kintone_record(record_id)

                if updated_record:
                    return_card = build_return_location_request_flex_message(updated_record)
                    send_line_reply_messages(reply_token, [return_card])
                else:
                    send_line_reply(
                        reply_token,
                        "集荷場所を登録しました。\n続いて返却場所の位置情報を送信してください。",
                        [quick_reply_location("📍 返却場所を送る")]
                    )
            else:
                send_line_reply(reply_token, "集荷場所を登録しました。")
        else:
            send_line_reply(
                reply_token,
                "位置情報の登録に失敗しました。お手数ですが店舗までご連絡ください。"
            )
        return

    if henkyakuhouhou == "LINEで位置情報を送る" and not henkyakubasho:
        res = update_location_return(record_id, location_text, latitude, longitude)

        if res.ok:
            send_line_reply(
                reply_token,
                "返却場所を登録しました。\nご協力ありがとうございます。"
            )
        else:
            send_line_reply(
                reply_token,
                "返却場所の登録に失敗しました。お手数ですが店舗までご連絡ください。"
            )
        return

    if henkyakuhouhou == "LINEで位置情報を送る" and henkyakubasho:
        send_line_reply(
            reply_token,
            "集荷場所と返却場所はすでに登録済みです。\n変更が必要な場合は店舗までご連絡ください。"
        )
        return

    if sameaddress == "はい" or henkyakuhouhou == "集荷場所と同じ":
        send_line_reply(
            reply_token,
            "集荷場所と返却場所はすでに登録済みです。\n変更が必要な場合は店舗までご連絡ください。"
        )
        return

    res = update_location_pickup(record_id, location_text, latitude, longitude)

    if res.ok:
        send_line_reply(reply_token, "位置情報を登録しました。")
    else:
        send_line_reply(
            reply_token,
            "位置情報の登録に失敗しました。お手数ですが店舗までご連絡ください。"
        )


def handle_postback(user_id, reply_token, data):
    parsed = parse_qs(data)

    action = parsed.get("action", [""])[0]
    record_id = parsed.get("recordid", [""])[0]

    if not action or not record_id:
        send_line_reply(reply_token, "操作内容を確認できませんでした。")
        return

    record_before = get_kintone_record(record_id)

    if not record_before:
        send_line_reply(reply_token, "対象の修理受付が見つかりませんでした。")
        return

    current_answer = getvalue(record_before, "shurikahikaito", "")
    current_cancel_action = getvalue(record_before, "canceltaio", "")
    current_status = getvalue(record_before, "ドロップダウン", "")

    if action == "checkstatus":
        text = build_status_text(record_before)
        send_line_reply(reply_token, text)
        return

    if action == "repair":
        if current_cancel_action:
            send_line_reply(
                reply_token,
                already_decided_text(current_answer, current_cancel_action)
            )
            return

        if current_answer == "キャンセル":
            send_line_reply(
                reply_token,
                "この修理受付は、すでに「キャンセル」で受付済みです。\n変更が必要な場合は店舗までご連絡ください。"
            )
            return

        if current_answer == "修理する":
            send_line_reply(
                reply_token,
                "この修理受付は、すでに「修理する」で受付済みです。\n変更が必要な場合は店舗までご連絡ください。"
            )
            return

        if is_cancel_status(current_status):
            send_line_reply(
                reply_token,
                "この修理受付は、すでに中止対応済みです。\n変更が必要な場合は店舗までご連絡ください。"
            )
            return

        res = update_repair_answer(record_id, "修理する")

        if not res.ok:
            send_line_reply(
                reply_token,
                "回答の登録に失敗しました。お手数ですが店舗までご連絡ください。"
            )
            return

        record_after = get_kintone_record(record_id)

        if not record_after:
            send_line_reply(
                reply_token,
                "修理進行は受け付けましたが、対象レコードの取得に失敗しました。"
            )
            return

        repair_accept_card = build_repair_accept_flex_message(record_after)

        send_line_reply_messages(
            reply_token,
            [repair_accept_card]
        )
        return

    if action == "cancel":
        if current_cancel_action:
            send_line_reply(
                reply_token,
                already_decided_text(current_answer, current_cancel_action)
            )
            return

        if current_answer == "修理する":
            send_line_reply(
                reply_token,
                "この修理受付は、すでに「修理する」で受付済みです。\n変更が必要な場合は店舗までご連絡ください。"
            )
            return

        if current_answer == "キャンセル":
            cancel_card = build_cancel_action_flex_message(record_before)
            send_line_reply_messages(
                reply_token,
                [cancel_card]
            )
            return

        if is_ordered_status(current_status) or is_done_status(current_status) or is_complete_status(current_status):
            send_line_reply(
                reply_token,
                "この修理受付は、すでに修理進行中または完了済みです。\n変更が必要な場合は店舗までご連絡ください。"
            )
            return

        res = update_repair_answer(record_id, "キャンセル")

        if not res.ok:
            send_line_reply(
                reply_token,
                "キャンセル回答の登録に失敗しました。お手数ですが店舗までご連絡ください。"
            )
            return

        record_after = get_kintone_record(record_id)

        if not record_after:
            send_line_reply(
                reply_token,
                "キャンセルは受け付けましたが、対象レコードの取得に失敗しました。"
            )
            return

        cancel_card = build_cancel_action_flex_message(record_after)

        send_line_reply_messages(
            reply_token,
            [cancel_card]
        )
        return

    if action in ["cancel_store", "cancel_return", "cancel_dispose"]:
        if current_answer == "修理する":
            send_line_reply(
                reply_token,
                "この修理受付は、すでに「修理する」で受付済みです。\n変更が必要な場合は店舗までご連絡ください。"
            )
            return

        if current_cancel_action:
            send_line_reply(
                reply_token,
                f"この修理受付は、すでに「{current_cancel_action}」で登録済みです。\n変更が必要な場合は店舗までご連絡ください。"
            )
            return

        if current_answer != "キャンセル":
            send_line_reply(
                reply_token,
                "先に「キャンセルする」を選択してください。\n変更が必要な場合は店舗までご連絡ください。"
            )
            return

        if action == "cancel_store":
            selected_action = "店舗引取"
        elif action == "cancel_return":
            selected_action = "返送"
        else:
            selected_action = "処分"

        res = update_cancel_action(record_id, selected_action)

        if not res.ok:
            send_line_reply(reply_token, "登録に失敗しました。")
            return

        record_after = get_kintone_record(record_id)

        if record_after:
            card = build_cancel_store_action_done_flex_message(record_after, selected_action)
            send_line_reply_messages(reply_token, [card])
        else:
            send_line_reply(
                reply_token,
                f"{selected_action}で承りました。"
            )
        return

    send_line_reply(reply_token, "未対応の操作です。")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
