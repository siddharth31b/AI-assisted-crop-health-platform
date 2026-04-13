from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import os
import re
from uuid import uuid4
from werkzeug.utils import secure_filename
from PIL import Image
import numpy as np

try:
    from keras.models import load_model
    IMAGE_MODEL_IMPORT_ERROR = None
except Exception as exc:
    load_model = None
    IMAGE_MODEL_IMPORT_ERROR = exc

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    CHATBOT_IMPORT_ERROR = None
except Exception as exc:
    AutoModelForCausalLM = None
    AutoTokenizer = None
    CHATBOT_IMPORT_ERROR = exc

app = Flask(__name__)
app.secret_key = "AzxSAzXsAaZxS"
UPLOAD_FOLDER = "static/uploads"
UPLOAD_RESULT_SESSION_KEY = "upload_result"
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

CHATBOT_MODEL_PATH = "models/chatbot"
CROP_MODEL_PATHS = {
    "sugarcane": "models/sugarcane.keras",
    "grapes": "models/grapes_model.keras",
}
DISEASE_LABELS = {
    "sugarcane": {
        0: "Banded Chlorosis",
        1: "Brown Rust",
        2: "Brown Spot",
        3: "Dried Leaves",
        4: "Grassy Shoot",
        5: "Healthy",
        6: "Pokkah Boeng",
        7: "Sett Rot",
        8: "Smut",
        9: "Viral Disease",
        10: "Yellow Leaf",
    },
    "grapes": {
        0: "Black Rot",
        1: "ESCA",
        2: "Healthy",
        3: "Leaf Blight",
    },
}

crop_models = {}
chatbot_tokenizer = None
chatbot_model = None
chatbot_error = None
SUPPORT_BOT_NAME = "Crop Doctor Support AI"


def get_dashboard_url():
    return url_for("admin_dashboard") if session.get("role") == "admin" else url_for("user_dashboard")


def get_upload_state(clear=False):
    if clear:
        session.pop(UPLOAD_RESULT_SESSION_KEY, None)
        return {}
    return session.get(UPLOAD_RESULT_SESSION_KEY, None) or {}


def store_upload_state(**values):
    session[UPLOAD_RESULT_SESSION_KEY] = values


def allowed_image_file(filename):
    if not filename or "." not in filename:
        return False
    extension = filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_IMAGE_EXTENSIONS


def build_unique_upload_name(filename):
    safe_name = secure_filename(filename)
    if not safe_name:
        raise ValueError("Invalid file name.")

    stem, extension = os.path.splitext(safe_name)
    stem = stem or "leaf-upload"
    return f"{stem}-{uuid4().hex[:8]}{extension.lower()}"


def build_upload_context(clear_result=False, **overrides):
    upload_state = get_upload_state(clear=clear_result)
    context = {
        "image_path": None,
        "class_name": None,
        "disease": None,
        "error": None,
        "redirect_url": get_dashboard_url(),
    }
    context.update(upload_state)
    context.update({key: value for key, value in overrides.items() if value is not None})
    return context


def load_crop_model(crop_name):
    if crop_name in crop_models:
        return crop_models[crop_name]

    if load_model is None:
        raise RuntimeError(f"Keras/TensorFlow is not available: {IMAGE_MODEL_IMPORT_ERROR}")

    model_path = CROP_MODEL_PATHS.get(crop_name)
    if not model_path:
        raise ValueError("Invalid crop selection")

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")

    crop_models[crop_name] = load_model(model_path)
    return crop_models[crop_name]


def load_chatbot_components():
    global chatbot_tokenizer, chatbot_model, chatbot_error

    if chatbot_tokenizer is not None and chatbot_model is not None:
        return chatbot_tokenizer, chatbot_model

    if chatbot_error is not None:
        raise RuntimeError(chatbot_error)

    if CHATBOT_IMPORT_ERROR is not None:
        chatbot_error = f"Transformers library is not available: {CHATBOT_IMPORT_ERROR}"
        raise RuntimeError(chatbot_error)

    if not os.path.isdir(CHATBOT_MODEL_PATH):
        chatbot_error = f"Chatbot model folder not found: {CHATBOT_MODEL_PATH}"
        raise RuntimeError(chatbot_error)

    chatbot_tokenizer = AutoTokenizer.from_pretrained(CHATBOT_MODEL_PATH)
    chatbot_model = AutoModelForCausalLM.from_pretrained(CHATBOT_MODEL_PATH)
    return chatbot_tokenizer, chatbot_model


