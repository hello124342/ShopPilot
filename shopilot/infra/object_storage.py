from __future__ import annotations

import hashlib
from io import BytesIO
from minio import Minio

class S3ObjectStorage:
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str, *, secure: bool = False):
        self.client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        self.bucket = bucket

    def ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def put(self, key: str, content: bytes, mime_type: str, metadata: dict[str, str] | None = None) -> dict:
        digest = hashlib.sha256(content).hexdigest()
        self.client.put_object(self.bucket, key, BytesIO(content), len(content), content_type=mime_type, metadata={**(metadata or {}), "sha256": digest})
        return {"key": key, "sha256": digest, "size_bytes": len(content)}

    def get(self, key: str) -> bytes:
        response = self.client.get_object(self.bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def health(self) -> dict:
        try:
            self.ensure_bucket()
            return {"status": "ready", "bucket": self.bucket}
        except Exception as exc:
            return {"status": "not_ready", "error_code": "object_storage_unavailable", "detail": type(exc).__name__}
