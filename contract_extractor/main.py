import os
import json
import time
import shutil
import logging
from pathlib import Path
from typing import Dict, Any

import pypdf
import pdfplumber
import requests
import pandas as pd

# Konfigurationsdatei-Name
CONFIG_FILE = "config.json"
OLLAMA_URL = "http://195.201.114.157:11434/api/generate"
OLLAMA_MODEL = "llama3" # <--- Nutzt jetzt das schlaue 8B Modell!

# Logging konfigurieren
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_or_create_config() -> Dict[str, str]:
    """Lädt die Konfiguration oder fordert den Nutzer zur Eingabe auf, falls sie nicht existiert."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    print("Konfigurationsdatei nicht gefunden. Bitte richte die Pfade ein:")
    config = {
        "eingang_ordner": input("Pfad zum Eingang-Ordner (z.B. ./eingang): ").strip() or "./eingang",
        "archiv_ordner": input("Pfad zum Archiv-Ordner (z.B. ./archiv): ").strip() or "./archiv",
        "fehler_ordner": input("Pfad zum Fehler-Ordner (z.B. ./fehler): ").strip() or "./fehler",
        "excel_pfad": input("Pfad zur Excel-Datei (z.B. ./vertragsdaten.xlsx): ").strip() or "./vertragsdaten.xlsx"
    }
    
    # Erstelle die Ordner, falls sie nicht existieren
    for key in ["eingang_ordner", "archiv_ordner", "fehler_ordner"]:
        Path(config[key]).mkdir(parents=True, exist_ok=True)
        
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
        
    print(f"Konfiguration in {CONFIG_FILE} gespeichert.")
    return config

def get_schema_from_excel(excel_path: str) -> Dict[str, str]:
    """Liest die Spaltenüberschriften aus der Excel-Datei aus und erstellt das JSON-Schema für die KI."""
    if not os.path.exists(excel_path):
        logger.warning(f"Excel-Datei '{excel_path}' nicht gefunden. Es wird kein Schema extrahiert.")
        return {}
    
    try:
        # Lese nur die Überschriften
        df = pd.read_excel(excel_path, nrows=0)
        columns = df.columns.tolist()
        columns = [str(c) for c in columns if not str(c).startswith("Unnamed") and c != "Quelldatei"]
        
        mapping_file = "schema_mapping.json"
        mapping = {}
        
        # Lade existierendes Mapping oder erstelle ein neues
        if os.path.exists(mapping_file):
            with open(mapping_file, 'r', encoding='utf-8') as f:
                mapping = json.load(f)
        else:
            mapping = {col: "" for col in columns}
            with open(mapping_file, 'w', encoding='utf-8') as f:
                json.dump(mapping, f, indent=4, ensure_ascii=False)
        
        schema = {}
        for col in columns:
            beschreibung = mapping.get(col, "").strip()
            if beschreibung:
                schema[col] = f"Extrahiere diese Info: {beschreibung}"
            else:
                schema[col] = f"Extrahiere diese Info: {col}"
            
        logger.info(f"Dynamisches Schema aus Excel eingelesen ({len(schema)} Spalten)")
        return schema
    except Exception as e:
        logger.error(f"Fehler beim Auslesen der Excel-Spalten: {e}")
        return {}

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extrahiert den normalen Text und ausgefüllte, interaktive Formularfelder aus einer PDF."""
    text = ""
    # 1. Normalen Text extrahieren (Hintergrund, Tabellen, Labels)
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        logger.error(f"Fehler beim Lesen des normalen PDF-Textes in {pdf_path}: {e}")
        raise e
        
    # 2. Ausgefüllte Formularfelder auslesen (für nicht-abgeschlossene, editierbare Verträge)
    try:
        import base64
        reader = pypdf.PdfReader(pdf_path)
        fields = reader.get_form_text_fields()
        if fields:
            text += "\n\n--- AUSGEFÜLLTE FORMULARFELDER ---\n"
            for field_name, field_value in fields.items():
                if field_value:
                    # Versuche Base64-Key zu dekodieren
                    decoded_name = field_name
                    try:
                        # Eventuelles Padding korrigieren
                        padded_name = field_name + "=" * ((4 - len(field_name) % 4) % 4)
                        decoded_bytes = base64.b64decode(padded_name.encode('utf-8'), validate=True)
                        decoded_str = decoded_bytes.decode('utf-8', errors='ignore')
                        # Nur übernehmen, wenn es ein lesbarer Text ist
                        if all(c.isprintable() or c in "\n\r\t" for c in decoded_str):
                            decoded_name = decoded_str
                    except Exception:
                        pass
                    
                    text += f"{decoded_name}: {field_value}\n"
    except Exception as e:
        logger.warning(f"Konnte Formularfelder nicht lesen (möglicherweise keine vorhanden): {e}")
        
    return text

