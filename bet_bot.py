import logging
import re
from curl_cffi import requests as c_requests
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = "8693283887:AAEgxhqF0EBnPYN_ROKfctF_arobToFiqP0"
ODDS_API_KEY = "c45b04a276247f9decdfdc24d6fb0056"  # The Odds API key'inizi yazın

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# --- TÜRKÇE İSİM SÖZLÜĞÜ ---
TEAM_NAME_MAP = {
    "galatasaray sk": "Galatasaray",
    "fenerbahce": "Fenerbahçe",
    "besiktas": "Beşiktaş",
    "trabzonspor": "Trabzonspor",
    "basaksehir": "Başakşehir",
    "bayern munich": "Bayern Münih",
    "inter milan": "Inter",
    "ac milan": "Milan",
    "real madrid": "Real Madrid",
    "barcelona": "Barcelona",
    "atletico madrid": "Atlético Madrid",
    "manchester city": "Manchester City",
    "manchester united": "Manchester United",
    "liverpool": "Liverpool",
    "arsenal": "Arsenal",
    "chelsea": "Chelsea",
    "tottenham hotspur": "Tottenham",
    "paris saint germain": "PSG",
    "psg": "PSG",
    "juventus": "Juventus",
    "borussia dortmund": "B. Dortmund",
    "sporting cp": "Sporting CP",
    "benfica": "Benfica",
}

