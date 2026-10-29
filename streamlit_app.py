import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import re
from datetime import datetime

# Configurare interfață profesională
st.set_page_config(page_title="Gestiune MADYT Cloud", page_icon="🏨", layout="wide")

@st.cache_resource
def conectare_google_sheets():
    try:
        # Definirea scope-urilor corecte pentru citire și scriere
        scope = [
            "https://googleapis.com",
            "https://googleapis.com"
        ]
        # LINIA 17 CORECTATĂ: Citim direct fișierul exact așa cum este salvat în repository
        creds = Credentials.from_service_account_file("hotel-anvelope-madyt-8fdbd5da8b0f.json", scopes=scope)
        client = gspread.authorize(creds)
        
        # ID-UL TABELULUI GOOGLE SHEETS
        tabel = client.open_by_key("1qs5DuQ4--vT0Ti91sqH2om4B1dHIm_iyNLnkcvL5IeA")
        return tabel.get_worksheet(0)
    except Exception as e:
        st.error(f"❌ Eroare la conexiunea cu Google Sheets: {e}")
        return None

ws = conectare_google_sheets()

if ws is not None:
    try:
        date_tabel = ws.get_all_records()
        df_anvelope = pd.DataFrame(date_tabel)
        df_anvelope.columns = df_anvelope.columns.str.strip()
        conexiune_ok = True
    except Exception as e:
        st.error(f"Eroare la procesarea datelor din tabel: {e}")
        conexiune_ok = False

    if conexiune_ok:
        tab_cautare, tab_receptie_gy, tab_rapoarte = st.tabs(["🔍 Căutare Stoc", "📦 Recepție Pre-Alertă GY", "📊 Rapoarte Management"])

        with tab_cautare:
            st.subheader("🔍 Verifică Stoc Hotel Anvelope")
            termen_cautat = st.text_input("Introdu Număr Auto, Cod VIN sau Nume Client:").upper().strip()

            if termen_cautat:
                masca = df_anvelope.astype(str).apply(lambda x: x.str.upper().str.contains(termen_cautat, na=False)).any(axis=1)
                rezultate = df_anvelope[masca]

                if not rezultate.empty:
                    st.success(f"✅ Am găsit {len(rezultate)} poziții în stoc în timp real:")
                    ordine_coloane = ['RegistrationNumber', 'FleetName', 'Chassis Num', 'Make/Model', 'MaterialDescription', 'StorageDate', 'TreadDepth', 'DOT', 'StorageNote(Comments/AccessoriesStored)']
                    nume_coloane_ecran = {'RegistrationNumber': 'Număr Auto', 'FleetName': 'Client', 'Chassis Num': 'Serie Șasiu', 'Make/Model': 'Model Mașină', 'MaterialDescription': 'Descriere Material', 'StorageDate': 'Dată Depozitare', 'TreadDepth': 'Adâncime Profil', 'DOT': 'DOT', 'StorageNote(Comments/AccessoriesStored)': 'Observații'}
                    cols_valide = [c for c in ordine_coloane if c in rezultate.columns]
                    st.dataframe(rezultate[cols_valide].rename(columns=nume_coloane_ecran), use_container_width=True)
                else:
                    st.warning(f"❌ Nu am găsit nicio înregistrare pentru '{termen_cautat}'.")

        with tab_receptie_gy:
            st.subheader("📦 Înregistrare Rapidă Loturi noi / Pre-Alertă email")
            text_email = st.text_area("Lipește textul emailului aici:", height=150)
            numar_raft = st.text_input("Introduceți numărul Raftului unde le depozitați fizic:")
            
            if st.button("Procesează și Încarcă în Google Sheets"):
                if text_email and numar_raft:
                    nr_auto_match = re.search(r'\b[A-Z]{1,2}\s*\d{2,3}\s*[A-Z]{3}\b', text_email.upper())
                    vin_match = re.search(r'\b[A-HJ-NPR-Z0-9]{17}\b', text_email.upper())
                    nr_auto = nr_auto_match.group(0).replace(" ", "") if nr_auto_match else "DE COMPLETAT"
                    vin = vin_match.group(0) if vin_match else "DE COMPLETAT"
                    data_curenta = datetime.now().strftime("%Y-%m-%d")
                    
                    rand_nou = {'RegistrationNumber': nr_auto, 'FleetName': "Client Pre-alertă", 'Chassis Num': vin, 'Make/Model': "Identificat din email", 'MaterialDescription': "Set Anvelope", 'StorageDate': data_curenta, 'TreadDepth': "N/A", 'DOT': "N/A", 'StorageNote(Comments/AccessoriesStored)': f"Locație: {numar_raft}."}
                    try:
                        toate_coloanele = df_anvelope.columns.tolist()
                        lista_valori_rand = [rand_nou.get(col, "") for col in toate_coloanele]
                        ws.append_row(lista_valori_rand)
                        st.success("✅ Datele au fost trimise direct în Google Sheets-ul tău!")
                        st.json(rand_nou)
                    except Exception as e:
                        st.error(f"Eroare la scrierea directă: {e}")
                else:
                    st.error("Te rog să completezi ambele câmpuri!")

        with tab_rapoarte:
            st.subheader("📊 Situație Sezonieră și Prognoză Facturare Extra")
            peste_termen = 0
            acum = datetime.now()
            if 'StorageDate' in df_anvelope.columns:
                df_anvelope['StorageDate_Clean'] = pd.to_datetime(df_anvelope['StorageDate'], errors='coerce')
                zile_depozitare = (acum - df_anvelope['StorageDate_Clean']).dt.days
                peste_termen = (zile_depozitare > 180).sum()
                
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Linii în Cloud", len(df_anvelope))
            col2.metric("Peste 180 Zile", int(peste_termen))
            col3.metric("Status Server", "Online")
            if peste_termen > 0:
                st.warning(f"💡 Există {peste_termen} poziții înregistrate care depășesc cele 180 de zile standard.")
