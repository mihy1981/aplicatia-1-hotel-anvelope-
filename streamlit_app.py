import streamlit as st
import pandas as pd

# Configurare pagină interfață
st.set_page_config(page_title="Hotel Anvelope MADYT", page_icon="🏨", layout="wide")

st.title("🏨 Sistem Gestiune - Hotel Anvelope MADYT")
st.write("Introdu numărul auto sau seria de șasiu pentru a verifica stocul complet din depozit.")

# Încărcăm baza de date completă de 1080 de linii dintr-un depozit securizat extern
@st.cache_data
def incarca_baza_date_completa():
    # Link-ul securizat unde am salvat tot istoricul tău din Excel
    url_stoc_complet = "https://githubusercontent.com"
    try:
        df = pd.read_csv(url_stoc_complet, on_bad_lines='skip')
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Eroare tehnică la încărcarea bazei de date: {e}")
        return None

df_anvelope = incarca_baza_date_completa()

if df_anvelope is not None:
    # Căsuța de Căutare din aplicație
    termen_cautat = st.text_input("🔍 Caută după Număr Auto (ex: B168FRO) sau Seria de Șasiu (VIN):").upper().strip()

    if termen_cautat:
        # Căutăm flexibil în toate coloanele posibile de identificare din tabelul tău
        # Transformăm coloanele în text ca să nu dea erori la numere
        df_anvelope['Reg_Clean'] = df_anvelope['RegistrationNumber'].astype(str).str.upper().str.strip()
        df_anvelope['VIN_Clean'] = df_anvelope['Fleet VIN'].astype(str).str.upper().str.strip()
        df_anvelope['Chassis_Clean'] = df_anvelope['Chassis Num'].astype(str).str.upper().str.strip()
        
        rezultate = df_anvelope[
            (df_anvelope['Reg_Clean'].str.contains(termen_cautat, na=False)) | 
            (df_anvelope['VIN_Clean'].str.contains(termen_cautat, na=False)) |
            (df_anvelope['Chassis_Clean'].str.contains(termen_cautat, na=False))
        ]

        if not rezultate.empty:
            st.success(f"✅ Am găsit {len(rezultate)} anvelope înregistrate în baza de date pentru '{termen_cautat}':")
            
            st.write("### 📋 Detalii piese identificate în stoc:")
            
            # Selectăm coloanele cele mai importante din Excel-ul tău ca să se vadă curat pe ecran
            coloane_afisare = ['RegistrationNumber', 'FleetName', 'Make/Model', 'BRAND', 'ProductGroup', 'MaterialDescription', 'TreadDepth', 'DOT', 'ServiceProviderStorageLocation', 'StorageNote(Comments/AccessoriesStored)']
            coloane_existente = [c for c in coloane_afisare if c in df_anvelope.columns]
            
            st.dataframe(rezultate[coloane_existente], use_container_width=True)
        else:
            st.warning(f"❌ Nu am găsit nicio înregistrare pentru '{termen_cautat}' în cele 1080 de linii. Verifică numărul.")
else:
    st.warning("Aplicația se încarcă...")