def normalize_text(text: str) -> str:
    text = text.lower()
    replacements = {'ç': 'c', 'ğ': 'g', 'ı': 'i', 'i': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u'}
    for search, replace in replacements.items():
        text = text.replace(search, replace)
    return text

def clean_team_name(name: str) -> str:
    norm = normalize_text(name)
    for key, value in TEAM_NAME_MAP.items():
        if key in norm:
            return value
    cleaned = re.sub(r'\b(FC|SK|CF|BSC|SV|FK|AS|SE)\b', '', name, flags=re.IGNORECASE).strip()
    return cleaned if cleaned else name

# --- 1. HAFTALIK BÜLTEN ÇEKİCİ ---
def get_global_data():
    url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h,totals"
    try:
        res = requests.get(url, timeout=12)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print(f"Global API Hatası: {e}")
    return []

# --- 2. ALGORİTMİK TAHMİN MOTORU ---
def generate_match_analysis(home_team, away_team, ms1, msX, ms2):
    p1 = (1 / ms1) if ms1 > 0 else 0.33
    pX = (1 / msX) if msX > 0 else 0.33
    p2 = (1 / ms2) if ms2 > 0 else 0.33
    total_p = p1 + pX + p2
    
    p1_pct = int((p1 / total_p) * 100)
    pX_pct = int((pX / total_p) * 100)
    p2_pct = 100 - (p1_pct + pX_pct)
    
    over_pct = 72 if (ms1 < 1.90 or ms2 < 1.90) else 54
    kg_var_pct = 78 if (ms1 < 2.10 and ms2 < 2.50) else 48
    
    if p1_pct > 60:
        ana_tahmin = "MS 1"
        tercih_oran = ms1
        surpriz = "İY 0 / MS 1"
    elif p2_pct > 60:
        ana_tahmin = "MS 2"
        tercih_oran = ms2
        surpriz = "İY 0 / MS 2"
    else:
        ana_tahmin = "2.5 ÜST"
        tercih_oran = 1.65
        surpriz = "MS X (Beraberlik)"

    return {
        "p1_pct": p1_pct, "pX_pct": pX_pct, "p2_pct": p2_pct,
        "over_pct": over_pct, "kg_var_pct": kg_var_pct,
        "ana_tahmin": ana_tahmin, "tercih_oran": tercih_oran, "surpriz": surpriz
    }

# --- TELEGRAM BOT KOMUTLARI ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🔥 *BetAnaliz - Yapay Zeka Kupon Oluşturucu Aktif!*\n\n"
        "Komutlar:\n"
        "👉 /kupon - Yapay zekanın seçtiği günün banko ve sürpriz kuponları\n"
        "👉 /populer - Günün ve haftanın öne çıkan maçları\n"
        "👉 /analiz [Takım Adı] - Detaylı Türkçe maç analizi\n\n"
        "Örnek: `/kupon` veya `/analiz Galatasaray`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def kupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Yapay zeka bültendeki tüm maçları tarıyor ve en ideal kuponları hazırlıyor...", parse_mode="Markdown")
    
    matches = get_global_data()
    if not matches:
        await update.message.reply_text("⚠️ Bültenden veri alınamadı. API Key'inizi kontrol edin.")
        return

    banko_maclar = []
    surpriz_maclar = []

    for match in matches:
        home_raw = match.get("home_team", "")
        away_raw = match.get("away_team", "")
        match_date = match.get("commence_time", "")[:10]
        
        home = clean_team_name(home_raw)
        away = clean_team_name(away_raw)
        
        bms = match.get("bookmakers", [])
        if not bms:
            continue
            
        bm = bms[0]
        markets = bm.get("markets", [])
        
        ms1, msX, ms2 = 0, 0, 0
        for m in markets:
            if m.get("key") == "h2h":
                for o in m.get("outcomes", []):
                    if o.get("name") == home_raw: ms1 = o.get("price", 1.0)
                    elif o.get("name") == away_raw: ms2 = o.get("price", 1.0)
                    else: msX = o.get("price", 1.0)
        
        if ms1 == 0 or ms2 == 0:
            continue
            
        analysis = generate_match_analysis(home, away, ms1, msX, ms2)
        
        # Banko seçim criteria: ev sahibi veya deplasman favori (%60+ olasılık)
        if (analysis["p1_pct"] >= 58 or analysis["p2_pct"] >= 58) and len(banko_maclar) < 3:
            banko_maclar.append({
                "match": f"{home} - {away}",
                "date": match_date,
                "tahmin": analysis["ana_tahmin"],
                "oran": analysis["tercih_oran"]
            })
        # Sürpriz/dengeli seçim criteria
        elif 30 <= analysis["p1_pct"] <= 45 and len(surpriz_maclar) < 3:
            surpriz_maclar.append({
                "match": f"{home} - {away}",
                "date": match_date,
                "tahmin": analysis["surpriz"],
                "oran": msX if "Beraberlik" in analysis["surpriz"] else (ms1 if "1" in analysis["surpriz"] else ms2)
            })

    rapor = "🎫 *YAPAY ZEKA GÜNÜN KUPONLARI*\n\n"
    
    # 1. BANKO KUPON
    if banko_maclar:
        rapor += "🎯 *GÜNÜN BANKO KUPONU*\n"
        toplam_oran_banko = 1.0
        for i, item in enumerate(banko_maclar, 1):
            toplam_oran_banko *= item["oran"]
            rapor += f"{i}. ⚽ *{item['match']}* (`{item['date']}`)\n"
            rapor += f"   • Tahmin: `{item['tahmin']}` | Oran: `{item['oran']:.2f}`\n"
        rapor += f"🔥 *Toplam Oran:* `{toplam_oran_banko:.2f}`\n\n"
    else:
        rapor += "🎯 *BANKO KUPON:* Bülten uygun bulunamadı.\n\n"

    # 2. SÜRPRİZ KUPON
    if surpriz_maclar:
        rapor += "💣 *GÜNÜN SÜRPRİZ / SİSTEM KUPONU*\n"
        toplam_oran_surpriz = 1.0
        for i, item in enumerate(surpriz_maclar, 1):
            toplam_oran_surpriz *= (item["oran"] if item["oran"] > 0 else 2.50)
            oran_val = item["oran"] if item["oran"] > 0 else 2.50
            rapor += f"{i}. ⚽ *{item['match']}* (`{item['date']}`)\n"
            rapor += f"   • Tahmin: `{item['tahmin']}` | Oran: `{oran_val:.2f}`\n"
        rapor += f"💥 *Toplam Oran:* `{toplam_oran_surpriz:.2f}`\n"

    await update.message.reply_text(rapor, parse_mode="Markdown")