def analyze_text_with_ollama(text: str, schema: Dict[str, str]) -> Dict[str, Any]:
    """Sendet den Text an die lokale Ollama-Instanz und fordert ein JSON-Ergebnis basierend auf dem dynamischen Schema an."""
    
    if not schema:
        raise ValueError("Kein Schema aus Excel-Datei erkannt. Bitte Excel-Datei überprüfen.")

    prompt = (
        "Du bist ein professioneller Assistent zur Datenextraktion.\n"
        "Hier ist der Vertragstext:\n"
        "===\n"
        f"{text[:25000]}\n"
        "===\n\n"
        "WICHTIGE ANWEISUNGEN ZUR EXTRAKTION:\n"
        "1. NAMEN AUFTEILEN:\n"
        "   - Wenn ein Name im Text als 'Nachname, Vorname' steht (z.B. 'Banner, Stefanie' oder 'Banner, Michael'):\n"
        "     * Für den Nachnamen (Key mit Endung '.Name') nimm NUR den Nachnamen vor dem Komma (z.B. 'Banner').\n"
        "     * Für den Vornamen (Key mit Endung '.Vorname') nimm NUR den Vornamen nach dem Komma (z.B. 'Stefanie').\n"
        "2. ADRESSEN AUFTEILEN:\n"
        "   - Wenn eine Anschrift als 'Straße | PLZ Ort' steht (z.B. 'Hugo-Dietz-Straße 14 | 91207 Lauf'):\n"
        "     * Für die Straße (Key mit Endung '.Strasse') nimm nur den Teil vor dem '|'.\n"
        "     * Für die PLZ (Key mit Endung '.Plz') nimm nur die 5-stellige Zahl.\n"
        "     * Für den Wohnort (Key mit Endung '.Wohnort') nimm nur den Ortsnamen.\n"
        "3. DATUMSANGABEN FORMATIEREN:\n"
        "   - Alle Datumsangaben (z.B. Geburtsdatum, Vertragsbeginn, Gültigkeit) MÜSSEN im Format 'DD.MM.YYYY' (z.B. '16.12.2019' statt '16/12/2019' oder '2019-12-16') zurückgegeben werden.\n"
        "4. UHRZEITEN FORMATIEREN:\n"
        "   - Alle Uhrzeiten (z.B. Buchungszeiten wie 'bb.MoV1', 'bb.MoB1' etc.) MÜSSEN im Format 'HH:MM' (z.B. '08:00', '16:00' statt '8' oder '16') zurückgegeben werden.\n\n"
        "Bitte extrahiere die Informationen aus dem Text und antworte AUSSCHLIESSLICH mit einem einzigen, gültigen JSON-Objekt.\n"
        "Verwende EXAKT diese JSON-Keys (wenn du etwas nicht findest, setze den Wert auf null):\n"
        f"{json.dumps(schema, ensure_ascii=False, indent=2)}\n"
    )
    
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "format": "json",
        "stream": True, # Streaming hält die Verbindung aktiv
        "options": {
            "num_ctx": 8000, # Verhindert, dass Ollama den Text abschneidet!
            "temperature": 0.0 # Macht die Extraktion deterministisch und präziser!
        }
    }
    
    try:
        # Timeout erhöht und stream=True übergeben
        response = requests.post(OLLAMA_URL, json=payload, stream=True, timeout=300)
        response.raise_for_status()
        
        full_response = ""
        # Lese die Antwort Stück für Stück mit, damit das Netzwerk nicht denkt, die Verbindung sei tot
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line)
                full_response += chunk.get("response", "")
                
        extracted_data = json.loads(full_response)
        return extracted_data
    except json.JSONDecodeError as e:
        logger.error(f"Ollama hat kein valides JSON zurückgegeben: {e}")
        raise ValueError("Invalid JSON response from Ollama")
    except requests.exceptions.RequestException as e:
        logger.error(f"Fehler bei der Verbindung zu Ollama: {e}")
        raise e

