import time
import pandas as pd

excel_path = r"C:\Users\samso\OneDrive - Arbeiter-Samariter-Bund Regionalverband Nürnberger Land e. V\Automatisierung\EingangRPA.xlsx"

for i in range(10):
    try:
        df = pd.read_excel(excel_path, nrows=0)
        columns = df.columns.tolist()
        print("COLUMNS:")
        print(columns)
        break
    except PermissionError:
        print("Excel is locked. Retrying...")
        time.sleep(2)
    except Exception as e:
        print(f"Error: {e}")
        break
