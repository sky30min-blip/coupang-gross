"""
로깅 설정 - logs/system.log
"""

import logging
import sys
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
SYSTEM_LOG = LOG_DIR / "system.log"
ERROR_LOG = LOG_DIR / "error.log"


def setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    # 모든 과정을 logs/system.log에 기록
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in root.handlers[:]:
        root.removeHandler(h)

    fh = logging.FileHandler(SYSTEM_LOG, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter(fmt, date_fmt))
    root.addHandler(fh)

    eh = logging.FileHandler(ERROR_LOG, encoding="utf-8")
    eh.setLevel(logging.ERROR)
    eh.setFormatter(logging.Formatter(fmt, date_fmt))
    root.addHandler(eh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(logging.Formatter(fmt, date_fmt))
    root.addHandler(sh)