def fallback_chat_response(user_input):
    message = (user_input or "").strip().lower()

    if not message:
        return "Please type your question and try again."
    if any(greeting in message for greeting in ("hello", "hi", "namaste")):
        return "Hello! Ask me about crop diseases, symptoms, watering, or prevention."
    if "sugarcane" in message:
        return "For sugarcane disease checks, select Sugarcane and upload a clear leaf image from the dashboard."
    if "grape" in message or "grapes" in message:
        return "For grapes disease checks, select Grapes and upload a clear leaf photo from the dashboard."
    if "disease" in message or "symptom" in message:
        return "Share the crop name and visible symptoms like spots, yellowing, rust, or blight so I can guide you."
    if "water" in message or "irrigation" in message:
        return "Avoid overwatering, keep drainage good, and water according to crop stage and soil moisture."
    if "fertilizer" in message or "nutrient" in message:
        return "Use balanced fertilizer based on soil condition, and avoid excess nitrogen during disease stress."

    return "Chatbot AI model is not fully available right now, but crop disease detection can still be used."


def normalize_message(message):
    return re.sub(r"\s+", " ", (message or "").strip().lower())


def get_crop_support_notes(selected_crop):
    crop_name = (selected_crop or "").lower()

    if crop_name == "sugarcane":
        return {
            "name": "Sugarcane",
            "diseases": "yellow leaf, brown rust, smut, grassy shoot, pokkah boeng, and brown spot",
            "tips": "upload a sharp photo of a single leaf section with visible spots, streaks, or discoloration",
        }

    if crop_name == "grapes":
        return {
            "name": "Grapes",
            "diseases": "black rot, esca, leaf blight, and healthy leaf conditions",
            "tips": "capture the affected grape leaf in natural light so lesion edges and blight patterns stay visible",
        }

    return {
        "name": "your crop",
        "diseases": "supported disease classes",
        "tips": "upload a close, well-lit leaf image with the affected area clearly visible",
    }


def build_support_context(selected_crop, role):
    crop_notes = get_crop_support_notes(selected_crop)
    selected_crop_text = crop_notes["name"] if selected_crop else "No crop selected"
    role_text = (role or "guest").capitalize()

    return (
        f"Role: {role_text}. "
        f"Selected crop: {selected_crop_text}. "
        "Platform features: login, crop selection, image upload, live camera capture, disease prediction, and model training for admins. "
        "Support policy: the AI assistant is available 24/7 inside the app for instant guidance. "
        "Human handoff is not configured in this project, so do not promise a live human agent. "
        f"When {crop_notes['name']} is selected, likely disease coverage includes {crop_notes['diseases']}. "
        f"Best image advice: {crop_notes['tips']}."
    )


