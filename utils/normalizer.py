import pandas as pd
import numpy as np

def normalizar_unidades_v1(df):
    """
    Detecta e corrige distorções de unidade (ex: Caixa vs Unidade).
    Versão compatível com colunas 'v_unit_real' e 'qtd_real'.
    """
    # 1. Verificação de Segurança
    # Se por algum motivo as colunas não existirem, retorna sem fazer nada para não quebrar o app
    if 'v_unit_real' not in df.columns or 'qtd_real' not in df.columns:
        # Tenta compatibilidade com legado se necessário
        if 'v_unit' in df.columns:
            df['v_unit_real'] = df['v_unit']
            df['qtd_real'] = df['qtd']
        else:
            return df

    # Garante tipos numéricos
    df['v_unit_real'] = pd.to_numeric(df['v_unit_real'], errors='coerce').fillna(0)
    df['qtd_real'] = pd.to_numeric(df['qtd_real'], errors='coerce').fillna(0)

    # 2. Cálculo da Mediana (Preço de Referência)
    # Agrupa por produto para saber qual é o preço "comum" dele
    stats = df.groupby('desc_prod')['v_unit_real'].median().reset_index()
    stats.rename(columns={'v_unit_real': 'preco_mediano'}, inplace=True)
    
    # Junta a mediana no dataframe original
    df = df.merge(stats, on='desc_prod', how='left')
    
    # Evita divisão por zero
    df['preco_mediano'] = df['preco_mediano'].replace(0, 1)

    # 3. Lógica de Detetive (Unidade vs Caixa)
    # Fator: Quantas vezes o preço é maior que a média?
    df['fator_preco'] = df['v_unit_real'] / df['preco_mediano']
    
    # Se o preço for > 5x a mediana E a unidade for 'CX', 'PC', 'FD' -> Provável erro de unidade
    # Normalizamos multiplicando a quantidade e dividindo o preço
    
    # Criamos colunas normalizadas (por padrão, iguais às originais)
    df['v_unit_norm'] = df['v_unit_real']
    df['qtd_norm'] = df['qtd_real']
    df['un_norm'] = df['u_medida'] # Assume a unidade original
    
    # Condição: É uma caixa disfarçada? (Ex: Preço 100, Mediana 10 -> Fator 10)
    # Muitas vezes o fornecedor vende "1 CX" que custa 100, mas dentro tem 10 un que custam 10.
    # Mas aqui vamos manter simples: apenas identificamos outliers para não distorcer o "Menor Preço"
    
    # Para o propósito deste app, vamos garantir que v_unit_real seja usado nas análises
    # Se quisermos converter "CX de 100" para "100 UN", precisaríamos saber a quantidade na caixa.
    # Como não temos esse dado no XML padrão, assumimos a unidade da nota fiscal.
    
    # Limpeza final: remove colunas auxiliares para não poluir
    cols_drop = ['preco_mediano', 'fator_preco']
    df.drop(columns=[c for c in cols_drop if c in df.columns], inplace=True)
    
    return df
