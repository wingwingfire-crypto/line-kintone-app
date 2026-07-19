from flask import Flask, request, send_from_directory
import requests
import os
from , timezone
from urllib.parse import parse_qs
import html

app = Flask(__name__)

# ===== Kintone設定 =====
KINTONE_BASE = "https://2r2oficviuff.cybozu.com"
KINTONE_RECORD_URL = KINTONE_BASE + "/k/v1/record.json"
KINTONE_GET_URL = KINTONE_BASE + "/k/v1/records.json"
KINTONE_API_TOKEN = os.environ.get("KINTONE_API_TOKEN")

KINTONE_APP_ID = 6

# ===== LINE設定 =====
LINE_TOKEN = os.environ.get("LINE_TOKEN")
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"

# ===== 日本時間 =====
JST = timezone(timedelta(hours=9))


# ===== 共通：Kintone値取得 =====
def getvalue(record, fieldcode, default=""):
    try:
        value = record.get(fieldcode, {}).get("value", default)
        if value is None:
            return default
        return value
    except Exception:
        return default


# ===== 共通：金額表示 =====
def formatprice(value):
    if value is None or value == "":
        return "未入力"

    try:
        return f"{int(float(value)):,}円"
    except Exception:
        return str(value) + "円"


# ===== 共通：日付表示 =====
def formatdate(value):
    if value is None or value == "":
        return "未入力"
    return value


# ===== 複数台選択ボタン名 =====
def makerecordlabel(record):
    recordid = getvalue(record, "$id", "")
    maker = getvalue(record, "maker", "")
    model = getvalue(record, "model", "")
    serial = getvalue(record, "serial", "")

    if model:
        label = f"型番:{model}"
    elif maker:
        label = f"メーカー:{maker}"
    elif serial:
        label = f"機番:{serial}"
    else:
        label = f"修理品#{recordid}"

    if len(label) > 20:
        label = label[:20]

    return label


# ===== LINE Push送信 =====
def sendlinemessage(userid, text, quickreplyitems=None):
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }

    message = {
        "type": "text",
        "text": text
    }

    if quickreplyitems:
        message["quickReply"] = {
            "items": quickreplyitems
        }

    data = {
        "to": userid,
        "messages": [message]
    }

    res = requests.post(
        LINE_PUSH_URL,
        headers=headers,
        json=data
    )

    print("LINE送信:", res.text)


# ===== LINE Reply送信 =====
def replylinemessage(replytoken, text, quickreplyitems=None):
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }

    message = {
        "type": "text",
        "text": text
    }

    if quickreplyitems:
        message["quickReply"] = {
            "items": quickreplyitems
        }

    data = {
        "replyToken": replytoken,
        "messages": [message]
    }

    res = requests.post(
        LINE_REPLY_URL,
        headers=headers,
        json=data
    )

    print("LINE返信:", res.text)


# ===== 複数台選択 Quick Reply =====
def replylinequickreply(replytoken, text, records):
    items = []

    for record in records[:10]:
        recordid = getvalue(record, "$id", "")
        label = makerecordlabel(record)

        items.append({
            "type": "action",
            "action": {
                "type": "postback",
                "label": label,
                "data": f"action=checkstatus&recordid={recordid}",
                "displayText": label
            }
        })

    replylinemessage(replytoken, text, items)


# ===== 修理可否ボタン =====
def makerepairanswerbuttons(recordid):
    return [
        {
            "type": "action",
            "action": {
                "type": "postback",
                "label": "修理を依頼する",
                "data": f"action=repairaccept&recordid={recordid}",
                "displayText": "修理を依頼する"
            }
        },
        {
            "type": "action",
            "action": {
                "type": "postback",
                "label": "キャンセルする",
                "data": f"action=repaircancel&recordid={recordid}",
                "displayText": "キャンセルする"
            }
        }
    ]


# ===== キャンセル後対応ボタン =====
def makecancelbuttons(recordid):
    return [
        {
            "type": "action",
            "action": {
                "type": "postback",
                "label": "店舗で受け取る",
                "data": f"action=cancelpickup&recordid={recordid}",
                "displayText": "店舗で受け取る"
            }
        },
        {
            "type": "action",
            "action": {
                "type": "postback",
                "label": "店舗で処分する",
                "data": f"action=canceldisposal&recordid={recordid}",
                "displayText": "店舗で処分する"
            }
        }
    ]


