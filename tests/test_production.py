import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from shopilot.app.api import create_app
from shopilot.app.observability import redact
from shopilot.fixtures import PRODUCT
from shopilot.runtime import AgnoRuntimeFactory, RuntimeMode, RuntimeSettings
from shopilot.runtime.errors import classify_provider_error
from shopilot.schemas import CampaignInput, EvaluationReport
from shopilot.settings import Settings
from shopilot.store import RunStore
from shopilot.workflows import CampaignWorkflow


def test_settings_mock_and_agno_readiness(monkeypatch, tmp_path):
    monkeypatch.delenv("SHOPILOT_API_KEY", raising=False)
    mock = Settings(_env_file=None, data_dir=tmp_path)
    assert mock.is_ready and mock.safe_diagnostics()["api_key_configured"] is False
    agno = Settings(_env_file=None, data_dir=tmp_path, runtime_mode="agno")
    assert not agno.is_ready and agno.readiness_error == "agno_api_key_missing"


def test_safe_diagnostics_never_contains_secret(tmp_path):
    secret = "sk-should-never-appear"
    settings = Settings(_env_file=None, data_dir=tmp_path, api_key=secret)
    serialized = json.dumps(settings.safe_diagnostics())
    assert secret not in serialized and "api_key" not in serialized.replace("api_key_configured", "")
    assert secret not in json.dumps(redact({"api_key": secret, "nested": {"authorization": f"Bearer {secret}"}}))


def test_openai_compatible_model_receives_configuration():
    runtime = RuntimeSettings(
        runtime_mode=RuntimeMode.AGNO,
        provider="openai-compatible",
        model_id="test-model",
        base_url="https://models.example/v1",
        api_key="construction-only-key",
        provider_timeout=19,
    )
    model = AgnoRuntimeFactory().build_model(runtime)
    assert model.id == "test-model" and model.base_url == "https://models.example/v1"
    # Agno's model repr contains constructor fields; ShopPilot must never log the object.
    assert model.api_key == "construction-only-key" and model.timeout == 19


def test_provider_error_classification():
    assert classify_provider_error(RuntimeError("HTTP 401")).code == "provider_authentication_failed"
    assert classify_provider_error(TimeoutError("timeout")).retryable
    assert classify_provider_error(RuntimeError("HTTP 429")).code == "provider_rate_limited"
    assert classify_provider_error(ValueError("schema invalid")).code == "provider_structured_output_invalid"


def test_agno_provider_timeout_is_retried_and_traceable(tmp_path):
    workflow = CampaignWorkflow(
        RunStore(tmp_path),
        RuntimeSettings(runtime_mode=RuntimeMode.AGNO, api_key="construction-only-key", retry_budget=2),
    )
    class TimeoutTeam:
        def run(self, *_):
            raise TimeoutError("provider timeout")
    workflow.agno = SimpleNamespace(
        campaign_workflow=SimpleNamespace(run=lambda *_: SimpleNamespace(status=SimpleNamespace(value="COMPLETED"))),
        research_team=TimeoutTeam(),
        agents={},
    )
    run = workflow.run(CampaignInput(**PRODUCT))
    trace = workflow.store.read(run["run_id"], "trace.jsonl")
    assert run["status"] == "human_handoff" and run["error"] == "provider_timeout"
    assert len([event for event in trace if event["payload"].get("error_code") == "provider_timeout"]) == 3


def test_store_survives_new_instance_and_lists_runs(tmp_path):
    first = CampaignWorkflow(RunStore(tmp_path))
    run = first.run(CampaignInput(**PRODUCT))
    report = EvaluationReport(passed=True, checks={"schema": True}, metrics={"cost": 0})
    first.store.save_evaluation(run["run_id"], report)
    restarted = RunStore(tmp_path)
    assert restarted.get_run(run["run_id"])["status"] == "waiting_review"
    assert restarted.list_runs()[0]["run_id"] == run["run_id"]
    assert restarted.get_evaluation(run["run_id"])["passed"] is True
    assert restarted.read(run["run_id"], "evaluations.jsonl")


def app_client(tmp_path, settings=None):
    configured = settings or Settings(_env_file=None, data_dir=tmp_path)
    workflow = CampaignWorkflow(RunStore(tmp_path), configured.runtime_settings()) if configured.is_ready else None
    return TestClient(create_app(configured, workflow))


def test_health_and_safe_runtime_diagnostics(tmp_path):
    with app_client(tmp_path) as client:
        assert client.get("/health/live").json()["status"] == "live"
        ready = client.get("/health/ready")
        assert ready.status_code == 200 and ready.json()["runtime"]["runtime_mode"] == "mock"
        assert "api_key" not in ready.text.replace("api_key_configured", "")
    unready = Settings(_env_file=None, data_dir=tmp_path / "agno", runtime_mode="agno")
    with app_client(tmp_path / "agno", unready) as client:
        response = client.get("/health/ready")
        assert response.status_code == 503 and response.json()["error_code"] == "agno_api_key_missing"
        create = client.post("/api/runs", json=PRODUCT)
        assert create.status_code == 503 and create.json()["error_code"] == "agno_api_key_missing"


def test_api_full_operations_flow_and_stable_errors(tmp_path):
    with app_client(tmp_path) as client:
        assert client.get("/").status_code == 200
        assert client.get("/static/styles.css").status_code == 200
        invalid = client.post("/api/runs", json={**PRODUCT, "product": ""})
        assert invalid.status_code == 422 and invalid.json()["error_code"] == "validation_error"
        missing = client.get("/api/runs/missing")
        assert missing.status_code == 404 and missing.json()["error_code"] == "run_not_found"
        assert missing.json()["request_id"] == missing.headers["X-Request-ID"]

        run = client.post("/api/runs", json=PRODUCT).json()
        run_id = run["run_id"]
        listed = client.get("/api/runs").json()
        assert listed["count"] == 1 and listed["items"][0]["run_id"] == run_id
        assert client.get(f"/api/runs/{run_id}/artifacts").json()
        assert client.get(f"/api/runs/{run_id}/trace").json()
        assert client.get(f"/api/runs/{run_id}/approvals").json() == []
        assert client.get(f"/api/runs/{run_id}/evaluation").status_code == 404
        evaluation = client.post(f"/api/runs/{run_id}/evaluate").json()
        assert evaluation["passed"]
        assert client.get(f"/api/runs/{run_id}/evaluation").json()["passed"]
        approved = client.post(f"/api/runs/{run_id}/approve", json={"feedback": "checked"}).json()
        assert approved["run"]["status"] == "optimized"
        assert client.get(f"/api/runs/{run_id}/approvals").json()[0]["decision"] == "approved"
        replay = client.post(f"/api/runs/{run_id}/replay").json()
        assert replay["side_effect_mode"] == "disabled"


def test_no_public_publish_endpoint_exists(tmp_path):
    with app_client(tmp_path) as client:
        run_id = client.post("/api/runs", json=PRODUCT).json()["run_id"]
        response = client.post(f"/api/runs/{run_id}/publish", json={})
        assert response.status_code == 404
