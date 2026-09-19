#!/usr/bin/env python3
"""
turbo_transcribe.py - Portable Ultra-Fast & Zero-Heat YouTube Transcript Engine.
- 0% GPU, < 3% CPU (pure lightweight HTTP network calls).
- Direct YouTube inner-tube API + yt-dlp fallback (android/ios/mweb client).
- Automatic deduplication (skip already downloaded files).
- Auto-resume & persistent channel manifest (.channel_done).
- Windows UTF-8 safe (Bangla & multilingual text supported without crash).
"""

import os
import sys
import json
import time
import glob
import re
import tempfile
import shutil
import argparse
from typing import Optional, Tuple, List, Dict

# Ensure terminal outputs UTF-8 cleanly on Windows without cp1252 charmap errors
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    import psutil
    p = psutil.Process()
    # Ensure background execution never overheats PC (Windows IDLE Priority)
    p.nice(getattr(psutil, "IDLE_PRIORITY_CLASS", 64))
except Exception:
    pass

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    _yta = YouTubeTranscriptApi()
except Exception:
    _yta = None

import yt_dlp

BASE_DIR = os.path.join(os.getcwd(), "transcripts")
SYSTEM_TEMP = tempfile.gettempdir()


def clean_slug(text: str) -> str:
    """Generate safe filename slug supporting Bangla and English."""
    t = re.sub(r'[\r\n\t]+', ' ', str(text))
    t = re.sub(r'[\\/:*?"<>|]+', '', t)
    t = re.sub(r'\s+', '_', t).strip('._ ')
    return t[:60] or "video"


