import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta

# Configurare pagină Streamlit
st.set_page_config(
    page_title="Gestiune MADYT Cloud",
    page_icon="🛞",
    layout="wide"
)

# ID-ul tabelului tău Google Sheets (Înlocuiește cu ID-ul tău real)
SPREADSHEET_ID = "ID_TABEL_GOOGLE_SHEETS_AICI"

# Funcție pentru inițializarea conexiunii fără cache (evită erorile JWT)
def get_gsheet_client():
    scopes = [
        "https://googleapis.com",
        "https://googleapis.com"
    ]
    # Citire cheie din fișierul local specificat
    credentials = Credentials.from_service_account_file("cheie_google.json", scopes=scopes)
    client = gspread.authorize(credentials)
    return client

def load_data():
    try:
        client = get_gsheet_client()
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1
        data = sheet.get_all_records()
        return pd.DataFrame(data), sheet
    except Exception as e:
        st.error(f"Eroare la conectarea cu Google Sheets: {e}")
        return pd.DataFrame(), None

# Încărcare date curente
df, google_sheet = load_data()

st.title("🛞 Gestiune MADYT Cloud")
st.subheader("Sistem de Gestiune Hotel Anvelope")

if df.empty:
    st.warning("Nu s-au putut încărca datele sau tabelul este gol. Asigură-te că fișierul 'cheie_google.json' este corect și ID-ul tabelului este valid.")
else:
    # Creare structură tab-uri cerută
    tab1, tab2, tab3 = st.tabs(["🔍 Căutare Stoc", "📦 Recepție Pre-Alertă", "📊 Rapoarte Management"])

    # ---------------------------------------------------------
    # TAB 1: CĂUTARE STOC
    # ---------------------------------------------------------
    with tab1:
        st.header("Căutare Rapidă în Stoc")
        
        col1, col2 = st.columns(2)
        with col1:
            search_query = st.text_input("Caută după Nume Client, Nr. Înmatriculare sau Telefon:")
        with col2:
            status_filter = st.selectbox("Filtrează după Status:", ["Toate", "Depozitat", "Eliberat"])
            
        # Filtrare date
        filtered_df = df.copy()
        if search_query:
            # Căutare parțială indiferent de majuscule pe coloanele principale
            search_mask = (
                filtered_df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)
            )
            filtered_df = filtered_df[search_mask]
            
        if status_filter != "Toate" and "Status" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Status"].str.lower() == status_filter.lower()]
            
        st.dataframe(filtered_df, use_container_width=True)

    # ---------------------------------------------------------
    # TAB 2: RECEPȚIE PRE-ALERTĂ
    # ---------------------------------------------------------
    with tab2:
        st.header("Adăugare Anvelope (Pre-Alertă)")
        
        with st.form("form_receptie"):
            col_a, col_b = st.columns(2)
            
            with col_a:
                nume = st.text_input("Nume Client *")
                telefon = st.text_input("Telefon *")
                nr_auto = st.text_input("Număr Înmatriculare *")
                dimensiune = st.text_input("Dimensiune Anvelope (ex: 205/55 R16) *")
            
            with col_b:
                brand = st.text_input("Brand / Producător *")
                cantitate = st.number_input("Cantitate (Bucăți)", min_value=1, max_value=8, value=4)
                pozitie = st.text_input("Locație Depozit / Raft (Opțional)")
                observatii = st.text_area("Observații / Detalii uzură")
                
            submit_btn = st.form_submit_button("Înregistrează Pre-Alertă")
            
            if submit_btn:
                if not nume or not telefon or not nr_auto or not dimensiune or not brand:
                    st.error("Te rog completează toate câmpurile obligatorii marcate cu (*).")
                else:
                    # Pregătire rând nou conform structurii standard a foii tale
                    data_curenta = datetime.now().strftime("%Y-%m-%d")
                    rand_nou = [
                        data_curenta, nume, telefon, nr_auto, dimensiune, 
                        brand, int(cantitate), pozitie, "Depozitat", observatii
                    ]
                    
                    try:
                        # Re-inițializare conexiune pentru salvare directă
                        client_write = get_gsheet_client()
                        sheet_write = client_write.open_by_key(SPREADSHEET_ID).sheet1
                        sheet_write.append_row(rand_nou)
                        st.success(f"Pre-alerta pentru clientul {nume} a fost înregistrată cu succes în Google Sheets!")
                        # Rerulare aplicație pentru a actualiza stocul instant
                        st.rerun()
                    except Exception as e:
                        st.error(f"Eroare la scrierea datelor: {e}")

    # ---------------------------------------------------------
    # TAB 3: RAPOARTE MANAGEMENT (Regula celor 180 de zile)
    # ---------------------------------------------------------
    with tab3:
        st.header("Analiză și Regula celor 180 de zile")
        st.write("Identificarea anvelopelor care au depășit termenul de depozitare standard de 180 de zile.")
        
        if "Data Depozitare" in df.columns:
            # Conversie coloană în format dată
            df["Data Depozitare DT"] = pd.to_datetime(df["Data Depozitare"], errors='coerce')
            
            limita_zile = datetime.now() - timedelta(days=180)
            
            # Filtrare stocuri vechi
            anvelope_vechi = df[
                (df["Data Depozitare DT"] < limita_zile) & 
                (df["Status"].str.lower() == "depozitat")
            ]
            
            # KPI Cards
            c1, c2 = st.columns(2)
            with c1:
                st.metric("Total Seturi Depozitate", len(df[df["Status"].str.lower() == "depozitat"]))
            with c2:
                st.metric("Seturi Peste Termen (180+ Zile)", len(anvelope_vechi), delta_color="inverse")
                
            st.subheader("Lista alertă: Anvelope ce necesită contactarea clientului")
            if not anvelope_vechi.empty:
                # Curățare coloană temporară înainte de afișare
                afisaj_vechi = anvelope_vechi.drop(columns=["Data Depozitare DT"])
                st.dataframe(afisaj_vechi, use_container_width=True)
            else:
                st.success("Felicitări! Nu există anvelope care să fi depășit termenul de 180 de zile în stocul activ.")
        else:
            st.error("Pentru acest raport este necesară o coloană numită exact 'Data Depozitare' în Google Sheets.")
