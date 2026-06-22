# KobiePWA - Contract Extractor (Vertragsextraktor)

Dieses Repository enthält den Vertragsextraktor zur automatisierten Datenextraktion aus PDF-Betreuungsverträgen in eine Excel-Tabelle (`EingangRPA.xlsx`) auf OneDrive für die Weiterverarbeitung durch einen Power Automate Desktop RPA-Bot.

## Features

- **LLM-basierte Extraktion**: Nutzt ein lokales LLM (z. B. Llama 3 via Ollama) für präzise Datenextraktion aus digitalen PDFs.
- **Base64 Dekodierung**: Entschlüsselt automatisch Base64-kodierte PDF-Formularfelder (z. B. `S2luZE5hY2huYW1lVm9ybmFtZW4=` -> `KindNachnameVornamen`).
- **Datenbereinigung**:
  - Aufteilung von Namen in Vorname und Nachname.
  - Aufteilung von Adressen in Straße, PLZ und Ort.
  - Einheitliche Formatierung von Datumsangaben (`DD.MM.YYYY`) und Uhrzeiten (`HH:MM`).
- **OneDrive Integration**: Archiviert verarbeitete Dateien in einen Erfolgs- (`Abgeschlossen`) oder Fehlerordner.
- **Excel-Link-Erstellung**: Fügt in Excel relative, anklickbare Hyperlinks zur Quelldatei ein, damit jeder synchronisierte Benutzer die PDFs direkt öffnen kann.

## Voraussetzungen

- **Python**: Installiere Python 3.10 oder neuer.
- **Ollama**: Stelle sicher, dass Ollama auf dem konfigurierten Server läuft (z. B. mit Llama 3).

## Installation & Einrichtung

1. Installiere die Python-Abhängigkeiten:
   ```bash
   pip install -r contract_extractor/requirements.txt
   ```
2. Kopiere die Datei `contract_extractor/config.json.example` nach `contract_extractor/config.json` und passe die OneDrive-Pfade an deine lokale Ordnerstruktur an:
   ```json
   {
       "eingang_ordner": "C:\\Users\\<name>\\OneDrive...\\Eingang",
       "archiv_ordner": "C:\\Users\\<name>\\OneDrive...\\Abgeschlossen",
       "fehler_ordner": "C:\\Users\\<name>\\OneDrive...\\Fehler",
       "excel_pfad": "C:\\Users\\<name>\\OneDrive...\\EingangRPA.xlsx"
   }
   ```

## Starten

Führe einfach die Datei `Start-Extraktor.bat` im Ordner `contract_extractor` per Doppelklick aus oder führe das Python-Skript manuell aus:
```bash
python contract_extractor/main.py
```
