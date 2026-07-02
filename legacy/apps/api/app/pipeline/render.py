"""Renderer for 9:16 short videos. Lifted from V1 tennisoutlet-video-agent.

Pillow text compositing → per-scene PNG sequences → ffmpeg concat → MP4.
Deterministic, $0 cost, no second runtime. See `docs/remotion-upgrade.md` of V1
for the eventual migration path to Remotion.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List

from PIL import Image, ImageDraw, ImageFont


WIDTH, HEIGHT, FPS = 1080, 1920, 30
SAFE_FONT_FALLBACK = "/usr/share/fonts/truetype/inter/Inter-VariableFont_slnt,wght.ttf"


@dataclass
class Scene:
    duration_s: float
    backdrop_path: str           # local image
    voiceover_path: str | None   # local audio
    on_screen_text: str = ""
    cta: str = ""


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in [
        SAFE_FONT_FALLBACK,
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _compose_frame(scene: Scene, out: Path) -> None:
    img = Image.open(scene.backdrop_path).convert("RGB").resize((WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img, "RGBA")
    if scene.on_screen_text:
        f = _font(72)
        bbox = draw.textbbox((0, 0), scene.on_screen_text, font=f)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        # subtle dark gradient at bottom
        draw.rectangle([(0, HEIGHT - th - 240), (WIDTH, HEIGHT)], fill=(0, 0, 0, 140))
        draw.text(((WIDTH - tw) // 2, HEIGHT - th - 180), scene.on_screen_text, font=f, fill=(255, 255, 255))
    if scene.cta:
        f = _font(54)
        bbox = draw.textbbox((0, 0), scene.cta, font=f)
        tw, _ = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.rectangle([((WIDTH - tw) // 2 - 24, HEIGHT - 120), ((WIDTH + tw) // 2 + 24, HEIGHT - 60)], fill=(204, 255, 0))
        draw.text(((WIDTH - tw) // 2, HEIGHT - 116), scene.cta, font=f, fill=(10, 10, 11))
    img.save(out)


def render_short_video(scenes: List[Scene], out_path: str) -> str:
    """Compose each scene as one still frame held for `duration_s`, then concat with ffmpeg.

    Returns the absolute output path on success.
    """
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        clip_paths: List[Path] = []

        for i, scene in enumerate(scenes):
            frame_png = td_path / f"frame_{i:02d}.png"
            _compose_frame(scene, frame_png)
            clip_mp4 = td_path / f"clip_{i:02d}.mp4"

            # build a clip from the still frame
            ff_in = ["ffmpeg", "-y", "-loop", "1", "-i", str(frame_png), "-t", str(scene.duration_s)]
            if scene.voiceover_path and os.path.exists(scene.voiceover_path):
                ff_in += ["-i", scene.voiceover_path, "-c:a", "aac", "-shortest"]
            ff_in += [
                "-c:v", "libx264",
                "-r", str(FPS),
                "-pix_fmt", "yuv420p",
                "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=cover,crop={WIDTH}:{HEIGHT}",
                "-loglevel", "error",
                str(clip_mp4),
            ]
            subprocess.run(ff_in, check=True)
            clip_paths.append(clip_mp4)

        # concat demuxer requires absolute paths
        list_file = td_path / "concat.txt"
        list_file.write_text("\n".join(f"file '{p.resolve()}'" for p in clip_paths))
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(list_file),
                "-c", "copy",
                "-loglevel", "error",
                out_path,
            ],
            check=True,
        )
    return out_path
