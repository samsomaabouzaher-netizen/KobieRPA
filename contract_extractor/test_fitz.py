try:
    import fitz
    doc = fitz.open(r'C:\Users\samso\OneDrive - Arbeiter-Samariter-Bund Regionalverband Nürnberger Land e. V\Wunderkinder\nemborn App- & Device-Support - Dokumente\General\Wunderkinder\Automatisierung_Adebis\Eingang\Barisch.pdf')
    text = chr(10).join(page.get_text() for page in doc)
    print("fitz success")
    print("Früh in text:", "Früh" in text)
except ImportError:
    print("fitz not installed")
