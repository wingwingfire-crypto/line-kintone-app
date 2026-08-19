import os
import json
import html
import requests
from datetime import datetime, timezone, timedelta
from urllib.parse import parse_qs
from flask import Flask, request, render_template

app = Flask(__name__)


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "https://9oh3c.cybozu.com"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN") or os.environ.get("LINE_TOKEN")
KINTONE_API_TOKEN = os.environ.get("KINTONE_API_TOKEN")
CUSTOMER_KINTONE_API_TOKEN = os.environ.get("CUSTOMER_KINTONE_API_TOKEN")

KINTONE_BASE = "https://9oh3c.cybozu.com"
KINTONE_APP_ID = 6
CUSTOMER_KINTONE_APP_ID = 4

PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "https://line-kintone-app.onrender.com")

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
STATUS_CANCEL_GENERIC = "🔴中止"
STATUS_CANCEL_STORE = "🔴中止(店舗引取)"
STATUS_CANCEL_RETURN = "🔴中止(返送)"
STATUS_CANCEL_DISPOSE = "❌中止(店舗処分)"

OLD_STATUS_ORDERED = "📦受注(部品待ち)"
OLD_STATUS_DONE = "✉️修理完了連絡済"
OLD_STATUS_COMPLETE = "🟢完了(精算済)"
OLD_STATUS_CANCEL_RETURN = "🔴中止(返却)"
OLD_STATUS_CANCEL_DISPOSE = "❌中止(処分)"

JST = timezone(timedelta(hours=9))


def now_utc_for_kintone():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_jst_for_kintone_date():
    return datetime.now(JST).strftime("%Y-%m-%d")


def kintone_headers():
    return {"X-Cybozu-API-Token": KINTONE_API_TOKEN, "Content-Type": "application/json"}


def customer_kintone_headers():
    return {"X-Cybozu-API-Token": CUSTOMER_KINTONE_API_TOKEN, "Content-Type": "application/json"}


def line_headers():
    return {"Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}", "Content-Type": "application/json"}


def getvalue(record, field_code, default=""):
    try:
        field = record.get(field_code)
        if not field:
            return default
        value = field.get("value")
        return default if value is None else value
    except Exception:
        return default


def make_field(value):
    return {"value": value if value is not None else ""}


def escape_kintone_query_value(value):
    return str(value or "").replace("\\", "\\\\").replace('"', '\\"')


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
    return value[:limit] + "..." if len(value) > limit else value


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
    return " / ".join(parts) if parts else "修理品情報 未入力"


def normalize_uketorihouhou_for_kintone(raw_uketorihouhou):
    if raw_uketorihouhou == "店舗持ち込み":
        return "店舗持ち込み"
    if raw_uketorihouhou.startswith("集荷依頼"):
        return "集荷依頼"
    return raw_uketorihouhou


def is_ordered_status(status):
    return status in [STATUS_ORDERED, OLD_STATUS_ORDERED] or "受注" in status


def is_done_status(status):
    return status in [STATUS_DONE_STORE, STATUS_DONE_SHIP, OLD_STATUS_DONE] or "修理完了連絡済" in status


def is_complete_status(status):
    return status in [STATUS_COMPLETE, OLD_STATUS_COMPLETE] or "完了" in status


def is_cancel_status(status):
    return status in [STATUS_CANCEL_GENERIC, STATUS_CANCEL_STORE, STATUS_CANCEL_RETURN, STATUS_CANCEL_DISPOSE, OLD_STATUS_CANCEL_RETURN, OLD_STATUS_CANCEL_DISPOSE] or "中止" in status


