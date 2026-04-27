from __future__ import annotations

import sys
from pathlib import Path


required_paths = [
    Path("app.py"),
    Path("aml_qc_engine"),
    Path("aml_qc_engine/__init__.py"),
    Path("aml_qc_engine/cli.py"),
    Path("aml_qc_engine/web.py"),
    Path("config/rules.json"),
]

missing = [str(path) for path in required_paths if not path.exists()]

if missing:
    print("Deployment files are missing from the repository root:")
    for path in missing:
        print(f" - {path}")
    print("\nRender root directory must point to the folder that contains app.py and aml_qc_engine/.")
    sys.exit(1)

import aml_qc_engine  # noqa: E402

print(f"Deployment check passed. aml_qc_engine {aml_qc_engine.__version__} is importable.")

