import base64
import os

import pytest
from cryptography.exceptions import InvalidTag

from pekua.security.vault import EnvEncryptedVault, SecretContext


def test_vault_encrypts_binds_context_and_revokes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TEST_VAULT_KEY", base64.urlsafe_b64encode(os.urandom(32)).decode())
    vault = EnvEncryptedVault(tmp_path, "TEST_VAULT_KEY")
    context = SecretContext(tenant_id="tenant-a", connector_id="epo-ops", version=1)
    reference = vault.put(context, b"credential")
    assert b"credential" not in next(tmp_path.iterdir()).read_bytes()
    assert vault.get(context, reference) == b"credential"
    with pytest.raises(InvalidTag):
        vault.get(SecretContext("tenant-b", "epo-ops", 1), reference)
    vault.revoke(reference)
    with pytest.raises(KeyError):
        vault.get(context, reference)


def test_vault_refuses_plaintext_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("MISSING_VAULT_KEY", raising=False)
    with pytest.raises(RuntimeError, match="plaintext fallback is forbidden"):
        EnvEncryptedVault(tmp_path, "MISSING_VAULT_KEY")
