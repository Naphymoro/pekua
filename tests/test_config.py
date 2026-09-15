import pytest
from pydantic import ValidationError

from pekua.config import Settings


def test_production_rejects_development_vault_and_credentials() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production")
