from unittest.mock import patch

from django.db import OperationalError
from django.test import SimpleTestCase


class AuthViewDatabaseResilienceTests(SimpleTestCase):
    @patch("tracker.views._start_signup_otp", side_effect=OperationalError("db unavailable"))
    def test_signup_db_error_renders_form_instead_of_500(self, _mock_start_signup):
        response = self.client.post(
            "/signup/",
            {
                "full_name": "Test User",
                "username": "testuser",
                "email": "test@example.com",
                "password": "Pass12345!",
                "confirm_password": "Pass12345!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "We are having trouble reaching the server right now. Please try again in a minute.",
        )
        self.assertEqual(response.context["full_name"], "Test User")
        self.assertEqual(response.context["username"], "testuser")
        self.assertEqual(response.context["email"], "test@example.com")

    @patch("tracker.views._start_login_otp", side_effect=OperationalError("db unavailable"))
    def test_login_db_error_renders_form_instead_of_500(self, _mock_start_login):
        response = self.client.post(
            "/login/",
            {
                "email": "test@example.com",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "We are having trouble reaching the server right now. Please try again in a minute.",
        )
