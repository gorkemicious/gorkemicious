from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

wb = Workbook()

# ─── Yardımcı fonksiyonlar ────────────────────────────────────────────────────
HEADER_FILL = PatternFill("solid", fgColor="1F2937")
ROW_FILL_A  = PatternFill("solid", fgColor="111827")
ROW_FILL_B  = PatternFill("solid", fgColor="1C2531")
HEADER_FONT = Font(bold=True, color="E5E7EB", name="Calibri", size=11)
DATA_FONT   = Font(color="D1D5DB", name="Calibri", size=11)
CENTER      = Alignment(horizontal="center", vertical="center")
LEFT        = Alignment(horizontal="left",   vertical="center")

thin = Side(border_style="thin", color="374151")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)

def style_sheet(ws, headers, rows, col_widths):
    ws.row_dimensions[1].height = 22
    for ci, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=ci, value=h)
        cell.fill   = HEADER_FILL
        cell.font   = HEADER_FONT
        cell.alignment = CENTER
        cell.border = BORDER

    for ri, row in enumerate(rows, 2):
        fill = ROW_FILL_A if ri % 2 == 0 else ROW_FILL_B
        ws.row_dimensions[ri].height = 18
        for ci, val in enumerate(row, 1):
            cell = ws.cell(row=ri, column=ci, value=val)
            cell.fill      = fill
            cell.font      = DATA_FONT
            cell.alignment = CENTER
            cell.border    = BORDER

    for ci, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(ci)].width = w

    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A2"

# ─── 1. KPI ──────────────────────────────────────────────────────────────────
ws_kpi = wb.active
ws_kpi.title = "KPI"
style_sheet(
    ws_kpi,
    headers=["Gösterge", "Değer", "Değişim", "Yön"],
    rows=[
        ["OEE",                "82.4%",  "+1.8%",  "up"],
        ["Üretim Verimliliği", "91.2%",  "+0.5%",  "up"],
        ["Kalite Oranı",       "98.7%",  "+0.2%",  "up"],
        ["Kullanılabilirlik",  "90.5%",  "-0.4%",  "down"],
        ["Toplam Downtime",    "108dk",  "-12dk",  "down"],
        ["Üretilen Parça",     "18,432", "+834",   "up"],
        ["Hedefe Ulaşma",      "96.1%",  "",       ""],
        ["Hata Sayısı",        "241",    "-18",    "down"],
    ],
    col_widths=[22, 14, 12, 8]
)

# ─── 2. Günlük Üretim ────────────────────────────────────────────────────────
ws_gun = wb.create_sheet("Gunluk_Uretim")
style_sheet(
    ws_gun,
    headers=["Gün", "Gerçek Üretim", "Hedef"],
    rows=[
        ["Pzt", 17840, 19175],
        ["Sal", 18120, 19175],
        ["Çar", 17590, 19175],
        ["Per", 18900, 19175],
        ["Cum", 18432, 19175],
        ["Cmt", 16200, 19175],
        ["Paz", 15800, 19175],
    ],
    col_widths=[10, 18, 12]
)

# ─── 3. OEE Bileşenleri ──────────────────────────────────────────────────────
ws_oee = wb.create_sheet("OEE_Bilesenleri")
style_sheet(
    ws_oee,
    headers=["Gösterge", "Bugün", "Hedef"],
    rows=[
        ["Kullanılabilirlik",   90.5, 95.0],
        ["Performans",          91.2, 95.0],
        ["Kalite",              98.7, 99.5],
        ["Güvenilirlik",        88.3, 93.0],
        ["Enerji Etkinliği",    85.0, 90.0],
    ],
    col_widths=[22, 10, 10]
)

