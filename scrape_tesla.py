#!/usr/bin/env python3
"""
Tesla Model Y Gebrauchtwagen Scraper & Radar
============================================
Automatische Abfrage des offiziellen Tesla Gebrauchtwagen-Bestands.
Filtert nach Wunschkriterien:
  - Erstzulassung: 2023 - 2026
  - Nur Grünheide Modelle (VIN: XP7...) mit BYD Blade LFP Akku
  - Unfallfrei (ohne Reparaturschäden / Schadenoffenlegungen)
  - Max. Kilometer: 70.000 km
  - Max. Preis: 35.000 €
  - Inkl. Berechnung der Fahrzeit ab PLZ 49504 (Lotte)
  - Unterstützt Push-Benachrichtigungen via Telegram & GitHub Pages
"""

import argparse
import datetime
import json
import os
import sys
import urllib.request
import webbrowser
from pathlib import Path
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

BERLIN_TZ = ZoneInfo("Europe/Berlin")

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "tesla_history.json"
HTML_REPORT = BASE_DIR / "tesla_angebote.html"
INDEX_HTML = BASE_DIR / "index.html"
LATEST_JSON = BASE_DIR / "angebote_aktuell.json"

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    RESET = '\033[0m'


def fetch_tesla_inventory(zip_code="49504", model="my"):
    """
    Ruft alle verfügbaren Gebrauchtwagen über die offizielle Tesla Inventory API ab.
    Verwendet Playwright WebKit für zuverlässige Verbindung ohne Bot-Blockaden.
    """
    print(f"\n{Colors.CYAN}⏳ Rufe aktuelle Gebrauchtwagen von Tesla ab (PLZ {zip_code})...{Colors.RESET}")
    
    with sync_playwright() as p:
        browser = p.webkit.launch(headless=True)
        page = browser.new_page()
        
        # Initialer Seitenaufruf zur Session-Erstellung
        page.goto(f"https://www.tesla.com/de_DE/inventory/used/{model}?zip={zip_code}", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3000)
        
        # Paginiertes Abrufen aller Fahrzeuge im Bestand
        all_raw_cars = page.evaluate(f'''async () => {{
            let cars = [];
            let offset = 0;
            let outsideOffset = 0;
            for (let i = 0; i < 15; i++) {{
                try {{
                    const query = {{
                        "query": {{
                            "model": "{model}",
                            "condition": "used",
                            "options": {{}},
                            "arrangeby": "Price",
                            "order": "asc",
                            "market": "DE",
                            "language": "de",
                            "super_region": "europe",
                            "lng": 7.92,
                            "lat": 52.28,
                            "zip": "{zip_code}",
                            "range": 0
                        }},
                        "offset": offset,
                        "count": 24,
                        "outsideOffset": outsideOffset,
                        "outsideSearch": true
                    }};
                    const resp = await fetch("https://www.tesla.com/inventory/api/v4/inventory-results?query=" + encodeURIComponent(JSON.stringify(query)));
                    if (!resp.ok) break;
                    const data = await resp.json();
                    const results = data.results || [];
                    if (!results.length) break;
                    cars.push(...results);
                    offset += results.length;
                    outsideOffset += results.length;
                    if (results.length < 24) break;
                }} catch (e) {{
                    break;
                }}
            }}
            return cars;
        }}''')
        browser.close()
        
    # Deduplizieren anhand VIN
    seen_vins = set()
    unique_cars = []
    for car in (all_raw_cars or []):
        vin = car.get("VIN")
        if vin and vin not in seen_vins:
            seen_vins.add(vin)
            unique_cars.append(car)
            
    print(f"{Colors.GREEN}✓ {len(unique_cars)} gebrauchte Model Y im deutschen Tesla-Bestand gescannt.{Colors.RESET}")
    return unique_cars


LOTTE_COORDS = (52.28, 7.92)  # PLZ 49504 Lotte / Osnabrück