async def populer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Genişletilmiş bülten taranıyor...")
    matches = get_global_data()
    if not matches:
        await update.message.reply_text("⚠️ Bültenden veri alınamadı. API Key'inizi kontrol edin.")
        return

    rapor = "🔥 *GÜNÜN VE HAFTANIN ÖNE ÇIKAN MAÇLARI*\n\n"
    count = 0
    
    for match in matches[:8]:
        home_raw = match.get("home_team", "")
        away_raw = match.get("away_team", "")
        commence_time = match.get("commence_time", "")[:10]
        
        home = clean_team_name(home_raw)
        away = clean_team_name(away_raw)
        
        bms = match.get("bookmakers", [])
        if bms and home and away:
            count += 1
            bm = bms[0]
            markets = bm.get("markets", [])
            
            ms1, msX, ms2 = 0, 0, 0
            for m in markets:
                if m.get("key") == "h2h":
                    for o in m.get("outcomes", []):
                        if o.get("name") == home_raw: ms1 = o.get("price", 1.0)
                        elif o.get("name") == away_raw: ms2 = o.get("price", 1.0)
                        else: msX = o.get("price", 1.0)
            
            analysis = generate_match_analysis(home, away, ms1, msX, ms2)
            
            rapor += (
                f"{count}. ⚽ *{home} - {away}* 🗓 `{commence_time}`\n"
                f"   • *Oranlar:* MS 1: `{ms1}` | X: `{msX}` | MS 2: `{ms2}`\n"
                f"   • *Eğilim:* %{analysis['p1_pct']} MS1 - %{analysis['pX_pct']} X - %{analysis['p2_pct']} MS2\n"
                f"   • *Gol / KG:* %{analysis['over_pct']} 2.5 ÜST | %{analysis['kg_var_pct']} KG VAR\n"
                f"   • *Öneri:* {analysis['ana_tahmin']}\n\n"
            )

    await update.message.reply_text(rapor, parse_mode="Markdown")

async def analiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠ Lütfen bir takım adı girin.\nÖrnek: `/analiz Galatasaray`", parse_mode="Markdown")
        return
        
    raw_query = " ".join(context.args)
    norm_query = normalize_text(raw_query)
    
    await update.message.reply_text(f"🔍 *{raw_query.title()}* için haftalık bülten taranıyor...", parse_mode="Markdown")
    
    matches = get_global_data()
    found = False
    
    if matches:
        for match in matches:
            home_raw = match.get("home_team", "")
            away_raw = match.get("away_team", "")
            
            if norm_query in normalize_text(home_raw) or norm_query in normalize_text(away_raw):
                found = True
                home = clean_team_name(home_raw)
                away = clean_team_name(away_raw)
                match_date = match.get("commence_time", "")[:10]
                
                bm = match.get("bookmakers", [{}])[0]
                markets = bm.get("markets", [])
                
                ms1, msX, ms2 = 0, 0, 0
                for m in markets:
                    if m.get("key") == "h2h":
                        for o in m.get("outcomes", []):
                            if o.get("name") == home_raw: ms1 = o.get("price", 1.0)
                            elif o.get("name") == away_raw: ms2 = o.get("price", 1.0)
                            else: msX = o.get("price", 1.0)
                
                analysis = generate_match_analysis(home, away, ms1, msX, ms2)
                
                detay = (
                    f"🔍 *360° DETAYLI MAÇ ANALİZİ*\n"
                    f"⚔️️ *{home.upper()} vs {away.upper()}*\n"
                    f"🗓 *Maç Tarihi:* `{match_date}`\n\n"
                    f"📊 *TOPLULUK & ORAN DAĞILIMI*\n"
                    f"• *MS 1:* %{analysis['p1_pct']} (Oran: `{ms1}`)\n"
                    f"• *MS X:* %{analysis['pX_pct']} (Oran: `{msX}`)\n"
                    f"• *MS 2:* %{analysis['p2_pct']} (Oran: `{ms2}`)\n\n"
                    f"⚽ *GOL VE KARŞILIKLI GOL TAHMİNİ*\n"
                    f"• *2.5 ÜST Olasılığı:* %{analysis['over_pct']}\n"
                    f"• *KG VAR Olasılığı:* %{analysis['kg_var_pct']}\n\n"
                    f"🎯 *SİSTEM TAHMİNLERİ*\n"
                    f"• *Ana Tercih:* `{analysis['ana_tahmin']}`\n"
                    f"• *Sürpriz / İY-MS:* `{analysis['surpriz']}`\n"
                )
                await update.message.reply_text(detay, parse_mode="Markdown")
                break
                
    if not found:
        await update.message.reply_text(f"⚠️ *{raw_query.title()}* için önümüzdeki 7 gün içinde oranları açılmış resmi bir maç bulunamadı.", parse_mode="Markdown")

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("kupon", kupon))
    app.add_handler(CommandHandler("populer", populer))
    app.add_handler(CommandHandler("analiz", analiz))
    print("🤖 Kupon Oluşturucu Özellikli Bot Başlatıldı!")
    app.run_polling()