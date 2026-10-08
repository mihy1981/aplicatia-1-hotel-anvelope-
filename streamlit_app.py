import streamlit as st
import pandas as pd

# Configurare pagină interfață
st.set_page_config(page_title="Hotel Anvelope MADYT", page_icon="🏨", layout="wide")

st.title("🏨 Sistem Gestiune - Hotel Anvelope MADYT")
st.write("Sistem conectat la baza de date completă (1080 rânduri).")

# Încărcare securizată și robustă din fișierul tău baza_date.csv
@st.cache_data(ttl=60)
def incarca_stoc_complet():
    try:
        # Citim fișierul ignorând eventualele linii defecte din Excel
        df = pd.read_csv("baza_date.csv", sep=',', engine='python', on_bad_lines='skip')
        # Curățăm spațiile goale din numele coloanelor
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Eroare tehnică la citirea bazei de date: {e}")
        return None

df_anvelope = incarca_stoc_complet()

if df_anvelope is not None:
    # Căsuța de Căutare principală
    termen_cautat = st.text_input("🔍 Caută după Număr Auto (ex: B115ZFL) sau Seria de Șasiu (VIN):").upper().strip()

    if termen_cautat:
        # Identificăm coloanele corecte din Excelul tău
        col_auto = 'RegistrationNumber' if 'RegistrationNumber' in df_anvelope.columns else df_anvelope.columns[3]
        col_vin = 'Fleet VIN' if 'Fleet VIN' in df_anvelope.columns else df_anvelope.columns[4]
        col_chassis = 'Chassis Num' if 'Chassis Num' in df_anvelope.columns else df_anvelope.columns[5]
        
        # Căutare flexibilă (găsește mașina chiar dacă scrii doar o parte din număr)
        rezultate = df_anvelope[
            df_anvelope[col_auto].astype(str).str.upper().str.contains(termen_cautat, na=False) |
            df_anvelope[col_vin].astype(str).str.upper().str.contains(termen_cautat, na=False) |
            df_anvelope[col_chassis].astype(str).str.upper().str.contains(termen_cautat, na=False)
        ]

        if not rezultate.empty:
            st.success(f"✅ Am găsit {len(rezultate)} anvelope în stoc pentru '{termen_cautat}':")
            
            # Selectăm doar coloanele importante din Excel ca să arate curat pe ecran
            coloane_afisare = [col_auto, 'FleetName', 'Make/Model', 'BRAND', 'ProductGroup', 'MaterialDescription', 'TreadDepth', 'DOT', 'ServiceProviderStorageLocation', 'StorageNote(Comments/AccessoriesStored)']
            coloane_existente = [c for c in coloane_afisare if c in df_anvelope.columns]
            
            st.dataframe(rezultate[coloane_existente], use_container_width=True)
        else:
            st.warning(f"❌ Nu am găsit nicio înregistrare pentru '{termen_cautat}' în cele 1080 de linii. Verifică numărul introdus.")
else:
    st.info("Se încarcă baza de date...")
