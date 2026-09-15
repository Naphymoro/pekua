from io import BytesIO

import pytest

from pekua.storage.objects import S3ObjectStore, assert_access


class FakeS3:
    class exceptions:
        class NoSuchKey(Exception):
            pass

    def __init__(self) -> None:
        self.items: dict[str, bytes] = {}

    def put_object(self, **kwargs: object) -> None:
        self.items[str(kwargs["Key"])] = bytes(kwargs["Body"])

    def get_object(self, **kwargs: object) -> dict[str, BytesIO]:
        key = str(kwargs["Key"])
        if key not in self.items:
            raise self.exceptions.NoSuchKey
        return {"Body": BytesIO(self.items[key])}

    def delete_object(self, **kwargs: object) -> None:
        self.items.pop(str(kwargs["Key"]), None)

    def head_bucket(self, **kwargs: object) -> None:
        return None


@pytest.mark.asyncio
async def test_tenant_storage_is_content_addressed_and_isolated() -> None:
    store = S3ObjectStore(FakeS3(), "documents")
    saved = await store.put(
        document_id="doc-1",
        body=b"evidence",
        media_type="text/plain",
        access_scope="restricted",
        tenant_id="tenant-a",
    )
    assert saved.key.startswith("tenants/tenant-a/documents/doc-1/")
    assert await store.get(saved.key, tenant_id="tenant-a") == b"evidence"
    with pytest.raises(PermissionError):
        await store.get(saved.key, tenant_id="tenant-b")


def test_non_public_objects_require_matching_tenant() -> None:
    assert_access("public/documents/a/hash", None)
    with pytest.raises(PermissionError):
        assert_access("tenants/a/documents/a/hash", None)