# Reale Routen-Fahrzeiten und Distanzen ab PLZ 49504 Lotte
KNOWN_HUBS = {
    "dortmund": (95, "ca. 1h 00m", 1.0),
    "bielefeld": (65, "ca. 45 Min.", 0.8),
    "bremen": (115, "ca. 1h 10m", 1.2),
    "hannover": (140, "ca. 1h 25m", 1.4),
    "essen": (125, "ca. 1h 15m", 1.3),
    "duisburg": (135, "ca. 1h 20m", 1.3),
    "düsseldorf": (155, "ca. 1h 35m", 1.6),
    "köln": (175, "ca. 1h 50m", 1.8),
    "kassel": (190, "ca. 2h 00m", 2.0),
    "hamburg": (230, "ca. 2h 15m", 2.3),
    "hanau": (315, "ca. 3h 10m", 3.2),
    "frankfurt": (325, "ca. 3h 15m", 3.3),
    "weiterstadt": (340, "ca. 3h 25m", 3.4),
    "potsdam": (410, "ca. 3h 55m", 3.9),
    "potsdam-mittelmark": (410, "ca. 3h 55m", 3.9),
    "berlin": (430, "ca. 4h 15m", 4.3),
    "grünheide": (450, "ca. 4h 25m", 4.4),
    "leipzig": (380, "ca. 3h 45m", 3.8),
    "nürnberg": (480, "ca. 4h 30m", 4.5),
    "fürth": (475, "ca. 4h 25m", 4.4),
    "holzgerlingen": (520, "ca. 5h 00m", 5.0),
    "stuttgart": (510, "ca. 4h 50m", 4.8),
    "neu-ulm": (585, "ca. 5h 30m", 5.5),
    "parsdorf": (650, "ca. 6h 00m", 6.0),
    "münchen": (640, "ca. 5h 50m", 5.8),
    "freiburg": (590, "ca. 5h 30m", 5.5),
    "karlsruhe": (430, "ca. 4h 05m", 4.1),
    "mannheim": (395, "ca. 3h 45m", 3.8),
    "dresden": (480, "ca. 4h 30m", 4.5),
    "rostock": (380, "ca. 3h 45m", 3.8)
}

def calculate_driving_distance_and_time(city, lat=None, lon=None):
    """Berechnet Distanz (km) und Fahrzeit in Autostunden ab 49504 Lotte/Osnabrück."""
    import math
    if city:
        city_lower = city.lower().strip()
        for key, val in KNOWN_HUBS.items():
            if key in city_lower or city_lower in key:
                return val[1], val[0], val[2]
                
    if lat and lon:
        lat1, lon1 = math.radians(LOTTE_COORDS[0]), math.radians(LOTTE_COORDS[1])
        lat2, lon2 = math.radians(lat), math.radians(lon)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        luftlinie_km = 6371 * c
        strasse_km = int(luftlinie_km * 1.28)
        stunden = strasse_km / 105.0
        h = int(stunden)
        m = int((stunden - h) * 60)
        time_str = f"ca. {h}h {m:02d}m" if h > 0 else f"ca. {m} Min."
        return time_str, strasse_km, round(stunden, 1)
        
    return "N/A", 0, 0