# ===== Kintone：LINEユーザーIDから複数取得 =====
def getrecordsbyuser(userid):
    headers = {
        "X-Cybozu-API-Token": KINTONE_API_TOKEN
    }

    query = f'lineid = "{userid}" order by $id desc limit 10'

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
def getrecordbyid(recordid):
    headers = {
        "X-Cybozu-API-Token": KINTONE_API_TOKEN
    }

    params = {
        "app": KINTONE_APP_ID,
        "id": recordid
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


# ===== Kintone：修理可否回答更新 =====
def updaterepairanswer(recordid, answertext):
    headers = {
        "X-Cybozu-API-Token": KINTONE_API_TOKEN,
        "Content-Type": "application/json"
    }

    data = {
        "app": KINTONE_APP_ID,
        "id": recordid,
        "record": {
            "shurikahikaito": {
                "value": answertext
            }
        }
    }

    res = requests.put(
        KINTONE_RECORD_URL,
        headers=headers,
        json=data
    )

    print("修理可否回答更新:", res.text)


# ===== Kintone：キャンセル後対応更新 =====
def updatecancelaction(recordid, canceltext):
    headers = {
        "X-Cybozu-API-Token": KINTONE_API_TOKEN,
        "Content-Type": "application/json"
    }

    data = {
        "app": KINTONE_APP_ID,
        "id": recordid,
        "record": {
            "canceltaio": {
                "value": canceltext
            }
        }
    }

    res = requests.put(
        KINTONE_RECORD_URL,
        headers=headers,
        json=data
    )

    print("キャンセル後対応更新:", res.text)


# ===== Kintone：位置情報更新 =====
def updatelocationinfo(recordid, shukabasho, ido, keido, mapurl):
    headers = {
        "X-Cybozu-API-Token": KINTONE_API_TOKEN,
        "Content-Type": "application/json"
    }

    data = {
        "app": KINTONE_APP_ID,
        "id": recordid,
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


# ===== Kintone：通知履歴更新 =====
def updatenotifyhistory(recordid, message):
    nowtime = datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S%z")

    headers = {
        "X-Cybozu-API-Token": KINTONE_API_TOKEN,
        "Content-Type": "application/json"
    }

    data = {
        "app": KINTONE_APP_ID,
        "id": recordid,
        "record": {
            "lastnotify": {
                "value": nowtime
            },
            "notifymessage": {
                "value": message
            }
        }
    }

    res = requests.put(
        KINTONE_RECORD_URL,
        headers=headers,
        json=data
    )

    print("履歴更新:", res.text)


# ===== 最新の進行中レコード取得 =====
def getlatestactiverecord(userid):
    records = getrecordsbyuser(userid)

    if len(records) == 0:
        return None

    closedstatuses = [
        "●完了(精算済)",
        "🔴中止(返却)",
        "❌中止(処分)"
    ]

    for record in records:
        status = getvalue(record, "ドロップダウン", "").strip()
        if status not in closedstatuses:
            return record

    return records[0]


# ===== 問い合わせ返信文作成 =====
def buildstatusmessage(record):
    name = getvalue(record, "customer_name", "")
    maker = getvalue(record, "maker", "")
    model = getvalue(record, "model", "")
    serial = getvalue(record, "serial", "")
    issue = getvalue(record, "issue", "")
    statusjp = getvalue(record, "ドロップダウン", "").strip()

    mitsumorikingaku = getvalue(record, "mitsumorikingaku", "")
    mitsumorinaiyo = getvalue(record, "mitsumorinaiyo", "")
    kanryoyoteibi = getvalue(record, "kanryoyoteibi", "")
    okurijobango = getvalue(record, "okurijobango", "")
    shukabasho = getvalue(record, "shukabasho", "")
    mapurl = getvalue(record, "mapurl", "")
    shurikahikaito = getvalue(record, "shurikahikaito", "")
    canceltaio = getvalue(record, "canceltaio", "")

    pricetext = formatprice(mitsumorikingaku)
    datetext = formatdate(kanryoyoteibi)

    baseinfo = f"""■ 修理品情報
メーカー：{maker}
型番：{model}
機番：{serial}

"""

    if statusjp in ["⚪修理受付中", "📩集荷依頼済", "🚚荷受待(店舗持込待ち)", "🚶荷受待(店舗持込待ち)"]:
        return f"""{name}様

以下の修理品の状況です。

{baseinfo}■ 現在の進捗
【受付完了・修理品荷受け待ち】

修理品の到着、または確認作業をお待ちしております。

■ 集荷場所
{shukabasho if shukabasho else "未登録"}

■ 地図URL
{mapurl if mapurl else "未登録"}
"""

    elif statusjp == "🟡見積中":
        return f"""{name}様

以下の修理品の状況です。

{baseinfo}■ 現在の進捗
【見積中】

ただいま修理内容を確認し、お見積りを作成しております。
もうしばらくお待ちください。
"""

    elif statusjp == "📄見積提出済":
        answertext = ""

        if shurikahikaito == "修理する":
            answertext = """

■ お客様回答
修理依頼済みです。
"""
        elif shurikahikaito == "キャンセル":
            answertext = f"""

■ お客様回答
キャンセル受付済みです。

■ キャンセル後対応
{canceltaio if canceltaio else "未選択"}
"""

        return f"""{name}様

以下の修理品の状況です。

{baseinfo}■ 現在の進捗
【見積提出済】

■ 故障内容
{issue}

■ お見積り金額
{pricetext}

■ お見積り内容
{mitsumorinaiyo if mitsumorinaiyo else "未入力"}

■ 修理完了予定日
{datetext}
{answertext}
修理を進めるか、キャンセルされるかをご確認ください。
"""

    elif statusjp == "📦受注(部品待ち)":
        return f"""{name}様

以下の修理品の状況です。

{baseinfo}■ 現在の進捗
【受注・部品待ち】

現在、修理作業または部品手配を進めております。

■ 修理完了予定日
{datetext}
"""

    elif statusjp == "✅修理完了連絡済":
        return f"""{name}様

以下の修理品の状況です。

{baseinfo}■ 現在の進捗
【修理完了】

修理が完了しております。
お手すきの際にご来店をお願いいたします。

■ 修理金額
{pricetext}
"""

    elif statusjp == "🚚発送完了":
        return f"""{name}様

以下の修理品の状況です。

{baseinfo}■ 現在の進捗
【発送完了】

修理品は発送済みです。

■ 送り状番号
{okurijobango if okurijobango else "未入力"}

配送状況はこちらからご確認ください。
https://toi.kuronekoyamato.co.jp/cgi-bin/tneko
"""

    elif statusjp == "🔴中止(返却)":
        return f"""{name}様

以下の修理品の状況です。

{baseinfo}■ 現在の進捗
【中止・返却】

修理は中止となり、返却対応となります。
"""

    elif statusjp == "❌中止(処分)":
        return f"""{name}様

以下の修理品の状況です。

{baseinfo}■ 現在の進捗
【中止・処分】

修理は中止となり、処分対応となります。
"""

    else:
        return f"""{name}様

以下の修理品の状況です。

{baseinfo}■ 現在の進捗
【{statusjp}】

です。
"""


# ===== 見積未回答ならボタン表示 =====
def shouldshowrepairanswerbuttons(record):
    statusjp = getvalue(record, "ドロップダウン", "").strip()
    shurikahikaito = getvalue(record, "shurikahikaito", "")

    if statusjp == "📄見積提出済" and shurikahikaito == "":
        return True

    return False


# ===== フォーム表示 =====
@app.route("/form", methods=["GET"])
def form():
    return send_from_directory(".", "form.html")


# ===== フォーム登録 =====
@app.route("/submit", methods=["POST"])
def submit():
    data = request.json

    try:
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

        coupon = data.get("coupon", "")
        kiyakuagree = data.get("kiyakuagree", "")

        lineuserid = data.get("lineuserid", "")

        notifyurl = f"https://line-kintone-app.onrender.com/notify?user={lineuserid}"

        recordfields = {
            "customer_name": {
                "value": name
            },
            "phone": {
                "value": phone
            },
            "maker": {
                "value": maker
            },
            "makerother": {
                "value": makerother
            },
            "model": {
                "value": model
            },
            "serial": {
                "value": serial
            },
            "issue": {
                "value": issue
            },
            "issueother": {
                "value": issueother
            },
            "symptomother": {
                "value": symptomother
            },
            "uketorihouhou": {
                "value": uketorihouhou
            },
            "shukajusho": {
                "value": shukajusho
            },
            "shukakiboubi": {
                "value": shukakiboubi if shukakiboubi else None
            },
            "shukakiboujikan": {
                "value": shukakiboujikan
            },
            "coupon": {
                "value": coupon
            },
            "kiyakuagree": {
                "value": kiyakuagree
            },
            "lineid": {
                "value": lineuserid
            },
            "notifyurl": {
                "value": notifyurl
            }
        }

        if uketorihouhou == "集荷依頼・住所を入力する" and shukajusho:
            recordfields["shukabasho"] = {
                "value": shukajusho
            }

        record = {
            "app": KINTONE_APP_ID,
            "record": recordfields
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

        if lineuserid:
            if uketorihouhou == "店舗持ち込み":
                message = f"""{name}様

📩 修理受付を受け付けました。

修理品は下記店舗までお持ち込みください。

国本刃物 上中野店
〒700-0972
岡山県岡山市北区上中野2丁目27-12
電話番号：086-230-6551
"""

            elif uketorihouhou == "集荷依頼・LINEで位置情報を送る":
                message = f"""{name}様

📩 修理受付を受け付けました。

続けて、LINEトーク画面から集荷場所の位置情報を送信してください。

送信方法：
LINEトーク画面の「＋」ボタン
↓
位置情報
↓
集荷場所を選んで送信
"""

            elif uketorihouhou == "集荷依頼・住所を入力する":
                message = f"""{name}様

📩 修理受付を受け付けました。

入力いただいた住所をもとに集荷手配を進めます。

■ 集荷住所
{shukajusho}

■ 集荷希望日
{shukakiboubi if shukakiboubi else "未指定"}

■ 集荷希望時間
{shukakiboujikan if shukakiboujikan else "未指定"}
"""

            else:
                message = f"""{name}様

📩 修理受付を受け付けました。
"""

            sendlinemessage(lineuserid, message)

        return {"status": "ok"}

    except Exception as e:
        print("登録エラー:", e)
        return {
            "status": "error",
            "message": str(e)
        }


# ===== 通知URLクリック用 =====
@app.route("/notify", methods=["GET"])
def notify():
    userid = request.args.get("user")
    print("受信user:", userid)

    try:
        headers = {
            "X-Cybozu-API-Token": KINTONE_API_TOKEN
        }

        query = f'lineid = "{userid}" order by $id desc limit 1'

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
        recordid = getvalue(record, "$id", "")

        name = getvalue(record, "customer_name", "")
        maker = getvalue(record, "maker", "")
        model = getvalue(record, "model", "")
        serial = getvalue(record, "serial", "")
        issue = getvalue(record, "issue", "")

        mitsumorikingaku = getvalue(record, "mitsumorikingaku", "")
        mitsumorinaiyo = getvalue(record, "mitsumorinaiyo", "")
        kanryoyoteibi = getvalue(record, "kanryoyoteibi", "")
        okurijobango = getvalue(record, "okurijobango", "")

        pricetext = formatprice(mitsumorikingaku)
        datetext = formatdate(kanryoyoteibi)

        statusjp = getvalue(record, "ドロップダウン", "").strip()
        print("取得ステータス:", statusjp)

        statusmap = {
            "⚪修理受付中": "received",
            "📩集荷依頼済": "pickuprequested",
            "🚚荷受待(店舗持込待ち)": "waitingarrival",
            "🚶荷受待(店舗持込待ち)": "waitingarrival",
            "🟡見積中": "estimating",
            "📄見積提出済": "quoted",
            "📦受注(部品待ち)": "waitingparts",
            "✅修理完了連絡済": "repaircompleted",
            "🚚発送完了": "shipped",
            "🔴中止(返却)": "cancelreturn",
            "❌中止(処分)": "canceldisposal"
        }

        statuscode = statusmap.get(statusjp, "unknown")
        print("変換後:", statuscode)

        quickreplyitems = None

        if statuscode == "received":
            message = f"""{name}様

【修理受付中】

この度は修理のご依頼ありがとうございます。

順次対応しております。
今しばらくお待ちください。
"""

        elif statuscode == "pickuprequested":
            message = f"""{name}様

【集荷依頼済】

集荷手配が完了しております。
出荷の準備をしてお待ちください。
"""

        elif statuscode == "waitingarrival":
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
            quickreplyitems = makerepairanswerbuttons(recordid)

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
{pricetext}

■ お見積り内容
{mitsumorinaiyo if mitsumorinaiyo else "未入力"}

■ 修理完了予定日
{datetext}

修理を進めるか、キャンセルされるかをご回答ください。
"""

        elif statuscode == "waitingparts":
            message = f"""{name}様

【受注・部品待ち】

修理のご依頼を承りました。

現在、必要部品を手配しております。
部品入荷後、修理作業を進めさせていただきます。

■ 修理完了予定日
{datetext}
"""

        elif statuscode == "repaircompleted":
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
{pricetext}

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
{pricetext}

■ 送り状番号
{okurijobango if okurijobango else "未入力"}

配送状況は以下よりご確認ください。
https://toi.kuronekoyamato.co.jp/cgi-bin/tneko

よろしくお願いいたします。
"""

        elif statuscode == "cancelreturn":
            message = f"""{name}様

【中止（返却）】

修理は中止となり、返却対応となります。

詳細につきましては、別途ご案内いたします。
"""

        elif statuscode == "canceldisposal":
            message = f"""{name}様

【中止（処分）】

修理は中止となり、処分対応となります。

何卒ご了承ください。
"""

        else:
            message = f"""{name}様

ステータス不一致：
{statusjp}
"""

        sendlinemessage(userid, message, quickreplyitems)
        updatenotifyhistory(recordid, message)

        return f"送信完了: {statusjp}"

    except Exception as e:
        print("通知エラー:", e)
        return "通知処理エラー"


# ===== LINE Webhook =====
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        body = request.json
        print("Webhook受信:", body)

        events = body.get("events", [])

        for event in events:
            eventtype = event.get("type")
            replytoken = event.get("replyToken")
            userid = event.get("source", {}).get("userId")

            # ===== Postback処理 =====
            if eventtype == "postback":
                postbackdata = event.get("postback", {}).get("data", "")
                postbackdata = html.unescape(postbackdata)

                print("Postback受信:", postbackdata)

                parsed = parse_qs(postbackdata)
                action = parsed.get("action", [""])[0]
                recordid = parsed.get("recordid", [""])[0]

                if action == "checkstatus" and recordid:
                    record = getrecordbyid(recordid)

                    if not record:
                        replylinemessage(
                            replytoken,
                            "選択された修理情報が見つかりませんでした。"
                        )
                        continue

                    replymessage = buildstatusmessage(record)

                    if shouldshowrepairanswerbuttons(record):
                        replylinemessage(
                            replytoken,
                            replymessage,
                            makerepairanswerbuttons(recordid)
                        )
                    else:
                        replylinemessage(replytoken, replymessage)

                    continue

                if action == "repairaccept" and recordid:
                    updaterepairanswer(recordid, "修理する")

                    record = getrecordbyid(recordid)

                    maker = getvalue(record, "maker", "") if record else ""
                    model = getvalue(record, "model", "") if record else ""
                    serial = getvalue(record, "serial", "") if record else ""

                    replymessage = f"""【修理受付完了】

ご依頼ありがとうございます。
これより修理作業に入らせていただきます。

完了次第、こちらのLINEにてご連絡いたします。

■ 修理品情報
メーカー：{maker}
型番：{model}
機番：{serial}
"""

                    replylinemessage(replytoken, replymessage)
                    continue

                if action == "repaircancel" and recordid:
                    updaterepairanswer(recordid, "キャンセル")

                    record = getrecordbyid(recordid)

                    maker = getvalue(record, "maker", "") if record else ""
                    model = getvalue(record, "model", "") if record else ""
                    serial = getvalue(record, "serial", "") if record else ""

                    replymessage = f"""【キャンセル受付】

修理キャンセルを承りました。

■ 修理品情報
メーカー：{maker}
型番：{model}
機番：{serial}

返却方法をお選びください。
"""

                    replylinemessage(
                        replytoken,
                        replymessage,
                        makecancelbuttons(recordid)
                    )
                    continue

                if action == "cancelpickup" and recordid:
                    updatecancelaction(recordid, "店舗引取")

                    record = getrecordbyid(recordid)

                    maker = getvalue(record, "maker", "") if record else ""
                    model = getvalue(record, "model", "") if record else ""
                    serial = getvalue(record, "serial", "") if record else ""

                    replymessage = f"""【返却受付完了】

修理品の店舗引取を承りました。

■ 修理品情報
メーカー：{maker}
型番：{model}
機番：{serial}

キャンセル料が発生する場合は、
商品返却時にお支払いください。

ご来店をお待ちしております。
"""

                    replylinemessage(replytoken, replymessage)
                    continue

                if action == "canceldisposal" and recordid:
                    updatecancelaction(recordid, "処分")

                    record = getrecordbyid(recordid)

                    maker = getvalue(record, "maker", "") if record else ""
                    model = getvalue(record, "model", "") if record else ""
                    serial = getvalue(record, "serial", "") if record else ""

                    replymessage = f"""【処分受付完了】

お預かり品を処分いたします。

■ 修理品情報
メーカー：{maker}
型番：{model}
機番：{serial}

キャンセル料が発生する場合は、
ご来店時または別途ご案内の方法にてお支払いください。
"""

                    replylinemessage(replytoken, replymessage)
                    continue

            # ===== Message処理 =====
            if eventtype != "message":
                continue

            message = event.get("message", {})
            messagetype = message.get("type")

            # ===== 位置情報処理 =====
            if messagetype == "location":
                title = message.get("title", "")
                address = message.get("address", "")
                latitude = message.get("latitude", "")
                longitude = message.get("longitude", "")

                print("位置情報受信 title:", title)
                print("位置情報受信 address:", address)
                print("位置情報受信 latitude:", latitude)
                print("位置情報受信 longitude:", longitude)

                record = getlatestactiverecord(userid)

                if not record:
                    replylinemessage(
                        replytoken,
                        "修理受付情報が見つかりませんでした。先に修理受付フォームをご入力ください。"
                    )
                    continue

                recordid = getvalue(record, "$id", "")
                maker = getvalue(record, "maker", "")
                model = getvalue(record, "model", "")
                serial = getvalue(record, "serial", "")

                mapurl = f"https://www.google.com/maps?q={latitude},{longitude}"

                if title and address:
                    shukabasho = f"{title}\n{address}"
                elif address:
                    shukabasho = address
                elif title:
                    shukabasho = title
                else:
                    shukabasho = "位置情報"

                updatelocationinfo(
                    recordid,
                    shukabasho,
                    latitude,
                    longitude,
                    mapurl
                )

                replymessage = f"""【位置情報受付完了】

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

                replylinemessage(replytoken, replymessage)
                continue

            # ===== テキスト処理 =====
            if messagetype != "text":
                continue

            usermessage = message.get("text", "").strip()

            print("受信メッセージ:", usermessage)
            print("受信userId:", userid)

            if usermessage not in ["修理問い合わせ", "問い合わせ", "状況確認"]:
                replylinemessage(
                    replytoken,
                    "修理状況を確認する場合は「修理問い合わせ」と送信してください。\n集荷場所を送る場合は、LINEの位置情報送信をご利用ください。"
                )
                continue

            records = getrecordsbyuser(userid)

            if len(records) == 0:
                replylinemessage(
                    replytoken,
                    "現在、修理受付情報が見つかりませんでした。"
                )
                continue

            closedstatuses = [
                "●完了(精算済)",
                "🔴中止(返却)",
                "❌中止(処分)"
            ]

            activerecords = []

            for record in records:
                status = getvalue(record, "ドロップダウン", "").strip()
                if status not in closedstatuses:
                    activerecords.append(record)

            if len(activerecords) == 0:
                replylinemessage(
                    replytoken,
                    "現在、進行中の修理受付情報はありません。"
                )
                continue

            if len(activerecords) == 1:
                replymessage = buildstatusmessage(activerecords[0])
                recordid = getvalue(activerecords[0], "$id", "")

                if shouldshowrepairanswerbuttons(activerecords[0]):
                    replylinemessage(
                        replytoken,
                        replymessage,
                        makerepairanswerbuttons(recordid)
                    )
                else:
                    replylinemessage(replytoken, replymessage)

                continue

            replylinequickreply(
                replytoken,
                "現在、複数の修理品をお預かりしています。\n確認したい修理品を選択してください。",
                activerecords
            )

        return "OK"

