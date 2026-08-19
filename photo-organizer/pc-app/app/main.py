"""FastAPI アプリ本体。ローカル(127.0.0.1)専用のWeb UIとAPI。

写真・動画そのものは外部へ送信しない。サムネイルもこのサーバーからしか配信しない。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import db, repository as repo
from .config import load_scoring_rules, load_settings
from .job_runner import is_running, start_scan_job
from .logging_utils import log_event
from .manifest import write_manifest
from .scoring import reason_labels_ja
from .settings_repo import OVERRIDABLE_THRESHOLD_KEYS, get_threshold_overrides, set_threshold_override
from .video_frames import clear_thumbnail_cache
import json as _json

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent
PC_APP_DIR = APP_DIR.parent
WEB_DIR = PC_APP_DIR / "web"

settings = load_settings()
settings.ensure_directories()

app = FastAPI(title="AI写真・動画整理システム(PC側解析アプリ)")
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")
app.mount("/thumbnails", StaticFiles(directory=str(settings.thumbnail_cache_dir)), name="thumbnails")
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))


def get_conn():
    return db.get_connection(settings.database_path)


def _dashboard_stats(conn) -> dict:
    photo_count = conn.execute("SELECT COUNT(*) c FROM media_items WHERE media_type='photo'").fetchone()["c"]
    video_count = conn.execute("SELECT COUNT(*) c FROM media_items WHERE media_type='video'").fetchone()["c"]
    total_size = conn.execute("SELECT COALESCE(SUM(file_size),0) s FROM media_items").fetchone()["s"]
    analyzed = conn.execute("SELECT COUNT(*) c FROM media_items WHERE analysis_status='analyzed'").fetchone()["c"]
    total = photo_count + video_count
    analyzed_pct = round((analyzed / total) * 100, 1) if total else 0.0

    candidate_count = conn.execute(
        "SELECT COUNT(*) c FROM delete_candidates WHERE user_status != 'excluded'"
    ).fetchone()["c"]
    estimated_savings = conn.execute(
        """
        SELECT COALESCE(SUM(m.file_size), 0) s
        FROM delete_candidates dc JOIN media_items m ON m.id = dc.media_id
        WHERE dc.user_status != 'excluded'
        """
    ).fetchone()["s"]

    return {
        "photo_count": photo_count,
        "video_count": video_count,
        "total_size": total_size,
        "analyzed_pct": analyzed_pct,
        "candidate_count": candidate_count,
        "estimated_savings": estimated_savings,
    }


def _category_stats(conn) -> list[dict]:
    categories = [
        ("完全重複", "SELECT COUNT(DISTINCT dgi.media_id) c, COALESCE(SUM(m.file_size),0) s "
                    "FROM duplicate_group_items dgi JOIN media_items m ON m.id=dgi.media_id "
                    "WHERE dgi.is_keep_recommended=0"),
        ("類似写真", "SELECT COUNT(DISTINCT sgi.media_id) c, COALESCE(SUM(m.file_size),0) s "
                    "FROM similarity_group_items sgi JOIN similarity_groups sg ON sg.id=sgi.group_id "
                    "JOIN media_items m ON m.id=sgi.media_id WHERE sg.group_type='photo' AND sgi.is_keep_recommended=0"),
        ("スクリーンショット", "SELECT COUNT(*) c, COALESCE(SUM(file_size),0) s FROM media_items WHERE is_screenshot=1"),
        ("ピンぼけ", "SELECT COUNT(*) c, COALESCE(SUM(file_size),0) s FROM media_items WHERE blur_variance IS NOT NULL "
                    "AND blur_variance < 100"),
        ("暗い写真", "SELECT COUNT(*) c, COALESCE(SUM(file_size),0) s FROM media_items WHERE brightness_mean IS NOT NULL "
                   "AND brightness_mean < 35"),
        ("大容量動画", "SELECT COUNT(*) c, COALESCE(SUM(file_size),0) s FROM media_items WHERE media_type='video' "
                    "AND file_size >= 524288000"),
        ("画面録画", "SELECT COUNT(*) c, COALESCE(SUM(file_size),0) s FROM media_items WHERE is_screen_recording=1"),
        ("類似動画", "SELECT COUNT(DISTINCT sgi.media_id) c, COALESCE(SUM(m.file_size),0) s "
                   "FROM similarity_group_items sgi JOIN similarity_groups sg ON sg.id=sgi.group_id "
                   "JOIN media_items m ON m.id=sgi.media_id WHERE sg.group_type='video' AND sgi.is_keep_recommended=0"),
    ]
    result = []
    for label, query in categories:
        row = conn.execute(query).fetchone()
        result.append({"label": label, "count": row["c"], "size": row["s"]})
    return result


@app.get("/")
def dashboard(request: Request):
    conn = get_conn()
    try:
        stats = _dashboard_stats(conn)
        categories = _category_stats(conn)
    finally:
        conn.close()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "stats": stats, "categories": categories, "job_running": is_running()},
    )


@app.post("/api/scan")
def api_scan(root_folder: str = Form(...)):
    root = Path(root_folder).expanduser()
    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=400, detail=f"フォルダが見つかりません: {root_folder}")

    conn = get_conn()
    try:
        log_event(conn, "scan_started", {"root_folder": str(root)})
    finally:
        conn.close()

    started = start_scan_job(settings, root)
    if not started:
        return JSONResponse({"status": "already_running"}, status_code=409)
    return JSONResponse({"status": "started"})


@app.get("/api/job-status")
def api_job_status():
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM jobs WHERE job_type='scan_and_analyze' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return {"running": is_running(), "job": None}
    return {
        "running": is_running(),
        "job": {
            "status": row["status"],
            "total_files": row["total_files"],
            "processed_files": row["processed_files"],
            "error_count": row["error_count"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
        },
    }


@app.get("/media/{media_id}/preview")
def media_preview(media_id: int):
    """写真プレビュー配信。ローカル(127.0.0.1)のみで完結し外部送信はしない。"""
    conn = get_conn()
    try:
        row = conn.execute("SELECT absolute_path, extension FROM media_items WHERE id=?", (media_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="見つかりません")
    file_path = Path(row["absolute_path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="ファイルが見つかりません(移動・削除された可能性があります)")
    return FileResponse(file_path)


@app.get("/similarity-groups")
def similarity_groups_list(request: Request, group_type: str = "photo"):
    conn = get_conn()
    try:
        groups = conn.execute(
            "SELECT * FROM similarity_groups WHERE group_type=? ORDER BY id", (group_type,)
        ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        "similarity_groups.html",
        {"request": request, "groups": groups, "group_type": group_type},
    )


@app.get("/similarity-groups/{group_id}")
def similarity_group_detail(request: Request, group_id: int):
    conn = get_conn()
    try:
        group = conn.execute("SELECT * FROM similarity_groups WHERE id=?", (group_id,)).fetchone()
        if group is None:
            raise HTTPException(status_code=404, detail="グループが見つかりません")
        items = conn.execute(
            """
            SELECT sgi.media_id, sgi.is_keep_recommended, sgi.user_decision, sgi.distance, m.*
            FROM similarity_group_items sgi JOIN media_items m ON m.id = sgi.media_id
            WHERE sgi.group_id = ? ORDER BY sgi.is_keep_recommended DESC
            """,
            (group_id,),
        ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        "similarity_group_detail.html", {"request": request, "group": group, "items": items}
    )


@app.post("/api/similarity-groups/{group_id}/items/{media_id}/decision")
def set_similarity_decision(group_id: int, media_id: int, decision: str = Form(...)):
    if decision not in ("keep", "delete"):
        raise HTTPException(status_code=400, detail="不正な値です")
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE similarity_group_items SET user_decision=? WHERE group_id=? AND media_id=?",
            (decision, group_id, media_id),
        )
        # ユーザーが手動で決めた場合は delete_candidates の除外状態にも反映する
        repo.set_delete_candidate_status(conn, media_id, "candidate" if decision == "delete" else "excluded")
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}


@app.get("/videos")
def videos_list(request: Request):
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT m.*, dc.deletion_candidate_score, dc.reasons_json
            FROM media_items m LEFT JOIN delete_candidates dc ON dc.media_id = m.id
            WHERE m.media_type = 'video'
            ORDER BY COALESCE(dc.deletion_candidate_score, 0) DESC
            """
        ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse("videos.html", {"request": request, "videos": rows})


