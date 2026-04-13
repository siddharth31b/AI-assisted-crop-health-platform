const SUPPORT_STORAGE_KEY = "crop-doctor-support-history";
const SUPPORT_MAX_MESSAGES = 24;
let supportElements = null;
let appInitialized = false;
let uploadInProgress = false;

function showToast(message, type = "info") {
    const host = document.querySelector("[data-alert-host]");
    if (!host) {
        window.alert(message);
        return;
    }

    const node = document.createElement("div");
    node.className = `alert alert-${type}`;
    node.textContent = message;
    host.appendChild(node);

    window.setTimeout(() => {
        node.remove();
    }, 3500);
}

function getSelectedCrop() {
    const selected = document.querySelector("input[name='crop']:checked");
    return selected ? selected.value : "";
}

function updateActionState() {
    const selectedCrop = getSelectedCrop();
    document.querySelectorAll("[data-requires-crop='true']").forEach((button) => {
        button.disabled = uploadInProgress || !selectedCrop;
    });

    document.querySelectorAll("[data-upload-trigger='true']").forEach((button) => {
        if (!button.dataset.defaultLabel) {
            button.dataset.defaultLabel = button.textContent.trim();
        }
        button.textContent = uploadInProgress
            ? (button.dataset.loadingLabel || "Uploading...")
            : button.dataset.defaultLabel;
    });
}

function setUploadInProgress(nextState) {
    uploadInProgress = nextState;
    updateActionState();
}

async function setCrop(selectedCrop) {
    try {
        const response = await fetch("/set_crop", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ crop: selectedCrop }),
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || "Crop selection failed.");
        }

        document.querySelectorAll("[data-crop-card]").forEach((card) => {
            const active = card.dataset.cropCard === selectedCrop;
            card.classList.toggle("selected", active);
            const input = card.querySelector("input[type='radio']");
            if (input) {
                input.checked = active;
            }
        });

        document.querySelectorAll("[data-selected-crop-label]").forEach((node) => {
            node.textContent = selectedCrop.charAt(0).toUpperCase() + selectedCrop.slice(1);
        });

        document.querySelectorAll(".support-meta-row .crop-pill").forEach((node) => {
            if (node.textContent.startsWith("Crop:")) {
                node.textContent = `Crop: ${selectedCrop.charAt(0).toUpperCase() + selectedCrop.slice(1)}`;
            }
        });

        updateActionState();
        showToast(`${selectedCrop} crop selected.`, "success");
    } catch (error) {
        showToast(error.message || "Unable to set crop.", "error");
    }
}

function uploadPhoto() {
    if (uploadInProgress) {
        return;
    }

    const selectedCrop = getSelectedCrop();
    if (!selectedCrop) {
        showToast("Please select a crop first.", "error");
        return;
    }

    const fileInput = document.getElementById("hidden-file-upload");
    if (fileInput) {
        fileInput.value = "";
        fileInput.click();
    }
}

async function submitUpload(file) {
    if (!file || uploadInProgress) {
        return;
    }

    const formData = new FormData();
    formData.append("file", file);

    closeSupportPanel();
    setUploadInProgress(true);

    try {
        const response = await fetch("/upload", {
            method: "POST",
            body: formData,
            redirect: "follow",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
            },
        });

        if (!response.ok) {
            throw new Error("Image upload failed.");
        }

        document.body.classList.remove("support-open");
        window.location.assign("/upload");
    } catch (error) {
        setUploadInProgress(false);
        showToast(error.message || "Unable to upload image.", "error");
    }
}

