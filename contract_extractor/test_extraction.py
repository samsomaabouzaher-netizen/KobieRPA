import os
import json
import logging
from main import extract_text_from_pdf, analyze_text_with_ollama, load_or_create_config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test():
    config = load_or_create_config()
    pdf_path = os.path.join(config["archiv_ordner"], "Betreuungsvertrag - Harime Lemouele Djouken.pdf")
    
    if not os.path.exists(pdf_path):
        # Fallback to Eingang in case they moved it
        pdf_path = os.path.join(config["eingang_ordner"], "Betreuungsvertrag - Harime Lemouele Djouken.pdf")
        
    if not os.path.exists(pdf_path):
        print(f"Error: PDF not found at {pdf_path}")
        return
        
    print(f"Reading PDF from: {pdf_path}")
    text = extract_text_from_pdf(pdf_path)
    
    # Load schema mapping directly from json
    mapping_file = "schema_mapping.json"
    with open(mapping_file, 'r', encoding='utf-8') as f:
        mapping = json.load(f)
        
    schema = {}
    for col, beschreibung in mapping.items():
        beschreibung = beschreibung.strip()
        if beschreibung:
            schema[col] = f"Extrahiere diese Info: {beschreibung}"
        else:
            schema[col] = f"Extrahiere diese Info: {col}"
        
    print(f"\nSending to Ollama with current main.py config...")
    try:
        result = analyze_text_with_ollama(text, schema)
        print("\n--- OLLAMA RAW JSON RESULT ---")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
