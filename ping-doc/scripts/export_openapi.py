"""Write ping-backend's OpenAPI spec to ping-doc/src/data/openapi.json.

Run from ping-backend (npm run gen:api does this) so its settings and
imports resolve. The docs' API reference is rendered from this file, so
re-run it whenever routes change.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from app.main import api  # noqa: E402

out = Path(__file__).resolve().parents[1] / "src" / "data" / "openapi.json"
spec = api.openapi()
out.write_text(json.dumps(spec, indent=1, sort_keys=False) + "\n")
ops = sum(len(v) for v in spec["paths"].values())
print(f"wrote {out} ({len(spec['paths'])} paths, {ops} operations)")
