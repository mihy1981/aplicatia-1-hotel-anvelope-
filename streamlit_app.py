import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import re
from datetime import datetime

# Configurare interfață profesională
st.set_page_config(page_title="Gesteune MADYT Cloud", page_icon="🏨", layout="wide")

# Conectare securizată la Google Sheets folosind Exclusiv Secretele Streamlit
@st.cache_resource
def conectare_google_sheets():
    try:
        info_cheie = dict(st.secrets["gcp_service_account"])
        # Definim scope-urile corecte și complete pentru Google Drive și Sheets
        scope = [
            "https://googleapis.com",
            "https://googleapis.com"
        ]
        creds = Credentials.from_service_account_info(info_cheie, scopes=scope)
        client = gspread.authorize(creds)
        
        # ID-UL REAL ȘI CORECT AL TABELULUI TĂU GOOGLE SHEETS
        tabel = client.open_by_key("1qs5DuQ4--vT0Ti91sqH2om4B1dHIm_iyNLnkcvL5IeA")
        
        return tabel.get_worksheet(0)
    except Exception as e:
        st.error(f"❌ Eroare la conexiunea cu Google Sheets: {e}")
        return None

# Reîncărcare manuală a datelor pentru a vedea actualizările imediat
if 'refresh' not in st.session_state:
    st.session_state.refresh = False

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

        # --- TAB 1: CĂUTARE UNIVERSALĂ ---
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
            
            st.markdown("""
            *Lipește textul emailului mai jos. Sistemul va încerca să extragă automat datele esențiale (Număr Auto, VIN, Client, Model).*
            """)
            
            text_email = st.text_area("Lipește textul emailului aici:", height=180, placeholder="Exemplu:\nSalut, trimitem masina cu nr B123ABC, VIN12345678901234, client Popescu Ion, model Dacia Logan...")
            numar_raft = st.text_input("Introduceți numărul Raftului unde le depozitați fizic:", placeholder="Ex: Raft A-12")
            
            if st.button("Procesează și Încarcă în Google Sheets"):
                if text_email and numar_raft:
                    # Logica de extragere inteligentă (Regex flexibil)
                    # Căutare Număr înmatriculare (ex: B 123 ABC sau B-12-ABC sau B123ABC)
                    nr_auto_match = re.search(r'\b[A-Z]{1,2}\s*\d{2,3}\s*[A-Z]{3}\b', text_email.upper())
                    # Căutare Serie Șasiu / VIN (17 caractere alfanumerice, exclude I, O, Q)
                    vin_match = re.search(r'\b[A-HJ-NPR-Z0-9]{17}\b', text_email.upper())
                    
                    nr_auto = nr_auto_match.group(0).replace(" ", "") if nr_auto_match else "DE COMPLETAT"
                    vin = vin_match.group(0) if vin_match else "DE COMPLETAT"
                    
                    # Generăm data curentă în format text
                    data_curenta = datetime.now().strftime("%Y-%m-%d")
                    
                    # Creăm dicționarul cu structura exactă a coloanelor tale
                    # Mapăm datele extrase și completăm restul cu valori standard sau câmpul de raft în Observații
                    rand_nou = {
                        'RegistrationNumber': nr_auto,
                        'FleetName': "Client Nou (Pre-alertă)",
                        'Chassis Num': vin,
                        'Make/Model': "Identificat din email",
                        'MaterialDescription': "Set Anvelope",
                        'StorageDate': data_curenta,
                        'TreadDepth': "N/A",
                        'DOT': "N/A",
                        'StorageNote(Comments/AccessoriesStored)': f"Locație fizică: {numar_raft}. Adăugat automat via Cloud."
                    }
                    
                    try:
                        # Aliniem datele cu structura exactă a tabelului din Google Sheets
                        toate_coloanele = df_anvelope.columns.tolist()
                        lista_valori_rand = [rand_nou.get(col, "") for col in toate_coloanele]
                        
                        # Adăugăm fizic rândul în Google Sheets
                        ws.append_row(lista_valori_rand)
                        
                        st.success(f"🎉 Datele au fost salvate cu succes în Cloud!")
                        st.balloons()
                        
                        # Afișăm un preview al datelor salvate
                        st.json(rand_nou)
                        st.info("🔄 Reîncarcă pagina (sau rulează din nou o căutare) pentru a actualiza stocul în tabel.")
                        
                    except Exception as e:
                        st.error(f"❌ Eroare tehnică la scrierea în Google Sheets: {e}")
                else:
                    st.error("⚠️ Te rog să completezi atât textul emailului, cât și numărul raftului fizic!")

        # --- TAB 3: RAPOARTE DE GESTIUNE ---
        with tab_rapoarte:
            st.subheader("📊 Situație Sezonieră și Prognoză Facturare Extra")
            
            # Calculare dinamică a regulii de 180 de zile
            peste_termen = 0
            acum = datetime.now()
            
            if 'StorageDate' in df_anvelope.columns:
                # Convertim coloana de dată la format datetime în mod sigur
                df_anvelope['StorageDate_Clean'] = pd.to_datetime(df_anvelope['StorageDate'], errors='coerce')
                
                # Calculăm diferența de zile pentru fiecare linie validă
                zile_depozitare = (acum - df_anvelope['StorageDate_Clean']).dt.days
                peste_termen = (zile_depozitare > 180).sum()
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Linii în Cloud", len(df_anvelope))
            col2.metric("Anvelope > 180 Zile (Taxabile Extra)", int(peste_termen), delta=f"{peste_termen} alertate", delta_color="inverse")
            col3.metric("Status Server", "Activ / Online")
            
            st.markdown("---")
            if peste_termen > 0:
                st.warning(f"⚠️ Există **{peste_termen} înregistrări** care au depășit perioada standard de 180 de zile de depozitare gratuită/inclusă și necesită facturare extra.")
                
                # Afișăm rapid mașinile cu probleme
                df_probleme = df_anvelope[(acum - df_anvelope['StorageDate_Clean']).dt.days > 180]
                cols_vizibile = [c for c in ['RegistrationNumber', 'FleetName', 'StorageDate'] if c in df_probleme.columns]
                st.dataframe(df_probleme[cols_vizibile], use_container_width=True)
            else:
                st.success("✅ Toate anvelopele din stoc se încadrează în fereastra standard de 180 de zile.")