# ─── 4. Kalite Dağılımı ──────────────────────────────────────────────────────
ws_kal = wb.create_sheet("Kalite")
style_sheet(
    ws_kal,
    headers=["Kategori", "Yüzde (%)"],
    rows=[
        ["1. Kalite",       95.2],
        ["Yeniden İşlem",    2.1],
        ["Hurda",            1.3],
        ["Beklemede",        1.4],
    ],
    col_widths=[20, 14]
)

# ─── 5. Downtime ─────────────────────────────────────────────────────────────
ws_dt = wb.create_sheet("Downtime")
style_sheet(
    ws_dt,
    headers=["Kategori", "Dakika"],
    rows=[
        ["Mekanik Arıza",    48],
        ["Setup / Ayar",     35],
        ["Malzeme Bekleme",  22],
        ["Elektrik Arıza",   18],
        ["Planlı Bakım",     15],
        ["Diğer",             8],
    ],
    col_widths=[22, 12]
)

# ─── 6. OEE Trend (24 veri noktası) ─────────────────────────────────────────
ws_trend = wb.create_sheet("OEE_Trend")
trend_data = [
    ("H1",79),("H2",81),("H3",80),("H4",82),("H5",78),("H6",83),
    ("H7",84),("H8",82),("H9",81),("H10",83),("H11",85),("H12",84),
    ("H13",82),("H14",83),("H15",84),("H16",85),("H17",83),("H18",82),
    ("H19",84),("H20",83),("H21",82),("H22",84),("H23",83),("Şimdi",82.4),
]
style_sheet(
    ws_trend,
    headers=["Hafta", "OEE (%)", "Hedef (%)"],
    rows=[[h, v, 85] for h, v in trend_data],
    col_widths=[10, 12, 12]
)

# ─── 7. Vardiya ──────────────────────────────────────────────────────────────
ws_var = wb.create_sheet("Vardiya")
style_sheet(
    ws_var,
    headers=["Vardiya Adı", "OEE (%)", "Verimlilik (%)", "Üretim (adet)", "Downtime (dk)"],
    rows=[
        ["1. Vardiya", 84.1, 93.4, 6820, 28],
        ["2. Vardiya", 81.9, 89.6, 6241, 47],
        ["3. Vardiya", 80.7, 88.2, 5371, 33],
    ],
    col_widths=[18, 12, 18, 18, 16]
)

# ─── 8. Makineler ────────────────────────────────────────────────────────────
ws_mak = wb.create_sheet("Makineler")
style_sheet(
    ws_mak,
    headers=["Hat / Makine", "Durum", "OEE (%)", "Üretim (bugün)", "Hedef", "Verimlilik (%)", "Son Arıza"],
    rows=[
        ["Hat 1 — CNC Alpha",     "Çalışıyor",  87.3, 2840, 3000, 94.7, "3 gün önce"],
        ["Hat 2 — Press B",       "Çalışıyor",  83.1, 2610, 3000, 87.0, "1 gün önce"],
        ["Hat 3 — Kaynak Robotu", "Bekleme",    61.4, 1920, 3000, 64.0, "Bugün 09:14"],
        ["Hat 4 — Montaj A",      "Çalışıyor",  90.2, 2950, 3000, 98.3, "5 gün önce"],
        ["Hat 5 — Boya Hattı",    "Bakım",      "",    890, 3000, 29.7, "Bugün 06:30"],
        ["Hat 6 — Paketleme",     "Çalışıyor",  85.8, 2740, 3000, 91.3, "2 gün önce"],
        ["Hat 7 — Kalite Kontrol","Çalışıyor",  92.6, 3000, 3000, 100,  "7 gün önce"],
        ["Hat 8 — CNC Beta",      "Durduruldu", 0,     482, 3000, 16.1, "Bugün 04:55"],
    ],
    col_widths=[26, 14, 12, 18, 10, 18, 16]
)

# ─── Kaydet ──────────────────────────────────────────────────────────────────
out = "/home/user/gorkemicious/uretim_kpi_template.xlsx"
wb.save(out)
print(f"Kaydedildi: {out}")