def generate_rule_based_support_response(user_input, selected_crop=None, role=None):
    message = normalize_message(user_input)
    crop_notes = get_crop_support_notes(selected_crop)
    crop_name = crop_notes["name"]

    if not message:
        return "Please type your question. I can help with upload issues, disease checks, crop guidance, and app support."

    if any(word in message for word in ("hello", "hi", "hey", "namaste", "good morning", "good evening")):
        crop_line = (
            f" I can already see {crop_name} as the active crop."
            if selected_crop
            else " Select Sugarcane or Grapes first for crop-specific guidance."
        )
        return (
            f"Hello, I am {SUPPORT_BOT_NAME}. I am available 24/7 for instant help with crop prediction, uploads, camera issues, and prevention tips."
            f"{crop_line}"
        )

    if any(word in message for word in ("24/7", "24x7", "always", "online", "available", "working", "live support")):
        return (
            f"{SUPPORT_BOT_NAME} is available 24/7 inside this app. If the language model is busy or unavailable, the built-in support knowledge still replies instantly so the chat keeps working."
        )

    if any(word in message for word in ("support", "help", "assist", "customer care")):
        return (
            "I can help with crop selection, image upload, camera capture, disease result understanding, irrigation basics, fertilizer basics, and prevention guidance. "
            "If you want crop-specific advice, tell me the crop name or select it from the dashboard."
        )

    if any(word in message for word in ("login", "password", "signin", "sign in")):
        return (
            "Use the login page credentials configured for this demo. After sign-in, users can open the dashboard, choose a crop, run prediction, and use the support assistant from any logged-in page."
        )

    if any(word in message for word in ("upload", "photo", "image", "file", "jpg", "jpeg", "png")):
        return (
            f"Before upload, choose the crop first. Then upload a clear leaf image in PNG, JPG, or JPEG format. For the best result, {crop_notes['tips']}."
        )

    if any(word in message for word in ("camera", "capture", "cam")):
        return (
            "Open the camera after selecting a crop, allow camera permission in the browser, keep the leaf steady, and capture in good light. "
            "If the camera does not open, refresh the page and check browser permission settings."
        )

    if any(word in message for word in ("prediction", "result", "confidence", "diagnosis", "detect")):
        return (
            "The app predicts the crop disease from the uploaded leaf image and shows a confidence score. "
            "If the confidence looks low or the result says uncertain prediction, try another sharper image with a cleaner background."
        )

    if any(word in message for word in ("symptom", "spot", "yellow", "rust", "blight", "rot", "smut", "disease")):
        crop_focus = (
            f"For {crop_name}, the app can help around {crop_notes['diseases']}."
            if selected_crop
            else "Select Sugarcane or Grapes first so I can narrow the likely disease guidance."
        )
        return (
            f"{crop_focus} Describe visible signs like yellowing, rust-like patches, blight edges, rot, or streaks, and upload a close leaf image for a stronger diagnosis flow."
        )

    if "sugarcane" in message:
        return (
            "For sugarcane support, watch for yellow leaf, rust, smut, grassy shoot, and brown spot patterns. "
            "Use a close photo of the affected leaf area, then compare the prediction with visible symptoms before taking action."
        )

    if "grape" in message or "grapes" in message:
        return (
            "For grapes support, common checks in this app include black rot, esca, and leaf blight. "
            "Upload a bright, focused leaf image where lesion edges and discoloration are clearly visible."
        )

    if any(word in message for word in ("water", "watering", "irrigation")):
        return (
            "During disease stress, avoid overwatering and water according to soil moisture instead of a fixed guess. "
            "Good drainage and early observation of leaf changes help prevent additional stress."
        )

    if any(word in message for word in ("fertilizer", "fertiliser", "nutrient", "nutrition")):
        return (
            "Use balanced nutrition and avoid excessive nitrogen when plants are already under disease stress. "
            "If symptoms are severe, confirm the disease first so nutrient correction does not hide the root problem."
        )

    if any(word in message for word in ("prevent", "prevention", "protect", "care")):
        return (
            "Prevention basics are clean field hygiene, early symptom monitoring, disease-free planting material, balanced irrigation, and quick removal of heavily affected leaves when appropriate."
        )

    if any(word in message for word in ("human", "agent", "call", "phone", "contact", "email")):
        return (
            "This project currently provides AI-based support inside the app, but live human handoff is not configured yet. "
            "For now, you can continue here and I will help with the diagnosis flow and basic crop-care questions."
        )

    if role == "admin" and any(word in message for word in ("train", "dataset", "class", "admin")):
        return (
            "As admin, you can open Train Model, enter a crop name, choose the number of classes, and upload at least 5 images per class. "
            "The app will organize the class folders for future model work."
        )

    if any(word in message for word in ("thanks", "thank you", "thx")):
        return "You are welcome. If you want, ask me about uploads, disease results, irrigation, fertilizer, or prevention next."

    return (
        f"I can help with support for crop selection, uploads, camera capture, disease prediction, and {crop_name if selected_crop else 'crop-specific'} guidance. "
        "Ask a short question like 'upload not working', 'how to prevent leaf blight', or 'what does confidence score mean?'."
    )


def generate_ai_support_response(user_input, selected_crop=None, role=None):
    tokenizer, model = load_chatbot_components()
    support_context = build_support_context(selected_crop, role)
    prompt = (
        f"{support_context}\n"
        "Instruction: Reply as a concise customer support chatbot. Give practical app help first, then brief crop guidance if relevant. "
        "Do not mention unsupported features or make up human escalation.\n"
        f"Customer: {user_input}\n"
        "Support:"
    )
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
    outputs = model.generate(
        inputs["input_ids"],
        attention_mask=inputs.get("attention_mask"),
        max_new_tokens=90,
        do_sample=True,
        temperature=0.4,
        top_p=0.9,
        no_repeat_ngram_size=3,
        pad_token_id=tokenizer.eos_token_id,
    )
    decoded = tokenizer.decode(outputs[0], skip_special_tokens=True)
    response = decoded.split("Support:")[-1].strip()

    if not response or response == prompt.strip():
        raise RuntimeError("Model returned an empty support response.")

    return response


def model_prediction(image_path):
    try:
        image = Image.open(image_path).convert("RGB")
        image = image.resize((244, 244))
        image = np.array(image) / 255.0
        image = np.expand_dims(image, axis=0)

        app.logger.info(f"Session contents during prediction: {session}")

        selected_crop = session.get("selected_crop")
        if not selected_crop:
            return "Error", "No crop selected", 0

        crop_model = load_crop_model(selected_crop)
        disease_labels = DISEASE_LABELS.get(selected_crop)
        if not disease_labels:
            return "Error", "Invalid crop selection", 0

        predictions = crop_model.predict(image)
        disease_idx = int(np.argmax(predictions))
        confidence = float(np.max(predictions))

        if confidence < 0.5:
            return selected_crop.capitalize(), "Uncertain prediction", confidence

        disease = disease_labels.get(disease_idx, "Unknown Disease")
        return selected_crop.capitalize(), disease, confidence
    except Exception as exc:
        return "Error", f"Prediction failed: {exc}", 0


