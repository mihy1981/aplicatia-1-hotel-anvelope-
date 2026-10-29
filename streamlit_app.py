import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import re
from datetime import datetime

# Configurare interfață profesională
st.set_page_config(page_title="Gestiune MADYT Cloud", page_icon="🏨", layout="wide")

# Conectare securizată securizată cu datele din contul tău de service integrat direct
@st.cache_resource
def conectare_google_sheets():
    try:
        # Datele tale reale transmise de Google Cloud Console
        info_cheie = {
          "type": "service_account",
          "project_id": "hotel-anvelope-madyt",
          "private_key_id": "8fdbd5da8b0ff9e6bc3d740abb08803d2c54ad65",
          "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDB6I3k2feYWRCN\npnZhiEMLg/JsFu4AY+Skx6OBqT5mW6imM/fwCVmGLwl59BMdu5OxsFVNfWLSqS2f\n15CqhYAUhLtGj7gBSfs2ChEEi4KQ7sbQwZAvHlyGoM+9iVpKCIztBHoszl2X1zF7\ndOkoQkbDU7vbzkvT0O/7QC/S+NRCEKgtvlUuehb8sFNggUxNg0137jRo+zeXOQFG\ndmYx92YWPks1fRGwYggHeFoL4AjzkbTSm1miOFgjMb+YdRJXQ47MM7y87/N+3Gsc\nCVQVcTITrFpmtgY+CJVAIW5OMghW8vEQwOoV/c8KTZZl/f4ax9+PhgTLisdO2cb2\nndQFsKqlAgMBAAECggEAAKQRTpA43QYBepuEayW/nGiGfCELIR7X+QJzewCfF1rf\njoDJHIkYhLAyLqTBVmtbCyWyFnsVyiNiOK8z9bzkuDpbFD67SX6pI1vV8ccUaFwC\nPv++fknyONeMAoMuvYjUV9bqsuL/lLFb7DAARNmLg4sdIIQa//t46UukQ641N2Nk\nKUwWa3OTma691FPAkl4BlrjiA1ISZZoNmZUa3dbsMWWErdWyP3uoWJwtRaBPVuZ4\nGncEQjz5qGmNKmmPzEej72JkOVpEremcaL+W+LysYOPgOjQ/IK9V8C0pvgdRRAD8\nk1Djvtrs29ecJaZFDNO+JlzF09bFl0B4P4RUOpcQSQKBgQDf+bmSTl9n53M9JhgC\nzcDRyZaYlWuxC/RmLmDVSu/17q6lRSzkSeuC3JUYS9qFm/g5wmGBu38MqU3CDpVN\nHe7auMhmnqH19vzEF/r0WxdJsMgirFLqEO1irATFnMcIM1Fkg5N1rrjuQDxtQLRp\nLKvFo/OFKoM2bwrGK0X1WHymvQKBgQDdokVWpYWfn5598J3/3w+RO7wrREk+PsJc\nzTdEZnSC0FFiaJanV6Hm/O/OSXFmDb+MnbJXEo5dNdrdi2DPKV06nDa99eCLu0d8\nuCo5sOTPHLv62h4ARbckd1/TZLzABfSF/TNKlHwL0oDxoQ8uamhxbDD7QUQCIuRn\nQJgeFhXmCQKBgFpsvQIXiCcv53OpnIoNPaq1A4ro0IizNeHHGasjTQvyaCorantk\naKP1oHAlt7y3gpj3JFy3MQ0QkWcmchqnWhaOAcKEiwj9xYD52YSr/hPvPm3ZOsRr\nPxvWLTsHF8f0yAiXooIhn2H5JyxIsk3ADj2F+rwptL3WSPhG4kCyj+jVAoGAHOQN\nQ9k5zPACugoGnpcWMWlnAwDYx1to/K3nmWv9nhvHsBtQICpFOZYZMHvUY2hBYvQf\njkgl9LKTgDOt//M1avF4FVUa2zwjeneLUY/kk7b8LhwGsyRjVkaVYDoOfL2J/Xlf\nGUa30Na05kqHbxaB3N8sl2QPmHOx8F+0NJ/OZPkCgYEAlYK/NhZZnXy+rZDVlF1o\nqKjMkUGaFSIOpsKp0zFba3eUUN0wn81mZHKL+IDo6GB3Hnxv4qI6VEQUkaF8N4Az\n+avrUetdEm3RSsq98WU0YlgY7wErxFN1dflLRNG65n5vke3gx/fQ3dELe38vW6aZ\nfQk1yHiZ4hPqx/F90T+TMqM=\n-----END PRIVATE KEY-----\n",
          "client_email": "madyt-hotel@hotel-anvelope-madyt.iam.gserviceaccount.com",
          "client_id": "105244728434298408950",
          "auth_uri": "https://accounts.google.com/o/oauth2/auth",
          "token_uri": "https://oauth2.googleapis.com/token",
          "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
          "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/madyt-hotel%40hotel-anvelope-madyt.iam.gserviceaccount.com",
          "universe_domain": "googleapis.com"
        }
        
        scope = [
            "https://googleapis.com",
            "https://googleapis.com"
        ]
        creds = Credentials.from_service_account_info(info_cheie, scopes=scope)
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
            text_email = st.text_area("Lipește textul emailului aici:", height=150)
            numar_raft = st.text_input("Introduceți numărul Raftului unde le depozitați fizic:")
            
            if st.button("Procesează și Încarcă în Google Sheets"):
                if text_email and numar_raft:
                    # Folosim regex-uri flexibile pentru extragere date
                    nr_auto_match = re.search(r'\b[A-Z]{1,2}\s*\d{2,3}\s*[A-Z]{3}\b', text_email.upper())
                    vin_match = re.search(r'\b[A-HJ-NPR-Z0-9]{17}\b', text_email.upper())
                    
                    nr_auto = nr_auto_match.group(0).replace(" ", "") if nr_auto_match else "DE COMPLETAT"
                    vin = vin_match.group(0) if vin_match else "DE COMPLETAT"
                    data_curenta = datetime.now().strftime("%Y-%m-%d")
                    
                    rand_nou = {
                        'RegistrationNumber': nr_auto,
                        'FleetName': "Client Pre-alertă",
                        'Chassis Num': vin,
                        'Make/Model': "Identificat din email",
                        'MaterialDescription': "Set Anvelope",
                        'StorageDate': data_curenta,
                        'TreadDepth': "N/A",
                        'DOT': "N/A",
                        'StorageNote(Comments/AccessoriesStored)': f"Locație: {numar_raft}."
                    }
                    
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

        # --- TAB 3: RAPOARTE DE GESTIUNE ---
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
