import os
import json
import html
import requests
from datetime import datetime, timezone
from urllib.parse import parse_qs

from flask import Flask, request, render_template

app = Flask(__name__)

# =========================
# 基本設定
# =========================

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


def quick_reply_text(label, text):
    return {
        "type": "action",
        "action": {
            "type": "message",
            "label": label,
            "text": text
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
        fields["ドロップダウン"] = make_field("受注")

    if answer == "キャンセル":
        fields["ドロップダウン"] = make_field("中止")

    return update_kintone_record(record_id, fields)


def update_cancel_action(record_id, action):
    fields = {
        "canceltaio": make_field(action)
    }

    return update_kintone_record(record_id, fields)


# =========================
# 表示・文面作成
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

    if "発送" in status or "出荷" in status:
        text += f"""
■ お問い合わせ送り状番号
{tracking or "未入力"}
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

    if status == "⚪修理受付中":
        return f"""修理のお申込みを受け付けました

受付番号：{record_id}

{name}様

お申し込みありがとうございます。
ただいま内容を確認しております。

確認・準備が整い次第、次のご案内をお送りいたしますので少々お待ちください。"""

    if status == "集荷依頼済":
        return f"""修理品の集荷手配が完了しました

受付番号：{record_id}

指定の日時に配送業者が伺いますので、修理品のご準備をお願いいたします。"""

    if status == "📄見積提出済" or "見積" in status:
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

    if status == "受注":
        return f"""修理作業を開始いたします

受付番号：{record_id}

修理実行のご連絡ありがとうございます。
これより修理作業に入らせていただきます。

完了まで今しばらくお待ちください。

受取方法やお届け先の変更がある場合は、店舗へお電話にてご連絡ください。

上中野店 TEL：086-230-6551
受付時間：7:00〜19:00"""

    if "修理完了連絡済" in status and "発送" in status:
        return f"""修理が完了いたしました

受付番号：{record_id}

大変お待たせいたしました。
修理作業が完了し、修理品のお荷物発送が完了いたしました。

■ お問い合わせ送り状番号
{tracking or "未入力"}

到着までもうしばらくお待ちください。

この度は修理サービスをご利用いただき、誠にありがとうございました。"""

    if "修理完了連絡済" in status and ("店頭" in status or "引取" in status or "受取" in status):
        return f"""修理が完了いたしました

受付番号：{record_id}

大変お待たせいたしました。
修理作業が完了し、店頭にてお渡しの準備が整っております。

ご都合の良いタイミングでご来店をお願いいたします。
ご来店の際は、本LINE画面または受付番号をスタッフへご提示ください。"""

    if status == "完了・出荷済" or "完了" in status:
        return f"""修理対応が完了しました

受付番号：{record_id}

この度は修理サービスをご利用いただき、誠にありがとうございました。"""

    if status == "中止":
        return f"""修理中止のお手続きについて

受付番号：{record_id}

修理中止のご連絡を承りました。
利用規約の通り、見積料1,500円を頂戴いたします。

お預かりした修理品の
【店舗引取・ご返送・当店にて処分】
のご判断をお知らせください。"""

    return build_status_text(record)


def build_notify_quick_replies(record_id, status):
    items = []

    if status == "📄見積提出済" or "見積" in status:
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

    if status == "中止":
        items.append(
            quick_reply_postback(
                "店舗引取",
                f"action=cancel_store&recordid={record_id}",
                "店舗引取"
            )
        )
        items.append(
            quick_reply_postback(
                "返送",
                f"action=cancel_return&recordid={record_id}",
                "返送"
            )
        )
        items.append(
            quick_reply_postback(
                "処分",
                f"action=cancel_dispose&recordid={record_id}",
                "処分"
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
        "ドロップダウン": make_field("⚪修理受付中")
    }

    res = add_kintone_record(record)

    if not res.ok:
        return res.text, 500

    result = res.json()
    record_id = result.get("id", "")

    base_message = f"""修理受付を受け付けました。

受付番号：{record_id}

{name}様

お申し込みありがとうございます。
内容を確認し、準備が整い次第ご案内いたします。"""

    if uketorihouhou == "集荷依頼・LINEで位置情報を送る":
        location_message = """📍 集荷場所の送信が必要です

下の「📍 集荷場所を送る」ボタンを押してください。

位置情報画面が開いたら、集荷場所を選び、緑の✅を押してください。"""

        messages = [
            {
                "type": "text",
                "text": base_message
            },
            {
                "type": "text",
                "text": location_message,
                "quickReply": {
                    "items": [
                        quick_reply_location("📍 集荷場所を送る")
                    ]
                }
            }
        ]

        send_line_push_messages(lineuserid, messages)
    else:
        send_line_push(lineuserid, base_message)

    return "OK", 200


@app.route("/notify", methods=["GET"])
def notify():
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

    quick_reply_items = build_notify_quick_replies(record_id, status)

    send_line_push(
        user_id,
        message,
        quick_reply_items if quick_reply_items else None
    )

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

    # 1回目：集荷場所として登録
    if not shukabasho:
        res = update_location_pickup(record_id, location_text, latitude, longitude)

        if res.ok:
            if sameaddress == "はい" or henkyakuhouhou == "集荷場所と同じ":
                send_line_reply(
                    reply_token,
                    "集荷場所を登録しました。\n返却場所は集荷場所と同じとして登録しています。"
                )
            elif henkyakuhouhou == "LINEで位置情報を送る":
                send_line_reply(
                    reply_token,
                    """集荷場所を登録しました。

📍 次に、返却場所を送ってください

下の「📍 返却場所を送る」ボタンを押してください。

位置情報画面が開いたら、返却場所を選び、緑の✅を押してください。""",
                    [quick_reply_location("📍 返却場所を送る")]
                )
            else:
                send_line_reply(
                    reply_token,
                    "集荷場所を登録しました。"
                )
        else:
            send_line_reply(
                reply_token,
                "位置情報の登録に失敗しました。お手数ですが店舗までご連絡ください。"
            )
        return

    # 2回目：返却場所として登録
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

    # すでに登録済みの場合
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
        send_line_reply(
            reply_token,
            "位置情報を登録しました。"
        )
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

    if action == "checkstatus":
        record = get_kintone_record(record_id)

        if not record:
            send_line_reply(reply_token, "対象の修理受付が見つかりませんでした。")
            return

        text = build_status_text(record)
        send_line_reply(reply_token, text)
        return

    if action == "repair":
        res = update_repair_answer(record_id, "修理する")

        if res.ok:
            send_line_reply(
                reply_token,
                "修理進行のご回答を受け付けました。\nこれより修理作業を進めさせていただきます。"
            )
        else:
            send_line_reply(
                reply_token,
                "回答の登録に失敗しました。お手数ですが店舗までご連絡ください。"
            )
        return

    if action == "cancel":
        res = update_repair_answer(record_id, "キャンセル")

        if res.ok:
            text = """キャンセルのご回答を受け付けました。

お預かりしている修理品について、今後の対応を選択してください。"""

            quick_items = [
                quick_reply_postback(
                    "店舗引取",
                    f"action=cancel_store&recordid={record_id}",
                    "店舗引取"
                ),
                quick_reply_postback(
                    "返送",
                    f"action=cancel_return&recordid={record_id}",
                    "返送"
                ),
                quick_reply_postback(
                    "処分",
                    f"action=cancel_dispose&recordid={record_id}",
                    "処分"
                )
            ]

            send_line_reply(reply_token, text, quick_items)
        else:
            send_line_reply(
                reply_token,
                "キャンセル回答の登録に失敗しました。お手数ですが店舗までご連絡ください。"
            )
        return

    if action == "cancel_store":
        res = update_cancel_action(record_id, "店舗引取")

        if res.ok:
            send_line_reply(
                reply_token,
                "店舗引取で承りました。\n店頭でのお渡し準備を進めます。"
            )
        else:
            send_line_reply(reply_token, "登録に失敗しました。")
        return

    if action == "cancel_return":
        res = update_cancel_action(record_id, "返送")

        if res.ok:
            send_line_reply(
                reply_token,
                "返送で承りました。\n着払いでの返送手配を進めます。"
            )
        else:
            send_line_reply(reply_token, "登録に失敗しました。")
        return

    if action == "cancel_dispose":
        res = update_cancel_action(record_id, "処分")

        if res.ok:
            send_line_reply(
                reply_token,
                "処分で承りました。\n当店にて適切に処分いたします。"
            )
        else:
            send_line_reply(reply_token, "登録に失敗しました。")
        return

    send_line_reply(reply_token, "未対応の操作です。")


# =========================
# 起動
# =========================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
