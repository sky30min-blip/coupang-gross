"""
database.py - 상업용 Products 테이블 (SQLite)
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
    """Products 테이블 생성"""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS Products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                category TEXT,
                naver_rank INTEGER,
                naver_search_vol REAL,
                coupang_avg_price INTEGER,
                rocket_count INTEGER,
                opportunity_score REAL,
                updated_at TEXT NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_products_keyword ON Products(keyword)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_products_updated ON Products(updated_at)")

        # market_data 테이블 (EDM 히스토리 엔진)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS market_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                search_vol REAL,
                rocket_count INTEGER,
                margin_rate REAL,
                credibility_score REAL,
                collected_at TEXT NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_market_data_keyword ON market_data(keyword)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_market_data_collected ON market_data(collected_at)")


def insert_product(
    keyword: str,
    category: str = "",
    naver_rank: int | None = None,
    naver_search_vol: float | None = None,
    coupang_avg_price: int | None = None,
    rocket_count: int | None = None,
    opportunity_score: float | None = None,
) -> int:
    """Products에 삽입 또는 업데이트. 기존 keyword면 업데이트."""
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM Products WHERE keyword = ?", (keyword,))
        row = cur.fetchone()
        if row:
            cur.execute("""
                UPDATE Products SET
                    category = ?, naver_rank = ?, naver_search_vol = ?,
                    coupang_avg_price = ?, rocket_count = ?, opportunity_score = ?,
                    updated_at = ?
                WHERE keyword = ?
            """, (category, naver_rank, naver_search_vol, coupang_avg_price,
                  rocket_count, opportunity_score, updated_at, keyword))
            return row["id"]
        cur.execute("""
            INSERT INTO Products (keyword, category, naver_rank, naver_search_vol,
                coupang_avg_price, rocket_count, opportunity_score, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (keyword, category, naver_rank, naver_search_vol, coupang_avg_price,
              rocket_count, opportunity_score, updated_at))
        return cur.lastrowid or 0


def get_all_products() -> list[dict]:
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM Products ORDER BY updated_at DESC")
        return [dict(row) for row in cur.fetchall()]


def insert_market_data(
    keyword: str,
    search_vol: float | None = None,
    rocket_count: int | None = None,
    margin_rate: float | None = None,
    credibility_score: float | None = None,
    collected_at: str | None = None,
) -> int:
    """market_data 테이블에 시계열 데이터 삽입."""
    if collected_at is None:
        collected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO market_data (keyword, search_vol, rocket_count, margin_rate, credibility_score, collected_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (keyword, search_vol, rocket_count, margin_rate, credibility_score, collected_at))
        return cur.lastrowid or 0


def update_product_rocket_count(keyword: str, rocket_count: int, opportunity_score: float | None = None) -> bool:
    """해당 키워드의 로켓수(및 선택적 진입점수) 업데이트. 존재하면 True."""
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM Products WHERE keyword = ?", (keyword,))
        row = cur.fetchone()
        if not row:
            return False
        if opportunity_score is not None:
            cur.execute(
                "UPDATE Products SET rocket_count = ?, opportunity_score = ?, updated_at = ? WHERE keyword = ?",
                (rocket_count, opportunity_score, updated_at, keyword),
            )
        else:
            cur.execute(
                "UPDATE Products SET rocket_count = ?, updated_at = ? WHERE keyword = ?",
                (rocket_count, updated_at, keyword),
            )
        return True


def get_products_by_keywords(keywords: list[str]) -> list[dict]:
    if not keywords:
        return []
    with db_session() as conn:
        cur = conn.cursor()
        ph = ",".join("?" * len(keywords))
        cur.execute(f"SELECT * FROM Products WHERE keyword IN ({ph})", keywords)
        return [dict(row) for row in cur.fetchall()]
