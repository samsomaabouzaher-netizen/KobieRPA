import pypdf
reader = pypdf.PdfReader(r'C:\Users\samso\OneDrive - Arbeiter-Samariter-Bund Regionalverband Nürnberger Land e. V\Wunderkinder\nemborn App- & Device-Support - Dokumente\General\Wunderkinder\Automatisierung_Adebis\Eingang\Barisch.pdf')
fields = reader.get_fields()
for key, value in fields.items():
    if value.get('/V'):
        print(f"{key}: {value.get('/V')}")
    else:
        print(f"{key}: No Value")
