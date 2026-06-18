#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run financial-automation skill entry with the project virtualenv and emit a user-identity bitable write plan.",
    )
    parser.add_argument(
        "attachments",
        nargs="+",
        help="One or more local attachment paths (.pdf/.jpg/.jpeg/.png).",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Optional config path. Defaults to config/app_config.yaml.",
    )
    return parser.parse_args()


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))

    from src.skill_entry import run_skill_job

    args = _parse_args()
    attachments: list[dict[str, str]] = []
    for raw_path in args.attachments:
        path = Path(raw_path).expanduser().resolve()
        attachments.append(
            {
                "file_name": path.name,
                "source_path": str(path),
            }
        )

    config_path = args.config or str(repo_root / "config" / "app_config.yaml")
    result = run_skill_job(attachments, config_path=config_path)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
