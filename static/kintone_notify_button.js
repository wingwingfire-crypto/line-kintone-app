(function () {
    "use strict";

    const NOTIFY_BASE_URL = "https://line-kintone-app.onrender.com/notify";

    const EVENTS = [
        "app.record.detail.show",
        "mobile.app.record.detail.show"
    ];

    kintone.events.on(EVENTS, function (event) {
        const record = event.record;

        // 二重表示防止
        if (document.getElementById("lineNotifyButtonArea")) {
            return event;
        }

        const recordId = event.recordId;
        const lineId = record.lineid && record.lineid.value ? record.lineid.value : "";
        const status = record["ドロップダウン"] && record["ドロップダウン"].value ? record["ドロップダウン"].value : "";
        const customerName = record.customer_name && record.customer_name.value ? record.customer_name.value : "";
        const notifyUrlField = record.notifyurl && record.notifyurl.value ? record.notifyurl.value : "";

        const buttonArea = document.createElement("div");
        buttonArea.id = "lineNotifyButtonArea";
        buttonArea.style.display = "flex";
        buttonArea.style.alignItems = "center";
        buttonArea.style.gap = "10px";
        buttonArea.style.margin = "0 0 12px 0";

        const button = document.createElement("button");
        button.id = "lineNotifyButton";
        button.textContent = "📩 LINE通知を送信";
        button.style.background = "#06c755";
        button.style.color = "#ffffff";
        button.style.border = "none";
        button.style.borderRadius = "8px";
        button.style.padding = "10px 16px";
        button.style.fontSize = "15px";
        button.style.fontWeight = "bold";
        button.style.cursor = "pointer";
        button.style.boxShadow = "0 2px 6px rgba(0,0,0,0.18)";

        const statusText = document.createElement("span");
        statusText.id = "lineNotifyStatus";
        statusText.style.fontSize = "13px";
        statusText.style.color = "#666";

        if (!lineId) {
            button.disabled = true;
            button.style.background = "#999";
            button.style.cursor = "not-allowed";
            statusText.textContent = "LINE IDがないため通知できません";
        } else {
            statusText.textContent = "現在の進捗：" + (status || "未設定");
        }

        button.addEventListener("mouseover", function () {
            if (!button.disabled) {
                button.style.background = "#04a846";
            }
        });

        button.addEventListener("mouseout", function () {
            if (!button.disabled) {
                button.style.background = "#06c755";
            }
        });

        button.addEventListener("click", function () {
            if (!lineId) {
                alert("LINE IDがありません。通知できません。");
                return;
            }

            const confirmMessage =
                "この内容でLINE通知を送信しますか？\n\n" +
                "お客様名：" + (customerName || "未入力") + "\n" +
                "進捗状況：" + (status || "未設定") + "\n" +
                "レコード番号：" + recordId;

            if (!window.confirm(confirmMessage)) {
                return;
            }

            button.disabled = true;
            button.textContent = "送信中...";
            button.style.background = "#999";
            statusText.textContent = "LINE通知を送信しています...";

            let notifyUrl = "";

            if (notifyUrlField) {
                notifyUrl = notifyUrlField;
            } else {
                notifyUrl = NOTIFY_BASE_URL + "?recordid=" + encodeURIComponent(recordId);
            }

            fetch(notifyUrl, {
                method: "GET",
                mode: "cors"
            })
                .then(function (response) {
                    return response.text().then(function (text) {
                        return {
                            ok: response.ok,
                            status: response.status,
                            text: text
                        };
                    });
                })
                .then(function (result) {
                    if (!result.ok) {
                        throw new Error("HTTP " + result.status + " : " + result.text);
                    }

                    button.textContent = "✅ 送信済み";
                    button.style.background = "#2e7d32";
                    statusText.textContent = "LINE通知を送信しました";

                    alert("LINE通知を送信しました。");
                })
                .catch(function (error) {
                    console.error("LINE通知送信エラー:", error);

                    button.disabled = false;
                    button.textContent = "📩 LINE通知を送信";
                    button.style.background = "#06c755";
                    statusText.textContent = "送信に失敗しました";

                    alert("LINE通知の送信に失敗しました。\n\n" + error);
                });
        });

        buttonArea.appendChild(button);
        buttonArea.appendChild(statusText);

        const headerSpace = kintone.app.record.getHeaderMenuSpaceElement
            ? kintone.app.record.getHeaderMenuSpaceElement()
            : null;

        if (headerSpace) {
            headerSpace.appendChild(buttonArea);
        } else {
            const fallback = document.querySelector(".gaia-argoui-app-show-toolbar");
            if (fallback) {
                fallback.appendChild(buttonArea);
            }
        }

        return event;
    });
})();
