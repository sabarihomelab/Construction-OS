from app.db import model_registry  # noqa: F401
from app.db.base import Base
from app.modules.audit.service import REDACTED, sanitize_audit_value


def test_audit_table_is_append_oriented() -> None:
    table = Base.metadata.tables["audit_events"]
    assert "updated_at" not in table.c
    assert "occurred_at" in table.c
    assert "changes" in table.c
    assert "metadata" in table.c


def test_audit_payload_redacts_credentials_and_tokens() -> None:
    payload = sanitize_audit_value(
        {
            "name": "Example",
            "password": "never-store-me",
            "access_token": "also-secret",
            "nested": {"api_key": "hidden", "status": "active"},
        }
    )
    assert payload["name"] == "Example"
    assert payload["password"] == REDACTED
    assert payload["access_token"] == REDACTED
    assert payload["nested"]["api_key"] == REDACTED
    assert payload["nested"]["status"] == "active"


def test_audit_payload_omits_binary_data() -> None:
    payload = sanitize_audit_value({"attachment": b"binary-file-data"})
    assert payload["attachment"] == "[BINARY_OMITTED]"


def test_audit_payload_limits_large_lists() -> None:
    payload = sanitize_audit_value({"items": list(range(100))})
    assert len(payload["items"]) == 51
    assert payload["items"][-1] == "[TRUNCATED]"
