import hashlib
from asyncio import to_thread
from dataclasses import dataclass
from inspect import iscoroutinefunction
from typing import Any, Protocol


@dataclass(frozen=True)
class StoredObject:
    key: str
    sha256: str
    byte_length: int
    media_type: str
    access_scope: str
    tenant_id: str | None


class ObjectStore(Protocol):
    async def put(
        self,
        *,
        document_id: str,
        body: bytes,
        media_type: str,
        access_scope: str,
        tenant_id: str | None,
    ) -> StoredObject: ...
    async def get(self, key: str, *, tenant_id: str | None) -> bytes | None: ...
    async def delete(self, key: str, *, tenant_id: str | None) -> None: ...
    async def healthy(self) -> bool: ...


def assert_access(key: str, tenant_id: str | None) -> None:
    if key.startswith("public/"):
        return
    if not tenant_id or not key.startswith(f"tenants/{tenant_id}/"):
        raise PermissionError("Object access denied for tenant")


async def _call(method: Any, /, **kwargs: Any) -> Any:
    """Call boto3-style sync clients or async test/aioboto clients safely."""
    if iscoroutinefunction(method):
        return await method(**kwargs)
    return await to_thread(method, **kwargs)


async def _read(body: Any) -> bytes:
    if iscoroutinefunction(body.read):
        return bytes(await body.read())
    return bytes(await to_thread(body.read))


class S3ObjectStore:
    """S3-compatible, content-addressed storage."""

    def __init__(self, client: Any, bucket: str) -> None:
        self.client = client
        self.bucket = bucket

    async def put(
        self,
        *,
        document_id: str,
        body: bytes,
        media_type: str,
        access_scope: str,
        tenant_id: str | None,
    ) -> StoredObject:
        if access_scope not in {"public", "tenant", "restricted"}:
            raise ValueError("Invalid object access scope")
        if access_scope != "public" and not tenant_id:
            raise ValueError("Tenant-scoped objects require tenant_id")
        digest = hashlib.sha256(body).hexdigest()
        prefix = "public" if access_scope == "public" else f"tenants/{tenant_id}"
        key = f"{prefix}/documents/{document_id}/{digest}"
        await _call(
            self.client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ContentType=media_type,
            Metadata={
                "sha256": digest,
                "access-scope": access_scope,
                "tenant-id": tenant_id or "",
            },
        )
        return StoredObject(key, digest, len(body), media_type, access_scope, tenant_id)

    async def get(self, key: str, *, tenant_id: str | None) -> bytes | None:
        assert_access(key, tenant_id)
        try:
            response = await _call(self.client.get_object, Bucket=self.bucket, Key=key)
        except self.client.exceptions.NoSuchKey:
            return None
        return await _read(response["Body"])

    async def delete(self, key: str, *, tenant_id: str | None) -> None:
        assert_access(key, tenant_id)
        await _call(self.client.delete_object, Bucket=self.bucket, Key=key)

    async def healthy(self) -> bool:
        await _call(self.client.head_bucket, Bucket=self.bucket)
        return True
