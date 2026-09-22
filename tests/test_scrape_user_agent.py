"""Round-2 2.16: Scrape sends a descriptive User-Agent.

Wikimedia (and others) answer 403 to the default "python-requests/x.y" identity;
their policy asks for a tool name, version and contact URL.
"""

from unittest.mock import MagicMock, patch

from windows_mcp.desktop import service


def test_session_sends_a_descriptive_user_agent():
    agent = service._http_session.headers["User-Agent"]
    assert agent.startswith("windows-mcp/")
    assert "github.com/CursorTouch/Windows-MCP" in agent
    assert "python-requests" not in agent


def test_scrape_uses_that_session():
    response = MagicMock(is_redirect=False, text="<p>hi</p>")
    with patch.object(service._http_session, "get", return_value=response) as get:
        assert "hi" in service.Desktop.__new__(service.Desktop).scrape("https://example.com")
    get.assert_called_once()
