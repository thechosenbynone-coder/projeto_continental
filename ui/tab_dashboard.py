import numpy as np
import pandas as pd

def classificar_materiais_turbo(df):
    """
    Classificação vetorizada (100x mais rápida que .apply).
    Recebe o DataFrame inteiro e retorna a coluna de categorias.
    """
    # Prepara dados para busca vetorial (Upper case e sem ponto)
    desc = df['desc_prod'].str.upper().str.strip()
    ncm = df['ncm'].astype(str).str.replace('.', '', regex=False)
    
    # --- DEFINIÇÃO DAS CONDIÇÕES (MÁSCARAS BOOLEANAS) ---
    
    # 1. QUÍMICOS
    cond_quimico = (
        ncm.str.startswith(('2710', '3403')) | 
        desc.str.contains('OLEO|GRAXA|SOLVENTE|ADESIVO|TINTA', regex=True)
    )
    
    # 2. IÇAMENTO
    cond_icamento = desc.str.contains('CABO DE ACO|MANILHA|CINTA DE ELEVACAO|ESTROPO', regex=True)
    
    # 3. EPI (Termos e NCMs)
    termos_epi = 'LUVA|CAPACETE|BOTA|OCULOS|PROTETOR|MASCARA|RESPIRADOR|CINTO|TALABARTE'
    ncms_epi = ('6403', '6405', '6506', '9004')
    cond_epi = (
        ncm.str.startswith(ncms_epi) | 
        desc.str.contains(termos_epi, regex=True)
    )
    
    # 4. GERAIS
    cond_hidraulica = desc.str.contains('TUBO|VALVULA|CONEXAO|FLANGE', regex=True)
    cond_eletrica = desc.str.contains('CABO|DISJUNTOR|FIO|TOMADA|RELE', regex=True)
    cond_civil = desc.str.contains('CIMENTO|AREIA|TIJOLO|TINTA|ARGAMASSA', regex=True)
    cond_ferramentas = desc.str.contains('CHAVE|BROCA|ALICATE|SERRA|MARTELO', regex=True)
    
    # --- LISTA DE CONDIÇÕES E ESCOLHAS (NA ORDEM DE PRIORIDADE) ---
    conditions = [
        cond_quimico,
        cond_icamento,
        cond_epi,
        cond_hidraulica,
        cond_eletrica,
        cond_civil,
        cond_ferramentas
    ]
    
    choices = [
        '🔴 QUÍMICO (CRÍTICO)',
        '🟡 IÇAMENTO (CRÍTICO)',
        '🟠 EPI (CRÍTICO)',
        '💧 HIDRÁULICA',
        '⚡ ELÉTRICA',
        '🧱 CIVIL',
        '🔧 FERRAMENTAS'
    ]
    
    # Aplica a lógica vetorizada (Se nenhuma condição bater, usa o default)
    return np.select(conditions, choices, default='📦 GERAL')
