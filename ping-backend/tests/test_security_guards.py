"""Security guards that need no database: production secrets, outbound
address checks, client IPs behind a proxy, and CSV export cells."""

import pytest
from pydantic import ValidationError

from app.api.deps import forwarded_client
from app.core import netguard
from app.core.config import Settings
from app.services import alert_service
from app.services.conversation_service import safe_cell

STRONG = "s" * 40


def _production(**overrides) -> Settings:
    values = {"environment": "production", "auth_jwt_secret": STRONG, "admin_jwt_secret": STRONG,
              "auth_cookie_secure": True, **overrides}
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize("overrides", [
    {"auth_jwt_secret": "change-me-in-production"},
    {"admin_jwt_secret": "change-me-admin-secret"},
    {"auth_jwt_secret": "too-short"},
    {"auth_cookie_secure": False},
])
def test_production_refuses_unsafe_secrets(overrides):
    with pytest.raises(ValidationError, match="Unsafe production settings"):
        _production(**overrides)


def test_production_accepts_strong_secrets_and_local_keeps_defaults():
    assert _production().environment == "production"
    local = Settings(_env_file=None, environment="local", auth_jwt_secret="change-me-in-production")
    assert local.auth_jwt_secret == "change-me-in-production"


@pytest.mark.parametrize("url", [
    "https://127.0.0.1/hook", "https://10.0.0.5/hook", "https://169.254.169.254/latest/meta-data",
    "https://localhost:8443/hook", "https://[::1]/hook", "https://192.168.1.10/",
])
def test_private_addresses_are_refused(url):
    assert netguard.private_host_reason(url) is not None


def test_public_addresses_are_allowed():
    assert netguard.private_host_reason("https://1.1.1.1/hook") is None


def test_alerts_never_post_to_private_addresses():
    # No network call: the guard answers first.
    assert alert_service._post("https://169.254.169.254/latest", {"text": "x"}) == "blocked"
    assert alert_service._post("https://127.0.0.1:6379/", {"text": "x"}) == "blocked"


@pytest.mark.parametrize("header,peer,hops,expected", [
    ("6.6.6.6, 9.9.9.9", "10.0.0.1", 1, "9.9.9.9"),      # the client wrote 6.6.6.6; the proxy appended 9.9.9.9
    ("9.9.9.9", "10.0.0.1", 1, "9.9.9.9"),
    ("1.1.1.1, 6.6.6.6, 9.9.9.9, 10.0.0.2", "10.0.0.1", 2, "9.9.9.9"),
    ("6.6.6.6, 9.9.9.9", "10.0.0.1", 0, "10.0.0.1"),      # no proxy: the header is ignored
    (None, "10.0.0.1", 1, "10.0.0.1"),
    ("", "10.0.0.1", 1, "10.0.0.1"),
    ("9.9.9.9", "10.0.0.1", 3, "9.9.9.9"),               # fewer entries than hops
])
def test_client_ip_ignores_what_the_client_wrote(header, peer, hops, expected):
    assert forwarded_client(header, peer, hops) == expected


@pytest.mark.parametrize("value,expected", [
    ('=HYPERLINK("https://evil.example")', '\'=HYPERLINK("https://evil.example")'),
    ("+1-555", "'+1-555"),
    ("-2+3", "'-2+3"),
    ("@SUM(A1)", "'@SUM(A1)"),
    ("\t=1+1", "'\t=1+1"),
    ("How do I export invoices?", "How do I export invoices?"),
    ("", ""),
])
def test_export_cells_cannot_run_formulas(value, expected):
    assert safe_cell(value) == expected
