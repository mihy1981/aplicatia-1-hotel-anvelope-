import streamlit as st
import pandas as pd

# Configurare pagină interfață
st.set_page_config(page_title="Hotel Anvelope MADYT", page_icon="🏨", layout="wide")

st.title("🏨 Sistem Gestiune - Hotel Anvelope MADYT")
st.write("Sistem conectat la baza de date completă (1080 rânduri).")

# Încărcare universală și imună la erori de structură
@st.cache_data(ttl=10)
def incarca_baza_date_universala():
    try:
        # Citim fișierul ignorând erorile de formatare cauzate de virgule sau comentarii lungi
        df = pd.read_csv("baza_date.csv", sep=',', engine='python', on_bad_lines='skip')
        # Curățăm spațiile goale din denumirile tuturor coloanelor
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Eroare tehnică la citirea fișierului de date: {e}")
        return None

df_anvelope = incarca_baza_date_universala()

if df_anvelope is not None:
    # Căsuța de Căutare din aplicație
    termen_cautat = st.text_input("🔍 Caută după Număr Auto, Cod VIN sau Nume Client:").upper().strip()

    if termen_cautat:
        # METODĂ UNIVERSALĂ: Căutăm textul în absolut toate coloanele tabelului deodată
        # Transformăm toate celulele în text brut și verificăm dacă conțin termenul căutat
        masca = df_anvelope.astype(str).apply(lambda x: x.str.upper().str.contains(termen_cautat, na=False)).any(axis=1)
        rezultate = df_anvelope[masca]

        if not rezultate.empty:
            st.success(f"✅ Am găsit {len(rezultate)} poziții în stoc pentru '{termen_cautat}':")
            st.write("### 📋 Detalii piese identificate în depozit:")
            # Afișăm tabelul complet, exact așa cum a fost încărcat
            st.dataframe(rezultate, use_container_width=True)
        else:
            st.warning(f"❌ Nu am găsit nicio înregistrare pentru '{termen_cautat}' în cele 1080 de linii. Verifică textul introdus.")
else:
    st.info("Se încarcă baza de date...")
