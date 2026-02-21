"""
SQLite 데이터베이스 모듈
상품명, 수집일, 네이버 검색량, 쿠팡 로켓수, 도매가 등 시계열 저장
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "coupang_gross.db"


def get_connection():
    return sqlite3.connect(str(DB_PATH))


@contextmanager
def db_session():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """테이블 생성"""
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS keyword_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                category TEXT,
                collected_at TEXT NOT NULL,
                naver_rank INTEGER,
                naver_change_trend TEXT,
                coupang_rocket_count INTEGER,
                coupang_avg_price INTEGER,
                coupang_total_products INTEGER,
                wholesale_min_price INTEGER,
                wholesale_source TEXT,
                naver_search_ratio REAL,
                consistency_score REAL,
                validation_status TEXT,
                UNIQUE(keyword, collected_at)
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_keyword_collected 
            ON keyword_data(keyword, collected_at)
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS raw_scrapes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                keyword TEXT,
                raw_json TEXT,
                scraped_at TEXT,
                success INTEGER
            )
        """)


def insert_keyword_data(
    keyword: str,
    collected_at: str | None = None,
    category: str = "",
    naver_rank: int | None = None,
    naver_change_trend: str = "",
    coupang_rocket_count: int | None = None,
    coupang_avg_price: int | None = None,
    coupang_total_products: int | None = None,
    wholesale_min_price: int | None = None,
    wholesale_source: str = "",
    naver_search_ratio: float | None = None,
    consistency_score: float | None = None,
    validation_status: str = "pending",
):
    if collected_at is None:
        collected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO keyword_data (
                keyword, category, collected_at,
                naver_rank, naver_change_trend,
                coupang_rocket_count, coupang_avg_price, coupang_total_products,
                wholesale_min_price, wholesale_source,
                naver_search_ratio, consistency_score, validation_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            keyword, category, collected_at,
            naver_rank, naver_change_trend,
            coupang_rocket_count, coupang_avg_price, coupang_total_products,
            wholesale_min_price, wholesale_source,
            naver_search_ratio, consistency_score, validation_status,
        ))


def get_keyword_history(keyword: str, limit: int = 30) -> list[dict]:
    """특정 키워드의 수집 이력 (시계열 분석용)"""
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM keyword_data
            WHERE keyword = ?
            ORDER BY collected_at DESC
            LIMIT ?
        """, (keyword, limit))
        return [dict(row) for row in cur.fetchall()]


def get_latest_by_keywords(keywords: list[str]) -> list[dict]:
    """각 키워드별 최신 데이터"""
    with db_session() as conn:
        cur = conn.cursor()
        placeholders = ",".join("?" * len(keywords))
        cur.execute(f"""
            SELECT * FROM keyword_data k1
            WHERE k1.keyword IN ({placeholders})
            AND k1.collected_at = (
                SELECT MAX(collected_at) FROM keyword_data k2
                WHERE k2.keyword = k1.keyword
            )
        """, keywords)
        return [dict(row) for row in cur.fetchall()]
