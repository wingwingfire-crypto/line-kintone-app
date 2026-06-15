@app.route("/submit", methods=["POST"])
def submit():
    data = request.json

    print("受信データ:", data)

    name = data.get("name", "")
    phone = data.get("phone", "")
    maker = data.get("maker", "")
    model = data.get("model", "")
    issue = data.get("issue", "")
    line_user_id = data.get("line_user_id", "")

    record = {
        "app": 5,
        "record": {
            "customer_name": {"value": name},
            "phone": {"value": phone},
            "maker": {"value": maker},
            "model": {"value": model},
            "issue": {"value": issue},
            "line_user_id": {"value": line_user_id}
        }
    }

    requests.post(KINTONE_URL, headers=HEADERS, json=record)

    return {"status": "ok"}