def parse_car_details(raw):
    """Extrahiert alle relevanten Fahrzeugdaten sauber in ein einheitliches Format."""
    vin = raw.get("VIN", "")
    
    # Produktionsstandort anhand der VIN
    if vin.startswith("XP7"):
        herkunft = "Berlin-Grünheide (Deutschland)"
        herkunft_kurz = "Grünheide (XP7)"
        akku_typ = "LFP (BYD Blade)"
    elif vin.startswith("LRW"):
        herkunft = "Gigafactory Shanghai (China)"
        herkunft_kurz = "Shanghai (LRW)"
        akku_typ = "LFP (CATL)"
    else:
        herkunft = "Fremont / USA"
        herkunft_kurz = "Fremont"
        akku_typ = "Unbekannt"

    # Optionen & Specs auslesen
    specs = raw.get("OptionCodeSpecs", {})
    c_opts = specs.get("C_OPTS", {}).get("options", [])
    c_callouts = specs.get("C_CALLOUTS", {}).get("options", [])
    
    # Farbe / Lackierung
    farbe = "Pearl White Multi-Coat"
    paint_str = str(raw.get("PAINT", "")).upper()
    if "BLACK" in paint_str or "$PBSB" in paint_str:
        farbe = "Solid Black"
    elif "GREY" in paint_str or "GRAY" in paint_str or "$PMNG" in paint_str:
        farbe = "Midnight Silver / Stealth Grey"
    elif "BLUE" in paint_str or "$PPSB" in paint_str:
        farbe = "Deep Blue Metallic"
    elif "RED" in paint_str or "$PPMR" in paint_str or "$PR01" in paint_str:
        farbe = "Red Multi-Coat / Ultra Red"
    elif "SILVER" in paint_str or "$PN01" in paint_str:
        farbe = "QuickSilver"
    elif "WHITE" in paint_str or "$PBCW" in paint_str:
        farbe = "Pearl White Multi-Coat"

    # Felgen
    felgen = "19-Zoll Gemini"
    for opt in c_opts:
        if opt.get("lexiconGroup") == "WHEELS":
            felgen = opt.get("name", felgen)

    # Innenraum
    innenraum = "Schwarz"
    for opt in c_opts:
        if opt.get("lexiconGroup") == "INTERIOR":
            innenraum = opt.get("name", "Schwarz")

    # Autopilot
    autopilot = "Standard Autopilot"
    for opt in c_callouts + c_opts:
        if opt.get("lexiconGroup") == "AUTOPILOT" or "Autopilot" in opt.get("name", ""):
            autopilot = opt.get("name", autopilot)

    # Anhängerkupplung prüfen
    opt_codes = str(raw.get("OptionCodeList", "")) + " " + str(raw.get("FlexibleOptionsData", ""))
    has_tow_hitch = ("$AP02" in opt_codes or "$AH00" in opt_codes or "tow" in opt_codes.lower() or "kupplung" in opt_codes.lower())
    
    # Unfall- / Reparaturschaden Disclosure prüfen
    # Unfall- / Reparaturschaden & VehicleHistory Disclosure prüfen
    vehicle_history_raw = str(raw.get("VehicleHistory", "CLEAN")).strip().upper()
    damage_guids = raw.get("DamageDisclosureGuids") or []
    has_damage = (
        (vehicle_history_raw != "" and vehicle_history_raw != "CLEAN") or
        raw.get("DamageDisclosure") is True or 
        raw.get("HasDamagePhotos") is True or 
        len(damage_guids) > 0
    )
    zustand_text = "🛡️ Unfallfrei (CLEAN)" if not has_damage else "⚠️ Reparierter Vorschaden (Repariertes Gebrauchtfahrzeug)"

    # Erstzulassungsdatum formatieren
    first_reg_raw = raw.get("FirstRegistrationDate")
    ez_jahr = raw.get("Year") or 2023
    ez_formatiert = str(ez_jahr)
    if first_reg_raw:
        try:
            dt = datetime.datetime.fromisoformat(first_reg_raw.replace("Z", "+00:00"))
            ez_formatiert = dt.strftime("%d.%m.%Y")
            ez_jahr = dt.year
        except Exception:
            pass

    # Preise & Kilometer
    preis = raw.get("TotalPrice") or raw.get("PurchasePrice") or 0
    km = raw.get("Odometer") or 0
    
    # Standort, Koordinaten und Fahrzeit ab 49504 berechnen
    standort = raw.get("City") or "Deutschland"
    vrl_list = raw.get("vrlList") or []
    lat, lon = None, None
    if vrl_list and isinstance(vrl_list, list) and isinstance(vrl_list[0], dict):
        lat = vrl_list[0].get("lat")
        lon = vrl_list[0].get("lon")
    
    fahrzeit_str, distanz_km, fahrzeit_std = calculate_driving_distance_and_time(standort, lat, lon)

    # Modellvariante
    trim_name = raw.get("TrimName") or "Model Y Hinterradantrieb"
    if raw.get("TrimVariantCode") == "AWD" or "Allrad" in trim_name:
        trim_name = "Model Y Maximale Reichweite AWD"
    elif raw.get("TrimVariantCode") == "PERF" or "Performance" in trim_name:
        trim_name = "Model Y Performance"

    # Garantie
    garantie_fahrzeug = raw.get("WarrantyVehicleExpDate", "")
    garantie_akku = raw.get("WarrantyBatteryExpDate", "")
    if garantie_fahrzeug:
        try:
            dt = datetime.datetime.fromisoformat(garantie_fahrzeug.replace("Z", "+00:00"))
            garantie_fahrzeug = dt.strftime("%m/%Y")
        except Exception:
            pass
    if garantie_akku:
        try:
            dt = datetime.datetime.fromisoformat(garantie_akku.replace("Z", "+00:00"))
            garantie_akku = dt.strftime("%m/%Y")
        except Exception:
            pass

    return {
        "vin": vin,
        "modell": trim_name,
        "baujahr": raw.get("Year"),
        "ez": ez_formatiert,
        "ez_jahr": ez_jahr,
        "preis": preis,
        "km": km,
        "standort": standort,
        "distanz_km": distanz_km,
        "fahrzeit_str": fahrzeit_str,
        "fahrzeit_std": fahrzeit_std,
        "bundesland": raw.get("StateProvinceLongName") or raw.get("StateProvince") or "",
        "herkunft": herkunft,
        "herkunft_kurz": herkunft_kurz,
        "akku_typ": akku_typ,
        "farbe": farbe,
        "felgen": felgen,
        "innenraum": innenraum,
        "autopilot": autopilot,
        "anhaengerkupplung": has_tow_hitch,
        "unfall_oder_schaden": has_damage,
        "zustand_text": zustand_text,
        "vehicle_history": vehicle_history_raw,
        "garantie_fahrzeug": garantie_fahrzeug,
        "garantie_akku": garantie_akku,
        "url": f"https://www.tesla.com/de_DE/my/order/{vin}",
        "raw_updated": datetime.datetime.now(BERLIN_TZ).isoformat()
    }


