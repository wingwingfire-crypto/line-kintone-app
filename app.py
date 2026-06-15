import requests
from flask import Flask, request

# 1. 最初にFlaskアプリ（app）を定義します（これがないとエラーになります）
app = Flask(__name__)

# ※ KINTONE_URL や HEADERS の設定がファイルの上のほうにある場合は、
# このあたり（@app.route より上）に残しておいてください。


# 2. 次に受付処理を行うルートを定義します
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
            "lineid": {"value": line_user_id}
        }
    }
    
    # すべて関数の内側（インデントが4マスの位置）に正しく並べ替えました
    print("保存データ:", record)
    response = requests.post(KINTONE_URL, headers=HEADERS, json=record)
    
    print("--- kintone通信結果 ---")
    print("ステータスコード:", response.status_code)
    print("レスポンス中身:", response.text)
    print("------------------------")

    return {"status": "ok"}


# 3. 最後にアプリを起動する処理を書きます（もしファイルの下部にあれば残してください）
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
