# 🚗 Tesla Model Y Gebrauchtwagen Radar (Grünheide XP7)

Automatische Überwachung des deutschen Tesla Gebrauchtwagen-Bestands mit:
* **Filter:** Nur Grünheide (`XP7...` mit BYD Blade LFP Akku), EZ 2023–2026, unfallfrei, max. 70.000 km, max. 35.000 €.
* **Fahrzeit-Berechnung:** Exakte Autobahn-Fahrzeiten & Entfernungen ab PLZ `49504` (Lotte / Osnabrück).
* **Push-Benachrichtigung:** Sofortige Benachrichtigung via Telegram bei neuen Inseraten oder Preissenkungen.
* **Web-Dashboard:** Kostenlos gehostet über GitHub Pages für Smartphone & Desktop.

---

## 🚀 Einrichtung in 2 Minuten (100% Kostenlos)

### Schritt 1: Telegram Bot erstellen (für Push-Nachrichten auf dein Handy)
1. Öffne Telegram und suche nach dem Nutzer **`@BotFather`**.
2. Sende `/newbot` und vergib einen Namen (z. B. `Mein Tesla Radar`).
3. Kopiere den **HTTP API Token** (z. B. `123456789:ABCdefGHIjkl...`).
4. Starte deinen neuen Bot mit `/start`.
5. Finde deine persönliche **Chat-ID** heraus: Suche in Telegram nach **`@userinfobot`** und starte ihn. Er zeigt dir direkt deine `Id` (z. B. `987654321`).

---

### Schritt 2: Code auf GitHub hochladen
1. Erstelle ein neues **Repository** auf GitHub (öffentlich oder privat).
2. Lade diesen Projektordner hoch:
   ```bash
   git init
   git add .
   git commit -m "Initial commit Tesla Radar"
   git branch -M main
   git remote add origin https://github.com/<DEIN-USERNAME>/<REPO-NAME>.git
   git push -u origin main
   ```

---

### Schritt 3: GitHub Secrets & Pages aktivieren

1. **Telegram-Keys hinterlegen:**
   * Gehe in deinem GitHub Repository auf **Settings** ➔ **Secrets and variables** ➔ **Actions**.
   * Klicke auf **New repository secret** und erstelle:
     * `TELEGRAM_BOT_TOKEN`: Deinen Token aus Schritt 1
     * `TELEGRAM_CHAT_ID`: Deine Chat-ID aus Schritt 1

2. **GitHub Pages aktivieren:**
   * Gehe auf **Settings** ➔ **Pages**.
   * Wähle unter *Build and deployment* ➔ *Source* die Option **`GitHub Actions`** aus.

---

## 📱 Von unterwegs nutzen
* **Automatisch:** Der GitHub Action Workflow läuft täglich alle 2 Stunden und schickt dir sofort eine Telegram-Nachricht, sobald ein passendes Auto eingestellt wird!
* **Manuell anstoßen:** Öffne das Repository in der **GitHub Mobile App** oder im mobilen Browser, gehe auf den Tab **Actions** ➔ **Tesla Radar Scraper & Monitor** ➔ **Run workflow**.
* **Dashboard als Handy-App:** Öffne deine GitHub Pages URL (z. B. `https://dein-username.github.io/repo-name/`) in Safari/Chrome auf dem Handy und wähle **„Zum Home-Bildschirm hinzufügen“**.
