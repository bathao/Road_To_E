"""Dump the FastAPI OpenAPI schema to a JSON file (no server needed).

Used by the frontend's `npm run gen:api` to regenerate TypeScript types
(src/shared/api/schema.d.ts) so hand-written mirrors can be checked against
the real backend schemas instead of drifting silently.

Usage: python scripts/dump_openapi.py [out.json]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402

out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("openapi.json")
out.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {out} ({out.stat().st_size} bytes)")
