"""CloudBase HTTP function entrypoint for image workshop API."""

import os
import sys

import uvicorn

from backend.main import app


if __name__ == "__main__":
    port = int(os.getenv("PORT") or os.getenv("SCF_HTTP_PORT") or "9000")
    print(
        f"image-workshop-api starting with Python {sys.version.split()[0]} on port {port}",
        flush=True,
    )
    uvicorn.run(app, host="0.0.0.0", port=port)
