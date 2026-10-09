import streamlit as st
import pandas as pd

# Configurare pagină interfață
st.set_page_config(page_title="Hotel Anvelope MADYT", page_icon="🏨", layout="wide")

st.title("🏨 Sistem Gestiune - Hotel Anvelope MADYT")
st.write("Sistem profesional pentru evidența și căutarea anvelopelor în depozit.")

# Meniu în partea stângă pentru încărcarea tabelului tău complet
st.sidebar.header("⚙️ Configurare Bază Date")
fisier_incarcat = st.sidebar.file_uploader("Încarcă fișierul tău Excel (.xlsx) cu toate cele 1080 de linii:", type=["xlsx", "xls"])

df_anvelope = None

# Dacă utilizatorul încarcă fișierul Excel de pe calculator
if fisier_incarcat is not None:
    try:
        # Citim direct foaia de Excel originală
        df_anvelope = pd.read_excel(fisier_incarcat)
        # Curățăm spațiile goale din numele coloanelor
        df_anvelope.columns = df_anvelope.columns.str.strip()
        st.sidebar.success(f"✅ Am încărcat cu succes {len(df_anvelope)} de linii din Excel!")
    except Exception as e:
        st.sidebar.error(f"Eroare la citirea fișierului Excel: {e}")

# Căsuța de Căutare principală
termen_cautat = st.text_input("🔍 Caută după Număr Auto, Cod VIN sau Nume Client:").upper().strip()

if termen_cautat:
    if df_anvelope is not None:
        # Căutăm textul în absolut toate coloanele din Excelul tău
        masca = df_anvelope.astype(str).apply(lambda x: x.str.upper().str.contains(termen_cautat, na=False)).any(axis=1)
        rezultate = df_anvelope[masca]

        if not rezultate.empty:
            st.success(f"✅ Am găsit {len(rezultate)} poziții în stoc pentru '{termen_cautat}':")
            st.write("### 📋 Detalii piese identificate în depozit:")
            
            # Definirea coloanelor tehnice din Excel în ordinea exactă solicitată: D, B, F, G, N, P, Q, R, U
            ordine_coloane = [
                'RegistrationNumber',                      # Coloana D
                'FleetName',                               # Coloana B
                'Chassis Num',                             # Coloana F
                'Make/Model',                              # Coloana G
                'MaterialDescription',                     # Coloana N
                'StorageDate',                             # Coloana P
                'TreadDepth',                              # Coloana Q
                'DOT',                                     # Coloana R
                'StorageNote(Comments/AccessoriesStored)'  # Coloana U
            ]
            
            # Dicționar pentru redenumirea lor pe ecran într-un mod prietenos
            nume_coloane_ecran = {
                'RegistrationNumber': 'Număr Auto (D)',
                'FleetName': 'Nume Client / Companie (B)',
                'Chassis Num': 'Serie Șasiu (F)',
                'Make/Model': 'Model Mașină (G)',
                'MaterialDescription': 'Descriere Material (N)',
                'StorageDate': 'Dată Depozitare (P)',
                'TreadDepth': 'Adâncime Profil / Uzură (Q)',
                'DOT': 'DOT (R)',
                'StorageNote(Comments/AccessoriesStored)': 'Observații Depozitare (U)'
            }
            
            # Păstrăm doar coloanele care există în fișier pentru a preveni erorile de sistem
            cols_valide = [c for c in ordine_coloane if c in rezultate.columns]
            
            # Filtrăm și ordonăm tabelul final exact după lista definită mai sus
            tabel_ordonat = rezultate[cols_valide].rename(columns=nume_coloane_ecran)
            
            st.dataframe(tabel_ordonat, use_container_width=True)
        else:
            st.warning(f"❌ Nu am găsit nicio înregistrare în fișier pentru '{termen_cautat}'.")
    else:
        st.info("💡 Pentru a începe căutarea, te rog să încarci mai întâi fișierul tău Excel folosind butonul din partea stângă!")
else:
    if df_anvelope is None:
        st.info("💡 Aștept încărcarea fișierului Excel în meniul din stânga...")
