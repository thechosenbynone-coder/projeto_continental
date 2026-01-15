import pandas as pd
import numpy as np

def validar_compliance(df):
    """
    Define a documentação exigida baseada na Categoria do item.
    """
    # 1. Cria colunas padrão
    df['Risco_Compliance'] = False
    df['Doc_Obrigatoria'] = "N/A"
    
    # Normaliza categoria para evitar erros de caixa alta/baixa
    cat = df['Categoria'].astype(str).str.upper()

    # ==========================================================================
    # MATRIZ DE DOCUMENTAÇÃO (REGRA DE NEGÓCIO)
    # ==========================================================================
    
    # 1. QUÍMICOS (Risco Ambiental e Saúde)
    # Regra: Todo produto químico precisa de FISPQ atualizada.
    mask_quim = cat.str.contains('QUÍMICO|QUIMICO')
    df.loc[mask_quim, 'Risco_Compliance'] = True
    df.loc[mask_quim, 'Doc_Obrigatoria'] = "FISPQ + Ficha Emergência"

    # 2. IÇAMENTO (Risco de Acidente Fatal)
    # Regra: Cabos, cintas e manilhas precisam de teste de tração.
    mask_ica = cat.str.contains('IÇAMENTO|ICAMENTO')
    df.loc[mask_ica, 'Risco_Compliance'] = True
    df.loc[mask_ica, 'Doc_Obrigatoria'] = "Certificado de Teste de Carga"

    # 3. ELÉTRICA (Risco de Incêndio/Choque - NR10)
    # Regra: Itens de baixa/média tensão precisam de conformidade.
    mask_elet = cat.str.contains('ELÉTRICA|ELETRICA')
    df.loc[mask_elet, 'Risco_Compliance'] = True
    df.loc[mask_elet, 'Doc_Obrigatoria'] = "Certificado Conformidade / INMETRO"

    # 4. EPI (Risco de Proteção Pessoal - NR6)
    # Regra: Precisa de CA válido.
    mask_epi = cat.str.contains('EPI')
    df.loc[mask_epi, 'Risco_Compliance'] = True
    df.loc[mask_epi, 'Doc_Obrigatoria'] = "CA (Certificado de Aprovação)"

    # 5. VASOS DE PRESSÃO / HIDRÁULICA CRÍTICA (Opcional - NR13)
    # Se quiser ser rigorosa com válvulas de segurança
    mask_nr13 = (cat.str.contains('HIDRÁULICA')) & (df['desc_prod'].str.contains('SEGURANCA|ALIVIO|CALDEIRA'))
    df.loc[mask_nr13, 'Risco_Compliance'] = True
    df.loc[mask_nr13, 'Doc_Obrigatoria'] = "Prontuário NR-13 / Calibração"

    return df