def filter_cars(cars, min_year=2023, max_year=2026, max_price=35000, max_km=70000, unfallfrei_only=True, xp7_only=True):
    """Filtert Fahrzeuge anhand der definierten Suchkriterien."""
    matched = []
    for c in cars:
        # VIN Filter (Grünheide XP7)
        if xp7_only and not c["vin"].startswith("XP7"):
            continue
        if not (min_year <= c["ez_jahr"] <= max_year):
            continue
        if c["preis"] > max_price or c["preis"] <= 0:
            continue
        if c["km"] > max_km:
            continue
        # Strikte Unfallfrei-Prüfung (inkl. PREVIOUS ACCIDENT(S) & Damage Disclosure)
        if unfallfrei_only and c["unfall_oder_schaden"]:
            continue
        matched.append(c)
    
    # Sortieren nach Preis aufsteigend, bei gleichem Preis nach Kilometer
    matched.sort(key=lambda x: (x["preis"], x["km"]))
    return matched


def update_history_and_tag(cars):
    """
    Vergleicht den aktuellen Abruf mit der Historie:
    - Markiert NEUE Fahrzeuge (✨ NEU)
    - Erkennt PREISÄNDERUNGEN (📉 Preissenkung / 📈 Preisanstieg)
    - Erkennt verkaufte/entfernte Fahrzeuge
    - Gibt zurück: (tagged_cars, has_changes)
    """
    history = {}
    if DB_FILE.exists():
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = {}

    today_str = datetime.datetime.now(BERLIN_TZ).date().isoformat()
    tagged_cars = []
    has_changes = False

    for car in cars:
        vin = car["vin"]
        car_tagged = dict(car)
        
        if vin not in history:
            car_tagged["status_tag"] = "NEU"
            car_tagged["status_text"] = "✨ NEU"
            has_changes = True
            history[vin] = {
                "first_seen": today_str,
                "last_seen": today_str,
                "initial_price": car["preis"],
                "last_price": car["preis"],
                "data": car
            }
        else:
            old_data = history[vin]
            old_price = old_data.get("last_price", car["preis"])
            old_data["last_seen"] = today_str
            old_data["data"] = car
            
            if car["preis"] < old_price:
                diff = old_price - car["preis"]
                car_tagged["status_tag"] = "PREISSENKUNG"
                car_tagged["status_text"] = f"📉 -{diff} €"
                old_data["last_price"] = car["preis"]
                has_changes = True
            elif car["preis"] > old_price:
                diff = car["preis"] - old_price
                car_tagged["status_tag"] = "PREISANSTIEG"
                car_tagged["status_text"] = f"📈 +{diff} €"
                old_data["last_price"] = car["preis"]
                has_changes = True
            else:
                car_tagged["status_tag"] = "BEKANNT"
                car_tagged["status_text"] = "Verfügbar"
                
        tagged_cars.append(car_tagged)

    # Prüfen, ob Fahrzeuge aus dem vorherigen Durchlauf verkauft/entfernt wurden
    previous_vins = history.get("_last_active_vins", [])
    current_vins = [c["vin"] for c in cars]
    if previous_vins and set(previous_vins) != set(current_vins):
        has_changes = True
    history["_last_active_vins"] = current_vins

    # Historie & aktueller JSON-Export speichern
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    with open(LATEST_JSON, "w", encoding="utf-8") as f:
        json.dump(tagged_cars, f, indent=2, ensure_ascii=False)

    return tagged_cars, has_changes