def post_json(url, payload, headers):
    return requests.post(url, headers=headers, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"))


# =========================
# LINE送信
# =========================

def send_line_reply(reply_token, text, quick_reply_items=None):
    message = {"type": "text", "text": text}
    if quick_reply_items:
        message["quickReply"] = {"items": quick_reply_items}
    res = post_json(LINE_REPLY_URL, {"replyToken": reply_token, "messages": [message]}, line_headers())
    print("LINE返信:", res.text)
    return res


def send_line_reply_messages(reply_token, messages):
    res = post_json(LINE_REPLY_URL, {"replyToken": reply_token, "messages": messages}, line_headers())
    print("LINE複数返信:", res.text)
    return res


def send_line_push(user_id, text, quick_reply_items=None):
    message = {"type": "text", "text": text}
    if quick_reply_items:
        message["quickReply"] = {"items": quick_reply_items}
    res = post_json(LINE_PUSH_URL, {"to": user_id, "messages": [message]}, line_headers())
    print("LINE送信:", res.text)
    return res


def send_line_push_messages(user_id, messages):
    res = post_json(LINE_PUSH_URL, {"to": user_id, "messages": messages}, line_headers())
    print("LINE複数送信:", res.text)
    return res


def quick_reply_location(label="📍 位置情報を送る"):
    return {"type": "action", "action": {"type": "location", "label": label}}


def quick_reply_postback(label, data, display_text=None):
    action = {"type": "postback", "label": label, "data": data}
    if display_text:
        action["displayText"] = display_text
    return {"type": "action", "action": action}


# =========================
# Kintone 修理管理アプリ操作
# =========================

def add_kintone_record(record):
    res = post_json(KINTONE_RECORD_URL, {"app": KINTONE_APP_ID, "record": record}, kintone_headers())
    print("Kintone登録:", res.text)
    return res


def get_kintone_record(record_id):
    res = requests.get(KINTONE_RECORD_URL, headers={"X-Cybozu-API-Token": KINTONE_API_TOKEN}, params={"app": KINTONE_APP_ID, "id": record_id})
    print("単体取得ステータス:", res.status_code)
    print("単体取得本文:", res.text)
    return res.json().get("record") if res.ok else None


def get_records_by_lineid(line_user_id, limit=10):
    safe_user_id = escape_kintone_query_value(line_user_id)
    query = f'lineid = "{safe_user_id}" order by $id desc limit {limit}'
    res = requests.get(KINTONE_RECORDS_URL, headers={"X-Cybozu-API-Token": KINTONE_API_TOKEN}, params={"app": KINTONE_APP_ID, "query": query})
    print("複数取得ステータス:", res.status_code)
    print("複数取得本文:", res.text)
    return res.json().get("records", []) if res.ok else []


def update_kintone_record(record_id, fields):
    res = requests.put(KINTONE_RECORD_URL, headers=kintone_headers(), data=json.dumps({"app": KINTONE_APP_ID, "id": record_id, "record": fields}, ensure_ascii=False).encode("utf-8"))
    print("Kintone更新:", res.text)
    return res


# =========================
# Kintone 顧客リストアプリ操作
# =========================

def customer_api_enabled():
    if not CUSTOMER_KINTONE_API_TOKEN:
        print("顧客リスト連携スキップ: CUSTOMER_KINTONE_API_TOKEN が未設定です。")
        return False
    return True


def get_customer_record_by_lineid_or_phone(lineid, phone):
    if not customer_api_enabled():
        return None

    query_parts = []
    if lineid:
        query_parts.append(f'lineid = "{escape_kintone_query_value(lineid)}"')
    if phone:
        query_parts.append(f'phone = "{escape_kintone_query_value(phone)}"')
    if not query_parts:
        return None

    query = " or ".join(query_parts) + " order by $id desc limit 1"
    res = requests.get(KINTONE_RECORDS_URL, headers={"X-Cybozu-API-Token": CUSTOMER_KINTONE_API_TOKEN}, params={"app": CUSTOMER_KINTONE_APP_ID, "query": query})
    print("顧客リスト検索ステータス:", res.status_code)
    print("顧客リスト検索本文:", res.text)
    if not res.ok:
        return None
    records = res.json().get("records", [])
    return records[0] if records else None


def add_customer_record(lineid, name, phone):
    if not customer_api_enabled():
        return None
    record = {
        "lineid": make_field(lineid),
        "customer_name": make_field(name),
        "phone": make_field(phone),
        "last_accept_date": make_field(today_jst_for_kintone_date()),
        "accept_count": make_field(1)
    }
    res = post_json(KINTONE_RECORD_URL, {"app": CUSTOMER_KINTONE_APP_ID, "record": record}, customer_kintone_headers())
    print("顧客リスト新規登録:", res.text)
    return res


def update_customer_record(customer_record, lineid, name, phone):
    if not customer_api_enabled():
        return None
    customer_record_id = getvalue(customer_record, "$id", "")
    current_count = getvalue(customer_record, "accept_count", 0)
    try:
        next_count = int(current_count or 0) + 1
    except Exception:
        next_count = 1

    fields = {
        "lineid": make_field(lineid),
        "customer_name": make_field(name),
        "phone": make_field(phone),
        "last_accept_date": make_field(today_jst_for_kintone_date()),
        "accept_count": make_field(next_count)
    }
    res = requests.put(KINTONE_RECORD_URL, headers=customer_kintone_headers(), data=json.dumps({"app": CUSTOMER_KINTONE_APP_ID, "id": customer_record_id, "record": fields}, ensure_ascii=False).encode("utf-8"))
    print("顧客リスト更新:", res.text)
    return res


def upsert_customer_record(lineid, name, phone):
    try:
        if not customer_api_enabled():
            return
        customer_record = get_customer_record_by_lineid_or_phone(lineid, phone)
        if customer_record:
            update_customer_record(customer_record, lineid, name, phone)
        else:
            add_customer_record(lineid, name, phone)
    except Exception as error:
        print("顧客リスト連携エラー:", repr(error))


# =========================
# 修理住所更新
# =========================

def update_location_pickup(record_id, address, latitude, longitude):
    map_url = f"https://www.google.com/maps?q={latitude},{longitude}"
    fields = {
        "shukajusho": make_field(address),
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
                "henkyakujusho": make_field(address),
                "henkyakubasho": make_field(address),
                "henkyakuido": make_field(str(latitude)),
                "henkyakukeido": make_field(str(longitude)),
                "henkyakumapurl": make_field(map_url)
            })
    return update_kintone_record(record_id, fields)


