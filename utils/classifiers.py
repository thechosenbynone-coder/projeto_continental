import numpy as np
import pandas as pd

def classificar_materiais_turbo(df):
    """
    Classificação de Precisão Baseada na SUP-PC-05.
    Combina Capítulos NCM com Análise Semântica da Descrição.
    """
    # 1. Padronização
    desc = df['desc_prod'].astype(str).str.upper().str.strip()
    ncm = df['ncm'].astype(str).str.replace('.', '', regex=False).str.strip()
    
    # ==============================================================================
    # 1. GRUPO HIDRÁULICA/PNEUMÁTICA (CAPÍTULOS 73, 40, 39, 84)
    # ==============================================================================
    # Filtra conexões, válvulas e tubulações
    cond_hidraulica = (
        # NCMs: 7307 (Conexões Aço), 4009 (Mangueiras), 8481 (Válvulas)
        ncm.str.startswith(('7307', '4009', '8481', '3917')) |
        # Descrições com termos de pressão ou rosca
        desc.str.contains(r'\bNPT\b|\bBSP\b|\bROSCA\b|\bSOLDAVEL\b|\bBAR\b|\bPSI\b|\bCONEXAO\b|\bVALVULA\b', regex=True)
    )

    # ==============================================================================
    # 2. GRUPO PRODUTOS QUÍMICOS (CAPÍTULOS 27, 32, 34, 38)
    # ==============================================================================
    # Filtra lubrificantes, tintas e solventes
    cond_quimico = (
        # NCMs: 2710 (Óleos/Graxas), 3403 (Sintéticos), 3208 (Tintas), 3814 (Solventes)
        ncm.str.startswith(('2710', '3403', '3208', '3209', '3814', '3402')) |
        # Descrições químicas
        desc.str.contains(r'OLEO|GRAXA|LUBRIFICANTE|SOLVENTE|THINNER|TINTA|VERNIZ|DESENGRAXANTE', regex=True)
    )

    # ==============================================================================
    # 3. GRUPO MOVIMENTAÇÃO DE CARGA (CAPÍTULO 73, 63, 84)
    # ==============================================================================
    # Filtra cabos de aço, correntes e cintas de elevação
    cond_icamento = (
        # NCMs: 7312 (Cabos), 7315 (Correntes), 63079090 (Cintas)
        ncm.str.startswith(('7312', '7315', '63079090')) |
        # Termos de elevação
        desc.str.contains(r'CABO DE ACO|CORRENTE GRAU 8|CINTA ELEVACAO|SLING|ESTROPO|MANILHA', regex=True)
    )

    # ==============================================================================
    # 4. GRUPO EPI - PROTEÇÃO INDIVIDUAL (CAPÍTULOS 39, 40, 62, 64, 65)
    # ==============================================================================
    # Filtra apenas se não for conexão metálica (resolvendo o erro da Luva de Aço)
    cond_epi = (
        (ncm.str.startswith(('6506', '9004', '4015', '4203', '6116', '6403', '6405', '630720'))) |
        (desc.str.contains(r'CAPACETE|OCULOS|PROTETOR AURICULAR|MASCARA|BOTA|CALCADO|CINTO PARAQUEDISTA', regex=True)) |
        # Caso especial: Luva só é EPI se não tiver termos de metalurgia
        (desc.str.contains(r'\bLUVA\b') & ~desc.str.contains(r'ACO|CARBONO|NPT|BSP|INOX|ZINCADO', regex=True))
    )

    # ==============================================================================
    # APLICAÇÃO DA HIERARQUIA DE PRIORIDADE
    # ==============================================================================
    conditions = [
        cond_quimico,
        cond_icamento,
        cond_hidraulica, # Hidráulica tem prioridade sobre EPI para evitar falsos positivos
        cond_epi
    ]
    
    choices = [
        '🔴 QUÍMICO (CRÍTICO)',
        '🟡 IÇAMENTO (CRÍTICO)',
        '💧 HIDRÁULICA/PNEUM.',
        '🟠 EPI (CRÍTICO)'
    ]
    
    return np.select(conditions, choices, default='📦 GERAL')
