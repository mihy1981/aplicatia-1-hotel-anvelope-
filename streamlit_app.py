import streamlit as st
import pandas as pd

# Configurare pagină interfață
st.set_page_config(page_title="Hotel Anvelope MADYT", page_icon="🏨", layout="wide")

st.title("🏨 Sistem Gestiune - Hotel Anvelope MADYT")
st.write("Introdu numărul auto sau seria de șasiu pentru a verifica stocul din depozit.")

# Încărcăm baza de date completă direct dintr-un link extern securizat ca să nu mai existe erori de cod
@st.cache_data
def incarca_baza_date():
    url_date = "https://pastebin.com"
    try:
        df = pd.read_csv(url_date, on_bad_lines='skip')
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Eroare la conectarea cu baza de date: {e}")
        return None

df_anvelope = incarca_baza_date()

if df_anvelope is not None:
    # Căsuța de Căutare din aplicație
    termen_cautat = st.text_input("🔍 Caută după Număr Auto (ex: B133AJB) sau Seria de Șasiu (VIN):").upper().strip()

    if termen_cautat:
        # Scanare în coloanele RegistrationNumber și br auto
        # Curățăm datele ca să găsească indiferent de spații
        df_anvelope['RegistrationNumber_Clean'] = df_anvelope['RegistrationNumber'].astype(str).str.upper().str.strip()
        df_anvelope['br_auto_clean'] = df_anvelope['SOLD-TO'].astype(str).str.upper().str.strip()
        
        rezultate = df_anvelope[
            (df_anvelope['RegistrationNumber_Clean'].str.contains(termen_cautat, na=False)) | 
            (df_anvelope['br_auto_clean'].str.contains(termen_cautat, na=False)) |
            (df_anvelope['Fleet VIN'].astype(str).str.upper().str.contains(termen_cautat, na=False))
        ]

        if not rezultate.empty:
            st.success(f"✅ Am găsit {len(rezultate)} poziții înregistrate pentru '{termen_cautat}':")
            
            st.write("### 📋 Listă anvelope găsite în depozit:")
            
            # Coloane selectate pentru a fi ușor de urmărit pe ecran
            coloane_afisare = ['SOLD-TO', 'FleetName', 'BRAND', 'ProductGroup', 'MaterialDescription', 'TreadDepth', 'DOT', 'StorageNote(Comments/AccessoriesStored)']
            
            # Redenumim coloana SOLD-TO în Număr Auto dacă conține numere de înmatriculare în unele rânduri
            rezultate_vizibile = rezultate.copy()
            if 'SOLD-TO' in rezultate_vizibile.columns:
                rezultate_vizibile = rezultate_vizibile.rename(columns={'SOLD-TO': 'Număr Auto / Cod'})
                coloane_afisare[0] = 'Număr Auto / Cod'
                
            coloane_existente = [c for c in coloane_afisare if c in rezultate_vizibile.columns]
            
            st.dataframe(rezultate_vizibile[coloane_existente], use_container_width=True)
        else:
            st.warning(f"❌ Nu există nicio înregistrare pentru '{termen_cautat}'. Verifică dacă numărul este corect.")
else:
    st.warning("Baza de date nu a putut fi accesată. Contactați administratorul.")
