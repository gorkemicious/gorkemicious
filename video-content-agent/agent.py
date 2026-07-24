#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Content Agent — Reels Transkripsiyon ve İçerik Üretici
=============================================================
Instagram Reels (veya herhangi bir video URL'si) videosunu indirir,
ses kaydını çıkarır, konuşmayı metne döker ve Claude API ile
farklı platformlar için sosyal medya içerikleri üretir.

Kullanım:
    python3 agent.py VIDEO_URL
    python3 agent.py VIDEO_URL --tone samimi
    python3 agent.py VIDEO_URL --lang tr
    python3 agent.py VIDEO_URL --no-content          # sadece transkript
    python3 agent.py VIDEO_URL --out data             # çıktı klasörü

Bağımlılıklar:
    - yt-dlp          : video indirme (pip install yt-dlp)
    - ffmpeg          : ses çıkarma (sistem paketi)
    - openai-whisper  : yerel transkripsiyon (pip install openai-whisper)
      VEYA
      OPENAI_API_KEY  : OpenAI Whisper API ile transkripsiyon
    - anthropic       : içerik üretimi (pip install anthropic, ANTHROPIC_API_KEY gerekli)
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


# ─────────────────────────────────────────────────────────────────
# 1. Video İndirme
# ─────────────────────────────────────────────────────────────────

def download_video(url, output_dir):
    """yt-dlp ile videoyu indir, dosya yolunu döndür."""
    if not shutil.which("yt-dlp"):
        print("✗ yt-dlp bulunamadı. Kur: pip install yt-dlp", file=sys.stderr)
        sys.exit(1)

    output_template = os.path.join(output_dir, "video.%(ext)s")
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--format", "bestaudio[ext=m4a]/bestaudio/best",
        "--output", output_template,
        "--no-warnings",
        "--print", "after_move:filepath",
        url,
    ]
    print(f"📥 Video indiriliyor: {url}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        print(f"✗ İndirme hatası: {stderr}", file=sys.stderr)
        sys.exit(1)

    filepath = result.stdout.strip().split("\n")[-1]
    if not os.path.exists(filepath):
        candidates = list(Path(output_dir).glob("video.*"))
        if candidates:
            filepath = str(candidates[0])
        else:
            print("✗ İndirilen dosya bulunamadı.", file=sys.stderr)
            sys.exit(1)

    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    print(f"  ✓ İndirildi: {Path(filepath).name} ({size_mb:.1f} MB)")
    return filepath


def get_video_info(url):
    """yt-dlp ile video meta bilgilerini al."""
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--no-warnings",
        "--dump-json",
        "--no-download",
        url,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            info = json.loads(result.stdout)
            return {
                "title": info.get("title", ""),
                "description": info.get("description", ""),
                "duration": info.get("duration", 0),
                "uploader": info.get("uploader", ""),
                "platform": info.get("extractor_key", "").lower(),
                "view_count": info.get("view_count"),
                "like_count": info.get("like_count"),
                "upload_date": info.get("upload_date", ""),
            }
    except Exception:
        pass
    return {"title": "", "description": "", "duration": 0, "uploader": "", "platform": "unknown"}


# ─────────────────────────────────────────────────────────────────
# 2. Ses Çıkarma
# ─────────────────────────────────────────────────────────────────

def extract_audio(video_path, output_dir):
    """ffmpeg ile videodan ses çıkar (16kHz WAV — Whisper için ideal)."""
    if not shutil.which("ffmpeg"):
        print("✗ ffmpeg bulunamadı. Kur: sudo apt install ffmpeg", file=sys.stderr)
        sys.exit(1)

    audio_path = os.path.join(output_dir, "audio.wav")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        audio_path,
    ]
    print("🔊 Ses çıkarılıyor…")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"✗ ffmpeg hatası: {result.stderr[-300:]}", file=sys.stderr)
        sys.exit(1)

    print(f"  ✓ Ses dosyası: audio.wav")
    return audio_path


# ─────────────────────────────────────────────────────────────────
# 3. Transkripsiyon
# ─────────────────────────────────────────────────────────────────

def transcribe_openai_api(audio_path, language=None):
    """OpenAI Whisper API ile transkripsiyon."""
    try:
        from openai import OpenAI
    except ImportError:
        return None

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    print("🎙️ Transkripsiyon: OpenAI Whisper API kullanılıyor…")
    client = OpenAI()

    with open(audio_path, "rb") as f:
        params = {"model": "whisper-1", "file": f, "response_format": "verbose_json"}
        if language:
            params["language"] = language
        response = client.audio.transcriptions.create(**params)

    segments = []
    if hasattr(response, "segments"):
        for seg in response.segments:
            segments.append({
                "start": round(seg["start"], 2),
                "end": round(seg["end"], 2),
                "text": seg["text"].strip(),
            })

    result = {
        "text": response.text,
        "language": getattr(response, "language", language or "unknown"),
        "segments": segments,
        "method": "openai-api",
    }
    print(f"  ✓ Transkript hazır ({len(result['text'])} karakter, dil: {result['language']})")
    return result


