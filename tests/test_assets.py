from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from shopilot.app.api import create_app
from shopilot.assets import (
    AgnoLocalAssetStorage,
    AssetCatalog,
    AssetIntegrityError,
    AssetKind,
    AssetQuotaExceeded,
    AssetReference,
    AssetService,
    AssetStatus,
    OpenAIImageGenerationAdapter,
    VideoGenerationAdapter,
)
from shopilot.fixtures import PRODUCT
from shopilot.schemas import PlatformPayload
from shopilot.settings import Settings
from shopilot.store import RunStore
from shopilot.workflows import CampaignWorkflow
from shopilot.workflows.approval import ApprovalService, payload_asset_versions


def service(tmp_path, **kwargs):
    return AssetService(
        AssetCatalog(tmp_path / "assets.db"),
        AgnoLocalAssetStorage(str(tmp_path / "media")),
        **kwargs,
    )


def create_asset(assets, content=b"asset-content", **kwargs):
    values = {
        "filename": "asset.txt",
        "mime_type": "text/plain",
        "kind": AssetKind.DOCUMENT,
        "owner_id": "tester",
        "run_id": "run-1",
        "created_by": "test-tool@1.0.0",
    }
    values.update(kwargs)
    return assets.create(content, **values)


def test_agno_storage_catalog_hash_dedup_and_immutable_version(tmp_path):
    assets = service(tmp_path)
    first = create_asset(assets)
    duplicate = create_asset(assets, run_id="run-2")
    second = create_asset(assets, b"new-content", asset_id=first.asset_id)

    assert first.status == AssetStatus.READY
    assert first.sha256 and first.size_bytes == len(b"asset-content")
    assert duplicate.asset_id == first.asset_id and duplicate.version == 1
    assert assets.catalog.list_for_run("run-2")[0].asset_id == first.asset_id
    assert second.asset_id == first.asset_id and second.version == 2
    assert assets.content(AssetReference(asset_id=first.asset_id, version=1))[1] == b"asset-content"
    assert len(assets.catalog.lineage(second.asset_id, second.version)) == 1


def test_png_metadata_is_recorded(tmp_path):
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAF/gL+XcX9WQAAAABJRU5ErkJggg=="
    )
    asset = create_asset(
        service(tmp_path),
        png,
        filename="pixel.png",
        mime_type="image/png",
        kind=AssetKind.IMAGE,
    )
    assert asset.media_metadata == {"width": 1, "height": 1}


def test_corruption_quarantines_asset_and_records_audit(tmp_path):
    assets = service(tmp_path)
    asset = create_asset(assets)
    physical = Path(assets.storage.native.base_path) / asset.storage_key
    physical.write_bytes(b"corrupt")

    with pytest.raises(AssetIntegrityError, match="asset_hash_mismatch"):
        assets.content(AssetReference(asset_id=asset.asset_id, version=asset.version))

    quarantined = assets.catalog.get(asset.asset_id, asset.version)
    assert quarantined.status == AssetStatus.QUARANTINED
    assert assets.catalog.events(asset.asset_id)[-1]["event_type"] == "asset_quarantined"


def test_storage_failure_never_marks_asset_ready(tmp_path):
    class FailingStorage:
        def put(self, *_args, **_kwargs):
            raise OSError("disk unavailable")

    assets = AssetService(AssetCatalog(tmp_path / "assets.db"), FailingStorage())
    with pytest.raises(OSError, match="disk unavailable"):
        create_asset(assets)
    failed = assets.catalog.list_for_run("run-1")[0]
    assert failed.status == AssetStatus.FAILED


def test_quota_and_retention_policy(tmp_path):
    assets = service(tmp_path, max_asset_bytes=10, tenant_quota_bytes=12)
    create_asset(
        assets,
        b"12345678",
        retention_until=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    with pytest.raises(AssetQuotaExceeded, match="tenant_asset_quota_exceeded"):
        create_asset(assets, b"abcde")
    with pytest.raises(AssetQuotaExceeded, match="asset_size_limit_exceeded"):
        create_asset(assets, b"x" * 11)
    assert assets.archive_expired() == 1


def test_approval_is_bound_to_asset_versions(tmp_path):
    assets = service(tmp_path)
    first = create_asset(assets)
    second = create_asset(assets, b"version-two", asset_id=first.asset_id)
    approvals = ApprovalService(RunStore(tmp_path / "runs"))
    original = PlatformPayload(
        platform="x",
        title="title",
        body="body",
        cta="go",
        media=[AssetReference(asset_id=first.asset_id, version=first.version)],
    )
    changed = original.model_copy(
        update={"media": [AssetReference(asset_id=second.asset_id, version=second.version)]}
    )
    approvals.decide("run-1", original, "approved")
    assert approvals.is_approved("run-1", 1, payload_asset_versions(original))
    assert not approvals.is_approved("run-1", 1, payload_asset_versions(changed))


def test_document_image_and_video_adapters(tmp_path):
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAF/gL+XcX9WQAAAABJRU5ErkJggg=="
    )

    class FakeImages:
        def generate(self, **kwargs):
            assert kwargs["model"] == "gpt-image-1"
            return SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(png).decode())])

    assets = service(tmp_path)
    generated = OpenAIImageGenerationAdapter(
        assets, SimpleNamespace(images=FakeImages())
    ).generate("product photo", run_id="run-image")
    assert generated.kind == AssetKind.IMAGE and generated.status == AssetStatus.READY
    with pytest.raises(NotImplementedError, match="video_generation_not_implemented"):
        VideoGenerationAdapter().generate("video")


def test_asset_api_is_tenant_scoped_and_hides_storage_paths(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path)
    workflow = CampaignWorkflow(RunStore(tmp_path), settings.runtime_settings())
    with TestClient(create_app(settings, workflow)) as client:
        run = client.post("/api/runs", json=PRODUCT).json()
        run_id = run["run_id"]
        payload = workflow.latest_payload(run_id)
        assert isinstance(payload.media[0], AssetReference)
        reference = payload.media[0]

        listed = client.get(f"/api/runs/{run_id}/assets").json()
        metadata = client.get(
            f"/api/assets/{reference.asset_id}/versions/{reference.version}"
        )
        preview = client.get(
            f"/api/assets/{reference.asset_id}/versions/{reference.version}/preview"
        )
        download = client.get(
            f"/api/assets/{reference.asset_id}/versions/{reference.version}/download"
        )
        exported = client.post(f"/api/runs/{run_id}/exports/markdown")

    assert listed and "storage_key" not in listed[0]
    assert metadata.status_code == 200 and "storage_key" not in metadata.text
    assert preview.headers["x-content-type-options"] == "nosniff"
    assert preview.headers["content-disposition"].startswith("inline")
    assert download.headers["content-disposition"].startswith("attachment")
    assert exported.status_code == 201 and exported.json()["kind"] == "document"


def test_legacy_media_strings_still_validate():
    payload = PlatformPayload(platform="x", title="t", body="b", cta="c", media=["legacy.jpg"])
    assert payload.media == ["legacy.jpg"]
