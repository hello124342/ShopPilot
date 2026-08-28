from __future__ import annotations

import argparse
import json

from .fixtures import PRODUCT
from .harness.runner import run_all
from .runtime import AgnoRuntimeFactory
from .schemas import CampaignInput
from .settings import Settings
from .store import RunStore
from .workflows import CampaignWorkflow


def print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def provider_smoke(settings: Settings) -> None:
    if not settings.is_ready or settings.runtime_mode.value != "agno":
        raise SystemExit("provider smoke requires SHOPILOT_RUNTIME_MODE=agno and SHOPILOT_API_KEY")
    components = AgnoRuntimeFactory().build_from_settings(settings.runtime_settings())
    response = components.agents["strategy"].run("请确认模型连接正常，用一句中文回答：ShopPilot provider smoke passed。")
    print_json({"status": response.status.value, "runtime": settings.safe_diagnostics(), "publish_side_effect": False})


def main() -> None:
    parser = argparse.ArgumentParser(description="ShopPilot operations and verification CLI")
    parser.add_argument("command", nargs="?", choices=("run", "scenarios", "provider-smoke"), default="run")
    args = parser.parse_args()
    settings = Settings()
    store = RunStore(settings.data_dir)
    if args.command == "scenarios":
        print_json(run_all(store))
    elif args.command == "provider-smoke":
        provider_smoke(settings)
    else:
        print_json(CampaignWorkflow(store, settings.runtime_settings()).run(CampaignInput(**PRODUCT)))


if __name__ == "__main__":
    main()
