"""Operating mode, the approval queue, and manual override.

The intended way to run this system is hands-off: the agents do the work and a
human only approves. These routes make that explicit.

  auto    agents generate on their own and everything lands in the approval
          queue. The human's whole job is approve / request changes.
  manual  nothing is generated automatically; the human drives each step.

Manual mode is also available per item: `revise` takes one creative back under
human control with a written instruction, re-runs just that creative, and files
the instruction as a correction so the same note never has to be given twice.
"""
from fastapi import APIRouter
from ._shared import *  # noqa: F401,F403
from ..ai import brain
from ..services import memory as mem

router = APIRouter()

MODES = ("auto", "manual")


class ModeIn(BaseModel):
    mode: str


class ReviseIn(BaseModel):
    instruction: str
    remember: bool = True


def _mode_of(b):
    return ((b.get("setup") or {}).get("mode") or "auto").lower()


@router.get("/api/brands/{bid}/mode")
def get_mode(bid: str, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    mode = _mode_of(b)
    return {
        "mode": mode,
        "modes": list(MODES),
        "description": ("Agents generate on their own; you only approve."
                        if mode == "auto" else
                        "Nothing is generated automatically; you drive each step."),
    }


@router.post("/api/brands/{bid}/mode")
def set_mode(bid: str, body: ModeIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    mode = (body.mode or "").strip().lower()
    if mode not in MODES:
        raise HTTPException(400, f"mode must be one of: {', '.join(MODES)}")
    setup = dict(b.get("setup") or {})
    setup["mode"] = mode
    db.update_brand(bid, setup=setup)
    return {"ok": True, "mode": mode}


@router.get("/api/approvals")
def approval_queue(user=Depends(current_user)):
    """The one screen a human needs: everything waiting on a decision.

    Ordered oldest-first so nothing sits forgotten at the bottom of a list.
    """
    brand_list = db.list_brands() if user.get("role") == "admin" else \
        [b for b in [db.get_brand(user.get("brand_id") or "")] if b]

    waiting, revising = [], []
    for b in brand_list:
        for cr in db.list_docs("creatives", b["id"]):
            payload = cr.get("payload") or {}
            approval = payload.get("approval") or {}
            gen = payload.get("gen_status") or ""
            item = {
                "id": cr["id"],
                "brand_id": b["id"],
                "brand": b.get("name"),
                "title": payload.get("title"),
                "format": cr.get("format"),
                "channel": cr.get("channel"),
                "asset_path": cr.get("asset_path"),
                "caption": (payload.get("caption") or "")[:400],
                "created_at": cr.get("created_at"),
                "ready": gen.startswith("done") or bool(cr.get("asset_path")),
            }
            state = approval.get("state")
            if not state:
                waiting.append(item)
            elif state == "changes_requested":
                item["comment"] = approval.get("comment")
                revising.append(item)

    waiting.sort(key=lambda x: x.get("created_at") or 0)
    revising.sort(key=lambda x: x.get("created_at") or 0)
    return {
        "waiting_for_approval": waiting,
        "changes_requested": revising,
        "counts": {"waiting": len(waiting), "changes_requested": len(revising)},
    }


def _revise(cid, bid, instruction):
    """Re-run one creative under an explicit human instruction."""
    run_id = mem.start_run(bid, "revise", creative_id=cid, meta={"instruction": instruction})
    try:
        c = db.get_doc("creatives", cid) or {}
        payload = dict(c.get("payload") or {})
        bp = dict(payload.get("blueprint") or {})
        brand = db.get_brand(bid)

        base = bp.get("static_image_prompt") or bp.get("core_idea") or payload.get("title") or ""
        prompt = f"{base}\n\nOPERATOR REVISION — apply this exactly: {instruction}"

        payload["gen_status"] = "Applying your changes…"
        db.update_doc("creatives", cid, payload=payload)

        logo = brain.brand_logo_url(brand)
        img = brain.fal_image(prompt, logo_url=logo, brand=brand)
        blob = brain.composite_brand_logo(img, logo) if (img and logo) else None
        if blob:
            rel = f"brain/assets/{cid}-rev.png"
            ref = _save_asset(brand, rel, blob)
            img = ref if ref.startswith("http") else f"/workspaces/{_wslug(brand)}/{ref}"

        payload = dict((db.get_doc("creatives", cid) or {}).get("payload") or {})
        payload["gen_status"] = "done ✓"
        payload["revision"] = {"instruction": instruction, "at": time.time()}
        payload["approval"] = None  # a revised asset needs a fresh decision
        db.update_doc("creatives", cid, payload=payload, asset_path=img)
        mem.finish_run(run_id, "done", result={"asset_path": img})
    except Exception as e:
        try:
            c = db.get_doc("creatives", cid) or {}
            payload = dict(c.get("payload") or {})
            payload["gen_status"] = f"revision failed: {e}"
            db.update_doc("creatives", cid, payload=payload)
        except Exception:
            pass
        mem.finish_run(run_id, "error", error=str(e))


@router.post("/api/brands/{bid}/creatives/{cid}/revise")
def revise(bid: str, cid: str, body: ReviseIn, user=Depends(current_user)):
    """Take one creative into manual control and apply a specific change.

    This is the escape hatch from hands-off mode: the rest of the brand keeps
    running on autopilot while this single item is redone to your instruction.
    """
    _brand_or_404(bid, user)
    _gen_guard(bid)
    c = _doc_or_404("creatives", cid, bid)
    instruction = (body.instruction or "").strip()
    if not instruction:
        raise HTTPException(400, "instruction is required — say what should change")

    if body.remember:
        # So the next brief already knows, instead of needing the same note again.
        mem.remember(bid, f"When making a {c.get('format') or 'post'}: {instruction}",
                     kind="correction", weight=2.0, source=f"revise:{cid}")

    threading.Thread(target=_revise, args=(cid, bid, instruction), daemon=True).start()
    return {"ok": True, "started": True, "creative_id": cid}
