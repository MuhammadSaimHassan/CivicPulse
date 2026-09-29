"""`python -m app.export_openapi [path]` — write the OpenAPI schema the
frontend's TypeScript client is generated from (frontend/src/api/schema.d.ts)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.core.config import Settings
from app.main import create_app


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("openapi.json")
    schema = create_app(Settings()).openapi()
    out.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
