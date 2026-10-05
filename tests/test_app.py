import io
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from bson import ObjectId
from PIL import Image
from werkzeug.security import check_password_hash

import app as app_module


class FakeCursor(list):
    def sort(self, field, direction):
        return FakeCursor(
            sorted(self, key=lambda document: document[field], reverse=direction < 0)
        )


class FakeCollection:
    def __init__(self):
        self.documents = []
        self.indexes = []

    def create_index(self, field, unique=False):
        self.indexes.append((field, unique))
        return f"{field}_1"

    def insert_one(self, document):
        document = {**document, "_id": ObjectId()}
        self.documents.append(document)
        return type("InsertResult", (), {"inserted_id": document["_id"]})()

    def find_one(self, query):
        return next(
            (
                document
                for document in self.documents
                if all(document.get(key) == value for key, value in query.items())
            ),
            None,
        )

    def find(self, query):
        return FakeCursor(
            document
            for document in self.documents
            if all(document.get(key) == value for key, value in query.items())
        )

    def delete_one(self, query):
        document = self.find_one(query)
        if document:
            self.documents.remove(document)
        return type("DeleteResult", (), {"deleted_count": int(document is not None)})()

    def delete_many(self, query):
        matching = [
            document
            for document in self.documents
            if all(document.get(key) == value for key, value in query.items())
        ]
        for document in matching:
            self.documents.remove(document)
        return type("DeleteResult", (), {"deleted_count": len(matching)})()

    def update_one(self, query, update):
        document = self.find_one(query)
        if document:
            document.update(update.get("$set", {}))
        return type(
            "UpdateResult",
            (),
            {
                "matched_count": int(document is not None),
                "modified_count": int(document is not None),
            },
        )()


class FakeImageBucket:
    def __init__(self):
        self.images = {}
        self.last_upload_filename = None

    def upload_from_stream(self, filename, stream, metadata=None):
        image_id = ObjectId()
        self.images[image_id] = (stream.read(), metadata)
        self.last_upload_filename = filename
        return image_id

    def open_download_stream(self, image_id):
        if image_id not in self.images:
            from gridfs.errors import NoFile

            raise NoFile("image not found")
        return io.BytesIO(self.images[image_id][0])

    def delete(self, image_id):
        if image_id not in self.images:
            from gridfs.errors import NoFile

            raise NoFile("image not found")
        del self.images[image_id]