def update_location_return(record_id, address, latitude, longitude):
    map_url = f"https://www.google.com/maps?q={latitude},{longitude}"
    return update_kintone_record(record_id, {
        "henkyakujusho": make_field(address),
        "henkyakubasho": make_field(address),
        "henkyakuido": make_field(str(latitude)),
        "henkyakukeido": make_field(str(longitude)),
        "henkyakumapurl": make_field(map_url)
    })


def update_notify_history(record_id, message):
    return update_kintone_record(record_id, {"lastnotify": make_field(now_utc_for_kintone()), "notifymessage": make_field(message)})


def update_repair_answer(record_id, answer):
    fields = {"shurikahikaito": make_field(answer)}
    if answer == "修理する":
        fields["ドロップダウン"] = make_field(STATUS_ORDERED)
    return update_kintone_record(record_id, fields)


def update_cancel_action(record_id, action):
    status = STATUS_CANCEL_DISPOSE if action == "処分" else STATUS_CANCEL_RETURN if action == "返送" else STATUS_CANCEL_STORE
    return update_kintone_record(record_id, {"canceltaio": make_field(action), "ドロップダウン": make_field(status)})


def already_decided_text(current_answer, current_cancel_action):
    if current_cancel_action:
        return f"この修理受付は、すでに「{current_cancel_action}」で登録済みです。\n変更が必要な場合は店舗までご連絡ください。"
    if current_answer == "修理する":
        return "この修理受付は、すでに「修理する」で受付済みです。\n変更が必要な場合は店舗までご連絡ください。"
    if current_answer == "キャンセル":
        return "この修理受付は、すでに「キャンセル」で受付済みです。\n変更が必要な場合は店舗までご連絡ください。"
    return "この修理受付は、すでに対応済みです。\n変更が必要な場合は店舗までご連絡ください。"


# =========================
# 通知文面
# =========================

def record_id_text(record):
    return getvalue(record, "$id", "") or getvalue(record, "レコード番号", "")


def build_notify_message(record):
    record_id = record_id_text(record)
    status = getvalue(record, "ドロップダウン", "")
    name = getvalue(record, "customer_name", "")

    if status == STATUS_RECEIVED:
        return f"修理のお申込みを受け付けました\n受付番号{record_id}\n{name}様\nお申し込みありがとうございます。ただいま内容を確認しております。\n確認・準備が整い次第、次のご案内をお送りいたしますので少々お待ちください。"

    if status == STATUS_PICKUP_REQUESTED:
        return f"受付番号{record_id}\n修理品の集荷手配が完了しました\n指定の日時に配送業者が伺いますので、修理品のご準備をお願いいたします。"

    if status == STATUS_ESTIMATE or "見積" in status:
        return f"受付番号{record_id}\n修理のお見積りが届きました\nお見積り金額：{getvalue(record, 'mitsumorikingaku', '') or '未入力'}\nお見積り内容：{getvalue(record, 'mitsumorinaiyo', '') or '未入力'}"

    if status == STATUS_ORDERED or "受注" in status:
        return f"受付番号{record_id}\n修理作業を開始いたします\n修理実行のご連絡ありがとうございます。\nこれより修理作業に入らせていただきます。完了まで今しばらくお待ちください。\n受取方法・お届け先の変更について\n受取方法の変更や、集荷場所・発送先の変更がある場合は店舗へお電話にてご連絡をお願いいたします。\n上中野店 TEL：086-230-6551 / 受付時間：7:00〜19:00"

    if status == STATUS_DONE_STORE:
        return f"受付番号{record_id}\n修理が完了いたしました\n大変お待たせいたしました。修理作業が完了し、店頭にてお渡しの準備が整っております。\nお手数ですが、ご都合の良いタイミングでご来店をお願いいたします。\nご来店の際は、本LINE画面または受付番号をスタッフへご提示ください。"

    if status == STATUS_DONE_SHIP:
        return f"受付番号{record_id}\n修理が完了いたしました\n大変お待たせいたしました。修理作業が完了し、修理品のお荷物発送が完了いたしました。\n到着までもうしばらくお待ちください。\nこの度は修理サービスをご利用いただき、誠にありがとうございました。"

    if status == STATUS_COMPLETE:
        return f"受付番号{record_id}\nこの修理は完了済となっております。"

    if status == STATUS_CANCEL_GENERIC:
        return f"受付番号{record_id}\n修理中止のお手続きについて\n修理中止のご連絡を承りました。\n利用規約の通り、見積料1,500円を頂戴いたします。\nお預かりした修理品の【店舗引取・ご返送・当店にて処分】のご判断をお知らせください。\nご指定いただいた内容に基づき、手続きを進めさせていただきます。"

    if status == STATUS_CANCEL_STORE:
        return f"受付番号{record_id}\n店舗にて返却のご準備が整いました\n修理中止のご連絡を承りました。\nお預かりしております修理品は、店頭にてお渡しの準備が整っております。\nご来店の際は、本LINE画面または受付番号をスタッフへご提示ください。\nご来店を心よりお待ちしております。"

    if status == STATUS_CANCEL_RETURN:
        return f"受付番号{record_id}\n修理品の返送手配を行っております\n修理中止のご連絡を承りました。\nお預かりしております修理品は、順次発送手配を進めております。\n商品は着払いでのご返送となりますので、到着時に配送業者へ送料のお支払いをお願いいたします。発送が完了しましたら改めてご連絡いたします。"

    if status == STATUS_CANCEL_DISPOSE:
        return f"受付番号{record_id}\n修理品の廃棄処分を承りました\n修理中止および廃棄処分のご了承をいただき、ありがとうございます。\nお預かりしております修理品につきましては、当店にて責任を持って適切に処分させていただきます。\nこれにてお手続きは完了となります。またのご利用を心よりお待ちしております。"

    return build_status_text(record)


