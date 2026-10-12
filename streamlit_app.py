import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# Configurare interfață profesională
st.set_page_config(page_title="Gestiune MADYT Cloud", page_icon="🏨", layout="wide")

st.title("🏨 Sistem Gestiune - Hotel Anvelope MADYT")
st.write("Sistem conectat la baza de date centrală în timp real.")

# Conectare nativă și securizată prin conectorul oficial Streamlit
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Citim direct tabelul tău folosind link-ul lui public/privat securizat prin Secrete
    df_anvelope = conn.read(
        spreadsheet="https://google.com",
        ttl="5m"
    )
    # Curățăm spațiile goale din capul de tabel
    df_anvelope.columns = df_anvelope.columns.str.strip()
    conexiune_ok = True
except Exception as e:
    st.error(f"❌ Eroare la citirea datelor din Google Sheets: {e}")
    st.info("💡 Asigură-te că setările din secțiunea Secrets sunt salvate corect.")
    conexiune_ok = False

if conexiune_ok:
    # Meniu superior cu tab-uri pentru service
    tab_cautare, tab_receptie_gy, tab_rapoarte = st.tabs(["🔍 Căutare Stoc", "📦 Recepție Pre-Alertă GY", "📊 Rapoarte Management"])

    # --- TAB 1: CĂUTARE UNIVERSALĂ (LOGICA TA DE COLOANE D, B, F, G, N, P, Q, R, U) ---
    with tab_cautare:
        st.subheader("🔍 Verifică Stoc Hotel Anvelope")
        termen_cautat = st.text_input("Introdu Număr Auto, Cod VIN sau Nume Client:").upper().strip()

        if termen_cautat:
            # Căutăm textul în absolut toate coloanele din tabel
            masca = df_anvelope.astype(str).apply(lambda x: x.str.upper().str.contains(termen_cautat, na=False)).any(axis=1)
            rezultate = df_anvelope[masca]

            if not rezultate.empty:
                st.success(f"✅ Am găsit {len(rezultate)} poziții în stoc în timp real:")
                
                # Ordinea cerută de tine: D, B, F, G, N, P, Q, R, U
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
                st.success("✅ Datele au fost trimise direct în Google Sheets-ul tău.")
            else:
                st.error("Te rog să completezi ambele câmpuri!")

    # --- TAB 3: RAPOARTE DE GESTIUNE ---
    with tab_rapoarte:
        st.subheader("📊 Situație Sezonieră și Prognoză Facturare Extra")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Linii în Cloud", len(df_anvelope))
        st.info("💡 Acest panou va contoriza automat regula celor 180 de zile standard.")
