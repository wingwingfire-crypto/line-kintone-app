(function () {
    "use strict";

    const BASE_URL = "https://line-kintone-app.onrender.com";
    const BUTTON_ID = "line-notify-simple-button";
    const MODAL_ID = "line-notify-confirm-modal";

    const SHOW_EVENTS = [
        "app.record.detail.show"
    ];

    function createButton(event) {
        const headerSpace = kintone.app.record.getHeaderMenuSpaceElement();

        if (!headerSpace) {
            return event;
        }

        if (document.getElementById(BUTTON_ID)) {
            return event;
        }

        const button = document.createElement("button");
        button.id = BUTTON_ID;
        button.textContent = "LINE通知を送信";
        button.type = "button";
        button.style.backgroundColor = "#06C755";
        button.style.color = "#ffffff";
        button.style.border = "none";
        button.style.borderRadius = "8px";
        button.style.padding = "10px 18px";
        button.style.fontSize = "15px";
        button.style.fontWeight = "700";
        button.style.cursor = "pointer";
        button.style.marginLeft = "8px";

        button.onclick = function () {
            const recordId = kintone.app.record.getId();

            if (!recordId) {
                showMessageModal({
                    title: "送信できません",
                    message: "レコード番号を確認できませんでした。",
                    type: "error"
                });
                return;
            }

            showConfirmModal(recordId, button);
        };

        headerSpace.appendChild(button);
        return event;
    }

    function showConfirmModal(recordId, button) {
        removeModal();

        const overlay = document.createElement("div");
        overlay.id = MODAL_ID;
        overlay.style.position = "fixed";
        overlay.style.top = "0";
        overlay.style.left = "0";
        overlay.style.width = "100%";
        overlay.style.height = "100%";
        overlay.style.backgroundColor = "rgba(0, 0, 0, 0.38)";
        overlay.style.zIndex = "99999";
        overlay.style.display = "flex";
        overlay.style.alignItems = "center";
        overlay.style.justifyContent = "center";
        overlay.style.padding = "20px";

        const box = document.createElement("div");
        box.style.backgroundColor = "#ffffff";
        box.style.borderRadius = "16px";
        box.style.padding = "26px 24px";
        box.style.maxWidth = "460px";
        box.style.width = "100%";
        box.style.boxShadow = "0 12px 32px rgba(0,0,0,0.22)";
        box.style.textAlign = "center";

        const title = document.createElement("div");
        title.textContent = "本当に送信しますか？";
        title.style.fontSize = "24px";
        title.style.fontWeight = "800";
        title.style.color = "#222222";
        title.style.lineHeight = "1.45";
        title.style.marginBottom = "22px";

        const buttonRow = document.createElement("div");
        buttonRow.style.display = "flex";
        buttonRow.style.gap = "12px";
        buttonRow.style.justifyContent = "center";

        const cancelButton = document.createElement("button");
        cancelButton.type = "button";
        cancelButton.textContent = "キャンセル";
        cancelButton.style.flex = "1";
        cancelButton.style.padding = "13px";
        cancelButton.style.borderRadius = "10px";
        cancelButton.style.border = "1px solid #cccccc";
        cancelButton.style.backgroundColor = "#ffffff";
        cancelButton.style.color = "#333333";
        cancelButton.style.fontSize = "15px";
        cancelButton.style.fontWeight = "700";
        cancelButton.style.cursor = "pointer";
        cancelButton.onclick = removeModal;

        const sendButton = document.createElement("button");
        sendButton.type = "button";
        sendButton.textContent = "送信する";
        sendButton.style.flex = "1";
        sendButton.style.padding = "13px";
        sendButton.style.borderRadius = "10px";
        sendButton.style.border = "none";
        sendButton.style.backgroundColor = "#06C755";
        sendButton.style.color = "#ffffff";
        sendButton.style.fontSize = "15px";
        sendButton.style.fontWeight = "800";
        sendButton.style.cursor = "pointer";
        sendButton.onclick = function () {
            removeModal();
            sendNotify(recordId, button);
        };

        buttonRow.appendChild(cancelButton);
        buttonRow.appendChild(sendButton);
        box.appendChild(title);
        box.appendChild(buttonRow);
        overlay.appendChild(box);
        document.body.appendChild(overlay);
    }

    function showMessageModal(options) {
        removeModal();

        const overlay = document.createElement("div");
        overlay.id = MODAL_ID;
        overlay.style.position = "fixed";
        overlay.style.top = "0";
        overlay.style.left = "0";
        overlay.style.width = "100%";
        overlay.style.height = "100%";
        overlay.style.backgroundColor = "rgba(0, 0, 0, 0.38)";
        overlay.style.zIndex = "99999";
        overlay.style.display = "flex";
        overlay.style.alignItems = "center";
        overlay.style.justifyContent = "center";
        overlay.style.padding = "20px";

        const box = document.createElement("div");
        box.style.backgroundColor = "#ffffff";
        box.style.borderRadius = "16px";
        box.style.padding = "26px 24px";
        box.style.maxWidth = "500px";
        box.style.width = "100%";
        box.style.boxShadow = "0 12px 32px rgba(0,0,0,0.22)";
        box.style.textAlign = "center";

        const title = document.createElement("div");
        title.textContent = options.title || "通知結果";
        title.style.fontSize = "22px";
        title.style.fontWeight = "800";
        title.style.lineHeight = "1.45";
        title.style.marginBottom = "14px";
        title.style.color = options.type === "error" ? "#D32F2F" : "#06C755";

        const message = document.createElement("div");
        message.textContent = options.message || "";
        message.style.fontSize = "17px";
        message.style.fontWeight = "700";
        message.style.lineHeight = "1.65";
        message.style.color = "#222222";
        message.style.marginBottom = "22px";

        const closeButton = document.createElement("button");
        closeButton.type = "button";
        closeButton.textContent = "閉じる";
        closeButton.style.width = "100%";
        closeButton.style.padding = "13px";
        closeButton.style.borderRadius = "10px";
        closeButton.style.border = "none";
        closeButton.style.backgroundColor = options.type === "error" ? "#D32F2F" : "#06C755";
        closeButton.style.color = "#ffffff";
        closeButton.style.fontSize = "15px";
        closeButton.style.fontWeight = "800";
        closeButton.style.cursor = "pointer";
        closeButton.onclick = removeModal;

        box.appendChild(title);
        box.appendChild(message);
        box.appendChild(closeButton);
        overlay.appendChild(box);
        document.body.appendChild(overlay);
    }

    function removeModal() {
        const current = document.getElementById(MODAL_ID);
        if (current) {
            current.remove();
        }
    }

    function sendNotify(recordId, button) {
        const originalText = button.textContent;
        button.disabled = true;
        button.textContent = "送信中...";
        button.style.opacity = "0.65";
        button.style.cursor = "not-allowed";

        fetch(BASE_URL + "/notify?recordid=" + encodeURIComponent(recordId), {
            method: "GET"
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
                    showMessageModal({
                        title: "送信できませんでした",
                        message: result.text || "通知送信中にエラーが発生しました。",
                        type: "error"
                    });
                    return;
                }

                if (
                    result.text.indexOf("既に同じ内容") !== -1 ||
                    result.text.indexOf("重複") !== -1 ||
                    result.text.indexOf("同じ内容") !== -1
                ) {
                    showMessageModal({
                        title: "送信できません",
                        message: "同じ内容なので送信できません。何か内容を変えたら送れます。",
                        type: "error"
                    });
                    return;
                }

                showMessageModal({
                    title: "送信しました",
                    message: "LINE通知を送信しました。",
                    type: "success"
                });
            })
            .catch(function (error) {
                showMessageModal({
                    title: "送信できませんでした",
                    message: String(error),
                    type: "error"
                });
            })
            .finally(function () {
                button.disabled = false;
                button.textContent = originalText;
                button.style.opacity = "1";
                button.style.cursor = "pointer";
            });
    }

    kintone.events.on(SHOW_EVENTS, createButton);
})();