def build_status_text(record):
    record_id = record_id_text(record)
    status = getvalue(record, "ドロップダウン", "未設定")
    text = f"""【修理進捗状況のご案内】

受付番号：{record_id}
現在のステータス：{status}

■ お客様名
{getvalue(record, 'customer_name', '')}

■ 修理品情報
メーカー：{getvalue(record, 'maker', '') or '未入力'}
型番：{getvalue(record, 'model', '') or '未入力'}
機番：{getvalue(record, 'serial', '') or '未入力'}

■ 故障内容
{getvalue(record, 'issue', '') or '未入力'}

■ 受け渡し方法
{getvalue(record, 'uketorihouhou', '') or '未入力'}
"""
    shukajusho = getvalue(record, "shukajusho", "")
    henkyakujusho = getvalue(record, "henkyakujusho", "")
    if shukajusho:
        text += f"\n■ 集荷住所\n{shukajusho}\n"
    if henkyakujusho:
        text += f"\n■ 返却住所\n{henkyakujusho}\n"
    if "見積" in status:
        text += f"\n■ お見積り金額\n{getvalue(record, 'mitsumorikingaku', '') or '未入力'}\n\n■ お見積り内容\n{getvalue(record, 'mitsumorinaiyo', '') or '未入力'}\n\n修理を進めるか、キャンセルされるかをご回答ください。\n"
    tracking = getvalue(record, "okurijobango", "")
    if tracking:
        text += f"\n■ お問い合わせ送り状番号\n{tracking}\n"
    due_date = getvalue(record, "kanryoyoteibi", "")
    if due_date:
        text += f"\n■ 修理完了予定日\n{due_date}\n"
    return text


# =========================
# Flex Message
# =========================

def tc(text, size="sm", weight=None, color=None, margin=None):
    item = {"type": "text", "text": text, "size": size, "wrap": True}
    if weight:
        item["weight"] = weight
    if color:
        item["color"] = color
    if margin:
        item["margin"] = margin
    return item


def paragraph_box(lines, bg="#FFFFFF", color="#333333"):
    contents = []
    for line in lines:
        if not line:
            continue
        contents.append(tc(line, size="sm", color=color, margin="sm" if contents else None))
    return {
        "type": "box",
        "layout": "vertical",
        "backgroundColor": bg,
        "cornerRadius": "12px",
        "paddingAll": "14px",
        "contents": contents
    }


def info_box(title, value, color, bg):
    return {
        "type": "box",
        "layout": "vertical",
        "backgroundColor": bg,
        "cornerRadius": "12px",
        "paddingAll": "14px",
        "margin": "md",
        "contents": [tc(title, "sm", "bold", color), tc(value, "lg", "bold", None, "sm")]
    }


def make_card(title, record_id, color, sub_color, body, footer=None, alt=None, quick=None):
    msg = {
        "type": "flex",
        "altText": alt or title,
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": color,
                "paddingAll": "16px",
                "contents": [tc(title, "lg", "bold", "#FFFFFF"), tc(f"受付番号：{record_id}", "sm", None, sub_color, "sm")]
            },
            "body": {"type": "box", "layout": "vertical", "spacing": "md", "contents": body}
        }
    }
    if footer:
        msg["contents"]["footer"] = {"type": "box", "layout": "vertical", "spacing": "sm", "contents": footer}
    if quick:
        msg["quickReply"] = {"items": quick}
    return msg


