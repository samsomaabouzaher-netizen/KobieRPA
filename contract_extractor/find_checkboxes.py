import pypdf
import base64
reader = pypdf.PdfReader(r'C:\Users\samso\OneDrive - Arbeiter-Samariter-Bund Regionalverband Nürnberger Land e. V\Wunderkinder\nemborn App- & Device-Support - Dokumente\General\Wunderkinder\Automatisierung_Adebis\Eingang\Barisch.pdf')
fields = reader.get_fields()
for key, value in fields.items():
    decoded_name = key
    try:
        padded_name = key + "=" * ((4 - len(key) % 4) % 4)
        decoded_bytes = base64.b64decode(padded_name.encode('utf-8'), validate=True)
        decoded_name = decoded_bytes.decode('utf-8', errors='ignore')
    except Exception:
        pass

    if 'Einfügebereich' in decoded_name:
        annot = value.indirect_reference.get_object()
        rect = annot.get('/Rect')
        val = value.get('/V', 'No Value')
        if rect:
            print(f"{decoded_name}: {val} | Rect: {rect}")
