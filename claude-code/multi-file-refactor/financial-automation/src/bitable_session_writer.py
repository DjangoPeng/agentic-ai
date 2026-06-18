from __future__ import annotations

import sys
from pathlib import Path

# Add parent common directory to path
COMMON_DIR = Path(__file__).parent.parent.parent / "common"
sys.path.insert(0, str(COMMON_DIR))

from feishu.bitable import pick_reusable_record_id, choose_write_action

TRANSPORT_TARGET = "transport"
EXPENSE_TARGET = "expense"
PRIMARY_FIELD = "doc_id"


def choose_bitable_write_action(existing_records: list[dict[str, Any]]) -> dict[str, Any]:
    return choose_write_action(existing_records)