def build_notify_flex_message(record):
    status = getvalue(record, "ドロップダウン", "")

    if status == STATUS_RECEIVED:
        return build_received_notify_card(record)
    if status == STATUS_PICKUP_REQUESTED:
        return build_pickup_requested_notify_card(record)
    if status == STATUS_ESTIMATE or "見積" in status:
        return build_estimate_flex_message(record)
    if status == STATUS_ORDERED or "受注" in status:
        return build_ordered_notify_card(record)
    if status == STATUS_DONE_STORE:
        return build_done_store_notify_card(record)
    if status == STATUS_DONE_SHIP:
        return build_done_ship_notify_card(record)
    if status == STATUS_COMPLETE:
        return build_complete_notify_card(record)
    if status == STATUS_CANCEL_GENERIC:
        return build_cancel_generic_notify_card(record)
    if status == STATUS_CANCEL_STORE:
        return build_cancel_store_notify_card(record)
    if status == STATUS_CANCEL_RETURN:
        return build_cancel_return_notify_card(record)
    if status == STATUS_CANCEL_DISPOSE:
        return build_cancel_dispose_notify_card(record)

    return build_generic_status_card(record)


def build_received_notify_card(record):
    record_id = record_id_text(record)
    name = getvalue(record, "customer_name", "") or "お客様"
    body = [
        tc(f"{name} 様", "md", "bold", "#222222"),
        paragraph_box([
            "お申し込みありがとうございます。",
            "ただいま内容を確認しております。",
            "確認・準備が整い次第、次のご案内をお送りいたしますので少々お待ちください。"
        ], "#F3FFF7")
    ]
    return make_card("修理のお申込みを受け付けました", record_id, "#06C755", "#E8F5E9", body, alt="修理のお申込みを受け付けました")


def build_pickup_requested_notify_card(record):
    record_id = record_id_text(record)
    body = [
        paragraph_box([
            "修理品の集荷手配が完了しました。",
            "指定の日時に配送業者が伺いますので、修理品のご準備をお願いいたします。"
        ], "#F2F8FF")
    ]
    return make_card("修理品の集荷手配が完了しました", record_id, "#1976D2", "#E3F2FD", body, alt="修理品の集荷手配が完了しました")


def build_estimate_flex_message(record):
    record_id = record_id_text(record)
    body = [
        tc(f"{getvalue(record, 'customer_name', '') or 'お客様'} 様", "md", "bold"),
        tc("修理品のお見積りが完了しました。", color="#666666"),
        {"type": "separator", "margin": "md"},
        tc("修理品情報", weight="bold", color="#06C755"),
        tc(f"メーカー：{getvalue(record, 'maker', '') or '未入力'}"),
        tc(f"型番：{getvalue(record, 'model', '') or '未入力'}"),
        tc(f"機番：{getvalue(record, 'serial', '') or '未入力'}"),
        tc("故障内容", weight="bold", color="#06C755", margin="md"),
        tc(shorten_text(getvalue(record, 'issue', ''), 70)),
        info_box("お見積り金額", format_yen(getvalue(record, 'mitsumorikingaku', '')), "#06C755", "#F3FFF7"),
        tc("お見積り内容", weight="bold", color="#06C755", margin="md"),
        tc(shorten_text(getvalue(record, 'mitsumorinaiyo', ''), 80))
    ]
    footer = [
        {"type": "button", "style": "primary", "height": "sm", "color": "#06C755", "action": {"type": "postback", "label": "修理する", "data": f"action=repair&recordid={record_id}", "displayText": "修理する"}},
        {"type": "button", "style": "secondary", "height": "sm", "action": {"type": "postback", "label": "キャンセルする", "data": f"action=cancel&recordid={record_id}", "displayText": "キャンセルする"}}
    ]
    return make_card("修理のお見積りが届きました", record_id, "#06C755", "#E8F5E9", body, footer, "修理のお見積りが届きました")


def build_ordered_notify_card(record):
    record_id = record_id_text(record)
    body = [
        paragraph_box([
            "修理実行のご連絡ありがとうございます。",
            "これより修理作業に入らせていただきます。",
            "完了まで今しばらくお待ちください。"
        ], "#F3FFF7"),
        paragraph_box([
            "【受取方法・お届け先の変更について】",
            "受取方法の変更や、集荷場所・発送先の変更がある場合は、店舗へお電話にてご連絡をお願いいたします。",
            "上中野店 TEL：086-230-6551",
            "受付時間：7:00〜19:00"
        ], "#FFFDF2")
    ]
    return make_card("修理作業を開始いたします", record_id, "#06C755", "#E8F5E9", body, alt="修理作業を開始いたします")


def build_done_store_notify_card(record):
    record_id = record_id_text(record)
    body = [
        paragraph_box([
            "大変お待たせいたしました。",
            "修理作業が完了し、店頭にてお渡しの準備が整っております。",
            "お手数ですが、ご都合の良いタイミングでご来店をお願いいたします。",
            "ご来店の際は、本LINE画面または受付番号をスタッフへご提示ください。"
        ], "#F2F8FF")
    ]
    return make_card("修理が完了いたしました", record_id, "#1976D2", "#E3F2FD", body, alt="修理が完了いたしました")