def clean_transcript_text(text: str) -> str:
    """Clean music, applause and noise tags from transcripts."""
    if not text:
        return ""
    # Strip bracketed noises like [Music], [Applause], [Muzică]
    cleaned = re.sub(r'\[[A-Za-zÀ-ž\s]+\]', ' ', text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def vtt_to_text(vtt_path: str) -> str:
    """Extract clean, deduplicated human-readable text from VTT / SRT subtitle files."""
    lines = []
    seen = set()
    with open(vtt_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(('WEBVTT', 'Kind:', 'Language:', 'NOTE', '-->')) or re.match(r'^\d+$', line):
                continue
            line = re.sub(r'<[^>]+>', '', line)  # Strip HTML tags
            line = re.sub(r'\[[A-Za-zÀ-ž\s]+\]', '', line)  # Strip noise annotations
            line = re.sub(r'\s+', ' ', line).strip()
            if line and line not in seen:
                lines.append(line)
                seen.add(line)
    return " ".join(lines)


def fetch_official_transcript(video_id: str, langs: str = "bn,bn-BD,en,en-US,en-GB") -> Tuple[Optional[str], Optional[str]]:
    """
    Zero-CPU Fast Caption Extractor:
    1. Direct HTTP call via YouTubeTranscriptApi (~200ms)
    2. Fallback to lightweight yt-dlp subtitle download (skip_download: True)
    Supports preferred languages (Bangla & English) and falls back to any available transcript.
    """
    langs_list = [l.strip() for l in langs.split(",") if l.strip()]

    # 1. Fast Direct HTTP Method
    if _yta:
        try:
            transcript_list = _yta.list(video_id)
            selected_transcript = None

            # Attempt 1: Try requested languages
            try:
                selected_transcript = transcript_list.find_transcript(langs_list)
            except Exception:
                pass

            # Attempt 2: If preferred not found, take the first available transcript (manual or auto)
            if not selected_transcript:
                for t in transcript_list:
                    selected_transcript = t
                    break

            if selected_transcript:
                fetched = selected_transcript.fetch()
                parts = []
                for item in fetched:
                    val = item.text if hasattr(item, "text") else item.get("text", "")
                    if val:
                        parts.append(val.strip())
                raw_text = " ".join(parts)
                cleaned = clean_transcript_text(raw_text)
                if cleaned and len(cleaned) > 40:
                    return cleaned, selected_transcript.language_code
        except Exception:
            pass

    # 2. Fallback Method (yt-dlp subtitles only)
    tmp_dir = os.path.join(SYSTEM_TEMP, f"yt_{video_id}_{os.getpid()}")
    os.makedirs(tmp_dir, exist_ok=True)
    try:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,       # No audio/video downloaded; zero bandwidth waste
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": langs_list + ["all"],
            "subtitlesformat": "vtt/srt/best",
            "outtmpl": os.path.join(tmp_dir, "%(id)s.%(ext)s"),
            "ignoreerrors": True,
            "retries": 1,
            "socket_timeout": 12,
            "extractor_args": {"youtube": {"player_client": ["android", "ios", "mweb"]}}, # Anti-bot bypass
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

        subs = glob.glob(os.path.join(tmp_dir, "*.vtt")) + glob.glob(os.path.join(tmp_dir, "*.srt"))
        if subs:
            # Prefer Bangla or English subtitles if present
            preferred_subs = [s for s in subs if any(l in os.path.basename(s).lower() for l in ["bn", "en"])]
            chosen = preferred_subs[0] if preferred_subs else subs[0]
            text = clean_transcript_text(vtt_to_text(chosen))
            if text and len(text) > 40:
                return text, "auto"
    except Exception:
        pass
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return None, None


def get_channel_videos(channel_url: str, max_videos: Optional[int] = None) -> Tuple[List[Dict[str, str]], str]:
    """Fetch channel or playlist video metadata list (fast flat extraction, no downloads)."""
    print(f"[*] Fetching playlist metadata from: {channel_url}", flush=True)
    opts = {
        "extract_flat": True,
        "quiet": True,
        "skip_download": True,
        "ignoreerrors": True,
    }
    if max_videos:
        opts["playlistend"] = max_videos

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)
        entries = info.get("entries", []) if info else []
        videos = []
        for e in entries:
            if e and e.get("id"):
                videos.append({
                    "id": e.get("id"),
                    "title": e.get("title", "untitled"),
                    "date": e.get("upload_date", "00000000")
                })
        channel_name = (info.get("channel") or info.get("uploader") or info.get("title") or "custom_channel") if info else "custom_channel"
        return videos, channel_name


def process_channel(
    channel_url: str, 
    channel_slug: Optional[str] = None, 
    max_videos: Optional[int] = None, 
    langs: str = "bn,bn-BD,en,en-US,en-GB",
    delay_seconds: float = 1.5
) -> None:
    """Process an entire YouTube channel with incremental deduplication, manifest tracking, and auto-resume."""
    videos, ch_name = get_channel_videos(channel_url, max_videos=max_videos)
    cslug = channel_slug or clean_slug(ch_name)
    out_dir = os.path.join(BASE_DIR, cslug)
    os.makedirs(out_dir, exist_ok=True)

    done_flag = os.path.join(out_dir, ".channel_done")
    manifest_file = os.path.join(out_dir, "manifest.json")

    if os.path.exists(done_flag):
        print(f"[SKIP] Channel '{cslug}' is already 100% completed & sealed.", flush=True)
        return

    manifest = {}
    if os.path.exists(manifest_file):
        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            manifest = {}

    # Check already existing text files in folder
    for tf in glob.glob(os.path.join(out_dir, "*.txt")):
        bn = os.path.basename(tf)
        parts = bn.split("_")
        for p in parts:
            if len(p) == 11 and re.match(r'^[a-zA-Z0-9_-]{11}$', p):
                manifest[p] = {"status": "ok"}

    pending = [v for v in videos if v["id"] not in manifest]
    print(f"[{cslug}] Total in Channel: {len(videos)} | Manifest/Done: {len(manifest)} | Pending: {len(pending)}", flush=True)

    if not pending:
        with open(done_flag, "w", encoding="utf-8") as df:
            json.dump({"slug": cslug, "total": len(videos), "channel": ch_name}, df, indent=2)
        print(f"[+] Channel '{cslug}' has no pending videos and is now sealed.", flush=True)
        return

    # Process pending videos
    for idx, v in enumerate(pending, 1):
        vid = v["id"]
        title = v["title"]
        date = v.get("date") or "00000000"
        fname = f"{date}_{vid}_{clean_slug(title)}.txt"
        dest_path = os.path.join(out_dir, fname)

        text, lang = fetch_official_transcript(vid, langs=langs)
        if text:
            header = (
                f"# Title: {title}\n"
                f"# Channel: {ch_name}\n"
                f"# Video ID: {vid}\n"
                f"# URL: https://www.youtube.com/watch?v={vid}\n"
                f"# Language: {lang}\n"
                f"# Date: {date}\n\n"
            )
            with open(dest_path, "w", encoding="utf-8") as fp:
                fp.write(header + text + "\n")
            manifest[vid] = {"status": "ok", "lang": lang, "chars": len(text)}
            print(f"  [{idx}/{len(pending)}] [OK] {vid} ({len(text):,} chars, lang={lang}) | {title[:45]}", flush=True)
        else:
            manifest[vid] = {"status": "no_captions"}
            print(f"  [{idx}/{len(pending)}] [NO_CAPTIONS] {vid} | {title[:45]}", flush=True)

        # Save manifest on every item to protect against power cut
        with open(manifest_file, "w", encoding="utf-8") as mf:
            json.dump(manifest, mf, indent=2, ensure_ascii=False)

        # Gentle pause to avoid rate limiting
        time.sleep(delay_seconds)

    # Final seal if all items in playlist were processed
    if len(manifest) >= len(videos):
        with open(done_flag, "w", encoding="utf-8") as df:
            json.dump({"slug": cslug, "total": len(videos), "channel": ch_name}, df, indent=2)
        print(f"[SUCCESS] Channel '{cslug}' is fully completed and sealed.", flush=True)
    else:
        print(f"[INFO] Batch finished. Manifest updated ({len(manifest)}/{len(videos)} items).", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Turbo YouTube Transcript Harvester (Zero-Heat & Ultra-Fast)")
    parser.add_argument("--channel", type=str, default="https://www.youtube.com/@JUSTINFOBD/videos", help="YouTube Channel or Playlist URL")
    parser.add_argument("--slug", type=str, default="justinfobd", help="Custom folder slug under transcripts/")
    parser.add_argument("--max-videos", type=int, default=None, help="Max videos to inspect from the playlist")
    parser.add_argument("--langs", type=str, default="bn,bn-BD,en,en-US,en-GB", help="Comma-separated preferred languages")
    parser.add_argument("--delay", type=float, default=1.5, help="Delay in seconds between videos")

    args = parser.parse_args()
    process_channel(
        channel_url=args.channel,
        channel_slug=args.slug,
        max_videos=args.max_videos,
        langs=args.langs,
        delay_seconds=args.delay
    )
