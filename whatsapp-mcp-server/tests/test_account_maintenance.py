"""Tests for the revoke_message / delete_chat bridge client functions and
their MCP tool wrappers.

The bridge HTTP calls are patched at the `requests.post` boundary; no real
bridge is contacted. The MCP tool wrappers are patched at the
`whatsapp_revoke_message` / `whatsapp_delete_chat` import sites inside
`main` so the tests exercise only the confirm gate and argument plumbing.
"""

from unittest.mock import MagicMock, patch


class TestRevokeMessageBridgeClient:
    def test_rejects_empty_chat_jid(self):
        from whatsapp import revoke_message

        ok, msg = revoke_message("", "MID123")
        assert ok is False
        assert "must be provided" in msg

    def test_rejects_empty_message_id(self):
        from whatsapp import revoke_message

        ok, msg = revoke_message("1234@s.whatsapp.net", "")
        assert ok is False
        assert "must be provided" in msg

    def test_posts_payload_with_confirm_true(self):
        from whatsapp import revoke_message

        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"success": True, "message": "Message revoke sent"}

        with patch("whatsapp.requests.post", return_value=response) as post:
            ok, msg = revoke_message("1234@s.whatsapp.net", "MID123")

        assert ok is True
        assert msg == "Message revoke sent"
        post.assert_called_once()
        _, kwargs = post.call_args
        assert kwargs["json"] == {
            "chat_jid": "1234@s.whatsapp.net",
            "message_id": "MID123",
            "confirm": True,
        }

    def test_propagates_http_failure(self):
        from whatsapp import revoke_message

        response = MagicMock()
        response.status_code = 503
        response.text = "WhatsApp client not connected"

        with patch("whatsapp.requests.post", return_value=response):
            ok, msg = revoke_message("1234@s.whatsapp.net", "MID123")

        assert ok is False
        assert "HTTP 503" in msg


class TestDeleteChatBridgeClient:
    def test_rejects_empty_chat_jid(self):
        from whatsapp import delete_chat

        ok, msg = delete_chat("")
        assert ok is False
        assert "must be provided" in msg

    def test_posts_payload_with_confirm_true(self):
        from whatsapp import delete_chat

        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"success": True, "message": "Chat deletion synced"}

        with patch("whatsapp.requests.post", return_value=response) as post:
            ok, msg = delete_chat("1234@s.whatsapp.net")

        assert ok is True
        assert msg == "Chat deletion synced"
        post.assert_called_once()
        _, kwargs = post.call_args
        assert kwargs["json"] == {
            "chat_jid": "1234@s.whatsapp.net",
            "confirm": True,
        }

    def test_propagates_http_failure(self):
        from whatsapp import delete_chat

        response = MagicMock()
        response.status_code = 500
        response.text = "delete chat failed: boom"

        with patch("whatsapp.requests.post", return_value=response):
            ok, msg = delete_chat("1234@s.whatsapp.net")

        assert ok is False
        assert "HTTP 500" in msg


class TestMcpToolConfirmGate:
    """The MCP tool wrappers must refuse to act unless `confirm=True`."""

    def test_revoke_message_rejects_missing_confirm(self):
        import main

        with patch.object(main, "whatsapp_revoke_message") as bridge:
            result = main.revoke_message("1234@s.whatsapp.net", "MID123")

        assert result["success"] is False
        assert "confirm must be True" in result["message"]
        bridge.assert_not_called()

    def test_revoke_message_rejects_confirm_false(self):
        import main

        with patch.object(main, "whatsapp_revoke_message") as bridge:
            result = main.revoke_message("1234@s.whatsapp.net", "MID123", confirm=False)

        assert result["success"] is False
        bridge.assert_not_called()

    def test_revoke_message_forwards_when_confirmed(self):
        import main

        with patch.object(
            main, "whatsapp_revoke_message", return_value=(True, "Message revoke sent")
        ) as bridge:
            result = main.revoke_message("1234@s.whatsapp.net", "MID123", confirm=True)

        assert result == {"success": True, "message": "Message revoke sent"}
        bridge.assert_called_once_with("1234@s.whatsapp.net", "MID123")

    def test_revoke_message_rejects_empty_args_even_when_confirmed(self):
        import main

        with patch.object(main, "whatsapp_revoke_message") as bridge:
            result = main.revoke_message("", "", confirm=True)

        assert result["success"] is False
        assert "must be provided" in result["message"]
        bridge.assert_not_called()

    def test_delete_chat_rejects_missing_confirm(self):
        import main

        with patch.object(main, "whatsapp_delete_chat") as bridge:
            result = main.delete_chat("1234@s.whatsapp.net")

        assert result["success"] is False
        assert "confirm must be True" in result["message"]
        bridge.assert_not_called()

    def test_delete_chat_forwards_when_confirmed(self):
        import main

        with patch.object(
            main, "whatsapp_delete_chat", return_value=(True, "Chat deletion synced")
        ) as bridge:
            result = main.delete_chat("1234@s.whatsapp.net", confirm=True)

        assert result == {"success": True, "message": "Chat deletion synced"}
        bridge.assert_called_once_with("1234@s.whatsapp.net")

    def test_delete_chat_rejects_empty_jid_even_when_confirmed(self):
        import main

        with patch.object(main, "whatsapp_delete_chat") as bridge:
            result = main.delete_chat("", confirm=True)

        assert result["success"] is False
        assert "must be provided" in result["message"]
        bridge.assert_not_called()
