"""解析処理をバックグラウンドスレッドで実行する。

大量の写真・動画を処理するとHTTPリクエストが長時間ブロックされてしまうため、
別スレッドで実行しWeb UIからはポーリングで進捗を確認する方式にする。
同時に複数のスキャンが走らないよう単純なロックで排他制御する。
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from . import db
from .config import Settings, load_scoring_rules
from .pipeline import run_grouping_and_scoring, scan_and_analyze

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_is_running = False


def is_running() -> bool:
    return _is_running


def start_scan_job(settings: Settings, root: Path) -> bool:
    """スキャン+解析+グルーピングをバックグラウンドで開始する。

    既に実行中の場合はFalseを返し、新しいジョブは開始しない(二重実行防止)。
    """
    global _is_running

    if not _lock.acquire(blocking=False):
        return False
    _is_running = True

    def _run() -> None:
        global _is_running
        try:
            conn = db.get_connection(settings.database_path)
            try:
                scan_and_analyze(conn, settings, root)
                scoring_rules = load_scoring_rules(settings)
                run_grouping_and_scoring(conn, settings, scoring_rules)
            finally:
                conn.close()
        except Exception:  # noqa: BLE001
            logger.exception("バックグラウンド解析ジョブでエラーが発生しました")
        finally:
            _is_running = False
            _lock.release()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return True
