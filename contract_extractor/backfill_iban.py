import os
import json
import time
import shutil
import logging
from typing import Dict, Any

import openpyxl

# Wir importieren die vorhandenen Funktionen aus deiner main.py
from main import load_or_create_config, extract_text_from_pdf, analyze_text_with_ollama

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def backfill():
    logger.info("Starte IBAN-Backfill Skript...")
    config = load_or_create_config()
    excel_path = config["excel_pfad"]
    archiv_ordner = config["archiv_ordner"]

    if not os.path.exists(excel_path):
        logger.error(f"Excel-Datei '{excel_path}' nicht gefunden.")
        return

    # Backup erstellen zur Sicherheit
    backup_path = excel_path.replace(".xlsx", f"_backup_{int(time.time())}.xlsx")
    shutil.copy2(excel_path, backup_path)
    logger.info(f"Backup der Excel-Datei erstellt unter: {backup_path}")

    # Lade das gesamte Schema
    schema_mapping_file = "schema_mapping.json"
    with open(schema_mapping_file, 'r', encoding='utf-8') as f:
        full_mapping = json.load(f)

    # Das Minimal-Schema, das an Ollama gesendet wird (nur die neuen Spalten)
    schema = {
        "Zahlungspflichtiger": full_mapping.get("Zahlungspflichtiger", ""),
        "Kreditinstitut": full_mapping.get("Kreditinstitut", ""),
        "IBAN": full_mapping.get("IBAN", "")
    }

    # Schema für Ollama formatieren
    formatted_schema = {k: f"Extrahiere diese Info: {v}" for k, v in schema.items()}

    # Excel mit openpyxl laden (data_only=False erhält Hyperlinks etc.)
    wb = openpyxl.load_workbook(excel_path, data_only=False)
    ws = wb.active

    headers = [cell.value for cell in ws[1]]
    
    # Prüfe, ob Quelldatei-Spalte existiert
    if "Quelldatei" not in headers:
        logger.error("Spalte 'Quelldatei' nicht in der Excel-Datei gefunden. Backfill nicht möglich.")
        return

    col_idx_quelldatei = headers.index("Quelldatei") + 1
    col_idx_zahlung = headers.index("Zahlungspflichtiger") + 1 if "Zahlungspflichtiger" in headers else None
    col_idx_kredit = headers.index("Kreditinstitut") + 1 if "Kreditinstitut" in headers else None
    col_idx_iban = headers.index("IBAN") + 1 if "IBAN" in headers else None

    if not all([col_idx_zahlung, col_idx_kredit, col_idx_iban]):
        logger.error("Die Spalten 'Zahlungspflichtiger', 'Kreditinstitut' oder 'IBAN' wurden in der Excel-Datei nicht gefunden.")
        return

    total_rows = ws.max_row
    logger.info(f"Untersuche {total_rows - 1} Verträge auf fehlende Bankdaten...")
    
    for row_idx in range(2, total_rows + 1):
        quelldatei_val = ws.cell(row=row_idx, column=col_idx_quelldatei).value
        
        # Check if IBAN is already filled
        iban_val = ws.cell(row=row_idx, column=col_idx_iban).value
        if iban_val and str(iban_val).strip() and str(iban_val).strip() != "None":
            logger.info(f"Zeile {row_idx}: Überspringe, da IBAN bereits vorhanden ist.")
            continue

        if not quelldatei_val:
            continue

        # Quelldatei_val ist meist ein relativer Pfad oder nur der Dateiname
        pdf_filename = os.path.basename(str(quelldatei_val))
        
        # Suche PDF im Archiv, Eingang oder Fehler-Ordner
        pdf_path = os.path.join(archiv_ordner, pdf_filename)
        if not os.path.exists(pdf_path):
            fallback_path = os.path.join(config["eingang_ordner"], pdf_filename)
            if os.path.exists(fallback_path):
                pdf_path = fallback_path
            else:
                logger.warning(f"Zeile {row_idx}: PDF {pdf_filename} im Archiv nicht gefunden. Überspringe...")
                continue

        logger.info(f"Zeile {row_idx}: Lese Zahlungsinfos aus {pdf_filename}...")
        
        try:
            # Nutze die vorhandenen Funktionen zum Lesen und Extrahieren
            text = extract_text_from_pdf(pdf_path)
            extracted_data = analyze_text_with_ollama(text, formatted_schema)
            
            # Hole Daten
            zahlung = extracted_data.get("Zahlungspflichtiger")
            kredit = extracted_data.get("Kreditinstitut")
            iban = extracted_data.get("IBAN")
            
            # Falls die KI den Namen versehentlich als {Name: X, Vorname: Y} Objekt zurückgibt
            if isinstance(zahlung, dict):
                parts = []
                if "Vorname" in zahlung: parts.append(str(zahlung["Vorname"]))
                if "Name" in zahlung: parts.append(str(zahlung["Name"]))
                elif "Nachname" in zahlung: parts.append(str(zahlung["Nachname"]))
                if not parts: # Fallback falls andere Keys genutzt wurden
                    parts = [str(v) for v in zahlung.values()]
                zahlung = " ".join(parts).strip()
            
            if isinstance(kredit, dict):
                kredit = " ".join(str(v) for v in kredit.values())
            if isinstance(iban, dict):
                iban = " ".join(str(v) for v in iban.values())

            # Trage extrahierte Daten ein
            ws.cell(row=row_idx, column=col_idx_zahlung).value = str(zahlung) if zahlung else ""
            ws.cell(row=row_idx, column=col_idx_kredit).value = str(kredit) if kredit else ""
            ws.cell(row=row_idx, column=col_idx_iban).value = str(iban) if iban else ""
            
            # Speichere nach jedem Vertrag, damit bei einem Abbruch nichts verloren geht
            wb.save(excel_path)
        except Exception as e:
            logger.error(f"Zeile {row_idx}: Fehler bei {pdf_filename}: {e}")

    wb.close()
    logger.info("Backfill erfolgreich abgeschlossen! Deine Excel-Datei ist nun aktuell.")

if __name__ == "__main__":
    backfill()
