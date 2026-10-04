import os
import secrets
import warnings
from datetime import datetime, timedelta, timezone
from functools import wraps
from io import BytesIO
from pathlib import Path

from bson import ObjectId
from bson.errors import InvalidId
from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from gridfs import GridFSBucket
from gridfs.errors import NoFile
from PIL import Image, UnidentifiedImageError
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from breed_model import ModelError, predict_breed
from breed_info import BreedDatasetError, get_breed_info

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)


def get_secret_key():
    configured_key = os.getenv("FLASK_SECRET_KEY")
    if configured_key:
        return configured_key

    secret_path = Path(app.instance_path) / "flask_secret_key"
    os.makedirs(app.instance_path, exist_ok=True)
    try:
        with secret_path.open("x", encoding="utf-8") as secret_file:
            secret_file.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    return secret_path.read_text(encoding="utf-8").strip()


app.secret_key = get_secret_key()
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024 + 64 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("FLASK_ENV") == "production"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

# --- FETCH MONGODB URI FROM .ENV ---
MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise ValueError("No MONGO_URI found in environment variables. Check your .env file!")

# Initialize standard PyMongoClient
client = MongoClient(MONGO_URI)
db = client["dru_ai_database"]       # Database name
users_collection = db["users"]       # Collection name
scans_collection = db["scans"]
image_bucket = GridFSBucket(db, bucket_name="scan_images")
MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
PROFILE_AVATARS = {
    "initial": None,
    "person": "person",
    "paw": "paw",
    "leaf": "leaf",
    "flower": "flower",
    "heart": "heart",
    "star": "star",
}
def authenticated_api(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Please sign in to continue."}), 401
        try:
            ObjectId(user_id)
        except (InvalidId, TypeError):
            session.clear()
            return jsonify({"error": "Your session is invalid. Please sign in again."}), 401
        return view(*args, **kwargs)

    return wrapped


def current_user_id():
    return ObjectId(session["user_id"])


def serialize_scan(scan):
    result = {
        "id": str(scan["_id"]),
        "breed": scan["breed"],
        "confidence": scan["confidence"],
        "created_at": scan["created_at"].isoformat(),
        "image_url": url_for("scan_image", scan_id=str(scan["_id"])),
    }
    return result


def valid_scan_id(scan_id):
    try:
        return ObjectId(scan_id)
    except (InvalidId, TypeError):
        abort(404)


@app.errorhandler(413)
def request_too_large(error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Image size must be 10 MB or less."}), 413
    return error.description, 413

# --- WEB PAGE ROUTES ---

@app.route('/')
def home():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template('pages/index.html')


@app.after_request
def prevent_home_page_caching(response):
    if request.endpoint == "home":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.get("/api/session-status")
def session_status():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"authenticated": False}), 200

    try:
        ObjectId(user_id)
    except (InvalidId, TypeError):
        session.clear()
        return jsonify({"authenticated": False}), 200

    user_name = session.get("user_name")
    user_name = user_name if isinstance(user_name, str) else ""
    user_avatar = session.get("user_avatar", "initial")
    if not isinstance(user_avatar, str) or user_avatar not in PROFILE_AVATARS:
        user_avatar = "initial"

    return jsonify(
        {
            "authenticated": True,
            "redirect": "/dashboard",
            "name": user_name,
            "avatar": user_avatar,
            "requires_name": bool(session.get("require_name_prompt"))
            or not bool(user_name.strip()),
        }
    ), 200


@app.route('/dashboard')
def dashboard():
    if "user_id" not in session:
        return redirect(url_for('home'))
    session_name = session.get("user_name")
    user_name = session_name if isinstance(session_name, str) else ""
    session_avatar = session.get("user_avatar", "initial")
    user_avatar = (
        session_avatar if isinstance(session_avatar, str) and session_avatar in PROFILE_AVATARS
        else "initial"
    )
    return render_template(
        "pages/users.html",
        user_name=user_name,
        user_initial=user_name[:1].upper() if user_name else "?",
        user_avatar=user_avatar,
        requires_name=bool(session.get("require_name_prompt"))
        or not bool(user_name.strip()),
    )

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


# --- API AUTHENTICATION ROUTES ---

