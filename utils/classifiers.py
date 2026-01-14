import numpy as np
import pandas as pd

def classificar_materiais_turbo(df):
    """
    Classificação cirúrgica baseada na Diretriz SUP-PC-05 e Taxonomia de Risco.
    Utiliza NCMs específicos cruzados com Mineração de Texto (Regex) para alta precisão.
    """
    # Normalização para performance
    # Garante que descrição e NCM estejam limpos para comparação vetorial
    desc = df['desc_prod'].astype(str).str.upper().str.strip()
    # Remove pontos do NCM (Ex: 2710.19.32 vira 27101932) e garante string
    ncm = df['ncm'].astype(str).str.replace('.', '', regex=False).str.strip()
    
    # ==============================================================================
    # GRUPO 1: PRODUTOS QUÍMICOS (RISCO AMBIENTAL E SAÚDE)
    # ==============================================================================
    
    # 1.1 Graxas (Diferenciação via Texto pois compartilha NCM com Óleos)
    # NCMs: 27101932, 2710199, 3403
    cond_graxa = (
        ncm.str.startswith(('27101932', '3403', '2710199')) & 
        desc.str.contains('GRAXA|LITIO|ROLAMENTO|ALTA TEMP', regex=True)
    )
    
    # 1.2 Óleos Lubrificantes (Minerais e Sintéticos)
    # NCMs Raiz: 2710193 (Minerais), 3403 (Sintéticos/Preparações)
    # Exclui o que já foi marcado como Graxa
    cond_lubrificante = (
        (ncm.str.startswith(('2710193', '3403'))) & 
        (~cond_graxa) # Garante que não é graxa
    )
    
    # 1.3 Solventes e Diluentes (Alto Risco de Inflamabilidade/Toxicidade)
    # NCMs: 3814 (Solventes orgânicos), 271012 (Aguarrás), 2902 (Tolueno/Xileno)
    cond_solvente = (
        ncm.str.startswith(('3814', '271012', '2902')) |
        desc.str.contains('SOLVENTE|DILUENTE|THINNER|AGUARRAS|REMOVEDOR|TOLUENO|XILENO', regex=True)
    )
    
    # 1.4 Tintas e Revestimentos Industriais
    # NCMs: 3208 (Base Solvente), 3209 (Base Água)
    cond_tinta = (
        ncm.str.startswith(('3208', '3209')) |
        desc.str.contains(r'\bTINTA\b|ESMALTE|VERNIZ|PRIMER|EPOXI|POLIURETANO', regex=True)
    )
    
    # 1.5 Químicos Gerais (Desengraxantes, Ácidos)
    cond_quimico_geral = (
        ncm.str.startswith(('340290', '3810')) | # Detergentes ind. e Decapantes
        desc.str.contains('DESENGRAXANTE|ACIDO|ALCALINO|DETERGENTE IND', regex=True)
    )

    # ==============================================================================
    # GRUPO 2: INTEGRIDADE MECÂNICA (PRESSÃO E IÇAMENTO)
    # ==============================================================================
    
    # 2.1 Içamento e Movimentação (Risco Catastrófico)
    # Cabos de Aço (7312), Correntes Grau 8 (73158), Cintas (63079090)
    cond_icamento = (
        (ncm.str.startswith('73121090') & desc.str.contains('ALMA|ELEVACAO|POLIDO|GALV')) |
        (ncm.str.startswith('73158') & desc.str.contains('GRAU 8|G8|LINK')) |
        (ncm.str.startswith('63079090') & desc.str.contains('CINTA|SLING|ELEVACAO|CARGA')) |
        desc.str.contains('MANILHA|ESTROPO|LACO DE CABO', regex=True)
    )
    
    # 2.2 Hidráulica e Pneumática (Alta Pressão - NR12)
    # Mangueiras (4009, 3917), Conexões (7307)
    cond_hidraulica = (
        (ncm.str.startswith(('4009', '3917', '7307'))) & 
        desc.str.contains('HIDRAULICA|PNEUMATICA|ALTA PRESSAO|TRAMA|CONEXAO|VALVULA', regex=True)
    )

    # ==============================================================================
    # GRUPO 3: EPIs (NR-06 - EXIGÊNCIA DE C.A.)
    # ==============================================================================
    
    # Lista exaustiva de NCMs de EPI baseada no relatório
    ncms_epi = (
        '650610', # Capacetes
        '900490', # Óculos
        '392690', # Protetor Auricular (Plástico/Silicone)
        '9020',   # Respiradores
        '4015',   # Luvas Borracha
        '420329', # Luvas Couro
        '6116',   # Luvas Malha
        '6403',   # Calçados Couro
        '6405',   # Outros Calçados
        '630720', # Cintos Altura
        '6210'    # Vestimentas Proteção
    )
    
    cond_epi = (
        ncm.str.startswith(ncms_epi) |
        desc.str.contains(r'\bEPI\b|LUVA|CAPACETE|BOTA|OCULOS|PROTETOR AURICULAR|MASCARA|RESPIRADOR|CINTO PARAQUEDISTA|TALABARTE', regex=True)
    )

    # ==============================================================================
    # GRUPO 4: CATEGORIAS GERAIS E SERVIÇOS
    # ==============================================================================
    
    cond_ferramentas = ncm.str.startswith(('820', '8467')) | desc.str.contains('CHAVE|ALICATE|FURADEIRA|LIXADEIRA|MARTELO', regex=True)
    cond_eletrica = ncm.str.startswith(('8544', '8536', '8538')) | desc.str.contains('CABO|FIO|DISJUNTOR|CONTATOR|RELE', regex=True)
    cond_civil = ncm.str.startswith(('2523', '6810')) | desc.str.contains('CIMENTO|AREIA|TIJOLO|CONCRETO', regex=True)
    
    # Serviços Críticos (Detectados via texto, já que NCM pode ser genérico em nota conjugada)
    cond_serv_calibracao = desc.str.contains('CALIBRACAO|AFERICAO|CERTIFICADO RBC', regex=True)
    cond_serv_residuos = desc.str.contains('COLETA DE RESIDUO|TRATAMENTO EFLUENTE|CACAMBA', regex=True)

    # ==============================================================================
    # LÓGICA DE PRIORIDADE (Numpy Select)
    # ==============================================================================
    # A ordem importa: O primeiro True vence.
    
    conditions = [
        # 1. Críticos Químicos
        cond_solvente,
        cond_graxa,
        cond_lubrificante,
        cond_tinta,
        cond_quimico_geral,
        
        # 2. Críticos Operacionais
        cond_icamento,
        cond_epi,
        cond_serv_calibracao,
        cond_serv_residuos,
        
        # 3. Técnicos
        cond_hidraulica,
        cond_eletrica,
        cond_ferramentas,
        cond_civil
    ]
    
    choices = [
        # Tags Visuais para o Streamlit
        '🔴 QUÍMICO (SOLVENTE)',
        '🔴 QUÍMICO (GRAXA)',
        '🔴 QUÍMICO (LUBRIFICANTE)',
        '🔴 QUÍMICO (TINTA)',
        '🔴 QUÍMICO (GERAL)',
        
        '🟡 IÇAMENTO (CRÍTICO)',
        '🟠 EPI (OBRIGATÓRIO CA)',
        '⚙️ SERV. CALIBRAÇÃO',
        '♻️ SERV. RESÍDUOS',
        
        '💧 HIDRÁULICA/PNEUM.',
        '⚡ ELÉTRICA',
        '🔧 FERRAMENTAS',
        '🧱 CIVIL'
    ]
    
    # Aplica a lógica. Default é 'GERAL'
    return np.select(conditions, choices, default='📦 GERAL')
