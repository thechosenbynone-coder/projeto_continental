import pandas as pd

def format_brl(v):
    """Converte float para string R$ 1.000,00"""
    if pd.isna(v): return "R$ 0,00"
    try:
        val = f"{float(v):,.2f}"
        return f"R$ {val.replace(',', 'X').replace('.', ',').replace('X', '.')}"
    except:
        return str(v)

def format_perc(v):
    """Converte 0.35 para 35,0%"""
    if pd.isna(v): return "0,0%"
    try:
        val = f"{float(v)*100:.1f}"
        return f"{val.replace('.', ',')}%"
    except:
        return str(v)
