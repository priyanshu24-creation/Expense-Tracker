from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from expense_tracker.settings import _email_domain, _env_bool
from tracker.services.email_sender import (
    _build_sendgrid_payload,
    _send_via_sendgrid_api,
    send_app_email,
)


class SendGridEmailSenderTests(SimpleTestCase):
    def test_env_bool_accepts_common_true_values(self):
        with patch("os.getenv", return_value="true"):
            self.assertTrue(_env_bool("ANY_FLAG", False))
        with patch("os.getenv", return_value="  YES  "):
            self.assertTrue(_env_bool("ANY_FLAG", False))
        with patch("os.getenv", return_value="1"):
            self.assertTrue(_env_bool("ANY_FLAG", False))

    def test_env_bool_accepts_common_false_values(self):
        with patch("os.getenv", return_value="false"):
            self.assertFalse(_env_bool("ANY_FLAG", True))
        with patch("os.getenv", return_value="0"):
            self.assertFalse(_env_bool("ANY_FLAG", True))
        with patch("os.getenv", return_value=None):
            self.assertTrue(_env_bool("ANY_FLAG", True))

    def test_email_domain_extracts_domain(self):
        self.assertEqual(_email_domain("user@gmail.com"), "gmail.com")
        self.assertEqual(_email_domain(" USER@Example.COM "), "example.com")
        self.assertEqual(_email_domain("not-an-email"), "")

    @override_settings(DEFAULT_FROM_EMAIL="sender@example.com")
    def test_build_sendgrid_payload_includes_to_email(self):
        payload, error = _build_sendgrid_payload(
            "recipient@example.com",
            "Verify Your Account",
            "Your OTP is 123456",
        )

        self.assertIsNone(error)
        self.assertEqual(payload["from"]["email"], "sender@example.com")
        self.assertEqual(
            payload["personalizations"][0]["to"][0]["email"],
            "recipient@example.com",
        )
        self.assertEqual(payload["subject"], "Verify Your Account")
        self.assertEqual(payload["content"][0]["value"], "Your OTP is 123456")

    @override_settings(DEFAULT_FROM_EMAIL="trackexpenseteam@gmail.com")
    def test_build_sendgrid_payload_rejects_public_webmail_sender(self):
        payload, error = _build_sendgrid_payload(
            "recipient@example.com",
            "Verify Your Account",
            "Your OTP is 123456",
        )

        self.assertIsNone(payload)
        self.assertEqual(
            error,
            "Use a verified custom-domain sender email in DEFAULT_FROM_EMAIL, not a Gmail/Outlook/Yahoo address",
        )

    @override_settings(DEFAULT_FROM_EMAIL="sender@example.com", SENDGRID_API_KEY="test-key", DEBUG=True)
    @patch("sendgrid.SendGridAPIClient")
    def test_sendgrid_api_uses_explicit_payload(self, mock_client_cls):
        mock_response = Mock(status_code=202, body=b"")
        mock_client = Mock()
        mock_client.client.mail.send.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        error = _send_via_sendgrid_api(
            "recipient@example.com",
            "Verify Your Account",
            "Your OTP is 123456",
        )

        self.assertIsNone(error)
        mock_client.client.mail.send.post.assert_called_once()
        payload = mock_client.client.mail.send.post.call_args.kwargs["request_body"]
        self.assertEqual(
            payload["personalizations"][0]["to"][0]["email"],
            "recipient@example.com",
        )
        self.assertEqual(payload["subject"], "Verify Your Account")

    @override_settings(DEFAULT_FROM_EMAIL="sender@example.com", SENDGRID_API_KEY="test-key", DEBUG=True)
    @patch("sendgrid.SendGridAPIClient")
    def test_missing_recipient_returns_debug_error_without_calling_sendgrid(self, mock_client_cls):
        error = _send_via_sendgrid_api("", "Verify Your Account", "Your OTP is 123456")

        self.assertEqual(error, "Failed to send email: Recipient email is required")
        mock_client_cls.assert_not_called()

    @override_settings(DEFAULT_FROM_EMAIL="trackexpenseteam@gmail.com", SENDGRID_API_KEY="test-key", DEBUG=True)
    @patch("sendgrid.SendGridAPIClient")
    def test_sendgrid_api_rejects_public_webmail_sender_without_calling_sendgrid(self, mock_client_cls):
        error = _send_via_sendgrid_api(
            "recipient@example.com",
            "Verify Your Account",
            "Your OTP is 123456",
        )

        self.assertEqual(
            error,
            "Failed to send email: Use a verified custom-domain sender email in DEFAULT_FROM_EMAIL, not a Gmail/Outlook/Yahoo address",
        )
        mock_client_cls.assert_not_called()

    @override_settings(DEBUG=True, SENDGRID_API_KEY="", USE_GMAIL_SMTP=False)
    @patch("tracker.services.email_sender._send_via_smtp")
    def test_missing_sendgrid_does_not_fallback_to_smtp_unless_explicitly_enabled(self, mock_smtp):
        error = send_app_email(
            "recipient@example.com",
            "Verify Your Account",
            "Your OTP is 123456",
        )

        self.assertEqual(error, "Failed to send email: Email service not configured")
        mock_smtp.assert_not_called()

    @override_settings(DEBUG=True, SENDGRID_API_KEY="", USE_GMAIL_SMTP=True)
    @patch("tracker.services.email_sender._send_via_smtp", return_value=None)
    def test_missing_sendgrid_uses_smtp_only_when_explicitly_enabled(self, mock_smtp):
        error = send_app_email(
            "recipient@example.com",
            "Verify Your Account",
            "Your OTP is 123456",
        )

        self.assertIsNone(error)
        mock_smtp.assert_called_once_with(
            "recipient@example.com",
            "Verify Your Account",
            "Your OTP is 123456",
        )

    @override_settings(DEBUG=False, SENDGRID_API_KEY="test-key", USE_GMAIL_SMTP=True)
    @patch("tracker.services.email_sender._send_via_smtp", return_value=None)
    @patch("tracker.services.email_sender._send_via_sendgrid_api")
    def test_gmail_smtp_takes_priority_when_explicitly_enabled(self, mock_sendgrid, mock_smtp):
        error = send_app_email(
            "recipient@example.com",
            "Verify Your Account",
            "Your OTP is 123456",
        )

        self.assertIsNone(error)
        mock_smtp.assert_called_once_with(
            "recipient@example.com",
            "Verify Your Account",
            "Your OTP is 123456",
        )
        mock_sendgrid.assert_not_called()
