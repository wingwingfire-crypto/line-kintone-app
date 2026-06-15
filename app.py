@app.route("/submit", methods=["POST"])
def submit():
    data = request.json

    print("受信データ:", data)

    name = data.get("name", "")
    phone = data.get("phone", "")
    maker = data.get("maker", "")
    model = data.get("model", "")
    issue = data.get("issue", "")
    
    # 1. フロント（LIFF/JS）からは今まで通り「line_user_id」で届くので、変数に格納します
    line_user_id = data.get("line_user_id", "")

    record = {
        "app": 5,
        "record": {
            "customer_name": {"value": name},
            "phone": {"value": phone},
            "maker": {"value": maker},
            "model": {"value": model},
            "issue": {"value": issue},
            # 2. kintone側の新しいフィールドコード「lineid」に対して、上の変数（値）をセットします
            "lineid": {"value": line_user_id}
        }
    }
    print("保存データ:", record)
    response = requests.post(KINTONE_URL, headers=HEADERS, json=record)
    print("--- kintone通信結果 ---")
    print("ステータスコード:", response.status_code)
    print("レスポンス中身:", response.text)
    print("------------------------")

    return {"status": "ok"}
