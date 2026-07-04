#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI PULSE — Yapay Zekâ Gündem Ajanı
===================================
Son 24 saat ve son 7 günün yapay zekâ / teknoloji gelişmelerini
RSS kaynaklarından, Hacker News'ten ve arXiv'den toplar; puanlar,
kategorilere ayırır ve dashboard'un okuduğu `data/news.js` +
`data/news.json` dosyalarını üretir.

Kullanım:
    python3 agent.py                  # tüm kaynakları tara, data/ altına yaz
    python3 agent.py --days 7         # kaç günlük pencere taransın (varsayılan 7)
    python3 agent.py --limit 80       # toplam kaç haber saklansın
    python3 agent.py --out data       # çıktı klasörü

Bağımlılık: sadece `requests` (yoksa stdlib urllib'e düşer).
"""

import argparse
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

try:
    import requests

    def http_get(url, timeout=15):
        r = requests.get(url, timeout=timeout, headers={"User-Agent": UA})
        r.raise_for_status()
        return r.content
except ImportError:  # requests yoksa stdlib ile devam et
    from urllib.request import Request, urlopen

    def http_get(url, timeout=15):
        req = Request(url, headers={"User-Agent": UA})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read()

UA = "Mozilla/5.0 (compatible; AIPulseAgent/1.0; +https://github.com/gorkemicious)"

# ─────────────────────────────────────────────────────────────────
# Kaynaklar: (isim, url, kaynak ağırlığı 0-1, dil)
# İstediğin kaynağı ekle/çıkar — RSS ya da Atom olması yeterli.
# ─────────────────────────────────────────────────────────────────
FEEDS = [
    ("TechCrunch AI",      "https://techcrunch.com/category/artificial-intelligence/feed/", 0.95, "en"),
    ("The Verge AI",       "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", 0.92, "en"),
    ("VentureBeat AI",     "https://venturebeat.com/category/ai/feed/",                     0.88, "en"),
    ("MIT Tech Review",    "https://www.technologyreview.com/feed/",                        0.90, "en"),
    ("Ars Technica",       "https://feeds.arstechnica.com/arstechnica/index",               0.85, "en"),
    ("Wired AI",           "https://www.wired.com/feed/tag/ai/latest/rss",                  0.85, "en"),
    ("The Decoder",        "https://the-decoder.com/feed/",                                 0.80, "en"),
    ("OpenAI Blog",        "https://openai.com/news/rss.xml",                               1.00, "en"),
    ("Google AI Blog",     "https://blog.google/technology/ai/rss/",                        0.95, "en"),
    ("Hugging Face",       "https://huggingface.co/blog/feed.xml",                          0.85, "en"),
    ("arXiv cs.AI",        "https://rss.arxiv.org/rss/cs.AI",                               0.55, "en"),
    ("Webrazzi",           "https://webrazzi.com/feed",                                     0.80, "tr"),
    ("Google News (TR)",   "https://news.google.com/rss/search?q=yapay+zeka&hl=tr&gl=TR&ceid=TR:tr", 0.70, "tr"),
]

HN_API = "https://hn.algolia.com/api/v1/search_by_date?tags=story&query={q}&numericFilters=created_at_i>{ts}&hitsPerPage=30"
HN_QUERIES = ["AI", "LLM", "OpenAI", "Anthropic", "GPT"]

# ─────────────────────────────────────────────────────────────────
# Kategoriler ve puanlama anahtar kelimeleri
# ─────────────────────────────────────────────────────────────────
CATEGORIES = {
    "modeller": ["gpt", "claude", "gemini", "llama", "grok", "mistral", "model", "sonnet", "opus", "fable",
                 "release", "launch", "benchmark", "reasoning", "multimodal", "chatbot", "sürüm"],
    "sirketler": ["openai", "anthropic", "google", "meta", "microsoft", "apple", "amazon", "xai", "nvidia",
                  "funding", "raise", "valuation", "acquisition", "ipo", "layoff", "yatırım", "satın al"],
    "arastirma": ["arxiv", "paper", "research", "study", "breakthrough", "discover", "science", "biology",
                  "protein", "mathematics", "araştırma", "bilim"],
    "donanim": ["chip", "gpu", "semiconductor", "datacenter", "data center", "nvidia", "tpu", "inference",
                "compute", "cerebras", "çip", "işlemci", "veri merkezi"],
    "politika": ["regulation", "policy", "law", "act", "government", "executive order", "eu", "un ",
                 "governance", "export", "ban", "yasa", "düzenleme", "hükümet"],
    "turkiye": ["türkiye", "turkey", "turkish", "tübitak", "istanbul", "ankara", "türkçe", "yerli"],
}

HOT_KEYWORDS = {
    "launch": 3, "release": 3, "announce": 2.5, "unveil": 2.5, "breakthrough": 3,
    "billion": 2, "record": 2, "first": 1.5, "open source": 2, "open-source": 2,
    "agi": 2, "agent": 1.5, "acquisition": 2, "funding": 1.5, "banned": 2, "lawsuit": 1.5,
    "gpt": 1.5, "claude": 1.5, "gemini": 1.5, "grok": 1.2, "deepseek": 1.5,
    "duyurdu": 2.5, "tanıttı": 2.5, "rekor": 2, "yerli": 1.5, "açık kaynak": 2,
}

TAG = re.compile(r"<[^>]+>")


def clean(text):
    """HTML etiketlerini ve fazlalıkları temizle."""
    if not text:
        return ""
    text = html.unescape(TAG.sub(" ", text))
    return re.sub(r"\s+", " ", text).strip()


def parse_date(value):
    """RSS (RFC822) ve Atom (ISO8601) tarihlerini UTC'ye çevir."""
    if not value:
        return None
    value = value.strip()
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def first_text(el, paths):
    for p in paths:
        node = el.find(p)
        if node is not None:
            if p.endswith("link") and node.text is None:  # Atom: <link href=...>
                href = node.get("href")
                if href:
                    return href
            if node.text:
                return node.text
    return None


def parse_feed(name, url, weight, lang):
    """Tek bir RSS/Atom kaynağını çek ve öğe listesi döndür."""
    raw = http_get(url)
    # Namespace'leri sadeleştir ki RSS ve Atom'u tek kodla gezelim
    raw = re.sub(rb'xmlns="[^"]+"', b"", raw, count=1)
    root = ET.fromstring(raw)
    ns = {"dc": "http://purl.org/dc/elements/1.1/",
          "content": "http://purl.org/rss/1.0/modules/content/"}
    items = []
    for item in root.iter("item"):  # RSS
        items.append({
            "title": clean(first_text(item, ["title"])),
            "link": (first_text(item, ["link"]) or "").strip(),
            "summary": clean(first_text(item, ["description", "content:encoded"]))[:400],
            "published": parse_date(first_text(item, ["pubDate", "dc:date"])),
        })
    for entry in root.iter("entry"):  # Atom
        items.append({
            "title": clean(first_text(entry, ["title"])),
            "link": (first_text(entry, ["link"]) or "").strip(),
            "summary": clean(first_text(entry, ["summary", "content"]))[:400],
            "published": parse_date(first_text(entry, ["published", "updated"])),
        })
    for it in items:
        it["source"] = name
        it["source_weight"] = weight
        it["lang"] = lang
    return [it for it in items if it["title"] and it["link"] and it["published"]]


def fetch_hackernews(since):
    """Hacker News'ten AI ile ilgili popüler hikâyeleri topla."""
    out, seen = [], set()
    ts = int(since.timestamp())
    for q in HN_QUERIES:
        try:
            data = json.loads(http_get(HN_API.format(q=q, ts=ts)))
        except Exception:
            continue
        for hit in data.get("hits", []):
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit['objectID']}"
            if url in seen or (hit.get("points") or 0) < 30:
                continue
            seen.add(url)
            out.append({
                "title": clean(hit.get("title")),
                "link": url,
                "summary": f"Hacker News'te {hit.get('points', 0)} puan, {hit.get('num_comments', 0)} yorum aldı.",
                "published": datetime.fromtimestamp(hit["created_at_i"], tz=timezone.utc),
                "source": "Hacker News",
                "source_weight": 0.75,
                "lang": "en",
                "hn_points": hit.get("points", 0),
            })
    return out


