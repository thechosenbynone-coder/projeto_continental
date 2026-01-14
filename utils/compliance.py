import pandas as pd
import re

def extrair_ca_epi(texto):
    """
    Usa a Regex do relatório para achar Certificado de Aprovação.
    Padrão: CA 12345, CA: 12345, CA-12345
    """
    if not isinstance(texto, str): return None
    # Regex sugerida no relatório: (?i)\bCA[:\s.-]*(\d{4,6})\b
    match = re.search(r'(?i)\bCA[:\s.-]*(\d{3,6})\b', texto)
    if match:
        return match.group(1)
    return None

def validar_compliance(df):
    """
    Roda verificações de segurança baseadas no SUP-PC-05.
    """
    df = df.copy()
    
    # 1. Extração de CA para EPIs
    # Só tenta extrair se for categorizado como EPI
    mask_epi = df['Categoria'].str.contains('EPI')
    df.loc[mask_epi, 'Numero_CA'] = df.loc[mask_epi, 'desc_prod'].apply(extrair_ca_epi)
    
    # 2. Flag de Risco: EPI sem CA
    df['Risco_Compliance'] = False
    df.loc[mask_epi & df['Numero_CA'].isna(), 'Risco_Compliance'] = True
    
    return df