def build_done_ship_notify_card(record):
    record_id = record_id_text(record)
    body = [
        paragraph_box([
            "大変お待たせいたしました。",
            "修理作業が完了し、修理品のお荷物発送が完了いたしました。",
            "到着までもうしばらくお待ちください。",
            "この度は修理サービスをご利用いただき、誠にありがとうございました。"
        ], "#FAF2FF")
    ]
    return make_card("修理が完了いたしました", record_id, "#6A1B9A", "#F3E5F5", body, alt="修理が完了いたしました")


def build_complete_notify_card(record):
    record_id = record_id_text(record)
    body = [paragraph_box(["この修理は完了済となっております。"], "#F3FFF7")]
    return make_card("この修理は完了済です", record_id, "#06C755", "#E8F5E9", body, alt="この修理は完了済です")


def build_cancel_generic_notify_card(record):
    record_id = record_id_text(record)
    body = [
        paragraph_box([
            "修理中止のご連絡を承りました。",
            "利用規約の通り、見積料1,500円を頂戴いたします。",
            "お預かりした修理品の【店舗引取・ご返送・当店にて処分】のご判断をお知らせください。",
            "ご指定いただいた内容に基づき、手続きを進めさせていただきます。"
        ], "#FFF5F5")
    ]
    return make_card("修理中止のお手続きについて", record_id, "#D32F2F", "#FFEBEE", body, alt="修理中止のお手続きについて")


def build_cancel_store_notify_card(record):
    record_id = record_id_text(record)
    body = [
        paragraph_box([
            "修理中止のご連絡を承りました。",
            "お預かりしております修理品は、店頭にてお渡しの準備が整っております。",
            "ご来店の際は、本LINE画面または受付番号をスタッフへご提示ください。",
            "ご来店を心よりお待ちしております。"
        ], "#F2F8FF")
    ]
    return make_card("店舗にて返却のご準備が整いました", record_id, "#1565C0", "#E3F2FD", body, alt="店舗にて返却のご準備が整いました")


def build_cancel_return_notify_card(record):
    record_id = record_id_text(record)
    body = [
        paragraph_box([
            "修理中止のご連絡を承りました。",
            "お預かりしております修理品は、順次発送手配を進めております。",
            "商品は着払いでのご返送となりますので、到着時に配送業者へ送料のお支払いをお願いいたします。",
            "発送が完了しましたら改めてご連絡いたします。"
        ], "#FAF2FF")
    ]
    return make_card("修理品の返送手配を行っております", record_id, "#6A1B9A", "#F3E5F5", body, alt="修理品の返送手配を行っております")


def build_cancel_dispose_notify_card(record):
    record_id = record_id_text(record)
    body = [
        paragraph_box([
            "修理中止および廃棄処分のご了承をいただき、ありがとうございます。",
            "お預かりしております修理品につきましては、当店にて責任を持って適切に処分させていただきます。",
            "これにてお手続きは完了となります。",
            "またのご利用を心よりお待ちしております。"
        ], "#FFF5F5")
    ]
    return make_card("修理品の廃棄処分を承りました", record_id, "#D32F2F", "#FFEBEE", body, alt="修理品の廃棄処分を承りました")


def build_generic_status_card(record):
    record_id = record_id_text(record)
    status = getvalue(record, "ドロップダウン", "未設定")
    body = [paragraph_box([f"現在のステータス：{status}", "詳しい内容は店舗までお問い合わせください。"], "#F7F7F7")]
    return make_card("修理進捗状況のご案内", record_id, "#666666", "#EEEEEE", body, alt="修理進捗状況のご案内")


def build_repair_accept_flex_message(record):
    record_id = record_id_text(record)
    body = [
        tc(f"{getvalue(record, 'customer_name', '') or 'お客様'} 様", "md", "bold"),
        paragraph_box(["修理進行のご回答ありがとうございます。", "これより修理作業を進めます。"], "#F3FFF7"),
        info_box("現在の状態", STATUS_ORDERED, "#06C755", "#F3FFF7")
    ]
    return make_card("修理進行を受け付けました", record_id, "#06C755", "#E8F5E9", body)


def build_cancel_action_flex_message(record):
    record_id = record_id_text(record)
    body = [
        tc(f"{getvalue(record, 'customer_name', '') or 'お客様'} 様", "md", "bold"),
        paragraph_box(["修理キャンセルのご回答を受け付けました。", "今後の対応を選択してください。"], "#FFF5F5")
    ]
    footer = [
        {"type": "button", "style": "primary", "height": "sm", "color": "#1565C0", "action": {"type": "postback", "label": "店舗引取", "data": f"action=cancel_store&recordid={record_id}", "displayText": "店舗引取"}},
        {"type": "button", "style": "secondary", "height": "sm", "action": {"type": "postback", "label": "返送", "data": f"action=cancel_return&recordid={record_id}", "displayText": "返送"}},
        {"type": "button", "style": "secondary", "height": "sm", "action": {"type": "postback", "label": "処分", "data": f"action=cancel_dispose&recordid={record_id}", "displayText": "処分"}}
    ]
    return make_card("キャンセルを受け付けました", record_id, "#D32F2F", "#FFEBEE", body, footer, "キャンセル後の対応を選択してください")