class FlaskApplicationTests(unittest.TestCase):
    def setUp(self):
        self.users = FakeCollection()
        self.scans = FakeCollection()
        self.images = FakeImageBucket()
        self.patches = (
            patch.object(app_module, "users_collection", self.users),
            patch.object(app_module, "scans_collection", self.scans),
            patch.object(app_module, "image_bucket", self.images),
        )
        for active_patch in self.patches:
            active_patch.start()
        app_module.app.config.update(TESTING=True)
        self.client = app_module.app.test_client()

    def tearDown(self):
        for active_patch in reversed(self.patches):
            active_patch.stop()

    def sign_in(self, user_id=None):
        with self.client.session_transaction() as user_session:
            user_session["user_id"] = str(user_id or ObjectId())
            user_session["user_name"] = "Test User"
            user_session["user_email"] = "test@example.com"

    @staticmethod
    def png_bytes():
        image = Image.new("RGB", (8, 8), color="green")
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        return stream.getvalue()

    def test_dashboard_requires_authentication(self):
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/")

    def test_home_redirects_authenticated_user_to_dashboard(self):
        self.sign_in()

        response = self.client.get("/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/dashboard")
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_logged_out_home_page_is_not_cached(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertEqual(response.headers["Pragma"], "no-cache")
        self.assertEqual(response.headers["Expires"], "0")

    def test_session_status_reports_authentication_state(self):
        anonymous_response = self.client.get("/api/session-status")
        self.assertEqual(anonymous_response.status_code, 200)
        self.assertFalse(anonymous_response.json["authenticated"])

        self.sign_in()
        authenticated_response = self.client.get("/api/session-status")
        self.assertEqual(authenticated_response.status_code, 200)
        self.assertTrue(authenticated_response.json["authenticated"])
        self.assertEqual(authenticated_response.json["redirect"], "/dashboard")
        self.assertEqual(authenticated_response.json["name"], "Test User")
        self.assertEqual(authenticated_response.json["avatar"], "initial")
        self.assertFalse(authenticated_response.json["requires_name"])

        with self.client.session_transaction() as user_session:
            user_session["require_name_prompt"] = True
        name_prompt_response = self.client.get("/api/session-status")
        self.assertTrue(name_prompt_response.json["requires_name"])

    def test_logout_clears_persistent_session_and_allows_home_page(self):
        self.sign_in()

        logout_response = self.client.get("/logout")

        self.assertEqual(logout_response.status_code, 302)
        self.assertEqual(logout_response.location, "/")
        with self.client.session_transaction() as user_session:
            self.assertNotIn("user_id", user_session)
        home_response = self.client.get("/")
        self.assertEqual(home_response.status_code, 200)
        self.assertIn(b"authModal", home_response.data)

    def test_signup_creates_user_and_authenticated_session(self):
        response = self.client.post(
            "/api/signup",
            json={
                "name": "Test User",
                "email": " TEST@EXAMPLE.COM ",
                "password": "password123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["redirect"], "/dashboard")
        self.assertEqual(self.users.documents[0]["email"], "test@example.com")
        self.assertEqual(self.users.documents[0]["name"], "Test User")
        self.assertTrue(
            check_password_hash(self.users.documents[0]["password"], "password123")
        )
        with self.client.session_transaction() as user_session:
            self.assertEqual(user_session["user_id"], str(self.users.documents[0]["_id"]))
            self.assertTrue(user_session["require_name_prompt"])
            self.assertTrue(user_session.permanent)
        self.assertIn(
            "Expires=",
            response.headers.get("Set-Cookie", ""),
        )
        dashboard_response = self.client.get("/dashboard")
        self.assertIn(b'id="requiredNameModal"', dashboard_response.data)
        self.assertIn(b'<div class="main" id="dashboardApp" inert>', dashboard_response.data)
        self.assertIn(
            b'id="requiredNameModal"',
            self.client.get("/dashboard").data,
        )
        self.assertEqual(self.users.indexes, [("email", True)])

    def test_signup_rejects_short_password(self):
        response = self.client.post(
            "/api/signup",
            json={"name": "Test", "email": "test@example.com", "password": "short"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("8 characters", response.json["error"])

    def test_signin_sets_session_and_redirects_to_dashboard(self):
        user_id = ObjectId()
        self.users.documents.append(
            {
                "_id": user_id,
                "name": "Test User",
                "email": "test@example.com",
                "password": app_module.generate_password_hash("password123"),
            }
        )

        response = self.client.post(
            "/api/signin",
            json={"email": " TEST@EXAMPLE.COM ", "password": "password123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["redirect"], "/dashboard")
        with self.client.session_transaction() as user_session:
            self.assertTrue(user_session.permanent)
        dashboard_response = self.client.get("/dashboard")
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertIn(b"Test User", dashboard_response.data)
        self.assertIn(b'id="profileSettingsForm"', dashboard_response.data)
        self.assertIn(b"Blue-violet &amp; white", dashboard_response.data)
        self.assertIn(b'id="deleteAccountButton"', dashboard_response.data)
        self.assertIn(b'id="accountDeleteModal"', dashboard_response.data)
        self.assertIn(b"Delete permanently", dashboard_response.data)
        self.assertIn(b"mailto:gmitprojectid@gmail.com", dashboard_response.data)
        self.assertIn(b"How can we", dashboard_response.data)
        self.assertIn(b'data-target="updates-section"', dashboard_response.data)
        self.assertIn(b">Updates</a>", dashboard_response.data)
        self.assertIn(b'id="updates-section"', dashboard_response.data)
        self.assertIn(b"Buffalo Breed Identification", dashboard_response.data)
        self.assertIn(b"Animal Disease Identification", dashboard_response.data)
        self.assertIn(b"Animal Species Identification", dashboard_response.data)
        self.assertIn(b"Cat Breed Detection", dashboard_response.data)
        self.assertIn(b"Dog Breed Detection", dashboard_response.data)
        self.assertIn(b"Subscriptions", dashboard_response.data)
        self.assertNotIn(b"learn-section", dashboard_response.data)
        self.assertNotIn(b"supportMessageForm", dashboard_response.data)
        self.assertIn(
            b"/static/scripts/users/informations.js",
            dashboard_response.data,
        )
        script_response = self.client.get("/static/scripts/users/informations.js")
        self.assertEqual(script_response.status_code, 200)
        script_response.close()

    def test_signin_with_legacy_account_without_name_requires_name_prompt(self):
        user_id = ObjectId()
        self.users.documents.append(
            {
                "_id": user_id,
                "email": "test@example.com",
                "password": app_module.generate_password_hash("password123"),
            }
        )

        response = self.client.post(
            "/api/signin",
            json={"email": "test@example.com", "password": "password123"},
        )

        self.assertEqual(response.status_code, 200)
        dashboard_response = self.client.get("/dashboard")
        self.assertIn(b'id="requiredNameModal"', dashboard_response.data)

    def test_signin_restores_saved_profile_icon(self):
        user_id = ObjectId()
        self.users.documents.append(
            {
                "_id": user_id,
                "name": "Test User",
                "profile_avatar": "paw",
                "email": "test@example.com",
                "password": app_module.generate_password_hash("password123"),
            }
        )

        response = self.client.post(
            "/api/signin",
            json={"email": "test@example.com", "password": "password123"},
        )

        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as user_session:
            self.assertEqual(user_session["user_avatar"], "paw")
        self.assertIn(b'data-avatar="paw"', self.client.get("/dashboard").data)

    def test_saving_profile_icon_persists_choice(self):
        user_id = ObjectId()
        self.users.documents.append({"_id": user_id, "name": "Test User"})
        self.sign_in(user_id)

        response = self.client.post("/api/profile/avatar", json={"avatar": "flower"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["avatar"], "flower")
        self.assertEqual(self.users.documents[0]["profile_avatar"], "flower")
        with self.client.session_transaction() as user_session:
            self.assertEqual(user_session["user_avatar"], "flower")

    def test_saving_unknown_profile_icon_is_rejected(self):
        self.sign_in()

        response = self.client.post("/api/profile/avatar", json={"avatar": "not-an-icon"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("available profile icons", response.json["error"])

    def test_saving_name_updates_current_user_and_session(self):
        user_id = ObjectId()
        self.users.documents.append({"_id": user_id, "name": "", "email": "test@example.com"})
        self.sign_in(user_id)

        response = self.client.post("/api/profile/name", json={"name": "  Asha Rao  "})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["name"], "Asha Rao")
        self.assertEqual(response.json["initial"], "A")
        self.assertEqual(self.users.documents[0]["name"], "Asha Rao")
        with self.client.session_transaction() as user_session:
            self.assertEqual(user_session["user_name"], "Asha Rao")
            self.assertNotIn("require_name_prompt", user_session)
        self.assertIn(
            b'id="requiredNameModal"\n      hidden',
            self.client.get("/dashboard").data,
        )

    def test_saving_blank_name_is_rejected(self):
        self.sign_in()

        response = self.client.post("/api/profile/name", json={"name": "  "})

        self.assertEqual(response.status_code, 400)
        self.assertIn("Enter your name", response.json["error"])

    def test_account_deletion_requires_confirmation(self):
        self.sign_in()

        response = self.client.post("/api/account/delete", json={"confirm": False})

        self.assertEqual(response.status_code, 400)
        self.assertIn("confirmation is required", response.json["error"])

    def test_account_deletion_removes_only_current_users_data(self):
        user_id = ObjectId()
        other_user_id = ObjectId()
        owned_image_id = ObjectId()
        other_image_id = ObjectId()
        self.sign_in(user_id)
        self.users.documents.extend(
            [
                {
                    "_id": user_id,
                    "name": "Test User",
                    "email": "test@example.com",
                    "password": app_module.generate_password_hash("password123"),
                },
                {"_id": other_user_id, "email": "other@example.com"},
            ]
        )
        self.scans.documents.extend(
            [
                {"_id": ObjectId(), "user_id": user_id, "image_id": owned_image_id},
                {"_id": ObjectId(), "user_id": other_user_id, "image_id": other_image_id},
            ]
        )
        self.images.images[owned_image_id] = (b"owned", {})
        self.images.images[other_image_id] = (b"other", {})

        response = self.client.post("/api/account/delete", json={"confirm": True})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["redirect"], "/")
        self.assertEqual([user["_id"] for user in self.users.documents], [other_user_id])
        self.assertEqual([scan["user_id"] for scan in self.scans.documents], [other_user_id])
        self.assertNotIn(owned_image_id, self.images.images)
        self.assertIn(other_image_id, self.images.images)
        with self.client.session_transaction() as user_session:
            self.assertNotIn("user_id", user_session)

        signin_response = self.client.post(
            "/api/signin",
            json={"email": "test@example.com", "password": "password123"},
        )
        self.assertEqual(signin_response.status_code, 401)

        signup_response = self.client.post(
            "/api/signup",
            json={
                "name": "Test User Again",
                "email": "test@example.com",
                "password": "password123",
            },
        )
        self.assertEqual(signup_response.status_code, 200)
        self.assertEqual(signup_response.json["redirect"], "/dashboard")

    def test_identification_persists_browser_prediction_and_image(self):
        user_id = ObjectId()
        self.sign_in(user_id)

        response = self.client.post(
            "/api/identify",
            data={
                "image": (io.BytesIO(self.png_bytes()), "cow.png"),
                "breed": "Amritmahal",
                "confidence": "93.25",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["breed"], "Amritmahal")
        self.assertEqual(response.json["confidence"], 93.25)
        self.assertEqual(len(self.scans.documents), 1)
        scan = self.scans.documents[0]
        self.assertEqual(scan["user_id"], user_id)
        self.assertEqual(scan["breed"], "Amritmahal")
        self.assertEqual(len(self.images.images), 1)
        self.assertEqual(self.images.last_upload_filename, "cow.png")

    def test_history_is_scoped_to_signed_in_user(self):
        user_id = ObjectId()
        self.sign_in(user_id)
        self.scans.documents.extend(
            [
                {
                    "_id": ObjectId(),
                    "user_id": user_id,
                    "breed": "Amritmahal",
                    "confidence": 90.0,
                    "created_at": datetime.now(timezone.utc),
                },
                {
                    "_id": ObjectId(),
                    "user_id": ObjectId(),
                    "breed": "Other user's result",
                    "confidence": 99.0,
                    "created_at": datetime.now(timezone.utc),
                },
            ]
        )

        response = self.client.get("/api/history")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json["scans"]), 1)
        self.assertEqual(response.json["scans"][0]["breed"], "Amritmahal")

    def test_local_breed_information_is_loaded_for_predicted_breed(self):
        self.sign_in()
        info = {
            "overview": "A hardy cattle breed.",
            "characteristics": [{"name": "Adaptation", "details": "Heat tolerant."}],
            "care_guide": [{"name": "Housing", "details": "Provide shade."}],
            "similar_breeds": ["Hallikar"],
        }

        with patch.object(app_module, "get_breed_info", return_value=info) as lookup:
            response = self.client.get("/api/breed-info?breed=Amritmahal")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["breed_info"], info)
        lookup.assert_called_once_with("Amritmahal")

    def test_local_breed_information_requires_authentication(self):
        response = self.client.get("/api/breed-info?breed=Amritmahal")

        self.assertEqual(response.status_code, 401)

    def test_web3forms_support_endpoint_has_been_removed(self):
        response = self.client.post(
            "/api/support/submit",
            json={"category": "support", "message": "This should no longer be accepted."},
        )

        self.assertEqual(response.status_code, 404)

    def test_local_breed_information_handles_breeds_missing_from_dataset(self):
        self.sign_in()
        with patch.object(app_module, "get_breed_info", return_value=None):
            response = self.client.get("/api/breed-info?breed=Unknown")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json["breed_info"])

    def test_local_breed_information_rejects_missing_breed(self):
        self.sign_in()

        response = self.client.get("/api/breed-info")

        self.assertEqual(response.status_code, 400)

    def test_scan_image_and_delete_are_available_only_to_owner(self):
        user_id = ObjectId()
        other_user_id = ObjectId()
        self.sign_in(user_id)
        image_id = ObjectId()
        image_data = self.png_bytes()
        self.images.images[image_id] = (image_data, {"content_type": "image/png"})
        scan_id = ObjectId()
        self.scans.documents.append(
            {
                "_id": scan_id,
                "user_id": user_id,
                "image_id": image_id,
                "image_content_type": "image/png",
                "breed": "Amritmahal",
                "confidence": 91.5,
                "created_at": datetime.now(timezone.utc),
            }
        )

        image_response = self.client.get(f"/api/history/{scan_id}/image")
        self.assertEqual(image_response.status_code, 200)
        self.assertEqual(image_response.data, image_data)
        self.assertEqual(image_response.mimetype, "image/png")

        with self.client.session_transaction() as user_session:
            user_session["user_id"] = str(other_user_id)
        denied_response = self.client.delete(f"/api/history/{scan_id}")
        self.assertEqual(denied_response.status_code, 404)

        with self.client.session_transaction() as user_session:
            user_session["user_id"] = str(user_id)
        delete_response = self.client.delete(f"/api/history/{scan_id}")
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(len(self.scans.documents), 0)
        self.assertEqual(len(self.images.images), 0)

    def test_invalid_image_is_rejected_before_inference(self):
        self.sign_in()
        response = self.client.post(
            "/api/identify",
            data={
                "image": (io.BytesIO(b"not an image"), "cow.png"),
                "breed": "Amritmahal",
                "confidence": "93.25",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)

    def test_oversized_image_resolution_is_rejected_before_inference(self):
        self.sign_in()
        image = MagicMock()
        image.format = "PNG"
        image.width = 5000
        image.height = 5000
        image.__enter__.return_value = image

        with patch.object(app_module.Image, "open", return_value=image):
            response = self.client.post(
                "/api/identify",
                data={
                    "image": (io.BytesIO(b"image data"), "large.png"),
                    "breed": "Amritmahal",
                    "confidence": "93.25",
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 413)
        self.assertIn("20 megapixels or less", response.json["error"])
        image.verify.assert_not_called()

    def test_identification_rejects_invalid_client_prediction(self):
        self.sign_in()

        for breed, confidence in (
            ("Not a cattle breed", "93.25"),
            ("Amritmahal", "NaN"),
            ("Amritmahal", "101"),
        ):
            with self.subTest(breed=breed, confidence=confidence):
                response = self.client.post(
                    "/api/identify",
                    data={
                        "image": (io.BytesIO(self.png_bytes()), "cow.png"),
                        "breed": breed,
                        "confidence": confidence,
                    },
                    content_type="multipart/form-data",
                )
                self.assertEqual(response.status_code, 400)

        self.assertEqual(self.scans.documents, [])
        self.assertEqual(self.images.images, {})


def tearDownModule():
    app_module.client.close()


if __name__ == "__main__":
    unittest.main()
