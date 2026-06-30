"""Entrypoint: `python -m app.backend` runs the uvicorn server."""
from __future__ import annotations

import uvicorn

from app.backend.api.deps import create_default_app


def main() -> None:
    uvicorn.run(create_default_app(), host="127.0.0.1", port=8000, factory=True)


if __name__ == "__main__":
    main()