async function capturePhoto() {
    if (uploadInProgress) {
        return;
    }

    const selectedCrop = getSelectedCrop();
    if (!selectedCrop) {
        showToast("Please select a crop before opening the camera.", "error");
        return;
    }

    let stream;
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.innerHTML = `
        <div class="camera-modal">
            <div>
                <span class="eyebrow">Live Capture</span>
                <h3 class="section-title">Capture a clear leaf image</h3>
                <p class="section-subtitle">Keep the leaf centered, well-lit, and steady for the best prediction.</p>
            </div>
            <video autoplay playsinline></video>
            <div class="camera-controls">
                <button class="button-primary" type="button" data-capture>Capture & Analyze</button>
                <button class="button-secondary" type="button" data-close>Close Camera</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);

    const video = overlay.querySelector("video");
    const closeButton = overlay.querySelector("[data-close]");
    const captureButton = overlay.querySelector("[data-capture]");

    const cleanup = () => {
        if (stream) {
            stream.getTracks().forEach((track) => track.stop());
        }
        overlay.remove();
    };

    closeButton.addEventListener("click", cleanup);

    try {
        stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: { ideal: "environment" } },
            audio: false,
        });
        video.srcObject = stream;
    } catch (error) {
        cleanup();
        showToast(`Unable to access camera: ${error.message}`, "error");
        return;
    }

    captureButton.addEventListener("click", () => {
        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth || 1280;
        canvas.height = video.videoHeight || 720;
        const context = canvas.getContext("2d");
        context.drawImage(video, 0, 0, canvas.width, canvas.height);

        captureButton.disabled = true;
        captureButton.textContent = "Analyzing...";

        canvas.toBlob(async (blob) => {
            if (!blob) {
                captureButton.disabled = false;
                captureButton.textContent = "Capture & Analyze";
                showToast("Could not capture image. Please try again.", "error");
                return;
            }

            const fileName = `captured_${Date.now()}.png`;
            await submitUpload(new File([blob], fileName, { type: "image/png" }));
            cleanup();
        }, "image/png");
    });
}

function trainModel() {
    window.location.href = "/train_model";
}

function loadSupportHistory() {
    try {
        const raw = window.localStorage.getItem(SUPPORT_STORAGE_KEY);
        const parsed = raw ? JSON.parse(raw) : [];
        return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
        return [];
    }
}

function saveSupportHistory(messages) {
    window.localStorage.setItem(
        SUPPORT_STORAGE_KEY,
        JSON.stringify(messages.slice(-SUPPORT_MAX_MESSAGES)),
    );
}

function buildSupportMessage(message, type) {
    const bubble = document.createElement("div");
    bubble.className = `chat-message ${type}`;
    bubble.textContent = message;
    return bubble;
}

function renderSupportMessages() {
    if (!supportElements) {
        return;
    }

    const history = loadSupportHistory();
    supportElements.messages.innerHTML = "";

    if (!history.length) {
        supportElements.messages.appendChild(
            buildSupportMessage(
                "Hello! I am Crop Doctor Support AI. I am available 24/7 for upload help, diagnosis support, and crop-care guidance.",
                "bot",
            ),
        );
        return;
    }

    history.forEach((item) => {
        supportElements.messages.appendChild(buildSupportMessage(item.text, item.type));
    });
    supportElements.messages.scrollTop = supportElements.messages.scrollHeight;
}

function appendSupportMessage(message, type, persist = true) {
    if (!supportElements) {
        return;
    }

    supportElements.messages.appendChild(buildSupportMessage(message, type));
    supportElements.messages.scrollTop = supportElements.messages.scrollHeight;

    if (!persist) {
        return;
    }

    const history = loadSupportHistory();
    history.push({ text: message, type });
    saveSupportHistory(history);
}

function setSupportPanelState(isOpen) {
    if (!supportElements) {
        return;
    }

    supportElements.panel.style.display = isOpen ? "grid" : "none";
    supportElements.backdrop.style.display = isOpen ? "block" : "none";
    supportElements.panel.hidden = !isOpen;
    supportElements.backdrop.hidden = !isOpen;
    supportElements.toggle.setAttribute("aria-expanded", String(isOpen));
    supportElements.widget.classList.toggle("open", isOpen);
    document.body.classList.toggle("support-open", isOpen);

    if (isOpen) {
        window.setTimeout(() => {
            supportElements.input.focus();
            supportElements.messages.scrollTop = supportElements.messages.scrollHeight;
        }, 80);
    }
}

function toggleChat(forceState) {
    if (!supportElements) {
        return;
    }

    const isCurrentlyOpen = supportElements.panel.style.display === "grid";
    const nextState = typeof forceState === "boolean" ? forceState : !isCurrentlyOpen;
    setSupportPanelState(nextState);
}

function closeSupportPanel() {
    toggleChat(false);
}

function handleSupportClose(event) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }

    closeSupportPanel();
}

function openChat(prefillMessage = "") {
    if (!supportElements) {
        window.location.href = "/chatbot";
        return;
    }

    toggleChat(true);
    if (prefillMessage) {
        supportElements.input.value = prefillMessage;
        supportElements.input.focus();
    }
}

function clearSupportChat() {
    window.localStorage.removeItem(SUPPORT_STORAGE_KEY);
    renderSupportMessages();
    showToast("Support chat cleared.", "info");
}

async function sendSupportMessage(messageOverride = "") {
    if (!supportElements) {
        return;
    }

    const message = (messageOverride || supportElements.input.value).trim();
    if (!message) {
        showToast("Please enter a message first.", "error");
        return;
    }

    appendSupportMessage(message, "user");
    supportElements.input.value = "";
    supportElements.send.disabled = true;

    const typingNode = buildSupportMessage("Typing...", "bot");
    typingNode.dataset.typing = "true";
    supportElements.messages.appendChild(typingNode);
    supportElements.messages.scrollTop = supportElements.messages.scrollHeight;

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                message,
                page: document.body.dataset.page || "",
                path: window.location.pathname,
            }),
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || "Support request failed.");
        }

        typingNode.remove();
        appendSupportMessage(data.response || "No response received.", "bot");
    } catch (error) {
        typingNode.remove();
        appendSupportMessage(
            error.message || "Something went wrong while contacting support.",
            "bot",
        );
    } finally {
        supportElements.send.disabled = false;
        supportElements.input.focus();
    }
}

function initializeSupportWidget() {
    const widget = document.querySelector("[data-support-widget]");
    if (!widget) {
        supportElements = null;
        return;
    }

    supportElements = {
        widget,
        toggle: widget.querySelector("[data-support-toggle]"),
        close: widget.querySelector("[data-support-close]"),
        backdrop: widget.querySelector("[data-support-backdrop]"),
        panel: widget.querySelector(".support-panel"),
        input: widget.querySelector("[data-support-input]"),
        send: widget.querySelector("[data-support-send]"),
        messages: widget.querySelector("[data-support-messages]"),
        clear: widget.querySelector("[data-support-clear]"),
    };

    if (!supportElements.toggle || !supportElements.close || !supportElements.backdrop || !supportElements.panel) {
        supportElements = null;
        return;
    }

    supportElements.panel.hidden = true;
    supportElements.panel.style.display = "none";
    supportElements.backdrop.hidden = true;
    supportElements.backdrop.style.display = "none";
    supportElements.toggle.setAttribute("aria-expanded", "false");
    supportElements.widget.classList.remove("open");
    document.body.classList.remove("support-open");

    renderSupportMessages();
    setSupportPanelState(false);

    supportElements.toggle.addEventListener("click", () => {
        toggleChat();
    });

    supportElements.close.addEventListener("click", handleSupportClose);
    supportElements.close.addEventListener("pointerup", handleSupportClose);

    supportElements.backdrop.addEventListener("click", () => {
        closeSupportPanel();
    });

    supportElements.send.addEventListener("click", () => {
        sendSupportMessage();
    });

    supportElements.input.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            sendSupportMessage();
        }
    });

    supportElements.clear.addEventListener("click", () => {
        clearSupportChat();
    });

    document.querySelectorAll("[data-support-prompt]").forEach((button) => {
        button.addEventListener("click", () => {
            openChat();
            sendSupportMessage(button.dataset.supportPrompt || "");
        });
    });

    document.querySelectorAll("[data-open-support-chat]").forEach((button) => {
        button.addEventListener("click", () => {
            openChat();
        });
    });

    supportElements.panel.addEventListener("click", (event) => {
        const closeButton = event.target.closest("[data-support-close]");
        if (closeButton) {
            handleSupportClose(event);
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && supportElements && !supportElements.panel.hidden) {
            closeSupportPanel();
        }
    });
}

window.toggleChat = toggleChat;
window.openChat = openChat;

function initializeApp() {
    if (appInitialized) {
        return;
    }

    appInitialized = true;
    const hiddenUpload = document.getElementById("hidden-file-upload");
    if (hiddenUpload) {
        hiddenUpload.addEventListener("change", () => {
            const [file] = hiddenUpload.files || [];
            hiddenUpload.value = "";
            if (file) {
                submitUpload(file);
            }
        });
    }

    document.querySelectorAll("[data-dashboard-upload]").forEach((button) => {
        button.addEventListener("click", uploadPhoto);
    });

    document.querySelectorAll("[data-dashboard-capture]").forEach((button) => {
        button.addEventListener("click", capturePhoto);
    });

    document.querySelectorAll("[data-crop-card]").forEach((card) => {
        card.addEventListener("click", () => {
            const crop = card.dataset.cropCard;
            if (crop) {
                setCrop(crop);
            }
        });
    });

    initializeSupportWidget();
    updateActionState();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeApp);
} else {
    initializeApp();
}
