from __future__ import annotations

import base64
import json
from typing import Any

from .models import Asset, AssetKind
from .service import AssetService


class MarkdownDocumentExporter:
    def __init__(self, assets: AssetService):
        self.assets = assets

    def export(self, data: dict[str, Any], *, run_id: str, tenant_id: str = "default") -> Asset:
        content = ("# ShopPilot Export\n\n```json\n" + json.dumps(data, ensure_ascii=False, indent=2) + "\n```\n").encode("utf-8")
        return self.assets.create(
            content,
            filename="shopilot-export.md",
            mime_type="text/markdown",
            kind=AssetKind.DOCUMENT,
            owner_id="workflow",
            run_id=run_id,
            created_by="document-exporter@1.0.0",
            tenant_id=tenant_id,
        )


class OpenAIImageGenerationAdapter:
    def __init__(self, assets: AssetService, client: Any, *, model: str = "gpt-image-1"):
        self.assets = assets
        self.client = client
        self.model = model

    def generate(self, prompt: str, *, run_id: str, tenant_id: str = "default") -> Asset:
        response = self.client.images.generate(model=self.model, prompt=prompt, size="1024x1024")
        content = base64.b64decode(response.data[0].b64_json)
        return self.assets.create(
            content,
            filename="generated.png",
            mime_type="image/png",
            kind=AssetKind.IMAGE,
            owner_id="workflow",
            run_id=run_id,
            created_by="openai-image-adapter@1.0.0",
            tenant_id=tenant_id,
            model_id=self.model,
            generation_parameters={"size": "1024x1024"},
        )


class MockImageGenerationAdapter:
    """Deterministic offline adapter used for tests, replay, and fault injection."""

    _PNG = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAF/gL+XcX9WQAAAABJRU5ErkJggg=="
    )

    def __init__(self, assets: AssetService):
        self.assets = assets

    def generate(self, prompt: str, *, run_id: str, tenant_id: str = "default") -> Asset:
        return self.assets.create(
            self._PNG,
            filename="product-scene.png",
            mime_type="image/png",
            kind=AssetKind.IMAGE,
            owner_id="workflow",
            run_id=run_id,
            created_by="mock-image-adapter@1.0.0",
            tenant_id=tenant_id,
            generation_parameters={"prompt": prompt, "mode": "deterministic-mock"},
        )


class VideoGenerationAdapter:
    def generate(self, *_: Any, **__: Any) -> Asset:
        raise NotImplementedError("video_generation_not_implemented")
