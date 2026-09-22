"""Scrape must verify HTTPS against the Windows certificate store.

Python 3.13+ applies strict X.509 checks that reject antivirus TLS-inspection
roots (Avast: "Basic Constraints of CA cert not marked critical"), so every
HTTPS scrape failed on machines running such products (seen 2026-09-22).
"""

from unittest.mock import MagicMock, patch

import truststore

from windows_mcp.desktop import service
from windows_mcp.desktop.service import Desktop


def test_https_adapter_uses_truststore_context():
    adapter = service._http_session.get_adapter("https://example.com")
    context = adapter.poolmanager.connection_pool_kw["ssl_context"]
    assert isinstance(context, truststore.SSLContext)


def test_scrape_goes_through_the_truststore_session():
    response = MagicMock(is_redirect=False, text="<p>hi</p>")
    with (
        patch.object(Desktop, "__init__", lambda self: None),
        patch.object(service._http_session, "get", return_value=response) as get,
        patch("windows_mcp.desktop.service.validate_url"),
    ):
        assert Desktop().scrape("https://example.com").strip() == "hi"
    get.assert_called_once_with("https://example.com", timeout=10, allow_redirects=False)
