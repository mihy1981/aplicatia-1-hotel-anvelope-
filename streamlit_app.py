import streamlit as st
import pandas as pd

# Configurare pagină interfață
st.set_page_config(page_title="Hotel Anvelope MADYT", page_icon="🏨", layout="wide")

st.title("🏨 Sistem Gestiune - Hotel Anvelope MADYT")
st.write("Introdu numărul auto sau seria de șasiu pentru a verifica stocul din depozit.")

# Baza de date structurată special ca să nu mai apară erori de sintaxă
date_curate = [
    {"Auto": "B116LAA", "Brand": "CONTINENTAL", "Sezon": "Summer", "Dimensiune": "185/65R15 88H ECOCONTACT 6", "Uzura": "5", "DOT": "3822", "Note": ""},
    {"Auto": "B119FEK", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2323", "Note": "NU SUNT LA NOI"},
    {"Auto": "B119FEK", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2323", "Note": "Ultima discutie in data de 28.12.2023"},
    {"Auto": "B119FEK", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2323", "Note": "Galati"},
    {"Auto": "B119FHR", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2323", "Note": "NU SUNT LA NOI"},
    {"Auto": "B119FHR", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2323", "Note": "Sixt Bucuresti"},
    {"Auto": "B119FHS", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2323", "Note": "NU SUNT LA NOI"},
    {"Auto": "B119FHS", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2323", "Note": "Sixt Bucuresti"},
    {"Auto": "B119FHU", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2323", "Note": "NU SUNT LA NOI"},
    {"Auto": "B119FHU", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2323", "Note": "Sixt Bucuresti"},
    {"Auto": "B119FHZ", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2323", "Note": "NU SUNT LA NOI"},
    {"Auto": "B119FHZ", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2323", "Note": "Brasov"},
    {"Auto": "B119FID", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2323", "Note": "NU SUNT LA NOI"},
    {"Auto": "B119FID", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2323", "Note": "Cluj"},
    {"Auto": "B119FIF", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2323", "Note": "NU SUNT LA NOI"},
    {"Auto": "B119FIF", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2323", "Note": "Cluj"},
    {"Auto": "B119FIG", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2323", "Note": "NU SUNT LA NOI"},
    {"Auto": "B119FIG", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2323", "Note": "Constanta"},
    {"Auto": "B119FIH", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2323", "Note": "NU SUNT LA NOI"},
    {"Auto": "B119FIH", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2323", "Note": "Constanta"},
    {"Auto": "B119FIK", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2323", "Note": "NU SUNT LA NOI"},
    {"Auto": "B119FIK", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2323", "Note": "Craiova"},
    {"Auto": "B119FIR", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2323", "Note": "NU SUNT LA NOI"},
    {"Auto": "B119FIR", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2323", "Note": "Craiova"},
    {"Auto": "B119FIW", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2523", "Note": "NU SUNT LA NOI"},
    {"Auto": "B119FIW", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2523", "Note": "Iasi"},
    {"Auto": "B119FJC", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2323", "Note": "NU SUNT LA NOI"},
    {"Auto": "B119FJC", "Brand": "BRIDGESTONE", "Sezon": "Summer", "Dimensiune": "225/65R17 102V TURANZA ECO ENLITEN", "Uzura": "6", "DOT": "2323", "Note": "Timisoara"},
    {"Auto": "B120JGK", "Brand": "KUMHO", "Sezon": "Summer", "Dimensiune": "185/65R15 88T ES31", "Uzura": "8", "DOT": "3723", "Note": "Baza Date D"},
    {"Auto": "B120JGK", "Brand": "KUMHO", "Sezon": "Summer", "Dimensiune": "185/65R15 88T ES31", "Uzura": "8", "DOT": "3623", "Note": "Baza Date D"},
    {"Auto": "B133AJB", "Brand": "DUNLOP", "Sezon": "Winter", "Dimensiune": "195/75R16C 110/108R ECONODRIVE", "Uzura": "7", "DOT": "3825", "Note": "Anvelopa 1"},
    {"Auto": "B133AJB", "Brand": "DUNLOP", "Sezon": "Winter", "Dimensiune": "195/75R16C 110/108R ECONODRIVE", "Uzura": "7", "DOT": "3825", "Note": "Anvelopa 2"},
    {"Auto": "B133AJB", "Brand": "DUNLOP", "Sezon": "Winter", "Dimensiune": "195/75R16C 110/108R ECONODRIVE", "Uzura": "5", "DOT": "3825", "Note": "Anvelopa 3"},
    {"Auto": "B133AJB", "Brand": "DUNLOP", "Sezon": "Winter", "Dimensiune": "195/75R16C 110/108R ECONODRIVE", "Uzura": "5", "DOT": "3825", "Note": "Anvelopa 4"},
    {"Auto": "B133AJB", "Brand": "DUNLOP", "Sezon": "Winter", "Dimensiune": "195/75R16C 110/108R ECONODRIVE", "Uzura": "5", "DOT": "3825", "Note": "Anvelopa 5"},
    {"Auto": "B133AJB", "Brand": "DUNLOP", "Sezon": "Winter", "Dimensiune": "195/75R16C 110/108R ECONODRIVE", "Uzura": "5", "DOT": "3825", "Note": "Anvelopa 6"}
]

df_anvelope = pd.DataFrame(date_curate)

# Căsuța de Căutare din aplicație
termen_cautat = st.text_input("🔍 Caută după Număr Auto (ex: B133AJB sau B119FEK):").upper().strip()

if termen_cautat:
    # Filtrare
    rezultate = df_anvelope[df_anvelope['Auto'].str.contains(termen_cautat, na=False)]

    if not rezultate.empty:
        st.success(f"✅ Am găsit {len(rezultate)} anvelope în custodie pentru '{termen_cautat}':")
        
        st.write("### 📋 Listă completă piese din depozit:")
        st.dataframe(rezultate, use_container_width=True)
    else:
        st.warning(f"❌ Nu există nicio înregistrare pentru '{termen_cautat}'.")
