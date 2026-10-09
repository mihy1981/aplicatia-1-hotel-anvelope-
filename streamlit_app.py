import streamlit as st
import pandas as pd
import os

# Configurare pagină interfață
st.set_page_config(page_title="Hotel Anvelope MADYT", page_icon="🏨", layout="wide")

st.title("🏨 Sistem Gestiune - Hotel Anvelope MADYT")
st.write("Sistem profesional conectat la baza de date centrală în timp real.")

# Numele exact al fișierului tău Excel pe care l-ai urcat pe GitHub
NUME_FISIER_EXCEL = "Madyt Inventar 29.07.2026.xlsx"

df_anvelope = None

# Sistemul caută fișierul încărcat permanent pe GitHub
if os.path.exists(NUME_FISIER_EXCEL):
    try:
        df_anvelope = pd.read_excel(NUME_FISIER_EXCEL)
        df_anvelope.columns = df_anvelope.columns.str.strip()
        st.success(f"📊 Bază de date activă: {len(df_anvelope)} linii încărcate automat din server.")
    except Exception as e:
        st.error(f"Eroare la citirea bazei de date centrale: {e}")
else:
    st.info("💡 Aștept încărcarea fișierului Excel pe GitHub...")

# Căsuța de Căutare principală
termen_cautat = st.text_input("🔍 Caută după Număr Auto, Cod VIN sau Nume Client:").upper().strip()

if termen_cautat:
    if df_anvelope is not None:
        # Căutăm textul în absolut toate coloanele din Excel
        masca = df_anvelope.astype(str).apply(lambda x: x.str.upper().str.contains(termen_cautat, na=False)).any(axis=1)
        rezultate = df_anvelope[masca]

        if not rezultate.empty:
            st.success(f"✅ Am găsit {len(rezultate)} poziții în stoc pentru '{termen_cautat}':")
            st.write("### 📋 Detalii piese identificate în depozit:")
            
            # Ordinea ta preferată: D, B, F, G, N, P, Q, R, U
            ordine_coloane = [
                'RegistrationNumber', 'FleetName', 'Chassis Num', 'Make/Model', 
                'MaterialDescription', 'StorageDate', 'TreadDepth', 'DOT', 
                'StorageNote(Comments/AccessoriesStored)'
            ]
            
            nume_coloane_ecran = {
                'RegistrationNumber': 'Număr Auto',
                'FleetName': 'Nume Client / Companie',
                'Chassis Num': 'Serie Șasiu',
                'Make/Model': 'Model Mașină',
                'MaterialDescription': 'Descriere Material',
                'StorageDate': 'Dată Depozitare',
                'TreadDepth': 'Adâncime Profil / Uzură',
                'DOT': 'DOT',
                'StorageNote(Comments/AccessoriesStored)': 'Observații Depozitare'
            }
            
            cols_valide = [c for c in ordine_coloane if c in rezultate.columns]
            tabel_ordonat = rezultate[cols_valide].rename(columns=nume_coloane_ecran)
            
            st.dataframe(tabel_ordonat, use_container_width=True)
        else:
            st.warning(f"❌ Nu am găsit nicio înregistrare în fișier pentru '{termen_cautat}'.")
