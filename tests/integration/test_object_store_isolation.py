from dataclasses import dataclass

import pytest

from pekua.storage.objects import S3ObjectStore


class NoSuchKey(Exception):
    pass


@dataclass
class Body:
    value: bytes

    def read(self) -> bytes:
        return self.value


class MemoryS3:
    class exceptions:
        NoSuchKey = NoSuchKey

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, **_: object) -> None:
        self.objects[f"{Bucket}/{Key}"] = Body

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Body]:
        try:
            return {"Body": Body(self.objects[f"{Bucket}/{Key}"])}
        except KeyError as exc:
            raise NoSuchKey from exc

    def delete_object(self, *, Bucket: str, Key: str) -> None:
        self.objects.pop(f"{Bucket}/{Key}", None)

    def head_bucket(self, *, Bucket: str) -> None:
        return None


@pytest.mark.asyncio
async def test_restricted_object_is_content_addressed_and_tenant_isolated() -> None:
    store = S3ObjectStore(MemoryS3(), "documents")
    stored = await store.put(
        document_id="record-1",
        body=b"licensed full text",
        media_type="application/pdf",
        access_scope="restricted",
        tenant_id="tenant-a",
    )

    assert stored.key.startswith("tenants/tenant-a/documents/record-1/")
    assert await store.get(stored.key, tenant_id="tenant-a") == b"licensed full text"
    with pytest.raises(PermissionError):
        await store.get(stored.key, tenant_id="tenant-b")