def build_cancel_done_flex_message(record, action_label):
    if action_label == "処分":
        return build_cancel_dispose_notify_card(record)
    if action_label == "返送":
        return build_cancel_return_notify_card(record)
    return build_cancel_store_notify_card(record)


def build_notify_quick_replies(record_id, status):
    if status == STATUS_ESTIMATE or "見積" in status:
        return [
            quick_reply_postback("修理する", f"action=repair&recordid={record_id}", "修理する"),
            quick_reply_postback("キャンセル", f"action=cancel&recordid={record_id}", "キャンセル")
        ]
    return []


# =========================
# Routes
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
    raw_uketorihouhou = data.get("uketorihouhou", "")
    uketorihouhou = normalize_uketorihouhou_for_kintone(raw_uketorihouhou)
    notify_url = f"{PUBLIC_BASE_URL}/notify?user={lineuserid}"

    record = {
        "lineid": make_field(lineuserid),
        "customer_name": make_field(name),
        "phone": make_field(phone),
        "maker": make_field(data.get("maker", "")),
        "makerother": make_field(data.get("makerother", "")),
        "model": make_field(data.get("model", "")),
        "serial": make_field(data.get("serial", "")),
        "issue": make_field(data.get("issue", "")),
        "issueother": make_field(data.get("issueother", "")),
        "uketorihouhou": make_field(uketorihouhou),
        "shukajusho": make_field(data.get("shukajusho", "")),
        "shukakiboubi": make_field(data.get("shukakiboubi", "")),
        "shukakiboujikan": make_field(data.get("shukakiboujikan", "")),
        "sameaddress": make_field(data.get("sameaddress", "")),
        "henkyakuhouhou": make_field(data.get("henkyakuhouhou", "")),
        "henkyakujusho": make_field(data.get("henkyakujusho", "")),
        "coupon": make_field(data.get("coupon", "")),
        "kiyakuagree": make_field(data.get("kiyakuagree", "")),
        "notifyurl": make_field(notify_url),
        "ドロップダウン": make_field(STATUS_RECEIVED)
    }

    res = add_kintone_record(record)
    if not res.ok:
        return res.text, 500

    record_id = res.json().get("id", "")
    upsert_customer_record(lineuserid, name, phone)

    receipt_card = build_received_notify_card({"$id": {"value": record_id}, "customer_name": {"value": name}})

    if raw_uketorihouhou == "集荷依頼・LINEで位置情報を送る":
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

    if record_id:
        record = get_kintone_record(record_id)
    else:
        records = get_records_by_lineid(user_id, limit=1)
        record = records[0] if records else None
        record_id = getvalue(record, "$id", "") if record else ""

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
        return "同じ内容なので送信できません。何か内容を変えたら送れます。", 200

    flex_message = build_notify_flex_message(record)
    line_res = send_line_push_messages(user_id, [flex_message])

    if not line_res.ok:
        return line_res.text, 500

    update_notify_history(record_id, message)
    return f"送信完了: {status}", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_json(force=True)
    print("Webhook受信:", body)

    for event in body.get("events", []):
        event_type = event.get("type")
        user_id = event.get("source", {}).get("userId", "")
        reply_token = event.get("replyToken", "")

        if event_type == "message":
            message = event.get("message", {})
            if message.get("type") == "text":
                text = message.get("text", "").strip()
                if text == "修理問い合わせ":
                    handle_repair_inquiry(user_id, reply_token)
                elif text.isdigit():
                    handle_record_number_inquiry(text, reply_token)
                else:
                    send_line_reply(reply_token, "メッセージありがとうございます。\n修理状況を確認する場合は「修理問い合わせ」と送信してください。")
            elif message.get("type") == "location":
                handle_location_message(user_id, reply_token, message)

        elif event_type == "postback":
            data = html.unescape(event.get("postback", {}).get("data", ""))
            print("Postback受信:", data)
            handle_postback(user_id, reply_token, data)

    return "OK", 200


# =========================
# Webhook handlers
# =========================

def handle_repair_inquiry(user_id, reply_token):
    records = get_records_by_lineid(user_id, limit=10)

    if not records:
        send_line_reply(reply_token, "現在、このLINEアカウントに紐づく修理受付は見つかりませんでした。")
        return

    if len(records) == 1:
        send_line_reply(reply_token, build_status_text(records[0]))
        return

    text = "複数の修理受付があります。\n確認したい受付を選んでください。"
    quick_items = []

    for record in records[:10]:
        rid = record_id_text(record)
        label = f"{rid} {getvalue(record, 'maker', '')} {getvalue(record, 'model', '')}".strip() or f"受付番号 {rid}"
        quick_items.append(quick_reply_postback(label[:20], f"action=checkstatus&recordid={rid}", label[:20]))

    send_line_reply(reply_token, text, quick_items)