@app.route('/api/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "A JSON request body is required."}), 400

        name = data.get("name")
        email = data.get("email")
        password = data.get("password")

        if (
            not isinstance(name, str)
            or not isinstance(email, str)
            or not isinstance(password, str)
        ):
            return jsonify({"error": "Name, email, and password must be text."}), 400

        name = name.strip()
        email = email.strip().casefold()
        if not name or not email or not password:
            return jsonify({"error": "All fields (Name, Email, Password) are required."}), 400
        if len(name) > 80:
            return jsonify({"error": "Name must be 80 characters or fewer."}), 400
        if len(password) < 8:
            return jsonify({"error": "Password must be at least 8 characters long."}), 400

        users_collection.create_index("email", unique=True)
        user_id = users_collection.insert_one(
            {
                "name": name,
                "email": email,
                "password": generate_password_hash(password),
                "plan": "Free",
            }
        ).inserted_id

        session.clear()
        session["user_id"] = str(user_id)
        session["user_email"] = email
        session["user_name"] = name
        session["user_avatar"] = "initial"
        session["require_name_prompt"] = True
        session.permanent = True

        return jsonify({"success": True, "redirect": "/dashboard"}), 200

    except DuplicateKeyError:
        return jsonify({"error": "An account with this email already exists."}), 400
    except PyMongoError:
        app.logger.exception("MongoDB error during signup")
        return jsonify({"error": "Registration is temporarily unavailable."}), 503
    except Exception:
        app.logger.exception("Unexpected signup error")
        return jsonify({"error": "Internal server error during registration."}), 500


@app.route('/api/signin', methods=['POST'])
def signin():
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "A JSON request body is required."}), 400

        email = data.get("email")
        password = data.get("password")

        if not isinstance(email, str) or not isinstance(password, str):
            return jsonify({"error": "Email and password must be text."}), 400
        email = email.strip().casefold()
        if not email or not password:
            return jsonify({"error": "Email and password are required."}), 400

        # Find user record by email
        user = users_collection.find_one({"email": email})
        
        if user and check_password_hash(user["password"], password):
            # Set session
            session.clear()
            session["user_id"] = str(user["_id"])
            session["user_email"] = user["email"]
            stored_name = user.get("name", "")
            session["user_name"] = stored_name.strip() if isinstance(stored_name, str) else ""
            stored_avatar = user.get("profile_avatar", "initial")
            session["user_avatar"] = (
                stored_avatar
                if isinstance(stored_avatar, str) and stored_avatar in PROFILE_AVATARS
                else "initial"
            )
            session.permanent = True
            return jsonify({"success": True, "redirect": "/dashboard"}), 200

        return jsonify({"error": "Invalid email address or password."}), 401

    except PyMongoError:
        app.logger.exception("MongoDB error during sign in")
        return jsonify({"error": "Sign in is temporarily unavailable."}), 503
    except Exception:
        app.logger.exception("Unexpected signin error")
        return jsonify({"error": "Internal server error during sign in."}), 500


@app.post("/api/profile/name")
@authenticated_api
def save_profile_name():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON request body is required."}), 400

    name = data.get("name")
    if not isinstance(name, str):
        return jsonify({"error": "Name must be text."}), 400
    name = name.strip()
    if not name:
        return jsonify({"error": "Enter your name to continue."}), 400
    if len(name) > 80:
        return jsonify({"error": "Name must be 80 characters or fewer."}), 400

    try:
        result = users_collection.update_one(
            {"_id": current_user_id()},
            {"$set": {"name": name}},
        )
    except PyMongoError:
        app.logger.exception("MongoDB error while saving profile name")
        return jsonify({"error": "Your name could not be saved. Please try again."}), 503

    if not result.matched_count:
        session.clear()
        return jsonify({"error": "Your account could not be found. Please sign in again."}), 401

    session["user_name"] = name
    session.pop("require_name_prompt", None)
    return jsonify({"success": True, "name": name, "initial": name[0].upper()}), 200


@app.post("/api/profile/avatar")
@authenticated_api
def save_profile_avatar():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON request body is required."}), 400

    avatar = data.get("avatar")
    if not isinstance(avatar, str) or avatar not in PROFILE_AVATARS:
        return jsonify({"error": "Choose one of the available profile icons."}), 400

    try:
        result = users_collection.update_one(
            {"_id": current_user_id()},
            {"$set": {"profile_avatar": avatar}},
        )
    except PyMongoError:
        app.logger.exception("MongoDB error while saving profile avatar")
        return jsonify({"error": "Your profile icon could not be saved. Please try again."}), 503

    if not result.matched_count:
        session.clear()
        return jsonify({"error": "Your account could not be found. Please sign in again."}), 401

    session["user_avatar"] = avatar
    return jsonify({"success": True, "avatar": avatar}), 200


@app.post("/api/account/delete")
@authenticated_api
def delete_account():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or data.get("confirm") is not True:
        return jsonify({"error": "Account deletion confirmation is required."}), 400

    user_id = current_user_id()
    try:
        if users_collection.find_one({"_id": user_id}) is None:
            session.clear()
            return jsonify({"error": "The account could not be found."}), 404

        scans = list(scans_collection.find({"user_id": user_id}))
        for scan in scans:
            image_id = scan.get("image_id")
            if image_id is None:
                app.logger.warning(
                    "Scan %s has no saved image while deleting account %s",
                    scan.get("_id"),
                    user_id,
                )
                continue
            try:
                image_bucket.delete(image_id)
            except NoFile:
                app.logger.warning(
                    "Missing image %s while deleting account %s",
                    image_id,
                    user_id,
                )

        scans_collection.delete_many({"user_id": user_id})
        result = users_collection.delete_one({"_id": user_id})
        if not result.deleted_count:
            return jsonify({"error": "The account could not be found."}), 404
    except PyMongoError:
        app.logger.exception("MongoDB error while deleting account %s", user_id)
        return jsonify(
            {"error": "Your account could not be deleted completely. Please try again."}
        ), 503

    session.clear()
    return jsonify({"success": True, "redirect": url_for("home")}), 200


