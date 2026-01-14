import pandas as pd
import numpy as np
import re

def extrair_fator_descricao(texto):
    """
    Tenta encontrar padrões como 'C/100', 'PCT 50' na descrição.
    Retorna o número encontrado ou 1 se não achar nada.
    """
    if not isinstance(texto, str): return 1
    
    # Padrões comuns: C/100, CX100, C-50, PCT 12, C/ 1000
    padroes = [
        r'(?:C/|CX|PCT|EMB|PC|CX/)\s*[-:]?\s*(\d+)', # Pega C/100, CX 50
        r'(\d+)\s*(?:UN|PC|PCS|PECAS)' # Pega 100 UN
    ]
    
    for p in padroes:
        match = re.search(p, texto.upper())
        if match:
            try:
                val = int(match.group(1))
                if val > 1: return val # Ignora se achar "1"
            except:
                continue
    return 1

def normalizar_unidades_v1(df):
    """
    Algoritmo Híbrido:
    1. Tenta achar fator de conversão no texto.
    2. Se não achar, usa estatística de preço (se a unidade for CX/PCT).
    
    Retorna o DataFrame com colunas novas: 'qtd_real', 'v_unit_real', 'un_real'
    """
    df = df.copy()
    
    # 1. Normalização de Texto (Limpeza Básica)
    # Transforma CXA, CX., CAIXA -> CX
    df['un_limpa'] = df['unid'].astype(str).str.upper().str.strip()
    mapeamento = {
        'CXA': 'CX', 'CAIXA': 'CX', 'CT': 'CX',
        'PC': 'UN', 'PÇ': 'UN', 'PCA': 'UN', 'PECA': 'UN', 
        'UND': 'UN', 'UNI': 'UN'
    }
    df['un_limpa'] = df['un_limpa'].replace(mapeamento)

    # 2. Detecção de Fator via Descrição (Ex: "PARAFUSO C/100")
    df['fator_txt'] = df['desc_prod'].apply(extrair_fator_descricao)
    
    # 3. Detecção via Estatística de Preço (O Pulo do Gato)
    # Calculamos a Mediana de preço POR PRODUTO (assumindo que a maioria é UN)
    stats = df.groupby('desc_prod')['v_unit'].median().reset_index()
    stats.rename(columns={'v_unit': 'preco_mediano_ref'}, inplace=True)
    
    df = df.merge(stats, on='desc_prod', how='left')
    
    # Calcula a razão: Preço da Compra / Preço Mediano
    # Se o preço for R$ 100 e a mediana R$ 1, ratio = 100.
    df['ratio_preco'] = df['v_unit'] / df['preco_mediano_ref']
    
    # --- LÓGICA DE DECISÃO ---
    def aplicar_regra(row):
        fator = 1
        
        # Se achou fator explicito no texto (Ex: C/100), confia nele
        if row['fator_txt'] > 1:
            fator = row['fator_txt']
            
        # Se é uma CAIXA/PACOTE e o preço é muito maior que a mediana (ex: > 5x)
        elif row['un_limpa'] in ['CX', 'PCT', 'EMB', 'FD', 'FARDO'] and row['ratio_preco'] > 4:
            # Tenta arredondar para o inteiro mais próximo (ex: ratio 11.8 -> 12)
            fator_estatistico = round(row['ratio_preco'])
            # Só aceita se for um número "redondo" ou plausível (evita erros de flutuação)
            if fator_estatistico > 1:
                fator = fator_estatistico
        
        return fator

    df['fator_final'] = df.apply(aplicar_regra, axis=1)
    
    # --- CRIAÇÃO DAS COLUNAS REAIS ---
    # Qtd Real = Qtd da Nota * Fator (Ex: 2 caixas * 100 = 200)
    df['qtd_real'] = df['qtd'] * df['fator_final']
    
    # Preço Real = Preço da Nota / Fator (Ex: R$ 100 a caixa / 100 = R$ 1,00 un)
    df['v_unit_real'] = df['v_unit'] / df['fator_final']
    
    # Unidade Real (Se houve conversão, vira UN)
    df['un_real'] = np.where(df['fator_final'] > 1, 'UN (Calc)', df['un_limpa'])
    
    return df
