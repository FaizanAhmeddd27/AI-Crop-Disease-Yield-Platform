"""Integration tests for user authentication, profile, and history endpoints."""

from __future__ import annotations

import io
import uuid

import numpy as np
from app.main import create_app
from fastapi.testclient import TestClient
from PIL import Image


def test_register_and_login_flow() -> None:
    app = create_app()
    with TestClient(app) as client:
        test_email = f"farmer_{uuid.uuid4().hex[:8]}@example.com"

        # 1. Register new user
        reg_payload = {
            "email": test_email,
            "password": "strongPassword123",
            "full_name": "Ali Hassan",
            "phone_number": "+923001234567",
            "role": "farmer",
            "preferred_language": "ur",
        }
        res = client.post("/api/v1/auth/register", json=reg_payload)
        assert res.status_code == 201, res.text
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"  # noqa: S105 - OAuth2 keyword, not a secret
        assert data["user"]["email"] == test_email
        assert data["user"]["full_name"] == "Ali Hassan"
        assert data["user"]["preferred_language"] == "ur"
        assert "password" not in data["user"]
        token = data["access_token"]

        # 2. Duplicate registration rejected
        res_dup = client.post("/api/v1/auth/register", json=reg_payload)
        assert res_dup.status_code == 400
        err_msg = res_dup.json().get("error", {}).get("message") or res_dup.json().get("detail", "")
        assert "already exists" in err_msg

        # 3. Password length validation
        bad_pw = reg_payload.copy()
        bad_pw["email"] = f"other_{uuid.uuid4().hex[:8]}@example.com"
        bad_pw["password"] = "123"  # too short  # noqa: S105 - test fixture, not a secret
        res_bad = client.post("/api/v1/auth/register", json=bad_pw)
        assert res_bad.status_code == 422

        # 4. Login with correct credentials
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": test_email, "password": "strongPassword123"},
        )
        assert login_res.status_code == 200
        login_data = login_res.json()
        assert "access_token" in login_data
        assert login_data["user"]["id"] == data["user"]["id"]

        # 5. Login with invalid password
        bad_login = client.post(
            "/api/v1/auth/login",
            json={"email": test_email, "password": "wrongPassword"},
        )
        assert bad_login.status_code == 401

        # 6. Login with nonexistent user
        no_user = client.post(
            "/api/v1/auth/login",
            json={
                "email": f"nonexistent_{uuid.uuid4().hex[:8]}@example.com",
                "password": "anyPassword",
            },
        )
        assert no_user.status_code == 401

        # 7. Access /me unauthenticated
        unauth_me = client.get("/api/v1/auth/me")
        assert unauth_me.status_code == 401

        # 8. Access /me authenticated
        auth_header = {"Authorization": f"Bearer {token}"}
        me_res = client.get("/api/v1/auth/me", headers=auth_header)
        assert me_res.status_code == 200
        assert me_res.json()["email"] == test_email

        # 9. Update profile
        update_res = client.put(
            "/api/v1/auth/me",
            headers=auth_header,
            json={"full_name": "Ali H. Malik", "preferred_language": "en"},
        )
        assert update_res.status_code == 200
        assert update_res.json()["full_name"] == "Ali H. Malik"
        assert update_res.json()["preferred_language"] == "en"

        # 10. Change password
        change_pw = client.post(
            "/api/v1/auth/change-password",
            headers=auth_header,
            json={"old_password": "strongPassword123", "new_password": "brandNewPassword456"},
        )
        assert change_pw.status_code == 200

        # Old password now fails
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": test_email, "password": "strongPassword123"},
            ).status_code
            == 401
        )

        # New password succeeds
        new_login = client.post(
            "/api/v1/auth/login",
            json={"email": test_email, "password": "brandNewPassword456"},
        )
        assert new_login.status_code == 200


def test_user_history_and_prediction_tracking() -> None:
    app = create_app()
    with TestClient(app) as client:
        test_email = f"hist_{uuid.uuid4().hex[:8]}@example.com"
        # Register user for history testing
        reg = client.post(
            "/api/v1/auth/register",
            json={
                "email": test_email,
                "password": "testPassword123",
                "full_name": "History Tester",
            },
        )
        assert reg.status_code == 201
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Run disease prediction with user token
        img = np.zeros((200, 200, 3), dtype=np.uint8)
        img[:] = [40, 150, 50]
        pil_img = Image.fromarray(img)
        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG")
        buf.seek(0)

        d_res = client.post(
            "/api/v1/disease/predict",
            files={"file": ("leaf.jpg", buf.getvalue(), "image/jpeg")},
            headers=headers,
        )
        assert d_res.status_code == 200
        d_pred_id = d_res.json()["prediction_id"]

        # 2. Run yield prediction with user token
        y_body = {
            "crop": "wheat",
            "location": {"lat": 31.42, "lon": 73.08, "district": "Faisalabad"},
            "season": {"year": 2024},
            "area_ha": 100.0,
            "weather_override": {
                "w_rain_total_mm": 250.0,
                "w_rainy_days": 20,
                "w_heavy_rain_days": 2,
                "w_dry_days": 130,
                "w_temp_mean_c": 19.0,
                "w_temp_max_c": 36.0,
                "w_temp_min_c": 4.0,
                "w_gdd_c": 2100.0,
                "w_heat_stress_days": 3,
                "w_grain_rain_mm": 35.0,
                "w_grain_gdd_c": 550.0,
                "w_water_balance_mm": -120.0,
                "w_humidity_mean_pct": 50.0,
                "w_solar_mj_m2": 19.0,
                "w_wind_max_kmh": 40.0,
                "w_days_observed": 180,
                "w_completeness": 0.95,
            },
        }
        y_res = client.post("/api/v1/yield/predict", json=y_body, headers=headers)
        assert y_res.status_code == 200
        y_pred_id = y_res.json()["prediction_id"]

        # 3. Check disease history
        hist_d = client.get("/api/v1/auth/history/disease", headers=headers)
        assert hist_d.status_code == 200
        d_items = hist_d.json()
        assert len(d_items) >= 1
        assert any(item["id"] == d_pred_id for item in d_items)

        # 4. Check yield history
        hist_y = client.get("/api/v1/auth/history/yield", headers=headers)
        assert hist_y.status_code == 200
        y_items = hist_y.json()
        assert len(y_items) >= 1
        assert any(item["id"] == y_pred_id for item in y_items)

        # 5. Check dashboard summary stats
        stats = client.get("/api/v1/auth/history/stats", headers=headers)
        assert stats.status_code == 200
        s_data = stats.json()
        assert s_data["total_disease_scans"] >= 1
        assert s_data["total_yield_forecasts"] >= 1
        assert s_data["avg_predicted_yield_tha"] is not None

        # 6. Delete disease history record
        del_d = client.delete(f"/api/v1/auth/history/disease/{d_pred_id}", headers=headers)
        assert del_d.status_code == 200
        # Verify gone
        hist_d_after = client.get("/api/v1/auth/history/disease", headers=headers)
        assert not any(item["id"] == d_pred_id for item in hist_d_after.json())

        # 7. Delete yield history record
        del_y = client.delete(f"/api/v1/auth/history/yield/{y_pred_id}", headers=headers)
        assert del_y.status_code == 200
        # Verify gone
        hist_y_after = client.get("/api/v1/auth/history/yield", headers=headers)
        assert not any(item["id"] == y_pred_id for item in hist_y_after.json())
