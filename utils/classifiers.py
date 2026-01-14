import numpy as np
import pandas as pd

def classificar_materiais_turbo(df):
    """
    Classificação vetorizada de alta performance.
    """
    desc = df['desc_prod'].str.upper().str.strip()
    ncm = df['ncm'].astype(str).str.replace('.', '', regex=False)
    
    # Definição das condições
    cond_quimico = ncm.str.startswith(('2710', '3403')) | desc.str.contains('OLEO|GRAXA|SOLVENTE', regex=True)
    cond_icamento = desc.str.contains('CABO DE ACO|MANILHA|CINTA DE ELEVACAO', regex=True)
    cond_epi = ncm.str.startswith(('6403', '6405', '6506', '9004')) | desc.str.contains('LUVA|CAPACETE|BOTA|OCULOS|MASCARA', regex=True)
    cond_hidraulica = desc.str.contains('TUBO|VALVULA|CONEXAO', regex=True)
    cond_eletrica = desc.str.contains('CABO|DISJUNTOR|FIO', regex=True)
    cond_civil = desc.str.contains('CIMENTO|AREIA|TIJOLO', regex=True)
    cond_ferramentas = desc.str.contains('CHAVE|BROCA|ALICATE', regex=True)
    
    conditions = [cond_quimico, cond_icamento, cond_epi, cond_hidraulica, cond_eletrica, cond_civil, cond_ferramentas]
    choices = ['🔴 QUÍMICO (CRÍTICO)', '🟡 IÇAMENTO (CRÍTICO)', '🟠 EPI (CRÍTICO)', '💧 HIDRÁULICA', '⚡ ELÉTRICA', '🧱 CIVIL', '🔧 FERRAMENTAS']
    
    return np.select(conditions, choices, default='📦 GERAL')