def save_to_excel(data: Dict[str, Any], excel_path: str):
    """Speichert die extrahierten Daten in der Excel-Datei."""
    df_new = pd.DataFrame([data])
    
    if os.path.exists(excel_path):
        try:
            df_existing = pd.read_excel(excel_path)
            # Nutze concat, um neue Zeile anzuhängen
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            df_combined.to_excel(excel_path, index=False)
            logger.info(f"Daten erfolgreich in {excel_path} angehängt.")
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren der Excel-Datei: {e}")
            raise e
    else:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(excel_path)), exist_ok=True)
            df_new.to_excel(excel_path, index=False)
            logger.info(f"Neue Excel-Datei {excel_path} erstellt.")
        except Exception as e:
            logger.error(f"Fehler beim Erstellen der Excel-Datei: {e}")
            raise e

def move_file(file_path: str, destination_folder: str, error_msg: str = None) -> str:
    """Verschiebt eine Datei in den Zielordner und gibt den neuen Pfad zurück."""
    filename = os.path.basename(file_path)
    dest_path = os.path.join(destination_folder, filename)
    
    # Stelle sicher, dass der Zielordner existiert
    Path(destination_folder).mkdir(parents=True, exist_ok=True)
    
    try:
        if os.path.exists(dest_path):
            base, ext = os.path.splitext(filename)
            dest_path = os.path.join(destination_folder, f"{base}_{int(time.time())}{ext}")
            
        shutil.move(file_path, dest_path)
        logger.info(f"Datei verschoben nach: {dest_path}")
        
        if error_msg:
            log_path = os.path.join(destination_folder, f"{os.path.basename(dest_path)}.error.log")
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(error_msg)
        return dest_path
    except Exception as e:
        logger.error(f"Konnte Datei {file_path} nicht nach {destination_folder} verschieben: {e}")
        raise e