def handle_record_number_inquiry(record_number, reply_token):
    record = get_kintone_record(record_number)
    if not record:
        send_line_reply(reply_token, "指定された受付番号の修理受付が見つかりませんでした。")
        return
    send_line_reply(reply_token, build_status_text(record))


def handle_location_message(user_id, reply_token, message):
    address = message.get("address", "")
    title = message.get("title", "")
    latitude = message.get("latitude", "")
    longitude = message.get("longitude", "")
    location_text = address or title or "位置情報"

    records = get_records_by_lineid(user_id, limit=5)

    if not records:
        send_line_reply(reply_token, "位置情報を受信しましたが、紐づく修理受付が見つかりませんでした。先に修理受付フォームを送信してください。")
        return

    record = records[0]
    rid = record_id_text(record)
    shukajusho = getvalue(record, "shukajusho", "")
    shukabasho = getvalue(record, "shukabasho", "")
    henkyakuhouhou = getvalue(record, "henkyakuhouhou", "")
    henkyakujusho = getvalue(record, "henkyakujusho", "")
    henkyakubasho = getvalue(record, "henkyakubasho", "")
    sameaddress = getvalue(record, "sameaddress", "")

    if not shukajusho and not shukabasho:
        res = update_location_pickup(rid, location_text, latitude, longitude)
        if res.ok:
            if sameaddress == "はい" or henkyakuhouhou == "集荷場所と同じ":
                send_line_reply(reply_token, "集荷住所を登録しました。\n返却住所は集荷住所と同じとして登録しています。")
            elif henkyakuhouhou == "LINEで位置情報を送る":
                updated_record = get_kintone_record(rid)
                send_line_reply_messages(reply_token, [build_return_location_request_flex_message(updated_record)])
            else:
                send_line_reply(reply_token, "集荷住所を登録しました。")
        else:
            send_line_reply(reply_token, "位置情報の登録に失敗しました。お手数ですが店舗までご連絡ください。")
        return

    if henkyakuhouhou == "LINEで位置情報を送る" and not henkyakujusho and not henkyakubasho:
        res = update_location_return(rid, location_text, latitude, longitude)
        send_line_reply(reply_token, "返却住所を登録しました。\nご協力ありがとうございます。" if res.ok else "返却場所の登録に失敗しました。お手数ですが店舗までご連絡ください。")
        return

    send_line_reply(reply_token, "集荷住所と返却住所はすでに登録済みです。\n変更が必要な場合は店舗までご連絡ください。")


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
        send_line_reply(reply_token, build_status_text(record_before))
        return

    if action == "repair":
        if current_cancel_action or current_answer in ["キャンセル", "修理する"] or is_cancel_status(current_status):
            send_line_reply(reply_token, already_decided_text(current_answer, current_cancel_action))
            return
        res = update_repair_answer(record_id, "修理する")
        if not res.ok:
            send_line_reply(reply_token, "回答の登録に失敗しました。お手数ですが店舗までご連絡ください。")
            return
        record_after = get_kintone_record(record_id)
        send_line_reply_messages(reply_token, [build_repair_accept_flex_message(record_after)])
        return

    if action == "cancel":
        if current_cancel_action or current_answer == "修理する" or is_ordered_status(current_status) or is_done_status(current_status) or is_complete_status(current_status):
            send_line_reply(reply_token, already_decided_text(current_answer, current_cancel_action))
            return
        if current_answer == "キャンセル":
            send_line_reply_messages(reply_token, [build_cancel_action_flex_message(record_before)])
            return
        res = update_repair_answer(record_id, "キャンセル")
        if not res.ok:
            send_line_reply(reply_token, "キャンセル回答の登録に失敗しました。お手数ですが店舗までご連絡ください。")
            return
        record_after = get_kintone_record(record_id)
        send_line_reply_messages(reply_token, [build_cancel_action_flex_message(record_after)])
        return

    if action in ["cancel_store", "cancel_return", "cancel_dispose"]:
        if current_answer == "修理する":
            send_line_reply(reply_token, "この修理受付は、すでに「修理する」で受付済みです。\n変更が必要な場合は店舗までご連絡ください。")
            return
        if current_cancel_action:
            send_line_reply(reply_token, f"この修理受付は、すでに「{current_cancel_action}」で登録済みです。\n変更が必要な場合は店舗までご連絡ください。")
            return
        if current_answer != "キャンセル":
            send_line_reply(reply_token, "先に「キャンセルする」を選択してください。\n変更が必要な場合は店舗までご連絡ください。")
            return
        selected_action = "店舗引取" if action == "cancel_store" else "返送" if action == "cancel_return" else "処分"
        res = update_cancel_action(record_id, selected_action)
        if not res.ok:
            send_line_reply(reply_token, "登録に失敗しました。")
            return
        record_after = get_kintone_record(record_id)
        send_line_reply_messages(reply_token, [build_cancel_done_flex_message(record_after, selected_action)])
        return

    send_line_reply(reply_token, "未対応の操作です。")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
