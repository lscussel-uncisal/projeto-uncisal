from unittest.mock import Mock, patch

import requests

from apps.accounts.services import TurnstileService


class TestTurnstileService:
    def test_empty_token_fails_without_calling_the_api(self):
        with patch("apps.accounts.services.requests.post") as mock_post:
            result = TurnstileService.verify("")

        assert result is False
        mock_post.assert_not_called()

    def test_successful_verification(self):
        mock_response = Mock()
        mock_response.json.return_value = {"success": True}
        with patch("apps.accounts.services.requests.post", return_value=mock_response) as mock_post:
            result = TurnstileService.verify("token-valido", remote_ip="1.2.3.4")

        assert result is True
        _, kwargs = mock_post.call_args
        assert kwargs["data"]["response"] == "token-valido"
        assert kwargs["data"]["remoteip"] == "1.2.3.4"
        assert kwargs["data"]["secret"]

    def test_cloudflare_rejects_the_token(self):
        mock_response = Mock()
        mock_response.json.return_value = {
            "success": False,
            "error-codes": ["invalid-input-response"],
        }
        with patch("apps.accounts.services.requests.post", return_value=mock_response):
            result = TurnstileService.verify("token-invalido")

        assert result is False

    def test_network_failure_fails_closed_without_raising(self):
        with patch("apps.accounts.services.requests.post", side_effect=requests.ConnectionError):
            result = TurnstileService.verify("qualquer-token")

        assert result is False
