from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from tracker.services.email_sender import (
    _build_sendgrid_payload,
    _send_via_sendgrid_api,
    send_app_email,
)


class SendGridEmailSenderTests(SimpleTestCase):
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
