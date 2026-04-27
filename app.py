from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aml_qc_engine.config import database_path, load_rule_config  # noqa: E402
from aml_qc_engine.db import fetch_alerts, init_db, seed_sample_alerts  # noqa: E402
from aml_qc_engine.sample_data import SAMPLE_ALERTS  # noqa: E402
from aml_qc_engine.web import run_server  # noqa: E402


def maybe_seed_demo_data(db_path: str) -> None:
    if os.getenv("AML_QC_SEED_SAMPLE", "false").lower() not in {"1", "true", "yes"}:
        return

    if fetch_alerts(db_path):
        return

    seed_sample_alerts(db_path, SAMPLE_ALERTS)


def main() -> None:
    db_path = database_path()
    rules_path = os.getenv("AML_QC_RULES_PATH", "config/rules.json")
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    load_rule_config(rules_path)
    init_db(db_path)
    maybe_seed_demo_data(db_path)
    run_server(db_path=db_path, rules_path=rules_path, host=host, port=port)


if __name__ == "__main__":
    main()

