#!/usr/bin/env bash
# Schnellstart-Skript für den täglichen Tesla Gebrauchtwagen-Check

cd "$(dirname "$0")"

if [ -d "venv" ]; then
    ./venv/bin/python scrape_tesla.py --open "$@"
else
    python3 scrape_tesla.py --open "$@"
fi