def categorize(item):
    text = f"{item['title']} {item['summary']}".lower()
    best, best_hits = "genel", 0
    for cat, words in CATEGORIES.items():
        hits = sum(1 for w in words if w in text)
        if hits > best_hits:
            best, best_hits = cat, hits
    # Türkiye kategorisi tek eşleşmeyle bile kazansın
    if any(w in text for w in CATEGORIES["turkiye"]):
        best = "turkiye"
    return best


def score(item, now):
    """0-100 arası 'sıcaklık' puanı: tazelik + kaynak + anahtar kelime."""
    age_h = max(0.0, (now - item["published"]).total_seconds() / 3600)
    recency = 40 * (0.5 ** (age_h / 24))            # her 24 saatte yarıya iner
    source = 25 * item["source_weight"]
    text = f"{item['title']} {item['summary']}".lower()
    keywords = min(25, sum(v * 2.2 for k, v in HOT_KEYWORDS.items() if k in text))
    social = min(10, item.get("hn_points", 0) / 40)
    return round(min(100, recency + source + keywords + social))


def dedupe(items):
    """Aynı haberin farklı kaynaklardaki kopyalarını ele."""
    seen, out = {}, []
    for it in sorted(items, key=lambda x: -x["score"]):
        key = re.sub(r"[^a-z0-9ğüşıöç]+", "", it["title"].lower())[:60]
        if key in seen:
            continue
        seen[key] = True
        out.append(it)
    return out


