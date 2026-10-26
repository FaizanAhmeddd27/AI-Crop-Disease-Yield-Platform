"""Regenerate the committed OpenAPI contract (docs/api/openapi.json).

Run from backend/:
    .venv\\Scripts\\python.exe -m app.export_openapi
"""

import json

# Force the deterministic local test environment before importing the app.
import os
from pathlib import Path

os.environ["DATABASE_URL"] = ""
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = ""
os.environ["REQUIRE_MODELS"] = "false"

from app.main import create_app  # noqa: E402

app = create_app()
schema = app.openapi()

out = Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi.json"
out.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")

paths = len(schema.get("paths", {}))
print(f"openapi.json written: {out} ({paths} paths)")
