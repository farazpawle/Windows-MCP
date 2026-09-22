"""SSLKEYLOGFILE must not reach the server's TLS stack.

Avast/AVG inject SSLKEYLOGFILE=\\\\.\\aswMonFltProxy\\... into every process. With
it set, the first HTTPS request (Scrape, telemetry) aborts the whole server in
native OpenSSL code ("OPENSSL_Uplink ... no OPENSSL_Applink"), seen 2026-09-22.
"""

from windows_mcp.__main__ import _drop_ssl_keylog_env


def test_keylog_variable_is_removed(monkeypatch):
    monkeypatch.setenv("SSLKEYLOGFILE", r"\\.\aswMonFltProxy\547b92436125180a")
    assert _drop_ssl_keylog_env() is True
    import os

    assert "SSLKEYLOGFILE" not in os.environ


def test_no_variable_is_a_no_op(monkeypatch):
    monkeypatch.delenv("SSLKEYLOGFILE", raising=False)
    assert _drop_ssl_keylog_env() is False