def transcribe_local_whisper(audio_path, language=None):
    """Yerel Whisper modeli ile transkripsiyon."""
    try:
        import whisper
    except ImportError:
        return None

    print("🎙️ Transkripsiyon: yerel Whisper modeli kullanılıyor…")
    model = whisper.load_model("base")
    options = {}
    if language:
        options["language"] = language

    result = model.transcribe(audio_path, **options)

    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "start": round(seg["start"], 2),
            "end": round(seg["end"], 2),
            "text": seg["text"].strip(),
        })

    out = {
        "text": result["text"].strip(),
        "language": result.get("language", language or "unknown"),
        "segments": segments,
        "method": "local-whisper",
    }
    print(f"  ✓ Transkript hazır ({len(out['text'])} karakter, dil: {out['language']})")
    return out


def transcribe_faster_whisper(audio_path, language=None):
    """faster-whisper ile transkripsiyon (CTranslate2 tabanlı, daha hafif)."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None

    print("🎙️ Transkripsiyon: faster-whisper kullanılıyor…")
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segs, info = model.transcribe(audio_path, language=language, beam_size=5)

    segments = []
    full_text_parts = []
    for seg in segs:
        segments.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        })
        full_text_parts.append(seg.text.strip())

    out = {
        "text": " ".join(full_text_parts),
        "language": info.language,
        "segments": segments,
        "method": "faster-whisper",
    }
    print(f"  ✓ Transkript hazır ({len(out['text'])} karakter, dil: {out['language']})")
    return out


def transcribe(audio_path, language=None):
    """Mevcut en iyi yöntemi seçerek transkripsiyon yap."""
    for fn in [transcribe_openai_api, transcribe_local_whisper, transcribe_faster_whisper]:
        result = fn(audio_path, language)
        if result:
            return result

    print("✗ Transkripsiyon yapılamadı. Şu seçeneklerden birini kur:", file=sys.stderr)
    print("  1) pip install openai  + OPENAI_API_KEY ortam değişkeni", file=sys.stderr)
    print("  2) pip install openai-whisper", file=sys.stderr)
    print("  3) pip install faster-whisper", file=sys.stderr)
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────
# 4. Claude ile İçerik Üretimi
# ─────────────────────────────────────────────────────────────────

CONTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "instagram": {
            "type": "object",
            "properties": {
                "caption": {"type": "string"},
                "hashtags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["caption", "hashtags"],
            "additionalProperties": False,
        },
        "twitter": {
            "type": "object",
            "properties": {
                "thread": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["thread"],
            "additionalProperties": False,
        },
        "linkedin": {
            "type": "object",
            "properties": {
                "post": {"type": "string"},
            },
            "required": ["post"],
            "additionalProperties": False,
        },
        "blog": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["title", "summary", "body"],
            "additionalProperties": False,
        },
        "key_points": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["instagram", "twitter", "linkedin", "blog", "key_points"],
    "additionalProperties": False,
}

TONE_MAP = {
    "samimi": "samimi, sıcak ve arkadaşça bir dil kullan; emoji kullanabilirsin",
    "profesyonel": "profesyonel, ciddi ve kurumsal bir dil kullan; jargondan kaçın",
    "egitici": "eğitici, öğretici ve bilgilendirici bir dil kullan; karmaşık konuları basitleştir",
    "eglenceli": "eğlenceli, enerjik ve dinamik bir dil kullan; espri ve pop kültür referansları ekleyebilirsin",
    "ilham": "ilham verici, motive edici ve güçlendirici bir dil kullan",
}


def generate_content(transcription, video_info, tone="samimi", model="claude-sonnet-4-20250514"):
    """Claude API ile transkriptten sosyal medya içerikleri üret."""
    try:
        import anthropic
    except ImportError:
        print("  ℹ İçerik üretimi atlandı: pip install anthropic", file=sys.stderr)
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  ℹ İçerik üretimi atlandı: ANTHROPIC_API_KEY ortam değişkeni gerekli", file=sys.stderr)
        return None

    tone_desc = TONE_MAP.get(tone, TONE_MAP["samimi"])
    video_ctx = ""
    if video_info.get("title"):
        video_ctx += f"\nVideo başlığı: {video_info['title']}"
    if video_info.get("description"):
        video_ctx += f"\nVideo açıklaması: {video_info['description'][:500]}"
    if video_info.get("uploader"):
        video_ctx += f"\nYükleyen: {video_info['uploader']}"

    client = anthropic.Anthropic()
    print("✨ İçerik üretiliyor (Claude)…")

    try:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=(
                "Sen deneyimli bir sosyal medya içerik üreticisisin. Sana bir video transkripsiyonu "
                "verilecek. Bu transkripsiyondan farklı platformlar için özgün, ilgi çekici içerikler "
                "üreteceksin.\n\n"
                "Kurallar:\n"
                f"- Ton: {tone_desc}\n"
                "- Instagram: 2200 karakter limiti, etkili bir caption yaz, ilgili hashtag'ler öner\n"
                "- Twitter/X: her tweet max 280 karakter, anlamlı bir thread oluştur (3-7 tweet)\n"
                "- LinkedIn: profesyonel ama okunabilir, 1300 karakter civarı\n"
                "- Blog: SEO uyumlu başlık, kısa özet ve detaylı blog yazısı\n"
                "- Key points: videonun ana mesajlarını 3-7 madde halinde özetle\n"
                "- Tüm içerikler Türkçe olmalı\n"
                "- Transkriptteki bilgileri kendi cümlelerinle yeniden ifade et, birebir kopyalama"
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"Aşağıdaki video transkripsiyonundan sosyal medya içerikleri üret:\n\n"
                    f"--- TRANSKRİPSİYON ---\n{transcription['text']}\n--- TRANSKRİPSİYON SONU ---"
                    f"{video_ctx}"
                ),
            }],
            output_config={"format": {"type": "json_schema", "schema": CONTENT_SCHEMA}},
        )

        if response.stop_reason == "refusal":
            print("  ✗ Claude içerik üretmeyi reddetti.", file=sys.stderr)
            return None

        text = next(b.text for b in response.content if b.type == "text")
        content = json.loads(text)
        content["tone"] = tone

        tweet_count = len(content.get("twitter", {}).get("thread", []))
        point_count = len(content.get("key_points", []))
        print(f"  ✓ İçerik hazır: Instagram caption, {tweet_count} tweet, LinkedIn post, blog yazısı, {point_count} anahtar nokta")
        return content

    except Exception as e:
        print(f"  ✗ İçerik üretim hatası ({type(e).__name__}): {e}", file=sys.stderr)
        return None


# ─────────────────────────────────────────────────────────────────
# 5. Çıktı
# ─────────────────────────────────────────────────────────────────

def save_output(payload, out_dir):
    """Sonuçları JSON ve JS dosyalarına yaz."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / "content.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    js = (
        "// Bu dosya agent.py tarafından otomatik üretilir — elle düzenleme.\n"
        "window.VIDEO_CONTENT = "
        + json.dumps(payload, ensure_ascii=False)
        + ";\n"
    )
    (out / "content.js").write_text(js, encoding="utf-8")

    print(f"\n💾 Çıktı kaydedildi → {json_path}")


