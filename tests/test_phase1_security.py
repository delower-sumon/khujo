import os
import unittest
from fastapi.testclient import TestClient

# Set mock env before importing backend
os.environ["DATABASE_URL"] = "postgresql://mock_user:mock_pass@localhost:5432/mock_db"
os.environ["ADMIN_API_KEY"] = "test_secret_admin_key_2026"
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000,http://localhost:8000"

from backend.main import app

class TestPhase1Security(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app, raise_server_exceptions=False)

    def test_root_api(self):
        response = self.client.get("/api")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Khujo API", response.json()["message"])

    def test_admin_stats_unauthorized_without_key(self):
        """Verify D1: Admin endpoints reject unauthenticated requests."""
        response = self.client.get("/api/v1/admin/stats")
        self.assertEqual(response.status_code, 401)
        self.assertIn("Unauthorized", response.json()["detail"])

    def test_admin_stats_unauthorized_with_wrong_key(self):
        """Verify D1: Admin endpoints reject invalid keys."""
        response = self.client.get("/api/v1/admin/stats", headers={"X-Admin-Key": "wrong_key"})
        self.assertEqual(response.status_code, 401)

    def test_admin_candidates_unauthorized(self):
        response = self.client.get("/api/v1/admin/candidates")
        self.assertEqual(response.status_code, 401)

    def test_admin_action_entity_unauthorized(self):
        response = self.client.post("/api/v1/admin/entities/123/action?action=approve")
        self.assertEqual(response.status_code, 401)

    def test_admin_with_valid_key_passes_auth_gate(self):
        """Verify valid key passes auth (reaches route, even if DB mock raises 500 masked error)."""
        response = self.client.get("/api/v1/admin/stats", headers={"X-Admin-Key": "test_secret_admin_key_2026"})
        # Should NOT be 401 Unauthorized
        self.assertNotEqual(response.status_code, 401)

    def test_cors_headers(self):
        """Verify D9: Safe CORS configuration."""
        response = self.client.options(
            "/api",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )
        self.assertEqual(response.headers.get("access-control-allow-origin"), "http://localhost:3000")
        self.assertEqual(response.headers.get("access-control-allow-credentials"), "true")

if __name__ == "__main__":
    unittest.main()
