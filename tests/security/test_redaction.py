from pekua.security.redaction import REDACTED, redact


def test_redacts_structured_and_inline_secrets() -> None:
    result = redact(
        {
            "authorization": "Bearer abc.def",
            "nested": {"api_key": "private", "message": "token=secret-value"},
            "safe": "public",
        }
    )
    assert result["authorization"] == REDACTED
    assert result["nested"]["api_key"] == REDACTED
    assert "secret-value" not in result["nested"]["message"]
    assert result["safe"] == "public"


def test_redacts_secret_bytes() -> None:
    assert redact(b"never-log-this") == REDACTED
