from __future__ import annotations

from agno.media.storage.local import LocalMediaStorage


class AgnoLocalAssetStorage:
    """Narrow adapter over Agno MediaStorage for local and Docker volumes."""

    def __init__(self, root: str):
        self.native = LocalMediaStorage(base_path=root)

    def put(self, media_id: str, content: bytes, *, filename: str, mime_type: str, metadata: dict) -> str:
        return self.native.upload(
            media_id,
            content,
            filename=filename,
            mime_type=mime_type,
            metadata=metadata,
        )

    def get(self, storage_key: str) -> bytes:
        return self.native.download(storage_key)

    def exists(self, storage_key: str) -> bool:
        return self.native.exists(storage_key)

    def delete(self, storage_key: str) -> bool:
        return self.native.delete(storage_key)