@app.post("/api/identify")
@authenticated_api
def identify():
    upload = request.files.get("image")
    if upload is None or not upload.filename:
        return jsonify({"error": "Choose an image to identify."}), 400

    image_bytes = upload.read(MAX_IMAGE_BYTES + 1)
    if len(image_bytes) > MAX_IMAGE_BYTES:
        return jsonify({"error": "Image size must be 10 MB or less."}), 413
    if not image_bytes:
        return jsonify({"error": "The selected image is empty."}), 400

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(image_bytes)) as image:
                image_format = image.format
                image.verify()
        if image_format not in ALLOWED_IMAGE_FORMATS:
            return jsonify({"error": "Use a JPEG, PNG, or WebP image."}), 400
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        return jsonify({"error": "The selected file is not a valid supported image."}), 400

    try:
        prediction = predict_breed(image_bytes)
    except ModelError:
        app.logger.exception("Cattle breed model inference failed")
        return jsonify({"error": "The breed recognition model is unavailable."}), 503
    except Exception:
        app.logger.exception("Unexpected image inference error")
        return jsonify({"error": "The image could not be processed."}), 500
    if not isinstance(prediction.get("breed"), str) or not isinstance(
        prediction.get("confidence"), (int, float)
    ):
        app.logger.error("Breed model returned an invalid prediction.")
        return jsonify({"error": "The breed recognition model returned an invalid result."}), 503
    if not 0 <= prediction["confidence"] <= 100:
        app.logger.error("Breed model returned an out-of-range confidence.")
        return jsonify({"error": "The breed recognition model returned an invalid result."}), 503

    image_id = None
    try:
        scans_collection.create_index([("user_id", 1), ("created_at", -1)])
        image_id = image_bucket.upload_from_stream(
            secure_filename(upload.filename) or "animal-image",
            BytesIO(image_bytes),
            metadata={"content_type": Image.MIME[image_format]},
        )
        scan_id = scans_collection.insert_one(
            {
                "user_id": current_user_id(),
                "image_id": image_id,
                "image_content_type": Image.MIME[image_format],
                "breed": prediction["breed"],
                "confidence": prediction["confidence"],
                "created_at": datetime.now(timezone.utc),
            }
        ).inserted_id
        scan = {
            "_id": scan_id,
            "breed": prediction["breed"],
            "confidence": prediction["confidence"],
            "created_at": datetime.now(timezone.utc),
        }
        return jsonify(serialize_scan(scan)), 201
    except PyMongoError:
        if image_id is not None:
            try:
                image_bucket.delete(image_id)
            except PyMongoError:
                app.logger.exception("Failed to clean up an image after saving scan failed")
        app.logger.exception("MongoDB error while saving identification")
        return jsonify({"error": "The identification could not be saved."}), 503


@app.get("/api/history")
@authenticated_api
def scan_history():
    try:
        scans = (
            scans_collection.find({"user_id": current_user_id()})
            .sort("created_at", -1)
        )
        return jsonify({"scans": [serialize_scan(scan) for scan in scans]})
    except PyMongoError:
        app.logger.exception("MongoDB error while loading scan history")
        return jsonify({"error": "Identification history is temporarily unavailable."}), 503


@app.get("/api/breed-info")
@authenticated_api
def breed_info():
    breed = request.args.get("breed", "").strip()
    if not breed:
        return jsonify({"error": "A predicted breed is required."}), 400

    try:
        return jsonify({"breed_info": get_breed_info(breed)})
    except BreedDatasetError as exc:
        app.logger.exception("Local cattle breed dataset could not be loaded")
        return jsonify({"error": str(exc)}), 503


@app.get("/api/history/<scan_id>/image")
@authenticated_api
def scan_image(scan_id):
    try:
        scan = scans_collection.find_one(
            {"_id": valid_scan_id(scan_id), "user_id": current_user_id()}
        )
        if scan is None:
            abort(404)
        image = image_bucket.open_download_stream(scan["image_id"])
        return send_file(
            BytesIO(image.read()),
            mimetype=scan["image_content_type"],
            download_name="animal-image",
            max_age=3600,
        )
    except NoFile:
        abort(404)
    except PyMongoError:
        app.logger.exception("MongoDB error while loading a scan image")
        return jsonify({"error": "The scan image is temporarily unavailable."}), 503


@app.delete("/api/history/<scan_id>")
@authenticated_api
def delete_scan(scan_id):
    try:
        scan = scans_collection.find_one(
            {"_id": valid_scan_id(scan_id), "user_id": current_user_id()}
        )
        if scan is None:
            abort(404)

        image_bucket.delete(scan["image_id"])
        scans_collection.delete_one({"_id": scan["_id"]})
        return jsonify({"success": True})
    except NoFile:
        app.logger.exception("Scan image is missing while deleting history")
        return jsonify({"error": "The scan image could not be found."}), 404
    except PyMongoError:
        app.logger.exception("MongoDB error while deleting a scan")
        return jsonify({"error": "The identification could not be deleted."}), 503


if __name__ == '__main__':
    app.run(debug=True, port=5000)