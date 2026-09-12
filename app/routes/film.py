"""Cinematic Storyboard Film — storyboard-first video.

Storyboard first, video second: `plan` directs a cut-by-cut storyboard and
renders NOTHING. The operator edits and reorders cuts; a human approves the
creative (the same approval gate as everything else); only then does `render`
generate the reference frames and voiceover. Both long operations run in the
bounded pool; poll `GET /api/agency/jobs/{job_id}`.
"""
from __future__ import annotations

import json

from fastapi import APIRouter

from ._shared import *  # noqa: F401,F403
from ..services import agency_pool, film_studio

router = APIRouter()


def _no_client(user):
    if user["role"] == "client":
        raise HTTPException(403, "Client logins can review and approve a film, but not edit or render it")


@router.get("/api/film-studio/options")
def film_options(user=Depends(current_user)):
    return {
        "looks": [{"id": k, "desc": v} for k, v in film_studio.FILM_LOOKS.items()],
        "aspects": list(film_studio.FILM_ASPECTS.keys()),
        "voices": ai_engine.VOICES,
        "transitions": film_studio.TRANSITIONS,
        "camera_moves": film_studio.CAMERA_MOVES,
        "limits": {"cut_min_s": film_studio.CUT_MIN, "cut_max_s": film_studio.CUT_MAX,
                   "max_cuts": film_studio.MAX_CUTS, "target_min": film_studio.TARGET_MIN,
                   "target_max": film_studio.TARGET_MAX},
    }


@router.post("/api/brands/{bid}/film/plan")
def film_plan(bid: str, body: FilmPlanIn, user=Depends(current_user)):
    """Direct a storyboard (no render). Runs in the pool; poll the returned job."""
    b = _brand_or_404(bid, user)
    _no_client(user)
    _gen_guard(bid)
    source = (body.prompt or "").strip()
    if body.creative_id:
        c = _doc_or_404("creatives", body.creative_id, bid)
        source = json.dumps({k: c["payload"].get(k) for k in ("title", "caption", "script", "film")}, ensure_ascii=False, default=str)
    if len(source) < 10:
        raise HTTPException(400, "Describe the film idea, or start from an existing creative")
    j = agency_pool.POOL.submit(bid, "film_plan", film_studio.plan, bid, source, body.look, body.aspect,
                                body.cuts, body.target_seconds, body.voice)
    resp = {"job_id": j["id"], "state": j["state"]}
    if j.get("state") == "done" and j.get("result"):
        resp.update(j["result"])
    elif j.get("state") == "failed":
        raise HTTPException(502, j.get("error") or "Storyboard failed")
    return resp


@router.get("/api/brands/{bid}/film/{cid}")
def film_get(bid: str, cid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    c = _doc_or_404("creatives", cid, bid)
    film = (c.get("payload") or {}).get("film")
    if not film:
        raise HTTPException(404, "This creative is not a film")
    return {"id": c["id"], "title": (c["payload"] or {}).get("title"), "channel": c.get("channel"),
            "approval": (c["payload"] or {}).get("approval"), "asset_path": c.get("asset_path"),
            "caption": (c["payload"] or {}).get("caption"), "hashtags": (c["payload"] or {}).get("hashtags"),
            "film": film, "summary": film_studio.summary_lines(c),
            "editable": user["role"] != "client" and film.get("status") != "rendering"}


@router.get("/api/brands/{bid}/films")
def films_list(bid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    out = []
    for c in db.list_docs("creatives", bid):
        film = (c.get("payload") or {}).get("film")
        if not film:
            continue
        out.append({"id": c["id"], "title": (c["payload"] or {}).get("title"),
                    "status": film.get("status"), "cuts": len(film.get("cuts", [])),
                    "total_seconds": film.get("total_seconds"), "look": film.get("look"),
                    "approval": ((c["payload"] or {}).get("approval") or {}).get("state"),
                    "created_at": c.get("created_at")})
    out.sort(key=lambda x: -(x.get("created_at") or 0))
    return out


def _edit(bid, cid, user, fn, *a):
    _brand_or_404(bid, user)
    _no_client(user)
    _doc_or_404("creatives", cid, bid)
    try:
        film = fn(bid, cid, *a)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "film": film}


@router.put("/api/brands/{bid}/film/{cid}/cut/{index}")
def film_edit_cut(bid: str, cid: str, index: int, body: FilmCutIn, user=Depends(current_user)):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    return _edit(bid, cid, user, film_studio.update_cut, index, patch)


@router.post("/api/brands/{bid}/film/{cid}/reorder")
def film_reorder(bid: str, cid: str, body: FilmReorderIn, user=Depends(current_user)):
    return _edit(bid, cid, user, film_studio.reorder, body.order)


@router.post("/api/brands/{bid}/film/{cid}/cut")
def film_add_cut(bid: str, cid: str, user=Depends(current_user), after: int | None = None):
    return _edit(bid, cid, user, film_studio.add_cut, after)


@router.delete("/api/brands/{bid}/film/{cid}/cut/{index}")
def film_remove_cut(bid: str, cid: str, index: int, user=Depends(current_user)):
    return _edit(bid, cid, user, film_studio.remove_cut, index)


@router.put("/api/brands/{bid}/film/{cid}")
def film_meta(bid: str, cid: str, body: FilmMetaIn, user=Depends(current_user)):
    return _edit(bid, cid, user, film_studio.set_meta, {k: v for k, v in body.model_dump().items() if v is not None})


@router.post("/api/brands/{bid}/film/{cid}/render")
def film_render(bid: str, cid: str, user=Depends(current_user)):
    """Gate: the storyboard must be human-approved. Then render in the pool."""
    _brand_or_404(bid, user)
    _no_client(user)
    c = _doc_or_404("creatives", cid, bid)
    film = (c.get("payload") or {}).get("film")
    if not film:
        raise HTTPException(404, "This creative is not a film")
    if ((c["payload"] or {}).get("approval") or {}).get("state") != "approved":
        raise HTTPException(400, "Approve the storyboard first — nothing renders until a human approves it")
    if film.get("status") == "rendering":
        raise HTTPException(409, "This film is already rendering")
    _gen_guard(bid)
    j = agency_pool.POOL.submit(bid, "film_render", film_studio.render, bid, cid, meta={"creative_id": cid})
    resp = {"job_id": j["id"], "state": j["state"], "creative_id": cid}
    if j.get("state") == "done" and j.get("result"):
        resp.update(j["result"])
    elif j.get("state") == "failed":
        raise HTTPException(502, j.get("error") or "Render failed")
    return resp