def send_telegram_summary_report(token, chat_id, total_scanned, cars, has_changes=False, dashboard_url="https://oliver19xx.github.io/tesla-radar/"):
    """
    Sendet per Telegram:
    - Bei Änderungen: Den vollen Bericht mit Auto-Details und Highlights.
    - Ohne Änderungen: Einen kurzen kompakten Hinweis ohne Auto-Listen.
    """
    if not token or not chat_id:
        return
        
    print(f"\n{Colors.CYAN}📲 Sende Telegram-Benachrichtigung (Änderungen: {has_changes})...{Colors.RESET}")
    now_str = datetime.datetime.now(BERLIN_TZ).strftime("%d.%m.%Y um %H:%M Uhr")
    
    if not has_changes:
        text = (
            "⚡ <b>TESLA MODEL Y RADAR</b>\n"
            f"📅 Stand: {now_str}\n"
            f"🔍 <b>{total_scanned}</b> gescannt • <b>{len(cars)} passende(r) XP7-Treffer</b>\n\n"
            "ℹ️ <i>Keine neuen Angebote oder Preisänderungen im Bestand.</i>\n\n"
            f"🌐 <a href=\"{dashboard_url}\"><b>Zum Online-Dashboard</b></a>"
        )
    else:
        lines = [
            "⚡ <b>TESLA MODEL Y RADAR - ÄNDERUNGEN GEFUNDEN!</b>",
            f"📅 Stand: {now_str}",
            f"🔍 <b>{total_scanned}</b> gescannt ➔ <b>{len(cars)} passende XP7-Treffer</b>:\n"
        ]
        
        if not cars:
            lines.append("ℹ️ <i>Aktuell gibt es kein Grünheide Model Y (XP7) unter 35.000 € mit unter 70.000 km im deutschen Bestand.</i>\n")
        else:
            for idx, c in enumerate(cars, 1):
                tag_badge = ""
                if c.get("status_tag") == "NEU":
                    tag_badge = " ✨ <b>NEU!</b>"
                elif c.get("status_tag") == "PREISSENKUNG":
                    tag_badge = f" 📉 <b>{c.get('status_text')}</b>"
                elif c.get("status_tag") == "PREISANSTIEG":
                    tag_badge = f" 📈 <b>{c.get('status_text')}</b>"
                    
                ahk_str = " | ⚓ AHK" if c.get("anhaengerkupplung") else ""
                lines.append(
                    f"🚗 <b>{idx}. {c['modell']} ({c['ez_jahr']})</b>{tag_badge}\n"
                    f"• 💰 <b>{c['preis']:,} €</b> | ⚡ <b>{c['km']:,} km</b> | 📅 EZ: {c['ez']}\n"
                    f"• 🛡️ <b>Zustand:</b> {c['zustand_text']}\n"
                    f"• 📍 <b>{c['standort']}</b> (🚗 <b>{c['fahrzeit_str']}</b> / {c['distanz_km']} km ab 49504)\n"
                    f"• 🔋 {c['akku_typ']} | 🎨 {c['farbe']}{ahk_str}\n"
                    f"• 👉 <a href='{c['url']}'><b>Direkt bei Tesla ansehen</b></a>\n"
                )
                
        lines.append(f"🌐 <a href='{dashboard_url}'><b>Zum Online-Dashboard</b></a>")
        text = "\n".join(lines)
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            if resp.status == 200:
                print(f"{Colors.GREEN}✓ Telegram Statusbericht erfolgreich gesendet!{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.RED}✗ Fehler beim Senden an Telegram: {e}{Colors.RESET}")


