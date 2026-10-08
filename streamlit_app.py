import streamlit as st

# Titlul aplicației tale pentru Hotelul de Anvelope
st.title("🏨 Aplicație Hotel Anvelope")

st.write("Sistem de gestionare și evidență anvelope.")

# Un exemplu de căutare interactivă
nume_client = st.text_input("Caută după numele clientului:")

if nume_client:
    st.info(f"Căutare pornită pentru clientul: {nume_client}")