def process_pdfs(config: Dict[str, str], current_schema: Dict[str, str]):
    """Durchsucht den Eingang-Ordner nach PDFs und verarbeitet diese."""
    eingang = config["eingang_ordner"]
    archiv = config["archiv_ordner"]
    fehler = config["fehler_ordner"]
    excel = config["excel_pfad"]
    
    # Stelle sicher, dass Eingang existiert
    Path(eingang).mkdir(parents=True, exist_ok=True)
    
    pdf_files = [os.path.join(eingang, f) for f in os.listdir(eingang) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        return
        
    for pdf_path in pdf_files:
        logger.info(f"---")
        logger.info(f"Starte Verarbeitung von: {pdf_path}")
        try:
            # 1. Text extrahieren
            text = extract_text_from_pdf(pdf_path)
            
            if not text.strip():
                raise ValueError("PDF enthält keinen extrahierbaren Text.")
                
            # 2. Text analysieren mit dynamischem Schema
            logger.info("Sende Text an Ollama zur Extraktion...")
            extracted_data = analyze_text_with_ollama(text, current_schema)
            logger.info(f"Erfolgreich extrahiert: {list(extracted_data.keys())}")
            
            # Datumsangaben und Uhrzeiten vereinheitlichen
            for k, v in extracted_data.items():
                # 1. Datumsangaben vereinheitlichen
                if isinstance(v, str) and ("dat" in k.lower() or k in ["bb.BelVon", "bb.BelBis"]):
                    cleaned_val = v.strip()
                    cleaned_val = cleaned_val.replace("/", ".")
                    if "-" in cleaned_val and len(cleaned_val) == 10:
                        parts = cleaned_val.split("-")
                        if len(parts) == 3 and len(parts[0]) == 4:
                            cleaned_val = f"{parts[2]}.{parts[1]}.{parts[0]}"
                    extracted_data[k] = cleaned_val
                
                # 2. Uhrzeiten vereinheitlichen (z.B. "8" -> "08:00", "16" -> "16:00")
                elif v is not None and any(day in k for day in ["MoV", "MoB", "DiV", "DiB", "MiV", "MiB", "DoV", "DoB", "FrV", "FrB"]):
                    time_str = str(v).strip().replace(",", ".").replace(" Uhr", "")
                    try:
                        # Fall A: Reine Zahl (z.B. 8, 8.5, 16)
                        val_float = float(time_str)
                        hours = int(val_float)
                        minutes = int(round((val_float - hours) * 60))
                        extracted_data[k] = f"{hours:02d}:{minutes:02d}"
                    except ValueError:
                        # Fall B: Bereits mit Doppelpunkt (z.B. "08:30" oder "8:30")
                        if ":" in time_str:
                            parts = time_str.split(":")
                            if len(parts) == 2:
                                try:
                                    h = int(parts[0])
                                    m = int(parts[1])
                                    extracted_data[k] = f"{h:02d}:{m:02d}"
                                except ValueError:
                                    pass
            
            # 3. Erfolgreich -> Ins Archiv verschieben (vor dem Excel-Speichern, um den finalen Pfad zu kennen)
            final_dest_path = move_file(pdf_path, archiv)
            filename = os.path.basename(final_dest_path)
            
            # Relativen Pfad berechnen, damit der Link auch für andere Personen auf OneDrive funktioniert!
            # Da die Excel-Datei und der Archiv-Ordner beide im selben OneDrive-Ordner liegen,
            # funktioniert ein relativer Pfad wie "Abgeschlossen\dateiname.pdf" auf jedem PC.
            relative_path = os.path.relpath(final_dest_path, start=os.path.dirname(excel))
            
            # Dateiname als klickbaren Hyperlink in die Excel-Tabelle eintragen (Excel XML verlangt intern immer ein Komma, auch bei deutschem Excel!)
            extracted_data["Quelldatei"] = f'=HYPERLINK("{relative_path}", "{filename}")'
            
            # 4. In Excel speichern
            try:
                save_to_excel(extracted_data, excel)
                logger.info(f"Verarbeitung abgeschlossen für: {filename}")
            except Exception as e:
                # Falls Excel gesperrt ist, Datei wieder aus Archiv in Fehlerordner verschieben
                move_file(final_dest_path, fehler, error_msg=f"Excel-Speicherfehler: {e}")
                raise e
            
        except Exception as e:
            logger.error(f"Fehler bei der Verarbeitung von {pdf_path}. Verschiebe in Fehlerordner.")
            move_file(pdf_path, fehler, error_msg=str(e))

def main():
    logger.info("Starte Vertragsdaten-Extraktions-System...")
    config = load_or_create_config()
    
    logger.info(f"Überwache Ordner: {config['eingang_ordner']}")
    logger.info("Drücke STRG+C zum Beenden.")
    
    # Endlosschleife zur kontinuierlichen Überwachung
    try:
        while True:
            # Lese das Schema vor jeder Verarbeitungsschleife neu aus!
            # Wenn du die Excel änderst, übernimmt das Skript die Änderung innerhalb von 10 Sekunden.
            current_schema = get_schema_from_excel(config["excel_pfad"])
            
            if current_schema:
                process_pdfs(config, current_schema)
                
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("\nSystem durch Benutzer beendet.")

if __name__ == "__main__":
    main()
