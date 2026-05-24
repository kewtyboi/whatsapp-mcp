"""Tests for WhatsApp MCP server functions."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from whatsapp import Chat, Contact, Message, chat_to_dict, contact_to_dict, get_message_context, msg_to_dict


class TestMessageConversion:
    """Tests for message conversion functions."""

    def test_msg_to_dict_basic(self):
        """Test basic message to dict conversion."""
        msg = Message(
            id="msg123",
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            sender="1234567890@s.whatsapp.net",
            content="Hello, world!",
            is_from_me=False,
            chat_jid="1234567890@s.whatsapp.net",
            chat_name="John Doe",
            media_type=None,
        )

        result = msg_to_dict(msg, include_sender_name=False)

        assert result["id"] == "msg123"
        assert result["timestamp"] == "2024-01-15T10:30:00"
        assert result["sender_jid"] == "1234567890@s.whatsapp.net"
        assert result["sender_phone"] == "1234567890"
        assert result["content"] == "Hello, world!"
        assert result["is_from_me"] is False
        assert result["chat_jid"] == "1234567890@s.whatsapp.net"
        assert result["chat_name"] == "John Doe"
        assert result["media_type"] is None

    def test_msg_to_dict_from_me(self):
        """Test message from self shows 'Me' as sender."""
        msg = Message(
            id="msg456",
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            sender="me@s.whatsapp.net",
            content="My message",
            is_from_me=True,
            chat_jid="1234567890@s.whatsapp.net",
        )

        result = msg_to_dict(msg, include_sender_name=True)

        assert result["sender_name"] == "Me"
        assert result["sender_display"] == "Me"

    def test_msg_to_dict_with_media(self):
        """Test message with media type."""
        msg = Message(
            id="msg789",
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            sender="1234567890@s.whatsapp.net",
            content="",
            is_from_me=False,
            chat_jid="1234567890@s.whatsapp.net",
            media_type="image",
        )

        result = msg_to_dict(msg, include_sender_name=False)

        assert result["media_type"] == "image"


class TestChatConversion:
    """Tests for chat conversion functions."""

    def test_chat_to_dict_dm(self):
        """Test direct message chat conversion."""
        chat = Chat(
            jid="1234567890@s.whatsapp.net",
            name="John Doe",
            last_message_time=datetime(2024, 1, 15, 10, 30, 0),
            last_message="Hello!",
            last_sender="1234567890@s.whatsapp.net",
            last_is_from_me=False,
        )

        result = chat_to_dict(chat)

        assert result["jid"] == "1234567890@s.whatsapp.net"
        assert result["name"] == "John Doe"
        assert result["is_group"] is False
        assert result["last_message_time"] == "2024-01-15T10:30:00"
        assert result["last_message"] == "Hello!"

    def test_chat_to_dict_group(self):
        """Test group chat conversion."""
        chat = Chat(
            jid="123456789@g.us",
            name="Family Group",
            last_message_time=datetime(2024, 1, 15, 10, 30, 0),
        )

        result = chat_to_dict(chat)

        assert result["jid"] == "123456789@g.us"
        assert result["is_group"] is True

    def test_chat_to_dict_no_last_message(self):
        """Test chat without last message time."""
        chat = Chat(
            jid="1234567890@s.whatsapp.net",
            name="Jane Doe",
            last_message_time=None,
        )

        result = chat_to_dict(chat)

        assert result["last_message_time"] is None


class TestContactConversion:
    """Tests for contact conversion functions."""

    def test_contact_to_dict(self):
        """Test contact to dict conversion."""
        contact = Contact(
            phone_number="1234567890",
            name="John Doe",
            jid="1234567890@s.whatsapp.net",
        )

        result = contact_to_dict(contact)

        assert result["phone_number"] == "1234567890"
        assert result["name"] == "John Doe"
        assert result["jid"] == "1234567890@s.whatsapp.net"

    def test_contact_to_dict_no_name(self):
        """Test contact without name."""
        contact = Contact(
            phone_number="9876543210",
            name=None,
            jid="9876543210@s.whatsapp.net",
        )

        result = contact_to_dict(contact)

        assert result["name"] is None


class TestGetMessageContextNullSafety:
    """Regression tests for VGP #73 — NULL DB values must not crash Message construction."""

    # 9-column row returned for the target message query
    _TARGET_ROW_ALL_NULL = (
        None,                      # 0: timestamp
        None,                      # 1: sender
        None,                      # 2: chat name
        None,                      # 3: content
        None,                      # 4: is_from_me
        "chat@s.whatsapp.net",     # 5: chats.jid (needed for context queries)
        "msg-abc",                 # 6: messages.id
        "chat@s.whatsapp.net",     # 7: messages.chat_jid (used in WHERE)
        None,                      # 8: media_type
    )

    # 8-column row returned for before/after context queries
    _CONTEXT_ROW_ALL_NULL = (
        None,                      # 0: timestamp
        None,                      # 1: sender
        None,                      # 2: chat name
        None,                      # 3: content
        None,                      # 4: is_from_me
        "chat@s.whatsapp.net",     # 5: chats.jid
        "msg-ctx",                 # 6: messages.id
        None,                      # 7: media_type
    )

    def test_null_fields_do_not_crash(self):
        """NULL timestamp/sender/is_from_me in DB rows must not raise during Message construction."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = self._TARGET_ROW_ALL_NULL
        mock_cursor.fetchall.return_value = [self._CONTEXT_ROW_ALL_NULL]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("whatsapp.sqlite3.connect", return_value=mock_conn):
            ctx = get_message_context("msg-abc", before=1, after=1)

        assert ctx.message.is_from_me is False
        assert ctx.message.sender == ""
        assert ctx.message.content == ""
        assert ctx.message.timestamp == datetime.fromtimestamp(0)
        assert len(ctx.before) == 1
        assert ctx.before[0].is_from_me is False
        assert ctx.before[0].timestamp == datetime.fromtimestamp(0)
        assert len(ctx.after) == 1

    def test_null_is_from_me_treated_as_false(self):
        """NULL is_from_me must resolve to False, not crash."""
        row = self._TARGET_ROW_ALL_NULL
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = row
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("whatsapp.sqlite3.connect", return_value=mock_conn):
            ctx = get_message_context("msg-abc")

        assert ctx.message.is_from_me is False

    def test_valid_row_still_works(self):
        """Normal rows with all fields present must still parse correctly."""
        target_row = (
            "2024-01-15T10:30:00",
            "1234567890@s.whatsapp.net",
            "Test Chat",
            "Hello",
            1,
            "1234567890@s.whatsapp.net",
            "msg-valid",
            "1234567890@s.whatsapp.net",
            None,
        )
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = target_row
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("whatsapp.sqlite3.connect", return_value=mock_conn):
            ctx = get_message_context("msg-valid")

        assert ctx.message.is_from_me is True
        assert ctx.message.sender == "1234567890@s.whatsapp.net"
        assert ctx.message.timestamp == datetime(2024, 1, 15, 10, 30, 0)
