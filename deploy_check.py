from __future__ import annotations

import py_compile
import sys
from pathlib import Path


required_paths = [
    Path("app.py"),
    Path("requirements.txt"),
    Path("render.yaml"),
]

missing = [str(path) for path in required_paths if not path.exists()]

if missing:
    print("ERROR: Deployment files are missing from the repository root:")
    for path in missing:
        print(f" - {path}")
    print("\nFix: Render root directory must point to the folder that contains app.py.")
    sys.exit(1)

try:
    py_compile.compile("app.py", doraise=True)
except py_compile.PyCompileError as error:
    print("ERROR: app.py has a Python syntax problem.")
    print(error)
    sys.exit(1)

print("OK: app.py found")
print("OK: requirements.txt found")
print("OK: render.yaml found")
print("OK: app.py syntax valid")
print("\nReady for Render deploy.")
