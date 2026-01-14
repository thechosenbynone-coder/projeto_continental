import pandas as pd
import re

def extrair_ca_epi(texto):
    """
    Tenta extrair o número do CA (Certificado de Aprovação) da descrição.
    Padrão: CA 1234, CA: 12345, C.A. 1234
    """
    if not isinstance(texto, str): return None
    
    # Regex robusta para capturar "CA" seguido de números
    # Aceita: "CA 12345", "CA: 12345", "C.A 12345"
    match = re.search(r'(?i)\bC\.?A\.?[:\s.-]*(\d{3,6})\b', texto)
    
    if match:
        return match.group(1)
    return None

def validar_compliance(df):
    """
    Aplica regras de compliance na base de dados.
    1. Para itens categorizados como EPI, verifica se existe CA.
    2. Cria coluna 'Compliance_OK' e 'Motivo_Risco'.
    """
    df = df.copy()
    
    # Inicializa colunas
    df['Numero_CA'] = None
    df['Risco_Compliance'] = False
    df['Motivo_Risco'] = None
    
    # --- REGRA 1: EPI SEM CA ---
    # Filtra apenas o que o classificador marcou como EPI
    mask_epi = df['Categoria'].str.contains('EPI', na=False)
    
    if mask_epi.any():
        # Tenta extrair o CA da descrição
        df.loc[mask_epi, 'Numero_CA'] = df.loc[mask_epi, 'desc_prod'].apply(extrair_ca_epi)
        
        # Onde é EPI e o CA é Nulo -> Risco!
        mask_risco_epi = mask_epi & df['Numero_CA'].isna()
        df.loc[mask_risco_epi, 'Risco_Compliance'] = True
        df.loc[mask_risco_epi, 'Motivo_Risco'] = 'EPI sem nº CA na descrição'

    # (Futuramente você pode adicionar regras para Químicos sem Licença, etc.)
    
    return df
