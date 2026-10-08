import streamlit as st
import pandas as pd

# Configurare pagină interfață
st.set_page_config(page_title="Hotel Anvelope MADYT", page_icon="🏨", layout="wide")

st.title("🏨 Sistem Gestiune - Hotel Anvelope MADYT")
st.write("Sistem conectat la baza de date completă (1080 rânduri).")

# Încărcare robustă din fișierul local baza_date.csv
@st.cache_data(ttl=60) # Forțează reîmprospătarea la fiecare minut
def incarca_date_robust():
    try:
        # Folosim motorul de Python și ignorăm erorile de formatare cauzate de virgule sau comentarii lungi
        df = pd.read_csv("baza_date.csv", sep=',', engine='python', on_bad_lines='skip')
        # Curățăm spațiile goale din numele coloanelor
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Eroare tehnică la citirea fișierului de date: {e}")
        return None

df_anvelope = incarca_date_robust()

if df_anvelope is not None:
    # Căsuța de Căutare din aplicație
    termen_cautat = st.text_input("🔍 Caută după Număr Auto (ex: B168FRO, B120LLR) sau Seria de Șasiu (VIN):").upper().strip()

    if termen_cautat:
        # Identificăm corect coloanele, chiar dacă numele lor diferă ușor în Excel
        col_auto = 'RegistrationNumber' if 'RegistrationNumber' in df_anvelope.columns else df_anvelope.columns[3]
        col_vin = 'Fleet VIN' if 'Fleet VIN' in df_anvelope.columns else df_anvelope.columns[4]
        
        # Filtrare completă (căutare parțială)
        rezultate = df_anvelope[
            df_anvelope[col_auto].astype(str).str.upper().str.contains(termen_cautat, na=False) |
            df_anvelope[col_vin].astype(str).str.upper().str.contains(termen_cautat, na=False)
        ]

        if not rezultate.empty:
            st.success(f"✅ Am găsit {len(rezultate)} poziții în stoc pentru '{termen_cautat}':")
            
            # Coloanele importante pentru afișarea în service
            coloane_afisare = [col_auto, 'FleetName', 'Make/Model', 'BRAND', 'ProductGroup', 'MaterialDescription', 'TreadDepth', 'DOT', 'ServiceProviderStorageLocation', 'StorageNote(Comments/AccessoriesStored)']
            coloane_existente = [c for c in coloane_afisare if c in df_anvelope.columns]
            
            st.dataframe(rezultate[coloane_existente], use_container_width=True)
        else:
            st.warning(f"❌ Nu am găsit nicio înregistrare pentru '{termen_cautat}'. Asigură-te că fișierul baza_date.csv a fost salvat complet.")
else:
    st.info("Se încarcă structura depozitului...")
