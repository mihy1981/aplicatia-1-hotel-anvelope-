import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread

# Configurare interfață profesională
st.set_page_config(page_title="Gestiune MADYT Cloud", page_icon="🏨", layout="wide")

# ==============================================================================
# PASUL 2: CONEXIUNE SECURIZATĂ ȘI VERIFICARE STRUCTURĂ DATE
# ==============================================================================

@st.cache_resource
def conectare_google_sheets():
    try:
        # Citim datele din secțiunea sigură Secrets a Streamlit
        info_cheie = dict(st.secrets["gcp_service_account"])
        
        # URL-urile oficiale și corecte pentru acces complet la foi de calcul și drive
        scope = [
            "https://googleapis.com",
            "https://googleapis.com"
        ]
        
        creds = Credentials.from_service_account_info(info_cheie, scopes=scope)
        client = gspread.authorize(creds)
        
        # ID-ul tabelului tău Google Sheets
        tabel = client.open_by_key("1qs5DuQ4--vT0Ti91sqH2om4B1dHIm_iyNLnkcvL5IeA")
        
        # Selectăm prima foaie disponibilă
        return tabel.get_worksheet(0)
    except Exception as e:
        st.error(f"❌ Eroare la conexiunea cu Google Sheets: {e}")
        return None

# Apelăm funcția de conectare
ws = conectare_google_sheets()

# Variabilă de control pentru a ne asigura că totul este pregătit
conexiune_ok = False

if ws is not None:
    try:
        # Încărcăm datele în timp real din cloud
        date_tabel = ws.get_all_records()
        
        if date_tabel:
            df_anvelope = pd.DataFrame(date_tabel)
            # Curățăm eventualele spații libere din numele coloanelor
            df_anvelope.columns = df_anvelope.columns.str.strip()
            conexiune_ok = True
        else:
            st.warning("⚠️ Tabelul din Google Sheets pare să fie gol sau nu are cap de tabel (antet).")
            
    except Exception as e:
        st.error(f"❌ Eroare la procesarea sau descărcarea datelor din tabel: {e}")

# ==============================================================================
# INTERFAȚA WEB (Se activează doar dacă baza de date s-a încărcat corect)
# ==============================================================================
if conexiune_ok:
    # Meniu superior cu tab-uri pentru spetele din service
    tab_cautare, tab_receptie_gy, tab_rapoarte = st.tabs([
        "🔍 Căutare Stoc", 
        "📦 Recepție Pre-Alertă GY", 
        "📊 Rapoarte Management"
    ])

    # --- TAB 1: CĂUTARE UNIVERSALĂ ---
    with tab_cautare:
        st.subheader("🔍 Verifică Stoc Hotel Anvelope")
        termen_cautat = st.text_input("Introdu Număr Auto, Cod VIN sau Nume Client:").upper().strip()

        if termen_cautat:
            # Căutare inteligentă în toate celulele tabelului
            masca = df_anvelope.astype(str).apply(lambda x: x.str.upper().str.contains(termen_cautat, na=False)).any(axis=1)
            rezultate = df_anvelope[masca]

            if not rezultate.empty:
                st.success(f"✅ Am găsit {len(rezultate)} poziții în stoc în timp real:")
                
                # Coloanele exacte pe care vrem să le extragem și să le redenumim prietenos
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
                
                # Afișăm doar coloanele care există fizic în fișierul tău Google Sheets
                cols_valide = [c for c in ordine_coloane if c in rezultate.columns]
                st.dataframe(rezultate[cols_valide].rename(columns=nume_coloane_ecran), use_container_width=True)
            else:
                st.warning(f"❌ Nu am găsit nicio înregistrare pentru '{termen_cautat}'.")

    # --- TAB 2: RECEPȚIE INTELIGENTĂ EMAIL / PRE-ALERTĂ (Macheta pregătită) ---
    with tab_receptie_gy:
        st.subheader("📦 Înregistrare Rapidă Loturi noi / Pre-Alertă email")
        text_email = st.text_area("Lipește textul emailului aici (pentru pasul următor):", height=150)
        numar_raft = st.text_input("Introduceți numărul Raftului unde le depozitați fizic:")
        
        if st.button("Procesează și Încarcă în Google Sheets"):
            if text_email and numar_raft:
                st.info("Logica de salvare va fi integrată la următorul pas.")
            else:
                st.error("Te rog să completezi ambele câmpuri!")

    # --- TAB 3: RAPOARTE DE GESTIUNE (Macheta pregătită) ---
    with tab_rapoarte:
        st.subheader("📊 Situație Sezonieră și Prognoză Facturare Extra")
        col1, col2 = st.columns(2)
        col1.metric("Total Linii în Cloud", len(df_anvelope))
        st.info("💡 Logica pentru regula celor 180 de zile va fi adăugată după ce stabilizăm recepția.")
