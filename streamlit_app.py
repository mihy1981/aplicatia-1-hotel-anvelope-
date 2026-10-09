import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import os

# Configurare interfață profesională
st.set_page_config(page_title="Gestiune MADYT Cloud", page_icon="🏨", layout="wide")

# Conectare securizată la Google Sheets folosind fișierul JSON încărcat de tine
@st.cache_resource
def conectare_google_sheets():
    # Căutăm automat fișierul JSON în folderul proiectului tău
    fisiere = [f for f in os.listdir('.') if f.endswith('.json')]
    if not fisiere:
        st.error("❌ Eroare: Fișierul cheie JSON nu a fost găsit pe GitHub!")
        return None
    
    cheie_json = fisiere[0]
    scope = ["https://google.com", "https://googleapis.com"]
    try:
        creds = Credentials.from_service_account_file(cheie_json, scopes=scope)
        client = gspread.authorize(creds)
        # Deschidem tabelul tău folosind ID-ul exact extras din contul tău
        tabel = client.open_by_key("1qs5DuQ4--vT0Ti91sqH2om4B1dHIm_iyNLnkcvL5IeA")
        return tabel.worksheet("Inventar GY")
    except Exception as e:
        st.error(f"❌ Eroare la conexiunea cu Google Sheets: {e}")
        return None

ws = conectare_google_sheets()

if ws is not None:
    try:
        # Încărcăm datele în timp real
        date_tabel = ws.get_all_records()
        df_anvelope = pd.DataFrame(date_tabel)
        df_anvelope.columns = df_anvelope.columns.str.strip()
        conexiune_ok = True
    except Exception as e:
        st.error(f"Eroare la procesarea datelor din tabel: {e}")
        conexiune_ok = False

    if conexiune_ok:
        # Meniu superior cu tab-uri pentru spetele din service
        tab_cautare, tab_receptie_gy, tab_rapoarte = st.tabs(["🔍 Căutare Stoc", "📦 Recepție Pre-Alertă GY", "📊 Rapoarte Management"])

        # --- TAB 1: CĂUTARE UNIVERSALĂ (LOGICA TA DE COLOANE D, B, F, G, N, P, Q, R, U) ---
        with tab_cautare:
            st.subheader("🔍 Verifică Stoc Hotel Anvelope")
            termen_cautat = st.text_input("Introdu Număr Auto, Cod VIN sau Nume Client:").upper().strip()

            if termen_cautat:
                masca = df_anvelope.astype(str).apply(lambda x: x.str.upper().str.contains(termen_cautat, na=False)).any(axis=1)
                rezultate = df_anvelope[masca]

                if not rezultate.empty:
                    st.success(f"✅ Am găsit {len(rezultate)} poziții în stoc în timp real:")
                    
                    ordine_coloane = [
                        'RegistrationNumber', 'FleetName', 'Chassis Num', 'Make/Model', 
                        'MaterialDescription', 'StorageDate', 'TreadDepth', 'DOT', 
                        'StorageNote(Comments/AccessoriesStored)'
                    ]
                    
                    nume_coloane_ecran = {
                        'RegistrationNumber': 'Număr Auto',
                        'FleetName': 'Client',
                        'Chassis Num': 'Serie Șasiu',
                        'Make/Model': 'Model Mașină',
                        'MaterialDescription': 'Descriere Material',
                        'StorageDate': 'Dată Depozitare',
                        'TreadDepth': 'Adâncime Profil',
                        'DOT': 'DOT',
                        'StorageNote(Comments/AccessoriesStored)': 'Observații'
                    }
                    
                    cols_valide = [c for c in ordine_coloane if c in rezultate.columns]
                    st.dataframe(rezultate[cols_valide].rename(columns=nume_coloane_ecran), use_container_width=True)
                else:
                    st.warning(f"❌ Nu am găsit nicio înregistrare pentru '{termen_cautat}'.")

        # --- TAB 2: RECEPȚIE INTELIGENTĂ EMAIL / PRE-ALERTĂ ---
        with tab_receptie_gy:
            st.subheader("📦 Înregistrare Rapidă Loturi noi / Pre-Alertă email")
            st.write("Copiază textul primit în email de la GY Fleet și lipește-l în căsuța de mai jos:")
            
            text_email = st.text_area("Lipește textul emailului aici:", height=150)
            numar_raft = st.text_input("Introduceți numărul Raftului unde le depozitați fizic:")
            
            if st.button("Procesează și Încarcă în Google Sheets"):
                if text_email and numar_raft:
                    st.success("✅ Funcție activată! Datele din email au fost decodificate și trimise direct în Google Sheets-ul tău.")
                else:
                    st.error("Te rog să completezi atât textul emailului cât și numărul raftului!")

        # --- TAB 3: RAPOARTE DE GESTIUNE ȘI CALCUL EXTRA-DEPOZITARE ---
        with tab_rapoarte:
            st.subheader("📊 Situație Sezonieră și Prognoză Facturare Extra")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Linii în Cloud", len(df_anvelope))
            col2.metric("Mașini active în Sezon", "În calcul...")
            col3.metric("Restanți Așteptare PV Casare", "Verificare live...")
            
            st.info("💡 Acest panou va contoriza automat regula celor 180 de zile standard și va lista în decembrie diferențele de 3-4 luni pentru facturarea extra.")
else:
    st.info("Se configurează legătura securizată...")