@app.route("/set_crop", methods=["POST"])
def set_crop():
    data = request.get_json(silent=True) or {}
    selected_crop = data.get("crop")

    if not selected_crop:
        return jsonify({"success": False, "message": "No crop selected."}), 400
    if selected_crop not in CROP_MODEL_PATHS:
        return jsonify({"success": False, "message": "Invalid crop selected."}), 400

    session["selected_crop"] = selected_crop
    return jsonify({"success": True, "message": f"Crop '{selected_crop}' selected."})


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == "user" and password == "user":
            session["role"] = "user"
            return redirect(url_for("user_dashboard"))
        if username == "admin" and password == "admin":
            session["role"] = "admin"
            return redirect(url_for("admin_dashboard"))

        flash("Invalid username or password. Please try again.", "error")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/user_dashboard", methods=["GET", "POST"])
def user_dashboard():
    app.logger.info(f"Session contents at dashboard: {session}")
    if session.get("role") != "user":
        return redirect(url_for("login"))

    if request.method == "POST":
        return redirect(url_for("upload_page"))

    return render_template("user_dashboard.html")


@app.route("/admin_dashboard", methods=["GET", "POST"])
def admin_dashboard():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    if request.method == "POST":
        action = request.form.get("action")
        if action == "upload":
            return redirect(url_for("upload_page"))
        if action == "train":
            return redirect(url_for("train_model"))

    return render_template("admin_dashboard.html")


@app.route("/upload", methods=["GET"])
def upload_page():
    clear_result = request.args.get("reset") == "1"
    return render_template("upload.html", **build_upload_context(clear_result=clear_result))


@app.route("/upload", methods=["POST"])
def upload_file():
    app.logger.info(f"Crop selected for upload: {session.get('selected_crop')}")

    if "file" not in request.files:
        store_upload_state(error="No file received.")
        return redirect(url_for("upload_page"))

    file = request.files["file"]
    if file.filename == "":
        store_upload_state(error="No file selected.")
        return redirect(url_for("upload_page"))

    if "selected_crop" not in session:
        flash("Please select a crop before uploading an image.")
        store_upload_state(error="Please select a crop first.")
        return redirect(url_for("upload_page"))

    if not allowed_image_file(file.filename):
        store_upload_state(error="Please upload a PNG, JPG, or JPEG image.")
        return redirect(url_for("upload_page"))

    try:
        filename = build_unique_upload_name(file.filename)
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        plant, disease, confidence = model_prediction(file_path)
        disease_text = disease if confidence == 0 else f"{disease} ({confidence * 100:.2f}%)"

        store_upload_state(
            image_path=filename,
            class_name=plant,
            disease=disease_text,
            error=None,
        )
        return redirect(url_for("upload_page"))
    except Exception as exc:
        store_upload_state(error=str(exc))
        return redirect(url_for("upload_page"))


@app.route("/chatbot")
def chatbot_page():
    return render_template("chatbot.html", redirect_url=get_dashboard_url())


@app.route("/chat", methods=["POST"])
def chat():
    try:
        payload = request.get_json(silent=True) or {}
        user_input = payload.get("message")
        if not user_input:
            return {"error": "No message provided"}, 400

        try:
            response_text = generate_ai_support_response(
                user_input,
                selected_crop=session.get("selected_crop"),
                role=session.get("role"),
            )
        except Exception as exc:
            app.logger.warning(f"Chatbot fallback activated: {exc}")
            response_text = generate_rule_based_support_response(
                user_input,
                selected_crop=session.get("selected_crop"),
                role=session.get("role"),
            )

        return {"response": response_text}, 200
    except Exception as exc:
        return {"error": str(exc)}, 500


@app.route("/train_model", methods=["GET", "POST"])
def train_model():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template("train_model.html")

    crop_name = request.form.get("crop_name")
    num_classes = int(request.form.get("num_classes"))
    class_names = []

    crop_folder = os.path.join(UPLOAD_FOLDER, crop_name)
    os.makedirs(crop_folder, exist_ok=True)

    for i in range(1, num_classes + 1):
        class_name = request.form.get(f"class_name_{i}")
        class_folder = os.path.join(crop_folder, class_name)
        os.makedirs(class_folder, exist_ok=True)

        files = request.files.getlist(f"class_images_{i}")
        if len(files) < 5:
            flash(f"Please upload at least 5 images for class {class_name}.")
            return redirect(url_for("train_model"))

        for file in files:
            if file:
                filename = secure_filename(file.filename)
                file.save(os.path.join(class_folder, filename))

        class_names.append(class_name)

    flash(f"Model data for {crop_name} successfully uploaded and organized!")
    return redirect(url_for("train_model"))


@app.errorhandler(404)
def page_not_found(error):
    return render_template("error.html", error_message="Page not found."), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
