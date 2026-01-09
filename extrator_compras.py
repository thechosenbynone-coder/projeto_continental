import xml.etree.ElementTree as ET
import sqlite3
import os

# --- CONFIGURAÇÕES ---
PASTA_RAIZ = r"C:\Users\Compras.2\Documents\VENDOR LIST\XML 25"
DB_NAME = "compras_suprimentos.db"
MEU_CNPJ = "32300758000131"

# BLOQUEIO DE OPERAÇÕES FISCAIS (NÃO SÃO COMPRAS)
BLACKLIST_CFOP_PREFIX = ['120', '220', '141', '241', '1554', '2554', '190', '290', '191', '291', '194', '294', '59', '69']
BLACKLIST_TEXTO = ['DEVOLUCAO', 'RETORNO', 'REMESSA', 'COMODATO', 'DEMONSTRACAO', 'BRINDE', 'AMOSTRA']
# ---------------------

def limpar_texto(texto):
    if not texto: return ""
    return " ".join(str(texto).split())

def pegar_valor(no, tags, ns):
    if no is None: return ""
    if isinstance(tags, str): tags = [tags]
    for tag in tags:
        busca = no.find(f"nfe:{tag}", ns)
        if busca is not None and busca.text: return busca.text
        busca = no.find(tag)
        if busca is not None and busca.text: return busca.text
    return ""

def executar():
    print(f"🕵️ INICIANDO EXTRAÇÃO ANTI-DUPLICIDADE (V7.0)...")
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('DROP TABLE IF EXISTS base_compras')
    cursor.execute('''
    CREATE TABLE base_compras (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chave_acesso TEXT UNIQUE, -- COLUNA NOVA PARA EVITAR DUPLICIDADE
        cnpj_emit TEXT, nome_emit TEXT,
        xLgr TEXT, nro TEXT, xBairro TEXT, xMun TEXT, uf_emit TEXT, cep TEXT,
        n_nf TEXT, data_emissao DATE, nat_op TEXT,
        cod_prod TEXT, desc_prod TEXT, ncm TEXT, cfop TEXT, u_medida TEXT,
        qtd REAL, v_unit REAL, v_prod REAL, v_total_item REAL
    )
    ''')
    conn.commit()

    arquivos_xml = []
    for root, dirs, files in os.walk(PASTA_RAIZ):
        for file in files:
            if file.lower().endswith(".xml"):
                arquivos_xml.append(os.path.join(root, file))
    
    print(f"📄 XMLs encontrados: {len(arquivos_xml)}")
    
    importados = 0
    duplicados = 0
    ignorados = 0
    
    # LISTA DE CONTROLE EM MEMÓRIA (Para velocidade)
    chaves_processadas = set()

    for arq in arquivos_xml:
        try:
            tree = ET.parse(arq)
            root = tree.getroot()
            ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

            inf_nfe = root.find('.//nfe:infNFe', ns) or root.find('.//infNFe')
            if inf_nfe is None: continue

            # --- TRAVA ANTI-DUPLICIDADE (PELA CHAVE DE ACESSO) ---
            chave = inf_nfe.attrib.get('Id') # Pega o ID da tag (NFe352401...)
            if not chave: continue # Se não tem chave, ignora
            
            # Remove o prefixo 'NFe' para ficar só os números
            chave_limpa = chave.replace('NFe', '')
            
            if chave_limpa in chaves_processadas:
                duplicados += 1
                continue # Pula para o próximo arquivo
            
            chaves_processadas.add(chave_limpa)
            # -----------------------------------------------------

            # Filtros de Regra de Negócio (CNPJ, Natureza, CFOP)
            emit = inf_nfe.find('nfe:emit', ns) or inf_nfe.find('emit')
            cnpj_emitente = ''.join(filter(str.isdigit, pegar_valor(emit, 'CNPJ', ns)))
            if cnpj_emitente == MEU_CNPJ: continue

            ide = inf_nfe.find('nfe:ide', ns) or inf_nfe.find('ide')
            nat_op = pegar_valor(ide, 'natOp', ns).upper()
            if any(p in nat_op for p in BLACKLIST_TEXTO): continue

            # Dados do Cabeçalho
            ender = emit.find('nfe:enderEmit', ns) or emit.find('enderEmit')
            nome = pegar_valor(emit, 'xNome', ns).upper()
            lgr = pegar_valor(ender, 'xLgr', ns)
            nro = pegar_valor(ender, 'nro', ns)
            bairro = pegar_valor(ender, 'xBairro', ns)
            mun = pegar_valor(ender, 'xMun', ns).upper()
            uf = pegar_valor(ender, 'UF', ns).upper()
            cep = pegar_valor(ender, 'CEP', ns)
            n_nf = pegar_valor(ide, 'nNF', ns)
            data = pegar_valor(ide, 'dhEmi', ns)[:10]

            dets = inf_nfe.findall('nfe:det', ns) or inf_nfe.findall('det')
            
            for det in dets:
                prod = det.find('nfe:prod', ns) or det.find('prod')
                cfop = pegar_valor(prod, 'CFOP', ns)
                
                if any(cfop.startswith(pre) for pre in BLACKLIST_CFOP_PREFIX): continue

                desc_principal = pegar_valor(prod, 'xProd', ns)
                info_adicional = pegar_valor(det, 'infAdProd', ns)
                codigo_ref = pegar_valor(prod, 'cProd', ns)
                
                descricao_completa = desc_principal
                if info_adicional: descricao_completa += f" - {info_adicional}"
                descricao_completa = limpar_texto(descricao_completa).upper()

                def to_f(v): 
                    try: return float(v)
                    except: return 0.0

                cursor.execute('''
                INSERT INTO base_compras (
                    chave_acesso,
                    cnpj_emit, nome_emit, xLgr, nro, xBairro, xMun, uf_emit, cep,
                    n_nf, data_emissao, nat_op, cod_prod, desc_prod, ncm, cfop, u_medida, 
                    qtd, v_unit, v_prod, v_total_item
                )
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ''', (chave_limpa, cnpj_emitente, nome, lgr, nro, bairro, mun, uf, cep, n_nf, data, nat_op,
                      codigo_ref, descricao_completa, pegar_valor(prod, 'NCM', ns), cfop,
                      pegar_valor(prod, 'uCom', ns), to_f(pegar_valor(prod, 'qCom', ns)), 
                      to_f(pegar_valor(prod, 'vUnCom', ns)), to_f(pegar_valor(prod, 'vProd', ns)), 
                      to_f(pegar_valor(prod, 'vProd', ns))))
            importados += 1

        except Exception:
            pass

    conn.commit()
    conn.close()
    print(f"✅ FINALIZADO!")
    print(f"📥 Notas Únicas Importadas: {importados}")
    print(f"👯 Duplicatas Removidas: {duplicados}")
    print("Agora seus dados estão livres de duplicidade.")

if __name__ == "__main__":
    executar()