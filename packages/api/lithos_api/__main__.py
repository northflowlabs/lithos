"""Run the LITHOS API with uvicorn: python -m lithos_api  (or the lithos-api script)."""

from __future__ import annotations

import os


def main() -> None:
    import uvicorn

    uvicorn.run(
        "lithos_api.app:app",
        host=os.getenv("LITHOS_API_HOST", "0.0.0.0"),
        port=int(os.getenv("LITHOS_API_PORT", "8000")),
        reload=os.getenv("LITHOS_API_RELOAD", "false").lower() == "true",
    )


if __name__ == "__main__":
    main()
