import pypdf
reader = pypdf.PdfReader(r'C:\Users\samso\OneDrive - Arbeiter-Samariter-Bund Regionalverband Nürnberger Land e. V\Wunderkinder\nemborn App- & Device-Support - Dokumente\General\Wunderkinder\Automatisierung_Adebis\Eingang\Barisch.pdf')
def visitor_body(text, cm, tm, fontDict, fontSize):
    if len(text.strip()) > 2:
        print(f"TEXT: {text.strip()} | Y: {tm[5]}")

for i, page in enumerate(reader.pages):
    print(f"--- PAGE {i} ---")
    page.extract_text(visitor_text=visitor_body)
