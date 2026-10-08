import streamlit as st
import pandas as pd

# Configurare pagină interfață
st.set_page_config(page_title="Hotel Anvelope MADYT", page_icon="🏨", layout="wide")

st.title("🏨 Sistem Gestiune - Hotel Anvelope MADYT")
st.write("Introdu numărul auto sau seria de șasiu pentru a verifica stocul complet din depozit.")

# Încărcăm baza de date din fișierul local al proiectului tău
@st.cache_data
def incarca_baza_date_locala():
    try:
        # Citim direct fișierul baza_date.csv din folderul tău de pe GitHub
        df = pd.read_csv("baza_date.csv", on_bad_lines='skip')
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Eroare tehnică la încărcarea fișierului local: {e}")
        return None

df_anvelope = incarca_baza_date_locala()

if df_anvelope is not None:
    # Căsuța de Căutare din aplicație
    termen_cautat = st.text_input("🔍 Caută după Număr Auto (ex: B168FRO) sau Seria de Șasiu (VIN):").upper().strip()

    if termen_cautat:
        # Verificăm ce coloane există pentru a evita erori de citire
        # Curățăm coloanele de căutare disponibile în tabelul tău
        cols = df_anvelope.columns
        df_anvelope['Reg_Clean'] = df_anvelope['RegistrationNumber'].astype(str).str.upper().str.strip() if 'RegistrationNumber' in cols else df_anvelope.iloc[:, 3].astype(str).str.upper().str.strip()
        
        # Filtrare flexibilă în funcție de termenul căutat
        rezultate = df_anvelope[df_anvelope['Reg_Clean'].str.contains(termen_cautat, na=False)]
        
        # Căutăm și în coloanele alternative dacă există în tabel
        if 'Fleet VIN' in cols:
            df_anvelope['VIN_Clean'] = df_anvelope['Fleet VIN'].astype(str).str.upper().str.strip()
            rezultate_vin = df_anvelope[df_anvelope['VIN_Clean'].str.contains(termen_cautat, na=False)]
            rezultate = pd.concat([rezultate, rezultate_vin]).drop_duplicates()

        if not rezultate.empty:
            st.success(f"✅ Am găsit {len(rezultate)} anvelope înregistrate în baza de date pentru '{termen_cautat}':")
            
            st.write("### 📋 Detalii piese identificate în stoc:")
            
            # Coloanele cele mai importante din Excel-ul tău pentru afișare ordonată
            coloane_afisare = ['RegistrationNumber', 'FleetName', 'Make/Model', 'BRAND', 'ProductGroup', 'MaterialDescription', 'TreadDepth', 'DOT', 'ServiceProviderStorageLocation', 'StorageNote(Comments/AccessoriesStored)']
            coloane_existente = [c for c in coloane_afisare if c in df_anvelope.columns]
            
            st.dataframe(rezultate[coloane_existente], use_container_width=True)
        else:
            st.warning(f"❌ Nu am găsit nicio înregistrare pentru '{termen_cautat}'. Verifică numărul introdus.")
else:
    st.info("Aplicația se încarcă...")