def run(days, limit, out_dir):
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    collected, errors = [], []

    print(f"⚡ AI PULSE ajanı çalışıyor — pencere: son {days} gün, {len(FEEDS)} RSS kaynağı + Hacker News")

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(parse_feed, n, u, w, l): n for n, u, w, l in FEEDS}
        futures[pool.submit(fetch_hackernews, since)] = "Hacker News"
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                items = fut.result()
                fresh = [it for it in items if it["published"] >= since]
                collected += fresh
                print(f"  ✓ {name}: {len(fresh)} haber")
            except Exception as e:
                errors.append(name)
                print(f"  ✗ {name}: {type(e).__name__}: {e}", file=sys.stderr)

    for it in collected:
        it["category"] = categorize(it)
        it["score"] = score(it, now)

    collected = dedupe(collected)
    collected.sort(key=lambda x: (-x["score"], x["published"]), reverse=False)
    collected = collected[:limit]

    payload = {
        "generated_at": now.isoformat(),
        "window_days": days,
        "source_count": len(FEEDS) + 1 - len(errors),
        "failed_sources": errors,
        "items": [{
            "title": it["title"],
            "link": it["link"],
            "summary": it["summary"],
            "source": it["source"],
            "published": it["published"].isoformat(),
            "category": it["category"],
            "score": it["score"],
            "lang": it["lang"],
        } for it in collected],
    }

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "news.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    js = "// Bu dosya agent.py tarafından otomatik üretilir — elle düzenleme.\nwindow.NEWS_DATA = " \
         + json.dumps(payload, ensure_ascii=False) + ";\n"
    (out / "news.js").write_text(js, encoding="utf-8")

    last24 = sum(1 for it in collected if (now - datetime.fromisoformat(it["published"].isoformat())).total_seconds() < 86400)
    print(f"\n✅ {len(collected)} haber yazıldı → {out/'news.js'}  (son 24 saat: {last24})")
    print("   Dashboard'u görmek için index.html'i tarayıcıda aç.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="AI PULSE — Yapay Zekâ Gündem Ajanı")
    ap.add_argument("--days", type=int, default=7, help="Kaç günlük haber toplansın (varsayılan 7)")
    ap.add_argument("--limit", type=int, default=80, help="Saklanacak maksimum haber sayısı")
    ap.add_argument("--out", default=str(Path(__file__).parent / "data"), help="Çıktı klasörü")
    args = ap.parse_args()
    run(args.days, args.limit, args.out)
