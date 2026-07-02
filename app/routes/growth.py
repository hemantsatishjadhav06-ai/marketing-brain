from fastapi import APIRouter
from ._shared import *  # noqa: F401,F403

router = APIRouter()


@router.post("/api/brands/{bid}/blog")
def blog(bid: str, body: BlogIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    try:
        art = ai_engine.write_blog(b, body.topic, body.keyword, _latest_insights(bid))
    except Exception as e:
        raise HTTPException(502, f"Blog generation failed: {e}")
    art["format"] = "blog"
    cid = db.insert_doc("creatives", bid, art, channel="blog", format="blog")
    md = f"# {art.get('title','')}\n\n*{art.get('meta_description','')}*\n\n{art.get('body_markdown','')}\n\n{art.get('cta','')}"
    ws.write_text(_wslug(b), f"blog/creatives/{cid}-{ws.slugify(art.get('title','post'))[:40]}.md", md)
    ws.write_json(_wslug(b), f"blog/creatives/{cid}.json", art)
    return db.get_doc("creatives", cid)


@router.post("/api/brands/{bid}/email")
def email(bid: str, body: EmailIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    try:
        out = ai_engine.write_email(b, body.etype, body.topic, max(1, min(7, body.email_count)), _latest_insights(bid))
    except Exception as e:
        raise HTTPException(502, f"Email generation failed: {e}")
    out["format"] = "email"
    out["etype"] = body.etype
    out.setdefault("title", out.get("sequence_name") or f"{body.etype}: {body.topic or 'untitled'}"[:80])
    cid = db.insert_doc("creatives", bid, out, channel="email", format="email")
    ws.write_json(_wslug(b), f"email/creatives/{cid}.json", out)
    return db.get_doc("creatives", cid)


@router.post("/api/brands/{bid}/playbook")
def playbook(bid: str, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    try:
        tactics = ai_engine.tactics_playbook(b, _latest_insights(bid))
    except Exception as e:
        raise HTTPException(502, f"Playbook generation failed: {e}")
    ws.write_json(_wslug(b), "brand-profile/tactics-playbook.json", tactics)
    return {"tactics": tactics}


@router.post("/api/brands/{bid}/chat")
def chat(bid: str, body: ChatIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    digest = _workspace_digest(b)
    try:
        reply = ai_engine.coach_chat(b, digest, body.history, body.message)
    except Exception as e:
        raise HTTPException(502, f"Coach unavailable: {e}")
    return {"reply": reply}


@router.post("/api/brands/{bid}/repurpose")
def repurpose(bid: str, body: RepurposeIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    if len(body.source.strip()) < 200:
        raise HTTPException(400, "Paste at least a few paragraphs of transcript/article to clip from")
    try:
        clips = ai_engine.repurpose_longform(b, body.source, body.count, body.platform)
    except Exception as e:
        raise HTTPException(502, f"Repurposing failed: {e}")
    # save each clip as a ready idea so it can flow into the normal pipeline
    saved = []
    for clip in clips:
        idea = {"title": clip.get("title"), "format": "reel", "hook": clip.get("hook"),
                "concept": clip.get("short_script"), "pillar": "repurposed",
                "funnel_stage": "awareness", "effort": "low",
                "why_it_works": clip.get("why_this_moment"), "cta": "",
                "virality": clip.get("virality"), "source_quote": clip.get("quote"),
                "timestamp": clip.get("timestamp_or_section")}
        iid = db.insert_doc("ideas", bid, idea, channel=body.platform)
        saved.append({"id": iid, "clip": clip})
    ws.write_json(_wslug(b), f"{body.platform}/ideas/repurposed-{db.new_id()}.json", clips)
    return {"clips": saved}


@router.post("/api/brands/{bid}/seo")
def seo(bid: str, body: SeoIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    try:
        out = ai_engine.seo_research(b, body.topic, body.platform)
    except Exception as e:
        raise HTTPException(502, f"SEO research failed: {e}")
    ws.write_json(_wslug(b), f"brand-profile/seo-{ws.slugify(body.topic)[:40]}.json", out)
    return out


@router.post("/api/brands/{bid}/trends")
def trends(bid: str, body: TrendsIn = None, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    body = body or TrendsIn()
    signals = None
    if body.live and trend_scanner.enabled():
        signals = trend_scanner.fresh_scan_of(b) if not body.keywords else None
        if not signals:
            kws = body.keywords or trend_scanner.default_keywords(b)
            signals = trend_scanner.scan(kws)
            if signals.get("ok"):
                profile = b.get("profile") or {}
                profile["trend_scan"] = signals
                db.update_brand(bid, profile=profile)
                b = db.get_brand(bid)
    try:
        out = ai_engine.trend_radar(b, signals)
    except Exception as e:
        raise HTTPException(502, f"Trend radar failed: {e}")
    ws.write_json(_wslug(b), "brand-profile/trend-radar.json", out)
    live_used = bool(signals and signals.get("ok"))
    return {"trends": out, "live_data": live_used,
            "scanned_keywords": (signals or {}).get("keywords") if live_used else None,
            "scanned_at": (signals or {}).get("scanned_at") if live_used else None,
            "note": "Grounded in scraped Google search signals." if live_used else
                    "AI-inferred hypotheses (no Apify token or scan failed) — validate before betting big."}


@router.post("/api/brands/{bid}/score")
def score(bid: str, body: ScoreIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    table = "ideas" if body.kind == "idea" else "creatives"
    doc = db.get_doc(table, body.id)
    if not doc:
        raise HTTPException(404, f"{body.kind} not found")
    try:
        result = ai_engine.score_virality(b, doc["payload"])
    except Exception as e:
        raise HTTPException(502, f"Scoring failed: {e}")
    payload = doc["payload"]
    payload["virality"] = {"score": result.get("score"), **(result.get("breakdown") or {})}
    payload["virality_verdict"] = result.get("verdict")
    db.update_doc(table, body.id, payload=payload)
    return result


@router.get("/api/playbook")
def playbook_catalog():
    """Public ShadowFox playbook catalog (5 systems / 29 prompts)."""
    return playbook.catalog()


@router.post("/api/brands/{bid}/playbook/run")
def playbook_run(bid: str, body: PlaybookRunIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    try:
        res = ai_engine.run_playbook(b, body.system, body.prompt, body.inputs)
    except Exception as e:
        raise HTTPException(502, f"Playbook failed: {e}")
    if res.get("kind") == "image":
        blob = ai_engine.generate_image(res["image_prompt"], b["name"], ai_engine.brand_palette(b))
        if not blob:
            raise HTTPException(502, "Image generation failed (model returned no image).")
        blob = _composite_logo(b, blob)
        rel = f"playbook/assets/{body.system}-{body.prompt}-{int(time.time())}.png"
        ref = _save_asset(b, rel, blob)
        db_url = ref if ref.startswith("http") else f"/workspaces/{_wslug(b)}/{ref}"
        return {"kind": "image", "asset_url": db_url}
    return res

