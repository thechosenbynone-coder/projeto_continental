import numpy as np
import pandas as pd

def classificar_materiais_turbo(df):
    """
    Classificação de Alta Precisão (V3)
    Critérios: NCM (Natureza) + Descrição (Aplicação) + Fiscal (CST/CSOSN)
    """
    # 1. Preparação e Limpeza
    desc = df['desc_prod'].astype(str).str.upper().str.strip()
    ncm = df['ncm'].astype(str).str.replace('.', '', regex=False).str.strip()
    u_med = df['u_medida'].astype(str).str.upper().str.strip()
    
    # Captura do código tributário (CST ou CSOSN)
    # 500 (Simples) e 060 (Normal) indicam Substituição Tributária (comum em Óleos/Químicos)
    fiscal_st = df['cod_tributario'].isin(['500', '060', '60'])

    # ==============================================================================
    # 1. GRUPO PRODUTOS QUÍMICOS (CRÍTICO)
    # ==============================================================================
    # Forte indicação: NCM Cap. 27/34 + Termos Químicos + ST Fiscal
    cond_quimico = (
        ncm.str.startswith(('2710', '3403', '3814', '3208', '3209', '3402')) |
        (desc.str.contains(r'OLEO|GRAXA|LUBRIF|SOLVENTE|THINNER|TINTA|VERNIZ|ADITIVO', regex=True) & 
         (fiscal_st | ncm.str.startswith(('27', '34'))))
    )

    # ==============================================================================
    # 2. GRUPO MOVIMENTAÇÃO DE CARGA / IÇAMENTO (CRÍTICO)
    # ==============================================================================
    cond_icamento = (
        ncm.str.startswith(('7312', '7315', '630790', '8425', '8431')) |
        desc.str.contains(r'CABO DE ACO|CINTA ELEVACAO|MANILHA|LACO DE CABO|ESTROPO|PONTE ROLANTE|TALHA', regex=True)
    )

    # ==============================================================================
    # 3. GRUPO HIDRÁULICA, PNEUMÁTICA E CONEXÕES (FILTRO DE METALURGIA)
    # ==============================================================================
    # Aqui matamos o erro da "Luva de Aço". Se for NCM 7307, É HIDRÁULICA.
    cond_hidraulica = (
        ncm.str.startswith(('7307', '8481', '3917', '4009', '7412', '7609')) |
        desc.str.contains(r'\bNPT\b|\bBSP\b|\bSCH\d+\b|\bANSI\b|\bPN10\b|\bPN16\b|\bBAR\b|ACO CARBONO|INOX|GALVANIZAD', regex=True) |
        desc.str.contains(r'VALVULA|CONEXAO|FLANGE|NIPLE|TAMPÃO|TE IGUAL|REDUCAO|UNIAO', regex=True)
    )

    # ==============================================================================
    # 4. GRUPO EPI - PROTEÇÃO INDIVIDUAL (CRÍTICO)
    # ==============================================================================
    # SÓ classifica como EPI se:
    # 1. Tiver NCM de proteção (6403, 4015, etc) 
    # 2. OU Descrição de EPI E NÃO FOR NCM de Metalurgia (7307)
    cond_epi = (
        (ncm.str.startswith(('6506', '9004', '4015', '4203', '6116', '6216', '6403', '6405'))) |
        (desc.str.contains(r'CAPACETE|OCULOS|PROTETOR AURICULAR|MASCARA|BOTA|CALCADO|LUVA|PROTETOR SOLAR', regex=True) & 
         ~ncm.str.startswith('7307') & # Veto: Se for conexão de aço, não é EPI
         ~desc.str.contains(r'NPT|BSP|SCH|ACO CARBONO', regex=True)) # Veto: Termos técnicos de tubulação
    )

    # ==============================================================================
    # 5. GRUPO ELÉTRICA (CRÍTICO - SUP-PC-05)
    # ==============================================================================
    cond_eletrica = (
        ncm.str.startswith(('8501', '8535', '8536', '8537', '8544')) |
        desc.str.contains(r'DISJUNTOR|CONTATOR|CABO FLEXIVEL|FIO ELETRICO|RELE|BORNE|BARRAMENTO', regex=True)
    )

    # ==============================================================================
    # HIERARQUIA DE DECISÃO (ORDEM IMPORTA)
    # ==============================================================================
    # 1. Químicos e Içamento primeiro (Alto Risco)
    # 2. Hidráulica (Para limpar falsos EPIs)
    # 3. EPI e Elétrica
    
    conditions = [
        cond_quimico,
        cond_icamento,
        cond_hidraulica, 
        cond_epi,
        cond_eletrica
    ]
    
    choices = [
        '🔴 QUÍMICO (CRÍTICO)',
        '🟡 IÇAMENTO (CRÍTICO)',
        '💧 HIDRÁULICA/PNEUM.',
        '🟠 EPI (CRÍTICO)',
        '⚡ ELÉTRICA'
    ]
    
    return np.select(conditions, choices, default='📦 GERAL')
