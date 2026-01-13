def classificar_material(row):
    """
    Recebe uma linha do DataFrame (com desc_prod e ncm) e retorna a categoria.
    Agora inclui regras para ÓCULOS, MÁSCARAS e NCM 9004.
    """
    # Garante que os campos sejam strings para evitar erro
    desc = str(row['desc_prod']).upper()
    ncm = str(row['ncm']).replace('.', '')
    
    # REGRA 1: QUÍMICOS
    if ncm.startswith(('2710','3403')) or any(x in desc for x in ['OLEO','GRAXA','SOLVENTE']): 
        return '🔴 QUÍMICO (CRÍTICO)'
    
    # REGRA 2: IÇAMENTO
    if any(x in desc for x in ['CABO DE ACO','MANILHA','CINTA DE ELEVACAO']): 
        return '🟡 IÇAMENTO (CRÍTICO)'
    
    # REGRA 3: EPI (Atualizada com OCULOS e NCM 9004)
    termos_epi = ['LUVA', 'CAPACETE', 'BOTA', 'OCULOS', 'PROTETOR', 'MASCARA', 'RESPIRADOR', 'CINTO', 'TALABARTE']
    # NCMs: 6403/6405 (Calçados), 6506 (Capacetes), 9004 (Óculos)
    if ncm.startswith(('6403', '6405', '6506', '9004')) or any(x in desc for x in termos_epi): 
        return '🟠 EPI (CRÍTICO)'
        
    # REGRA 4: CATEGORIAS GERAIS
    if any(x in desc for x in ['TUBO','VALVULA','CONEXAO']): return '💧 HIDRÁULICA'
    if any(x in desc for x in ['CABO','DISJUNTOR','FIO']): return '⚡ ELÉTRICA'
    if any(x in desc for x in ['CIMENTO','AREIA','TIJOLO']): return '🧱 CIVIL'
    if any(x in desc for x in ['CHAVE','BROCA','ALICATE']): return '🔧 FERRAMENTAS'
    
    return '📦 GERAL'