# ─────────────────────────────────────────────────────────────────
# Ana Akış
# ─────────────────────────────────────────────────────────────────

def run(url, language=None, tone="samimi", generate=True,
        model="claude-sonnet-4-20250514", out_dir=None):
    now = datetime.now(timezone.utc)
    if out_dir is None:
        out_dir = str(SCRIPT_DIR / "data")

    print(f"🎬 Video Content Agent başlatılıyor")
    print(f"   URL: {url}\n")

    video_info = get_video_info(url)

    with tempfile.TemporaryDirectory(prefix="vcagent_") as tmp:
        video_path = download_video(url, tmp)
        audio_path = extract_audio(video_path, tmp)
        transcription = transcribe(audio_path, language)

    content = None
    if generate:
        content = generate_content(transcription, video_info, tone=tone, model=model)

    payload = {
        "generated_at": now.isoformat(),
        "video": {
            "url": url,
            **video_info,
        },
        "transcription": {
            "text": transcription["text"],
            "language": transcription["language"],
            "segments": transcription["segments"],
            "method": transcription["method"],
        },
    }
    if content:
        payload["content"] = content

    save_output(payload, out_dir)

    print(f"\n✅ Tamamlandı!")
    print(f"   Transkript: {len(transcription['text'])} karakter")
    if content:
        print(f"   İçerik: 4 platform + anahtar noktalar")
    print(f"   Dashboard: index.html'i tarayıcıda aç.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Video Content Agent — Reels Transkripsiyon ve İçerik Üretici")
    ap.add_argument("url", help="Video URL'si (Instagram Reels, YouTube, TikTok, vb.)")
    ap.add_argument("--lang", default=None, help="Video dili (tr, en, vb.) — boş bırakılırsa otomatik algılanır")
    ap.add_argument("--tone", default="samimi", choices=list(TONE_MAP.keys()),
                    help="İçerik tonu (varsayılan: samimi)")
    ap.add_argument("--no-content", action="store_true", help="Sadece transkript yap, içerik üretme")
    ap.add_argument("--model", default="claude-sonnet-4-20250514",
                    help="Claude modeli (varsayılan: claude-sonnet-4-20250514)")
    ap.add_argument("--out", default=None, help="Çıktı klasörü (varsayılan: data/)")
    args = ap.parse_args()
    run(args.url, language=args.lang, tone=args.tone, generate=not args.no_content,
        model=args.model, out_dir=args.out)
