# AI-Assisted Crop Health Platform (Crop Doctor)

AI-Assisted Crop Health Platform, also presented in the UI as Crop Doctor, is a Flask-based crop disease detection project built for final-year presentation and practical demos. The app lets users select a crop, upload or capture a leaf image, get a disease prediction, and ask follow-up questions through an in-app support assistant.

## What the project includes

- Leaf image disease detection for `Sugarcane` and `Grapes`
- Upload-based prediction flow with confidence score
- Live camera capture from the dashboard
- User and admin dashboards
- In-app AI support chatbot with rule-based fallback
- Admin training-data organizer for new class folders and image sets

## Supported crops and disease classes

### Sugarcane
- Banded Chlorosis
- Brown Rust
- Brown Spot
- Dried Leaves
- Grassy Shoot
- Healthy
- Pokkah Boeng
- Sett Rot
- Smut
- Viral Disease
- Yellow Leaf

### Grapes
- Black Rot
- ESCA
- Healthy
- Leaf Blight

## Tech stack

- Python
- Flask
- TensorFlow / Keras
- Pillow
- NumPy
- Transformers
- HTML, CSS, JavaScript

## Project flow

### User flow
1. Login as `user`
2. Open the user dashboard
3. Select a crop
4. Upload a leaf image or use the camera
5. View crop class, disease result, and confidence on the upload page
6. Use the support assistant for guidance

### Admin flow
1. Login as `admin`
2. Open the admin dashboard
3. Select a crop for testing the prediction flow
4. Open `Train Model`
5. Enter crop name, number of classes, class names, and upload at least 5 images per class
6. Let the app organize the uploaded dataset into folders

## Login credentials

Use these demo credentials from the login screen:

- User
  - Username: `user`
  - Password: `user`
- Admin
  - Username: `admin`
  - Password: `admin`

## Installation

### 1. Clone the project

```bash
git clone <your-repository-url>
cd "AI-assisted crop health platform"
```

If your local folder name is different, use that folder name in the `cd` command.

### 2. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
python app.py
```

The application starts on:

```text
http://127.0.0.1:5000
```

## Requirements

Current Python packages used by the project:

- `flask`
- `keras`
- `Pillow`
- `numpy`
- `transformers`
- `tensorflow==2.20.0`

## Main routes

- `/` - login page
- `/user_dashboard` - user dashboard
- `/admin_dashboard` - admin dashboard
- `/upload` - upload form and prediction result page
- `/chatbot` - chatbot page
- `/chat` - chatbot API endpoint
- `/train_model` - admin dataset upload page
- `/set_crop` - crop selection API endpoint
- `/logout` - logout route

## Project structure

```text
AI-assisted crop health platform/
|-- app.py
|-- requirements.txt
|-- README.md
|-- models/
|   |-- sugarcane.keras
|   |-- grapes_model.keras
|   `-- chatbot/
|-- static/
|   |-- css/
|   |   `-- styles.css
|   |-- js/
|   |   `-- app.js
|   |-- images/
|   `-- uploads/
|-- templates/
|   |-- base.html
|   |-- login.html
|   |-- user_dashboard.html
|   |-- admin_dashboard.html
|   |-- upload.html
|   |-- chatbot.html
|   |-- train_model.html
|   `-- error.html
`-- App_Images/
```

## Notes about the models

- The app loads crop-specific `.keras` models from the `models/` folder.
- Crop selection is stored in session and used during prediction.
- If the chatbot model is unavailable, the app automatically falls back to built-in support responses.

## Future improvements

- Add support for more crops and disease classes
- Replace demo authentication with secure user management
- Add proper model-training pipeline inside the app
- Improve dataset validation and upload reporting
- Add prediction history and report export