@app.get("/delete-review")
def delete_review(request: Request):
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT m.*, dc.deletion_candidate_score, dc.reasons_json, dc.user_status
            FROM delete_candidates dc JOIN media_items m ON m.id = dc.media_id
            ORDER BY dc.deletion_candidate_score DESC
            """
        ).fetchall()
        items = []
        for r in rows:
            reasons = _json.loads(r["reasons_json"]) if r["reasons_json"] else []
            items.append({
                "media_id": r["id"],
                "file_name": r["file_name"],
                "media_type": r["media_type"],
                "file_size": r["file_size"],
                "captured_at": r["captured_at"],
                "score": r["deletion_candidate_score"],
                "reasons_ja": reason_labels_ja(reasons),
                "user_status": r["user_status"],
            })
        photo_items = [i for i in items if i["media_type"] == "photo" and i["user_status"] != "excluded"]
        video_items = [i for i in items if i["media_type"] == "video" and i["user_status"] != "excluded"]
        total_size = sum(i["file_size"] for i in items if i["user_status"] != "excluded")
    finally:
        conn.close()
    return templates.TemplateResponse(
        "delete_review.html",
        {
            "request": request,
            "items": items,
            "photo_count": len(photo_items),
            "video_count": len(video_items),
            "total_size": total_size,
        },
    )


@app.post("/api/delete-candidates/{media_id}/status")
def set_candidate_status(media_id: int, user_status: str = Form(...)):
    if user_status not in ("candidate", "excluded", "confirmed"):
        raise HTTPException(status_code=400, detail="不正な値です")
    conn = get_conn()
    try:
        repo.set_delete_candidate_status(conn, media_id, user_status)
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}


@app.post("/api/generate-manifest")
def generate_manifest():
    conn = get_conn()
    try:
        conn.execute("UPDATE delete_candidates SET user_status='confirmed' WHERE user_status='candidate'")
        conn.commit()
        rows = conn.execute(
            """
            SELECT m.* FROM delete_candidates dc JOIN media_items m ON m.id = dc.media_id
            WHERE dc.user_status = 'confirmed'
            """
        ).fetchall()
        items = [repo.row_to_media_item(r) for r in rows]

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = settings.database_path.parent / "exports" / f"delete_manifest_{timestamp}.json"
        write_manifest(items, output_path)

        log_event(conn, "manifest_generated", {"item_count": len(items), "total_size": sum(i.file_size for i in items)})
    finally:
        conn.close()

    return {"status": "ok", "item_count": len(items), "file": str(output_path)}


@app.get("/api/manifest/download")
def download_manifest(path: str):
    export_dir = (settings.database_path.parent / "exports").resolve()
    file_path = Path(path).resolve()
    if export_dir not in file_path.parents:
        raise HTTPException(status_code=400, detail="不正なパスです")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="ファイルが見つかりません")
    return FileResponse(file_path, filename=file_path.name, media_type="application/json")


@app.get("/settings")
def settings_page(request: Request):
    conn = get_conn()
    try:
        overrides = get_threshold_overrides(conn)
    finally:
        conn.close()
    rules = load_scoring_rules(settings)
    defaults = rules.get("thresholds", {})
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "keys": OVERRIDABLE_THRESHOLD_KEYS,
            "defaults": defaults,
            "overrides": overrides,
        },
    )


@app.post("/api/settings/threshold")
def update_threshold(key: str = Form(...), value: float = Form(...)):
    conn = get_conn()
    try:
        set_threshold_override(conn, key, value)
    finally:
        conn.close()
    return {"status": "ok"}


@app.post("/api/thumbnails/clear-cache")
def clear_cache():
    """サムネイルキャッシュを削除する(仕様42)。"""
    clear_thumbnail_cache(settings.thumbnail_cache_dir)
    return {"status": "ok"}
