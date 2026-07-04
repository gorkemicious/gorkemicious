# ⚡ AI PULSE — Yapay Zekâ Gündem Ajanı

Son **24 saat** ve son **7 günün** yapay zekâ / teknoloji gelişmelerini otomatik toplayan,
puanlayan ve şık bir arayüzle sunan ajan. Instagram ve YouTube'da paylaşmaya hazır
görseller üreten **Paylaşım Stüdyosu** dahildir.

## Neler yapar?

- 📡 **13+ kaynağı tarar**: TechCrunch, The Verge, VentureBeat, MIT Tech Review, Wired,
  OpenAI, Google AI, Hugging Face, arXiv, Hacker News, Webrazzi, Google News (TR)…
- 🔥 **Sıcaklık puanı** hesaplar: tazelik + kaynak güvenilirliği + anahtar kelime + HN etkileşimi
- 🗂 **Kategorilere ayırır**: Modeller · Şirketler · Araştırma · Donanım · Politika · Türkiye
- 🧹 Aynı haberin kopyalarını eler
- 🎨 **Paylaşım Stüdyosu** ile tek tıkla PNG üretir:
  - Instagram Post (1080×1080)
  - Story / Reels (1080×1920)
  - YouTube Kapak (1280×720)
  - 3 tema: Neon Mor · Gece Mavisi · Alev

## Kurulum & kullanım

```bash
# 1) Haberleri topla (tek bağımlılık: requests — çoğu sistemde hazır)
python3 agent.py

# 2) Arayüzü aç
#    index.html'i tarayıcıda açman yeterli (sunucu gerekmez)
open index.html        # macOS
xdg-open index.html    # Linux
start index.html       # Windows
```

Ajan `data/news.js` ve `data/news.json` dosyalarını üretir; arayüz bunları okur.

### Seçenekler

```bash
python3 agent.py --days 7      # kaç günlük pencere taransın (varsayılan 7)
python3 agent.py --limit 80    # en fazla kaç haber saklansın
python3 agent.py --out data    # çıktı klasörü
```

### Otomatikleştirme (isteğe bağlı)

Her sabah 08:00'de otomatik güncellensin istersen (cron):

```
0 8 * * * cd /path/to/ai-news-agent && python3 agent.py
```

## Sosyal medya akışı

1. `python3 agent.py` → veriler tazelenir
2. `index.html` → **🎨 Paylaşım Stüdyosu** sekmesi
3. Format + tema + haber sayısını seç, kullanıcı adını yaz
4. **⬇ PNG İndir** → Instagram'a/YouTube'a yükle 🚀

Kullanıcı adın tarayıcıda hatırlanır (localStorage).

## Kaynak ekleme / çıkarma

`agent.py` içindeki `FEEDS` listesine herhangi bir RSS/Atom adresi ekleyebilirsin:

```python
FEEDS = [
    ("Kaynak Adı", "https://ornek.com/feed", 0.9, "tr"),
    ...
]
```

Üçüncü değer kaynak ağırlığıdır (0–1): puanlamada kaynağın güvenilirlik katkısı.
