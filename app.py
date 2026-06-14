from flask import Flask, request
import requests
import os

app = Flask(__name__)

KINTONE_URL = "https://2zx7vnpprtja.cybozu.com/k/v1/record.json"
API_TOKEN = os.environ.get("KINTONE_API_TOKEN")

HEADERS = {
    "X-Cybozu-API-Token": API_TOKEN,
    "Content-Type": "application/json"
}

@app.route("/", methods=["GET"])
def home():
    return "OK"

@app.route("/callback", methods=["POST"])
def callback():
    data = request.json

    try:
        event = data["events"][0]
        user_id = event["source"]["userId"]
        text = event["message"]["text"]

        record = {
            "app": 5,
            "record": {
                "customer_name": {"value": text},
                "line_user_id": {"value": user_id}
            }
        }

        requests.post(KINTONE_URL, headers=HEADERS, json=record)

    except Exception as e:
        print("エラー:", e)

    return "OK"