@st.cache_resource
def conectare_google_sheets():
    try:
        # Citim datele din secțiunea sigură Secrets a Streamlit
        info_cheie = dict(st.secrets["gcp_service_account"])
        
        # METODA NATIVĂ ȘI SIGURĂ: gspread configurează automat URL-urile corecte intern
        client = gspread.service_account_from_dict(info_cheie)
        
        # ID-ul tabelului tău Google Sheets
        id_tabel = "1qs5DuQ4--vT0Ti91sqH2om4B1dHIm_iyNLnkcvL5IeA"
        
        tabel = client.open_by_key(id_tabel.strip())
        
        # Selectăm prima foaie disponibilă
        return tabel.get_worksheet(0)
    except Exception as e:
        st.error(f"❌ Eroare la conexiunea cu Google Sheets: {e}")
        return None