def generate_html_report(cars, min_year, max_year, max_price, max_km, xp7_only=True):
    """Erstellt ein interaktives, modernes HTML Dashboard für die schnelle tägliche Übersicht."""
    now_str = datetime.datetime.now(BERLIN_TZ).strftime("%d.%m.%Y um %H:%M Uhr")
    
    cards_html = []
    for c in cars:
        status_tag = c.get("status_tag", "BEKANNT")
        if status_tag == "NEU":
            status_badge = '<span class="badge badge-new">✨ NEU IM BESTAND</span>'
        elif status_tag == "PREISSENKUNG":
            status_badge = f'<span class="badge badge-price-drop">{c["status_text"]}</span>'
        else:
            status_badge = '<span class="badge badge-info">Verfügbar</span>'

        herkunft_badge = '<span class="badge badge-gruenheide">🇩🇪 Grünheide (BYD Blade)</span>' if "Grünheide" in c["herkunft_kurz"] else '<span class="badge badge-shanghai">🇨🇳 Shanghai (CATL)</span>'
        ahk_badge = '<span class="badge badge-feature">⚓ Anhängerkupplung</span>' if c.get("anhaengerkupplung") else ''
        zustand_badge = '<span class="badge badge-clean">🛡️ Unfallfrei (CLEAN)</span>' if not c.get("unfall_oder_schaden") else '<span class="badge badge-accident">⚠️ Reparierter Vorschaden</span>'
        
        cards_html.append(f"""
        <div class="car-card">
            <div class="card-top">
                <div class="badges-row">
                    {status_badge}
                    {zustand_badge}
                    {herkunft_badge}
                    {ahk_badge}
                </div>
                <div class="price">{c['preis']:,} €</div>
            </div>
            
            <h3 class="car-title">{c['modell']}</h3>
            <div class="car-vin">VIN: {c['vin']}</div>
            
            <div class="specs-grid">
                <div class="spec-item">
                    <span class="spec-label">Kilometerstand</span>
                    <span class="spec-value km-val">{c['km']:,} km</span>
                </div>
                <div class="spec-item">
                    <span class="spec-label">Erstzulassung</span>
                    <span class="spec-value">{c['ez']}</span>
                </div>
                <div class="spec-item">
                    <span class="spec-label">Fahrzeit (ab 49504 Lotte)</span>
                    <span class="spec-value drive-val">🚗 <strong>{c['fahrzeit_str']}</strong> ({c['distanz_km']} km)</span>
                </div>
                <div class="spec-item">
                    <span class="spec-label">Standort</span>
                    <span class="spec-value location-val">📍 {c['standort']}</span>
                </div>
                <div class="spec-item">
                    <span class="spec-label">Zustand</span>
                    <span class="spec-value">{c['zustand_text']}</span>
                </div>
                <div class="spec-item">
                    <span class="spec-label">Farbe / Lack</span>
                    <span class="spec-value">{c['farbe']}</span>
                </div>
                <div class="spec-item">
                    <span class="spec-label">Felgen</span>
                    <span class="spec-value">{c['felgen']}</span>
                </div>
                <div class="spec-item">
                    <span class="spec-label">Akku-Technik</span>
                    <span class="spec-value">{c['akku_typ']}</span>
                </div>
                <div class="spec-item">
                    <span class="spec-label">Garantie Basisfahrzeug</span>
                    <span class="spec-value">Bis {c['garantie_fahrzeug'] or 'N/A'}</span>
                </div>
            </div>

            <div class="card-bottom">
                <a href="{c['url']}" target="_blank" class="order-button">
                    Fahrzeug bei Tesla ansehen ➔
                </a>
            </div>
        </div>
        """)

    empty_state = """
    <div class="empty-state">
        <h2>Aktuell keine Treffer für deine Filterkriterien</h2>
        <p>Momentan gibt es kein Model Y aus Grünheide (XP7) unter 35.000 € mit unter 70.000 km. Bitte später erneut prüfen!</p>
    </div>
    """ if not cars else ""

    cheapest_str = f"{cars[0]['preis']:,} €" if cars else "N/A"
    lowest_km_str = f"{min(c['km'] for c in cars):,} km" if cars else "N/A"
    xp7_badge = '<span class="filter-chip" style="border-color: #38bdf8; color: #38bdf8;">🇩🇪 Nur Grünheide (VIN: XP7...)</span>' if xp7_only else ''

    html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#0b0f19">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <title>Tesla Model Y Gebrauchtwagen-Radar</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #0b0f19;
            --card-bg: #131b2e;
            --card-border: #1f2d4a;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent-green: #10b981;
            --accent-blue: #38bdf8;
            --accent-yellow: #f59e0b;
            --tesla-red: #e82127;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg);
            color: var(--text-main);
            padding: 2.5rem 1.5rem;
            line-height: 1.5;
        }}
        .container {{
            max-width: 1280px;
            margin: 0 auto;
        }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            flex-wrap: wrap;
            gap: 1.5rem;
            margin-bottom: 2rem;
            padding-bottom: 1.5rem;
            border-bottom: 1px solid var(--card-border);
        }}
        h1 {{
            font-size: 2rem;
            font-weight: 800;
            color: #ffffff;
            letter-spacing: -0.02em;
        }}
        .subtitle {{
            color: var(--text-muted);
            font-size: 0.95rem;
            margin-top: 0.35rem;
        }}
        .filter-summary {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 1rem;
        }}
        .filter-chip {{
            background: #1e293b;
            padding: 0.35rem 0.85rem;
            border-radius: 9999px;
            font-size: 0.825rem;
            color: #cbd5e1;
            border: 1px solid #334155;
            font-weight: 500;
        }}
        .stats-bar {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .stat-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 0.875rem;
            padding: 1.25rem;
        }}
        .stat-label {{
            font-size: 0.8rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-weight: 600;
        }}
        .stat-value {{
            font-size: 1.75rem;
            font-weight: 800;
            margin-top: 0.35rem;
            color: #ffffff;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
            gap: 1.5rem;
        }}
        .car-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 1rem;
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: all 0.2s ease;
        }}
        .car-card:hover {{
            transform: translateY(-3px);
            border-color: #38bdf8;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
        }}
        .card-top {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 1rem;
            margin-bottom: 0.85rem;
        }}
        .badges-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem;
        }}
        .price {{
            font-size: 1.65rem;
            font-weight: 800;
            color: var(--accent-green);
            white-space: nowrap;
        }}
        .badge {{
            display: inline-block;
            padding: 0.25rem 0.65rem;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 700;
        }}
        .badge-new {{
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.35);
        }}
        .badge-price-drop {{
            background: rgba(245, 158, 11, 0.15);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.35);
        }}
        .badge-clean {{
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.35);
        }}
        .badge-accident {{
            background: rgba(239, 68, 68, 0.15);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.35);
        }}
        .badge-gruenheide {{
            background: rgba(56, 189, 248, 0.15);
            color: #38bdf8;
            border: 1px solid rgba(56, 189, 248, 0.3);
        }}
        .badge-shanghai {{
            background: rgba(168, 85, 247, 0.15);
            color: #c084fc;
            border: 1px solid rgba(168, 85, 247, 0.3);
        }}
        .badge-feature {{
            background: rgba(251, 191, 36, 0.15);
            color: #fcd34d;
            border: 1px solid rgba(251, 191, 36, 0.3);
        }}
        .badge-info {{
            background: rgba(148, 163, 184, 0.15);
            color: #94a3b8;
        }}
        .car-title {{
            font-size: 1.2rem;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 0.15rem;
        }}
        .car-vin {{
            font-size: 0.75rem;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            color: var(--text-muted);
            margin-bottom: 1.25rem;
        }}
        .specs-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.85rem;
            background: #0d1322;
            padding: 1rem;
            border-radius: 0.75rem;
            margin-bottom: 1.25rem;
            font-size: 0.85rem;
            border: 1px solid #182238;
        }}
        .spec-item {{
            display: flex;
            flex-direction: column;
        }}
        .spec-label {{
            color: var(--text-muted);
            font-size: 0.75rem;
            margin-bottom: 0.15rem;
        }}
        .spec-value {{
            font-weight: 600;
            color: #e2e8f0;
        }}
        .drive-val {{
            color: #fbbf24;
            font-weight: 700;
        }}
        .km-val {{
            color: var(--accent-blue);
        }}
        .location-val {{
            color: #ffffff;
        }}
        .order-button {{
            display: block;
            text-align: center;
            background: var(--tesla-red);
            color: #ffffff;
            text-decoration: none;
            padding: 0.75rem 1rem;
            border-radius: 0.5rem;
            font-weight: 700;
            font-size: 0.9rem;
            transition: background 0.15s ease, transform 0.15s ease;
        }}
        .order-button:hover {{
            background: #c2191e;
            transform: scale(1.01);
        }}
        .empty-state {{
            text-align: center;
            padding: 4rem 2rem;
            background: var(--card-bg);
            border-radius: 1rem;
            border: 1px solid var(--card-border);
        }}
        footer {{
            margin-top: 3.5rem;
            text-align: center;
            color: var(--text-muted);
            font-size: 0.85rem;
            border-top: 1px solid var(--card-border);
            padding-top: 1.5rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>⚡ Tesla Model Y Gebrauchtwagen-Radar</h1>
                <p class="subtitle">Automatische Überwachung • PLZ 49504 (Lotte / Osnabrück) • Stand: {now_str}</p>
                <div class="filter-summary">
                    {xp7_badge}
                    <span class="filter-chip">📅 EZ: {min_year} - {max_year}</span>
                    <span class="filter-chip">💰 Max. {max_price:,} €</span>
                    <span class="filter-chip">⚡ Max. {max_km:,} km</span>
                    <span class="filter-chip">🛡️ Nur unfallfrei</span>
                </div>
            </div>
        </header>

        <div class="stats-bar">
            <div class="stat-card">
                <div class="stat-label">Passende Angebote (XP7)</div>
                <div class="stat-value">{len(cars)}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Günstigster Preis</div>
                <div class="stat-value" style="color: var(--accent-green);">{cheapest_str}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Niedrigste Laufleistung</div>
                <div class="stat-value" style="color: var(--accent-blue);">{lowest_km_str}</div>
            </div>
        </div>

        {empty_state}
        <div class="grid">
            {"".join(cards_html)}
        </div>

        <footer>
            <p>Täglicher Check via <code>./check_angebote.sh</code> • Fahrzeiten berechnet ab PLZ 49504 (Lotte)</p>
        </footer>
    </div>
</body>
</html>
"""
    # Speichern für lokale Nutzung und für GitHub Pages (index.html)
    with open(HTML_REPORT, "w", encoding="utf-8") as f:
        f.write(html_content)
    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"{Colors.GREEN}✓ HTML-Dashboard aktualisiert: {HTML_REPORT} & {INDEX_HTML}{Colors.RESET}")


def print_terminal_results(cars):
    """Gibt eine übersichtliche formatierte Tabelle im Terminal aus."""
    print(f"\n{Colors.BOLD}{'='*120}{Colors.RESET}")
    print(f"{Colors.BOLD}{'MODELL & BAUJAHR':<27} | {'PREIS':<9} | {'KILOMETER':<10} | {'STANDORT':<14} | {'FAHRZEIT (49504)':<20} | {'STATUS':<10}{Colors.RESET}")
    print(f"{'='*120}")

    for idx, c in enumerate(cars, 1):
        status_tag = c.get("status_tag", "")
        status_badge = c.get("status_text", "")
        if status_tag == "NEU":
            status_str = f"{Colors.GREEN}{Colors.BOLD}✨ NEU{Colors.RESET}"
        elif status_tag == "PREISSENKUNG":
            status_str = f"{Colors.YELLOW}{Colors.BOLD}{status_badge}{Colors.RESET}"
        else:
            status_str = f"{Colors.CYAN}{status_badge}{Colors.RESET}"

        title = f"{c['modell']} ({c['ez_jahr']})"[:26]
        price_str = f"{c['preis']:,} €"
        km_str = f"{c['km']:,} km"
        standort = c['standort'][:13]
        fahrzeit = f"🚗 {c['fahrzeit_str']} ({c['distanz_km']}km)"
        
        print(f"{title:<27} | {price_str:<9} | {km_str:<10} | {standort:<14} | {Colors.YELLOW}{fahrzeit:<20}{Colors.RESET} | {status_str}")
        
        features = [
            f"VIN: {c['vin']}",
            f"EZ: {c['ez']}",
            f"Zustand: {c['zustand_text']}",
            f"Lack: {c['farbe']}",
            f"Akku: {c['akku_typ']}"
        ]
        if c.get("anhaengerkupplung"):
            features.append("⚓ AHK")
        
        print(f"  {Colors.BLUE}🔗 {c['url']}{Colors.RESET} | {' | '.join(features)}")
        print(f"{'-'*120}")

    print(f"\n{Colors.BOLD}Ergebnis:{Colors.RESET} {Colors.GREEN}{len(cars)} passende Angebote{Colors.RESET} entsprechen exakt deinen Kriterien.\n")


def main():
    parser = argparse.ArgumentParser(description="Tesla Model Y Gebrauchtwagen Scraper")
    parser.add_argument("--min-year", type=int, default=2023, help="Mindest-Erstzulassungsjahr (Default: 2023)")
    parser.add_argument("--max-year", type=int, default=2026, help="Maximal-Erstzulassungsjahr (Default: 2026)")
    parser.add_argument("--max-price", type=int, default=35000, help="Maximaler Preis in Euro (Default: 35000)")
    parser.add_argument("--max-km", type=int, default=70000, help="Maximale Kilometer (Default: 70000)")
    parser.add_argument("--zip", type=str, default="49504", help="Postleitzahl für Standortberechnung (Default: 49504)")
    parser.add_argument("--all-vins", action="store_true", help="Auch Fahrzeuge außerhalb von Grünheide (z.B. Shanghai LRW) anzeigen")
    parser.add_argument("--telegram-token", type=str, default=os.environ.get("TELEGRAM_BOT_TOKEN"), help="Telegram Bot Token")
    parser.add_argument("--telegram-chat-id", type=str, default=os.environ.get("TELEGRAM_CHAT_ID"), help="Telegram Chat ID")
    parser.add_argument("--notify-all", action="store_true", help="Benachrichtigung für alle passenden Angebote senden (auch bekannte)")
    parser.add_argument("--open", action="store_true", help="Öffnet das generierte HTML-Dashboard automatisch im Browser")
    args = parser.parse_args()

    xp7_only = not args.all_vins

    # 1. Daten von Tesla abrufen
    raw_cars = fetch_tesla_inventory(zip_code=args.zip, model="my")
    
    # 2. Daten parsen
    parsed_cars = [parse_car_details(car) for car in raw_cars]
    
    # 3. Filtern nach Kriterien
    matched_cars = filter_cars(
        parsed_cars,
        min_year=args.min_year,
        max_year=args.max_year,
        max_price=args.max_price,
        max_km=args.max_km,
        unfallfrei_only=True,
        xp7_only=xp7_only
    )
    
    # 4. Mit Verlaufsdaten abgleichen (NEU / Preissenkungen / Abgänge)
    tagged_cars, has_changes = update_history_and_tag(matched_cars)
    
    # 5. HTML Dashboard erzeugen
    generate_html_report(
        tagged_cars,
        min_year=args.min_year,
        max_year=args.max_year,
        max_price=args.max_price,
        max_km=args.max_km,
        xp7_only=xp7_only
    )
    
    # 6. Telegram Statusbericht senden (falls Token & Chat-ID hinterlegt sind)
    if args.telegram_token and args.telegram_chat_id:
        send_telegram_summary_report(
            args.telegram_token,
            args.telegram_chat_id,
            total_scanned=len(raw_cars),
            cars=tagged_cars,
            has_changes=(has_changes or args.notify_all)
        )
    
    # 7. Im Terminal ausgeben
    print_terminal_results(tagged_cars)
    
    # 8. Optional im Browser öffnen
    if args.open:
        webbrowser.open(f"file://{HTML_REPORT}")

if __name__ == "__main__":
    main()
