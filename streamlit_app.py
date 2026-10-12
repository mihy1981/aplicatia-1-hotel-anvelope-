@st.cache_resource
def conectare_google_sheets():
    try:
        # Citim datele din secțiunea sigură Secrets a Streamlit
        info_cheie = dict(st.secrets["gcp_service_account"])
        
        # URL-urile oficiale corecte pentru scopul de autentificare oauth2
        scope = [
            "https://googleapis.com",
            "https://googleapis.com"
        ]
        
        creds = Credentials.from_service_account_info(info_cheie, scopes=scope)
        client = gspread.authorize(creds)
        
        # ID-ul extras cu grijă din URL-ul foii tale de calcul
        # ATENȚIE: Verifică să nu aibă spații înainte sau după ghilimele!
        id_tabel = "1qs5DuQ4--vT0Ti91sqH2om4B1dHIm_iyNLnkcvL5IeA"
        
        tabel = client.open_by_key(id_tabel.strip())
        
        # Luăm prima foaie de lucru (Worksheet 1)
        return tabel.get_worksheet(0)
    except Exception as e:
        st.error(f"❌ Eroare la conexiunea cu Google Sheets: {e}")
        return None
