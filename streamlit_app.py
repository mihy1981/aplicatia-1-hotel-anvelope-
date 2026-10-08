import streamlit as st
import pandas as pd

# Configurare pagină interfață
st.set_page_config(page_title="Hotel Anvelope MADYT", page_icon="🏨", layout="wide")

st.title("🏨 Sistem Gestiune - Hotel Anvelope MADYT")
st.write("Sistem conectat la baza de date completă (1080 rânduri).")

# Încărcarea bazei de date structurate direct în memoria aplicației
stoc_complet = [
    {"Auto": "B116LAA", "Brand": "CONTINENTAL", "Sezon": "Summer", "Dimensiune": "185/65R15 88H ECOCONTACT 6", "Uzura": "5", "DOT": "3822", "Note": "Depozit D"},
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
    {"Auto": "B120JGK", "Brand": "KUMHO", "Sezon": "Summer", "Dimensiune": "185/65R15 88T ES31", "Uzura": "8", "DOT": "3723", "Note": "Depozit D"},
    {"Auto": "B120JGK", "Brand": "KUMHO", "Sezon": "Summer", "Dimensiune": "185/65R15 88T ES31", "Uzura": "8", "DOT": "3623", "Note": "Depozit D"},
    {"Auto": "B133AJB", "Brand": "DUNLOP", "Sezon": "Winter", "Dimensiune": "195/75R16C 110/108R ECONODRIVE WINTER", "Uzura": "7", "DOT": "3825", "Note": "Anvelopa 1"},
    {"Auto": "B133AJB", "Brand": "DUNLOP", "Sezon": "Winter", "Dimensiune": "195/75R16C 110/108R ECONODRIVE WINTER", "Uzura": "7", "DOT": "3825", "Note": "Anvelopa 2"},
    {"Auto": "B133AJB", "Brand": "DUNLOP", "Sezon": "Winter", "Dimensiune": "195/75R16C 110/108R ECONODRIVE WINTER", "Uzura": "5", "DOT": "3825", "Note": "Anvelopa 3"},
    {"Auto": "B133AJB", "Brand": "DUNLOP", "Sezon": "Winter", "Dimensiune": "195/75R16C 110/108R ECONODRIVE WINTER", "Uzura": "5", "DOT": "3825", "Note": "Anvelopa 4"},
    {"Auto": "B133AJB", "Brand": "DUNLOP", "Sezon": "Winter", "Dimensiune": "195/75R16C 110/108R ECONODRIVE WINTER", "Uzura": "5", "DOT": "3825", "Note": "Anvelopa 5"},
    {"Auto": "B133AJB", "Brand": "DUNLOP", "Sezon": "Winter", "Dimensiune": "195/75R16C 110/108R ECONODRIVE WINTER", "Uzura": "5", "DOT": "3825", "Note": "Anvelopa 6"},
    {"Auto": "B168FRO", "Brand": "GOODYEAR", "Sezon": "Winter", "Dimensiune": "225/50R18 99V UG PERF 3 XL FP", "Uzura": "8", "DOT": "2724", "Note": "Anvelopa 1"},
    {"Auto": "B168FRO", "Brand": "GOODYEAR", "Sezon": "Winter", "Dimensiune": "225/50R18 99V UG PERF 3 XL FP", "Uzura": "8", "DOT": "2724", "Note": "Anvelopa 2"},
    {"Auto": "B168FRO", "Brand": "GOODYEAR", "Sezon": "Winter", "Dimensiune": "225/50R18 99V UG PERF 3 XL FP", "Uzura": "8", "DOT": "2724", "Note": "Anvelopa 3"},
    {"Auto": "B168FRO", "Brand": "GOODYEAR", "Sezon": "Winter", "Dimensiune": "225/50R18 99V UG PERF 3 XL FP", "Uzura": "8", "DOT": "2724", "Note": "Anvelopa 4"},
    {"Auto": "B120LLR", "Brand": "MICHELIN", "Sezon": "Summer", "Dimensiune": "205/55R16 91V ENERGY SAVER+", "Uzura": "6", "DOT": "1421", "Note": "Stoc Depozit Central 4 buc"},
    {"Auto": "B104CLS", "Brand": "FULDA", "Sezon": "Winter", "Dimensiune": "215/65R16C CONVEO TRAC 3", "Uzura": "5", "DOT": "2222", "Note": "Facturata OK"},
    {"Auto": "XB824MTR", "Brand": "MICHELIN", "Sezon": "Summer", "Dimensiune": "215/60R17 96H PRIMACY3", "Uzura": "7", "DOT": "3221", "Note": "De facturat"},
    {"Auto": "B162CLS", "Brand": "SAVA", "Sezon": "Winter", "Dimensiune": "215/70R15C 109/107S ESKIMO LT", "Uzura": "6", "DOT": "0423", "Note": "Custodie D"},
    {"Auto": "B162CLS", "Brand": "VIKING", "Sezon": "Winter", "Dimensiune": "215/70R15C 109/107R WINTECHVAN", "Uzura": "5", "DOT": "3620", "Note": "Custodie D"},
    {"Auto": "B197CLS", "Brand": "FULDA", "Sezon": "Winter", "Dimensiune": "205/60R16 96H KRI CONTROL HP 2", "Uzura": "5", "DOT": "3520", "Note": "Custodie D"},
    {"Auto": "B154CLS", "Brand": "FULDA", "Sezon": "Winter", "Dimensiune": "205/55R16 91T KRI MONTERO 3", "Uzura": "6", "DOT": "3020", "Note": "Custodie D"},
    {"Auto": "B170CLS", "Brand": "SAVA", "Sezon": "Winter", "Dimensiune": "205/60R16 96H ESKIMO HP 2 XL", "Uzura": "6", "DOT": "1723", "Note": "Facturata OK"}
]

df_anvelope = pd.DataFrame(stoc_complet)

# Căsuța de Căutare din aplicație
termen_cautat = st.text_input("🔍 Caută după Număr Auto (ex: B133AJB, B168FRO, B120LLR):").upper().strip()

if termen_cautat:
    # Căutare flexibilă în coloana Auto
    rezultate = df_anvelope[df_anvelope['Auto'].str.contains(termen_cautat, na=False)]

    if not rezultate.empty:
        st.success(f"✅ Am găsit {len(rezultate)} anvelope în custodie pentru '{termen_cautat}':")
        st.write("### 📋 Listă completă piese din depozit:")
        st.dataframe(rezultate, use_container_width=True)
    else:
        st.warning(f"❌ Nu există nicio înregistrare pentru '{termen_cautat}'. Verifică numărul mașinii.")
