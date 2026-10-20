"""
项目入口：把 src 加进 sys.path 后转给 cli。
python run.py check
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from cityu_power.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
