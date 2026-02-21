"""
main.py - 마스터 실행 매니저
trending_keywords.csv → DB → 분석 → 업데이트
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.logging_config import setup_logging
from core.runner import run_workflow

if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50, help="처리할 키워드 수")
    args = parser.parse_args()
    run_workflow(limit=args.limit)
