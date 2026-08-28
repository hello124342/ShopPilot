from __future__ import annotations

import uvicorn

from .settings import Settings


def main() -> None:
    settings = Settings()
    uvicorn.run(
        "shopilot.app.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        workers=1,
    )


if __name__ == "__main__":
    main()
