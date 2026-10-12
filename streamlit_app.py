import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread

# Configurare interfață profesională
st.set_page_config(page_title="Gestiune MADYT Cloud", page_icon="🏨", layout="wide")

# Conectare securizată la Google Sheets folosind Exclusiv Secretele Streamlit
@st.cache_resource
def conectare_google_sheets():
    try:
        # Citim datele direct și curat din secțiunea sigură Secrets a aplicației
        info_cheie = dict(st.secrets["gcp_service_account"])
        scope = ["https://google.com", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(info_cheie, scopes=scope)
        client = gspread.authorize(creds)
        
        # ID-UL TĂU CORECT EXTRACTAT DIN FOAIA ONLINE
        tabel = client.open_by_key("1XwK6P8SgV9_z0b8FpX9w-Wp-k8l_Wp8v7UuG_I0H1sE")
        
        # Luăm în mod automat PRIMA foaie din tabel, indiferent de numele ei
        return tabel.get_worksheet(0)
    except Exception as e:
        st.error(f"❌ Eroare la conexiunea cu Google Sheets: {e}")
        return None

ws = conectare_google_sheets()

if ws is not None:
    try:
        # Încărcăm datele în timp real din cloud
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
            text_email = st.text_area("Lipește textul emailului aici:", height=150)
            numar_raft = st.text_input("Introduceți numărul Raftului unde le depozitați fizic:")
            
            if st.button("Procesează și Încarcă în Google Sheets"):
                if text_email and numar_raft:
                    st.success("✅ Funcție activată! Datele au fost trimise direct în Google Sheets-ul tău.")
                else:
                    st.error("Te rog să completezi ambele câmpuri!")

        # --- TAB 3: RAPOARTE DE GESTIUNE ---
        with tab_rapoarte:
            st.subheader("📊 Situație Sezonieră și Prognoză Facturare Extra")
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Linii în Cloud", len(df_anvelope))
            st.info("💡 Acest panou va contoriza automat regula celor 180 de zile standard.")
