import numpy as np
import pandas as pd

def classificar_materiais_turbo(df):
    """
    Classificação Balanceada V4
    Objetivo: Garantir que Químicos, Içamento e Elétrica apareçam, 
    não apenas EPI.
    """
    # 1. Preparação
    desc = df['desc_prod'].astype(str).str.upper().str.strip()
    ncm = df['ncm'].astype(str).str.replace('.', '', regex=False).str.strip()
    
    # Pegamos os 2 e 4 primeiros dígitos para facilitar a busca
    ncm_2 = ncm.str.slice(0, 2)
    ncm_4 = ncm.str.slice(0, 4)

    # ==============================================================================
    # 1. GRUPO QUÍMICOS (CRÍTICO) - REGRA ABRANGENTE
    # ==============================================================================
    # Qualquer coisa dos capítulos 27 (Minerais), 32 (Tintas), 34 (Sabões/Lubs), 35 (Colas), 38 (Químicos div)
    cond_quimico = (
        (ncm_2.isin(['27', '32', '34', '35', '38'])) | 
        (desc.str.contains(r'OLEO|GRAXA|LUBRIFICANTE|TINTA|VERNIZ|SOLVENTE|DILUENTE|ADESIVO|COLA|RESINA|GASOLINA|DIESEL|ALCOOL', regex=True))
    )

    # ==============================================================================
    # 2. GRUPO IÇAMENTO E MOVIMENTAÇÃO (CRÍTICO)
    # ==============================================================================
    cond_icamento = (
        # NCMs: 7312 (Cabos Aço), 7315 (Correntes), 5607 (Cordas), 6307 (Cintas - cuidado com EPI)
        (ncm_4.isin(['7312', '7315', '5607', '8425', '8426'])) |
        (desc.str.contains(r'CABO DE ACO|CINTA DE ELEVACAO|CINTA DE CARGA|MANILHA|ESTROPO|LACO|CORRENTE GRAU|TALHA|GUINCHO|MOITAO|GANCHO', regex=True))
    )

    # ==============================================================================
    # 3. GRUPO ELÉTRICA (CRÍTICO - NR10)
    # ==============================================================================
    cond_eletrica = (
        (ncm_2.isin(['85'])) | # Capítulo 85 é Quase tudo Elétrica
        (desc.str.contains(r'DISJUNTOR|CONTATOR|CABO ELETRICO|FIO |CABO FLEX|RELE|FUSIVEL|TRANSFORMADOR|MOTOR|LAMPADA|LUMINARIA', regex=True))
    )

    # ==============================================================================
    # 4. GRUPO HIDRÁULICA/PNEUMÁTICA (MECÂNICA)
    # ==============================================================================
    # Filtro para capturar peças metálicas e evitar que virem EPI
    cond_hidraulica = (
        (ncm_4.isin(['7307', '8481', '3917', '4009', '7412'])) |
        (desc.str.contains(r'VALVULA|CONEXAO|TUBO|MANGUEIRA|ENGATE|NIPLE|TAMPÃO|COTOVELO|TE |LUVA DE ACO|LUVA DE FERRO', regex=True))
    )

    # ==============================================================================
    # 5. GRUPO EPI (CRÍTICO) - COM TRAVA DE SEGURANÇA
    # ==============================================================================
    cond_epi = (
        (ncm_4.isin(['6403', '6405', '6506', '4015', '4203', '6116', '6216', '9004', '9020'])) |
        (desc.str.contains(r'CAPACETE|OCULOS|PROTETOR|MASCARA|RESPIRADOR|BOTA|BOTINA|LUVA|CINTO PARAQUEDISTA|AVENTAL|MACACAO', regex=True) & 
         # VETOS IMPORTANTES:
         ~cond_hidraulica &  # Se já foi marcado como hidráulica, não é EPI
         ~cond_icamento)     # Se é cinta de carga, não é cinto de segurança
    )

    # ==============================================================================
    # HIERARQUIA DE DECISÃO (Quem ganha se empatar?)
    # ==============================================================================
    conditions = [
        cond_epi,       # Tenta EPI primeiro (com os vetos já aplicados dentro dele)
        cond_quimico,   # Depois Químicos
        cond_icamento,  # Depois Içamento
        cond_eletrica,  # Depois Elétrica
        cond_hidraulica # Por fim Hidráulica
    ]
    
    choices = [
        '🟠 EPI (CRÍTICO)',
        '🔴 QUÍMICO (CRÍTICO)',
        '🟡 IÇAMENTO (CRÍTICO)',
        '⚡ ELÉTRICA (CRÍTICO)',
        '💧 HIDRÁULICA'
    ]
    
    return np.select(conditions, choices, default='📦 GERAL')
