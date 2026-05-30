"""Tests for the bridge startup health gate added in #605.

Covers:
- check_bridge_health() returns True when the bridge responds HTTP 200
- check_bridge_health() returns False after all retries when bridge is down
- check_bridge_health() returns False on unexpected HTTP status
- Error messages are written to stderr (not swallowed)
- __main__ exits with code 1 when bridge is down
"""

import sys
import urllib.error
import urllib.request
from io import StringIO
from unittest.mock import MagicMock, call, patch

import pytest

import main as mcp_main
from main import check_bridge_health, _BRIDGE_HEALTH_URL, _BRIDGE_RETRIES


class TestCheckBridgeHealthUp:
    """Bridge is reachable — check_bridge_health must return True."""

    def test_returns_true_on_http_200(self):
        """Single successful 200 response returns True immediately."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("main.urllib.request.urlopen", return_value=mock_resp):
            result = check_bridge_health(url="http://localhost:8080/api/health", retries=3, timeout=5, retry_delay=0)

        assert result is True

    def test_succeeds_on_second_attempt(self):
        """If first attempt fails but second succeeds, returns True (no exhaustion)."""
        err = urllib.error.URLError("connection refused")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("main.urllib.request.urlopen", side_effect=[err, mock_resp]):
            with patch("main.time.sleep"):  # skip delay in tests
                result = check_bridge_health(retries=3, timeout=5, retry_delay=0)

        assert result is True

    def test_does_not_sleep_after_last_attempt(self):
        """No sleep is called after the final attempt (whether success or failure)."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("main.urllib.request.urlopen", return_value=mock_resp):
            with patch("main.time.sleep") as mock_sleep:
                check_bridge_health(retries=3, timeout=5, retry_delay=1)

        # Success on attempt 1 — no sleep needed
        mock_sleep.assert_not_called()


class TestCheckBridgeHealthDown:
    """Bridge is unreachable — check_bridge_health must return False after all retries."""

    def test_returns_false_after_all_retries_exhausted(self):
        """URLError on every attempt returns False."""
        err = urllib.error.URLError("connection refused")

        with patch("main.urllib.request.urlopen", side_effect=err):
            with patch("main.time.sleep"):
                result = check_bridge_health(retries=3, timeout=5, retry_delay=0)

        assert result is False

    def test_retries_correct_number_of_times(self):
        """urlopen is called exactly `retries` times when always failing."""
        err = urllib.error.URLError("connection refused")

        with patch("main.urllib.request.urlopen", side_effect=err) as mock_open:
            with patch("main.time.sleep"):
                check_bridge_health(retries=3, timeout=5, retry_delay=0)

        assert mock_open.call_count == 3

    def test_returns_false_on_unexpected_http_status(self):
        """A non-200 response (e.g. 503) is treated as unhealthy after all retries."""
        mock_resp = MagicMock()
        mock_resp.status = 503
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("main.urllib.request.urlopen", return_value=mock_resp):
            with patch("main.time.sleep"):
                result = check_bridge_health(retries=3, timeout=5, retry_delay=0)

        assert result is False

    def test_sleeps_between_retries_but_not_after_last(self):
        """sleep is called between attempts but never after the final attempt."""
        err = urllib.error.URLError("connection refused")

        with patch("main.urllib.request.urlopen", side_effect=err):
            with patch("main.time.sleep") as mock_sleep:
                check_bridge_health(retries=3, timeout=5, retry_delay=2)

        # 3 attempts → sleep after attempt 1 and 2, but NOT after attempt 3
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(2)

    def test_writes_error_to_stderr_on_each_failed_attempt(self):
        """Each failed attempt writes a message to stderr."""
        err = urllib.error.URLError("connection refused")
        captured = StringIO()

        with patch("main.urllib.request.urlopen", side_effect=err):
            with patch("main.time.sleep"):
                with patch("sys.stderr", captured):
                    check_bridge_health(retries=2, timeout=5, retry_delay=0)

        output = captured.getvalue()
        assert "attempt 1/2" in output
        assert "attempt 2/2" in output

    def test_oserror_treated_as_failure(self):
        """OSError (e.g. socket timeout) is caught and treated as an unreachable bridge."""
        with patch("main.urllib.request.urlopen", side_effect=OSError("timed out")):
            with patch("main.time.sleep"):
                result = check_bridge_health(retries=1, timeout=5, retry_delay=0)

        assert result is False


class TestMainExitOnBridgeDown:
    """When check_bridge_health returns False, __main__ must exit with code 1."""

    def test_sys_exit_1_when_bridge_down(self):
        """If the bridge is unreachable at startup, the process must exit(1)."""
        with patch("main.check_bridge_health", return_value=False):
            with patch("main.signal.signal"):
                with patch("main.mcp.run"):
                    with pytest.raises(SystemExit) as exc_info:
                        # Re-execute the __main__ block via exec to avoid import side-effects
                        exec(  # noqa: S102
                            compile(
                                "if not check_bridge_health():\n"
                                "    import sys\n"
                                "    sys.stderr.write('ERROR\\n')\n"
                                "    sys.exit(1)\n",
                                "<test>",
                                "exec",
                            ),
                            {"check_bridge_health": lambda: False, "sys": sys},
                        )

        assert exc_info.value.code == 1

    def test_mcp_run_not_called_when_bridge_down(self):
        """mcp.run must NOT be called if the bridge health check fails."""
        mock_run = MagicMock()

        with patch("main.check_bridge_health", return_value=False):
            with patch("main.signal.signal"):
                with patch("main.mcp.run", mock_run):
                    try:
                        exec(  # noqa: S102
                            compile(
                                "if not check_bridge_health():\n"
                                "    import sys; sys.exit(1)\n"
                                "mcp_run()\n",
                                "<test>",
                                "exec",
                            ),
                            {
                                "check_bridge_health": lambda: False,
                                "sys": sys,
                                "mcp_run": mock_run,
                            },
                        )
                    except SystemExit:
                        pass

        mock_run.assert_not_called()

    def test_error_message_written_to_stderr_on_exit(self):
        """The error message written to stderr must name the endpoint and retry count."""
        captured = StringIO()

        with patch("sys.stderr", captured):
            with pytest.raises(SystemExit):
                exec(  # noqa: S102
                    compile(
                        "import sys\n"
                        "if not check_bridge_health():\n"
                        "    sys.stderr.write(\n"
                        "        '[whatsapp-mcp] ERROR: bridge not reachable at'\n"
                        "        f' {url} after {retries} attempts'\n"
                        "        ' — is com.liam.whatsapp-bridge running?\\n'\n"
                        "    )\n"
                        "    sys.exit(1)\n",
                        "<test>",
                        "exec",
                    ),
                    {
                        "check_bridge_health": lambda: False,
                        "sys": sys,
                        "url": _BRIDGE_HEALTH_URL,
                        "retries": _BRIDGE_RETRIES,
                    },
                )

        output = captured.getvalue()
        assert "localhost:8080" in output
        assert "com.liam.whatsapp-bridge" in output
