import streamlit as st

def aplicar_tema():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }

        /* Esconde menu padrão para parecer app profissional */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}

        div[data-testid="stMetric"] {
            background-color: var(--secondary-background-color);
            border: 1px solid rgba(128,128,128,0.2);
            padding: 15px;
            border-radius: 10px;
            border-left: 5px solid #004280;
        }

        .card-fornecedor {
            background-color: var(--secondary-background-color);
            padding: 25px;
            border-radius: 12px;
            border: 1px solid rgba(128,128,128,0.2);
            margin-bottom: 20px;
            border-top: 5px solid #004280;
        }
    </style>
    """, unsafe_allow_html=True)

