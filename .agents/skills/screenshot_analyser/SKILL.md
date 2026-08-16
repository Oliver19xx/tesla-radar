---
name: "screenshot_analyser"
description: "Triggers when the user asks to analyze screenshots of vehicle offers (e.g. Tesla Model Y) and extract or save their data to the database."
---

# Screenshot Analyser Skill

Use this skill when you need to analyze a screenshot of a vehicle offer (specifically Tesla Model Y) and insert it into the local JSON database.

## Extraction Instructions

1. **Read Screenshot File**: Use the `view_file` tool to display/load the binary image file of the screenshot.
2. **Extract Key Fields**: Read the screenshot carefully and extract the following data points:
   - **Model Name (`modell`)**: Look for the title (e.g., "Model Y", "Model Y Hinterradantrieb", "Model Y RWD"). Format it consistently as e.g., `"Tesla Model Y RWD"`.
   - **Purchase Price (`preisEur`)**: Locate the vehicle price in EUR (typically formatted as `XX.XXX €`). Extract it as a clean integer (e.g., `32600`).
   - **Mileage (`kilometerstand`)**: Find the odometer reading in km (e.g., `40.528 km`). Extract it as a clean integer (e.g., `40528`).
   - **VIN (`vin`)**: Search for the 17-character VIN (starts with `XP7` for Germany or `LRW` for China).
   - **Color (`farbe`)**: Look for the exterior paint color (e.g., "Pearl White Multi-Coat", "Solid Black", "Midnight Cherry Red", "Deep Blue Metallic", "Quicksilver").
   - **Baujahr (`baujahr`)**: Retrieve the year of manufacture (typically 2022, 2023, or 2024). You can infer this from the "Erstzulassung" or "Herstellungsdatum" in the screenshot.
   - **Abholort (`abholort`)**: Identify the Tesla Center/delivery location (e.g., "Dortmund", "Düsseldorf", "Hannover").

## Smart Inference Rules

To ensure database consistency and correct calculations, apply the following rules:

- **Produktionsort (`produktion`)**:
  - If the VIN starts with `XP7` -> Set to `"Grünheide"`
  - If the VIN starts with `LRW` -> Set to `"Shanghai"`
- **Akku-Typ (`akkuTyp`)**:
  - If VIN starts with `XP7` (Grünheide) and it is a Model Y RWD -> Set to `"LFP Akku (BYD)"`
  - If VIN starts with `LRW` (Shanghai) and it is a Model Y RWD -> Set to `"LFP Akku (CATL)"`
  - If it is a Long Range (Maximale Reichweite) or Performance model -> Set to `"NMC Akku"`
- **TSN (`tsn`)**:
  - If the battery type contains "BYD" (LFP Akku (BYD)) -> Set to `"ABP"`
  - Otherwise -> Set to `"AAQ"`
- **Abhol-Distanz (`abholDistanzKm`)**:
  Tesla screenshots list the Tesla Center location. Map this location to the distance from **Steinfurt (48565)** using this lookup table:
  - Dortmund: `95`
  - Düsseldorf: `130`
  - Essen: `110`
  - Hannover: `170`
  - Hamburg: `280`
  - Köln / Cologne: `165`
  - Bremen: `140`
  - Bielefeld: `90`
  - Frankfurt: `280`
  - München / Munich: `600`
  - Berlin: `470`
  - Stuttgart: `460`
  - Mannheim: `340`
  - Karlsruhe: `400`
  - Weiterstadt: `300`
  - Nossen: `440`
  - Regensburg: `560`
  - *If a location is not in this list, search the web or calculate its road distance to Steinfurt (48565).*
- **Other Defaults**:
  - `maxGarantieKm`: `100000`
  - `hsn`: `"1480"`
  - `url`: `https://www.tesla.com/de_DE/my/order/<VIN>` (format using the extracted VIN)

## Verification and Double-Check Procedure (MANDATORY)

Accuracy is critical. Perform the following verification checks before saving:
1. **VIN Integrity**: Verify that the VIN extracted from the screenshot exactly matches the filename of the screenshot (if the filename includes a VIN).
2. **Text Validation**: Re-read the price and odometer values from the screenshot to ensure no OCR or reading mistakes were made.
3. **Garantie / Warranty Alignment**: Cross-reference the warranty expiration date. Standard vehicle warranty is 4 years or 80.000 km. Make sure the extraction aligns with standard Tesla warranty rules.

## Execution / Insertion

Once verified, format the extracted data into a single JSON string.
Run the database manager command from the workspace directory:
```bash
python db_manager.py add-json '<json_string>'
```

Example JSON format:
```json
{
  "modell": "Tesla Model Y RWD",
  "baujahr": 2023,
  "preisEur": 32600,
  "kilometerstand": 40528,
  "vin": "XP7YGCEJ1PB138335",
  "farbe": "Pearl White Multi-Coat",
  "akkuTyp": "LFP Akku (BYD)",
  "produktion": "Grünheide",
  "abholort": "Dortmund",
  "abholDistanzKm": 95,
  "maxGarantieKm": 100000,
  "hsn": "1480",
  "tsn": "ABP",
  "url": "https://www.tesla.com/de_DE/my/order/XP7YGCEJ1PB138335"
}
```
Verify that the output confirms successful execution: `✓ JSON-Datenbank aktualisiert ...`
