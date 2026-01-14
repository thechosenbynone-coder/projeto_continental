import numpy as np
import pandas as pd
import re

def classificar_materiais_turbo(df):
    """
    Classificação de Alta Precisão (Cross-Referencing NCM + Texto).
    Corrige falsos positivos como 'Luva de Aço' (Conexão) vs 'Luva de Raspa' (EPI).
    """
    # 1. Limpeza e Padronização
    # Remove acentos e caracteres especiais para comparação segura
    desc = df['desc_prod'].astype(str).str.upper().str.strip()
    
    # Remove pontos do NCM para garantir pureza numérica (Ex: 7307.19 -> 730719)
    ncm = df['ncm'].astype(str).str.replace('.', '', regex=False).str.strip()
    
    # ==============================================================================
    # REGRA 0: BLOQUEIOS DE AMBIGUIDADE (RESOLUÇÃO DE CONFLITOS)
    # ==============================================================================
    
    # Define o que é CONEXÃO (Hidráulica) para não confundir com EPI
    # NCM 7307 = Acessórios para tubos (Luvas, Cotovelos, Tês) de ferro/aço
    # NCM 3917 = Tubos e acessórios de plástico
    # Termos técnicos de tubulação: NPT, BSP, ROSCA, SOLDAVEL, FLANGE
    cond_conexao_tubulacao = (
        ncm.str.startswith(('7307', '391740', '7412')) | 
        desc.str.contains(r'\bNPT\b|\bBSP\b|\bROSCA\b|\bFEMEA\b|\bMACHO\b|\bSOLDAVEL\b|\bFLANGE\b', regex=True)
    )

    # ==============================================================================
    # GRUPO 1: PRODUTOS QUÍMICOS (RISCO AMBIENTAL E SAÚDE)
    # ==============================================================================
    
    # Graxas (NCMs específicos ou texto claro + exclusão de peças metálicas)
    cond_graxa = (
        (ncm.str.startswith(('27101932', '3403', '2710199'))) & 
        desc.str.contains('GRAXA|LITIO|ROLAMENTO|ALTA TEMP', regex=True)
    )
    
    # Óleos Lubrificantes
    cond_lubrificante = (
        (ncm.str.startswith(('2710193', '3403'))) & 
        (~cond_graxa)
    )
    
    # Solventes e Diluentes
    cond_solvente = (
        ncm.str.startswith(('3814', '271012', '2902')) |
        desc.str.contains('SOLVENTE|DILUENTE|THINNER|AGUARRAS|REMOVEDOR|TOLUENO|XILENO', regex=True)
    )
    
    # Tintas
    cond_tinta = (
        ncm.str.startswith(('3208', '3209')) |
        desc.str.contains(r'\bTINTA\b|ESMALTE|VERNIZ|PRIMER|EPOXI|POLIURETANO', regex=True)
    )
    
    cond_quimico_geral = (
        ncm.str.startswith(('340290', '3810')) |
        desc.str.contains('DESENGRAXANTE|ACIDO|ALCALINO|DETERGENTE IND', regex=True)
    )

    # ==============================================================================
    # GRUPO 2: INTEGRIDADE MECÂNICA (PRESSÃO E IÇAMENTO)
    # ==============================================================================
    
    # Içamento (Cabos e Cintas)
    cond_icamento = (
        (ncm.str.startswith('73121090') & desc.str.contains('ALMA|ELEVACAO|POLIDO|GALV')) |
        (ncm.str.startswith('73158') & desc.str.contains('GRAU 8|G8|LINK')) |
        (ncm.str.startswith('63079090') & desc.str.contains('CINTA|SLING|ELEVACAO|CARGA')) |
        desc.str.contains('MANILHA|ESTROPO|LACO DE CABO', regex=True)
    )
    
    # Hidráulica e Pneumática
    # AQUI ENTRA A CORREÇÃO DA "LUVA": Se for cond_conexao_tubulacao, cai aqui!
    cond_hidraulica = (
        cond_conexao_tubulacao |
        (ncm.str.startswith(('4009', '3917'))) | 
        desc.str.contains('HIDRAULICA|PNEUMATICA|ALTA PRESSAO|TRAMA|VALVULA', regex=True)
    )

    # ==============================================================================
    # GRUPO 3: EPIs (NR-06 - EXIGÊNCIA DE C.A.)
    # ==============================================================================
    
    # NCMs Oficiais de EPI (Filtro Duro)
    ncms_epi_list = (
        '650610', '900490', '392690', '9020', '4015', 
        '420329', '6116', '6403', '6405', '630720', '6210'
    )
    
    # Regex de EPIs (Filtro Suave)
    regex_epi = r'\bEPI\b|CAPACETE|BOTA|OCULOS|PROTETOR AURICULAR|MASCARA|RESPIRADOR|CINTO PARAQUEDISTA|TALABARTE'
    
    # Lógica Cruzada para Luvas:
    # Só é luva EPI se tiver NCM de EPI **OU** palavras-chave de proteção (Raspa, Vaqueta, Nitrilica, Latex)
    # E NÃO pode ser uma conexão hidráulica (já filtrada acima, mas reforçamos)
    cond_luva_real = (
        desc.str.contains('LUVA') & 
        (
            ncm.str.startswith(('4015', '4203', '6116')) | 
            desc.str.contains('RASPA|VAQUETA|NITRILICA|LATEX|ANTICORTE|PU|TATO|PEDREIRO|ALTA TENSAO', regex=True)
        ) &
        (~desc.str.contains('ACO|NPT|BSP|ROSCA|EMENDA|ELETRODUTO', regex=True))
    )

    cond_epi = (
        (ncm.str.startswith(ncms_epi_list)) |
        desc.str.contains(regex_epi, regex=True) |
        cond_luva_real # Adiciona a regra específica da luva
    ) & (~cond_conexao_tubulacao) # GARANTE QUE NÃO É CONEXÃO

    # ==============================================================================
    # GRUPO 4: CATEGORIAS GERAIS E SERVIÇOS
    # ==============================================================================
    
    cond_ferramentas = ncm.str.startswith(('820', '8467')) | desc.str.contains('CHAVE|ALICATE|FURADEIRA|LIXADEIRA|MARTELO', regex=True)
    cond_eletrica = ncm.str.startswith(('8544', '8536', '8538')) | desc.str.contains('CABO|FIO|DISJUNTOR|CONTATOR|RELE', regex=True)
    cond_civil = ncm.str.startswith(('2523', '6810')) | desc.str.contains('CIMENTO|AREIA|TIJOLO|CONCRETO', regex=True)
    
    cond_serv_calibracao = desc.str.contains('CALIBRACAO|AFERICAO|CERTIFICADO RBC', regex=True)
    cond_serv_residuos = desc.str.contains('COLETA DE RESIDUO|TRATAMENTO EFLUENTE|CACAMBA', regex=True)

    # ==============================================================================
    # ORDEM DE PRIORIDADE (PRIMEIRO MATCH VENCE)
    # ==============================================================================
    
    conditions = [
        # 1. Químicos
        cond_solvente, cond_graxa, cond_lubrificante, cond_tinta, cond_quimico_geral,
        
        # 2. Críticos Operacionais
        cond_icamento,
        cond_epi, # Agora "Luva NPT" não entra aqui porque falha no check de NCM/Texto
        cond_serv_calibracao, cond_serv_residuos,
        
        # 3. Técnicos (Luva NPT cai aqui em Hidráulica)
        cond_hidraulica, 
        cond_eletrica, cond_ferramentas, cond_civil
    ]
    
    choices = [
        '🔴 QUÍMICO (SOLVENTE)', '🔴 QUÍMICO (GRAXA)', '🔴 QUÍMICO (LUBRIFICANTE)', '🔴 QUÍMICO (TINTA)', '🔴 QUÍMICO (GERAL)',
        '🟡 IÇAMENTO (CRÍTICO)',
        '🟠 EPI (CRÍTICO)', # Obrigatório CA
        '⚙️ SERV. CALIBRAÇÃO', '♻️ SERV. RESÍDUOS',
        '💧 HIDRÁULICA/PNEUM.', '⚡ ELÉTRICA', '🔧 FERRAMENTAS', '🧱 CIVIL'
    ]
    
    return np.select(conditions, choices, default='📦 GERAL')
