import pandas as pd
import re

def extrair_ca_epi(texto):
    if not isinstance(texto, str): return None
    # Procura por CA 1234, C.A. 12345
    match = re.search(r'(?i)\bC\.?A\.?[:\s.-]*(\d{3,6})\b', texto)
    if match:
        return match.group(1)
    return None

def validar_compliance(df):
    df = df.copy()
    df['Numero_CA'] = None
    df['Risco_Compliance'] = False
    
    # Verifica se tem 'EPI' na categoria
    mask_epi = df['Categoria'].str.contains('EPI', na=False)
    
    if mask_epi.any():
        df.loc[mask_epi, 'Numero_CA'] = df.loc[mask_epi, 'desc_prod'].apply(extrair_ca_epi)
        # Se é EPI e NÃO tem CA -> Risco
        mask_risco = mask_epi & df['Numero_CA'].isna()
        df.loc[mask_risco, 'Risco_Compliance'] = True
        
    return df
