import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
from datetime import datetime
import tempfile
import io
import csv
import json
import re
from PIL import Image, ImageDraw, ImageFont
import fitz  # PyMuPDF
import numpy as np

# Configuração
st.set_page_config(page_title="Extrator de Cultivares", page_icon="🌱")
st.title("Extrator de Cultivares")

# API Key
gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEM_API_KEY")
if not gemini_api_key:
    st.error("Configure GEMINI_API_KEY")
    st.stop()

try:
    genai.configure(api_key=gemini_api_key)
    modelo_visao = genai.GenerativeModel("gemini-2.5-flash")
    modelo_texto = genai.GenerativeModel("gemini-2.5-flash")
except Exception as e:
    st.error(f"Erro ao configurar Gemini: {str(e)}")
    st.stop()

# Criar lista de meses detalhados
meses_detalhados = []
for mes in ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]:
    for num in ["1", "2", "3"]:
        meses_detalhados.append(f"{mes} {num}")

# COLUNAS EXATAS conforme o template
COLUNAS_EXATAS = [
    "Cultura", "Nome do produto", "NOME TÉCNICO/ REG", "Descritivo para SEO", 
    "Fertilidade", "Grupo de maturação", "Lançamento", "Slogan", "Tecnologia", 
    "Região (por extenso)", "Estado (por extenso)", "Ciclo", "Finalidade", 
    "URL da imagem do mapa", "Número do ícone 1", "Titulo icone 1", "Descrição Icone 1", 
    "Número do ícone 2", "Titulo icone 2", "Descrição Icone 2", "Número do ícone 3", 
    "Titulo icone 3", "Descrição Icone 3", "Número do ícone 4", "Título icone 4", 
    "Descrição Icone 4", "Número do ícone 5", "Título icone 5", "Descrição Icone 5", 
    "Exigência à fertilidade", "Grupo de maturidade", "PMS MÉDIO", "Tipo de crescimento", 
    "Cor da flor", "Cor da pubescência", "Cor do hilo", "Cancro da haste", 
    "Pústula bacteriana ", "Nematoide das galhas - M. javanica", 
    "Nematóide de Cisto (Raça 3)", "Nematóide de Cisto (Raça 9)", 
    "Nematóide de Cisto (Raça 10)", "Nematóide de Cisto (Raça 14)", 
    "Fitóftora (Raça 1)", "Recomendações", "Resultado 1 - Nome", "Resultado 1 - Local", 
    "Resultado 1", "Resultado 2 - Nome", "Resultado 2 - Local", "Resultado 2", 
    "Resultado 3 - Nome", "Resultado 3 - Local", "Resultado 3", "Resultado 4 - Nome", 
    "Resultado 4 - Local", "Resultado 4", "Resultado 5 - Nome", "Resultado 5 - Lcal", 
    "Resultado 5", "Resultado 6 - Nome", "Resultado 6 - Local", "Resultado 6", 
    "Resultado 7 - Nome", "Resultado 7 - Local", "Resultado 7", "REC", "UF", 
    "Região"
] + meses_detalhados

# Session state
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=COLUNAS_EXATAS)
if 'csv_content' not in st.session_state:
    st.session_state.csv_content = ""
if 'texto_transcrito' not in st.session_state:
    st.session_state.texto_transcrito = ""
if 'imagens_paginas' not in st.session_state:
    st.session_state.imagens_paginas = []
if 'tipo_cultura' not in st.session_state:
    st.session_state.tipo_cultura = "Milho"

# Função para converter PDF para imagens
def pdf_para_imagens(pdf_bytes):
    try:
        st.info("Convertendo PDF para imagens...")
        imagens = []
        
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_paginas = len(doc)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for page_num in range(total_paginas):
            progresso = (page_num + 1) / total_paginas
            status_text.text(f"Convertendo página {page_num + 1} de {total_paginas}...")
            progress_bar.progress(progresso)
            
            try:
                page = doc.load_page(page_num)
                zoom = 4
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img_data = pix.tobytes("ppm")
                img = Image.open(io.BytesIO(img_data))
                
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                imagens.append(img)
                
            except Exception as e:
                st.warning(f"Erro na página {page_num + 1}: {str(e)[:100]}")
                continue
        
        doc.close()
        progress_bar.empty()
        status_text.empty()
        
        if imagens:
            st.success(f"✅ PDF convertido em {len(imagens)} página(s)")
            return imagens
        else:
            st.error("❌ Não foi possível converter nenhuma página")
            return []
            
    except Exception as e:
        st.error(f"Erro ao converter PDF: {str(e)}")
        return []

# Função para processar imagens em lote
def processar_imagens_em_lote(imagens, batch_size=3):
    if not imagens:
        return ""
    
    texto_completo = ""
    total_paginas = len(imagens)
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for batch_start in range(0, total_paginas, batch_size):
        batch_end = min(batch_start + batch_size, total_paginas)
        batch_imagens = imagens[batch_start:batch_end]
        
        status_text.text(f"Processando páginas {batch_start + 1} a {batch_end} de {total_paginas}...")
        
        for idx, imagem in enumerate(batch_imagens):
            pagina_num = batch_start + idx + 1
            progresso = pagina_num / total_paginas
            progress_bar.progress(progresso, text=f"Transcrevendo página {pagina_num}/{total_paginas}")
            
            try:
                # Redimensionar se necessário
                largura_max = 1600
                if imagem.width > largura_max:
                    proporcao = largura_max / imagem.width
                    nova_altura = int(imagem.height * proporcao)
                    imagem = imagem.resize((largura_max, nova_altura), Image.Resampling.LANCZOS)
                
                img_bytes = io.BytesIO()
                imagem.save(img_bytes, format='PNG', optimize=True, quality=95)
                img_bytes = img_bytes.getvalue()
                
                prompt = """TRANSCREVA TODO o texto desta página EXATAMENTE como aparece.
                
                INSTRUÇÕES CRÍTICAS:
                1. Transcreva TODO o texto visível EXATAMENTE
                2. Mantenha a formatação original de tabelas
                3. Para tabelas de meses, transcreva LINHA POR LINHA com os valores
                4. Inclua TODOS os números e valores
                5. Se houver "REC", "Registro" ou números de registro, transcreva
                
                Formato importante para tabelas:
                - Mantenha as colunas separadas por |
                - Mantenha os valores como estão
                - Não resuma, não interprete
                
                Retorne APENAS o texto transcrito."""
                
                response = modelo_visao.generate_content([
                    prompt,
                    {"mime_type": "image/png", "data": img_bytes}
                ])
                
                texto_pagina = response.text.strip()
                texto_completo += f"\n\n--- PÁGINA {pagina_num} ---\n{texto_pagina}\n"
                
                import time
                time.sleep(1)
                
            except Exception as e:
                texto_completo += f"\n\n--- ERRO PÁGINA {pagina_num}: {str(e)[:100]} ---\n"
                continue
        
        import time
        if batch_end < total_paginas:
            time.sleep(3)
    
    progress_bar.empty()
    status_text.empty()
    
    return texto_completo

# Função para criar prompt baseado no tipo de cultura
def criar_prompt_para_cultura(texto_transcrito, tipo_cultura):
    """Cria prompt específico para Milho ou Soja"""
    
    if tipo_cultura == "Soja":
        prompt_rec = """
        G. REC, UF, REGIÃO (IMPORTANTE! - APENAS PARA SOJA):
           - "REC": Procure por números de registro como: 201, 300, 400, etc.
           - Geralmente são números de 2-5 dígitos
           - Se uma cultivar tiver MAIS DE UM REC, crie uma LINHA SEPARADA para cada REC
           - Se não encontrar REC, use "NR"
           - "UF": Estados (ex: "TO,PA,MA,PI", "SP,MG,MS,GO,DF,MT")
           - "Região": Região (ex: "Norte", "Centro-Oeste,Sudeste")
        """
    else:  # Milho
        prompt_rec = """
        G. REC, UF, REGIÃO (PARA MILHO - SEM REC):
           - "REC": SEMPRE "NR" (Milho não tem REC)
           - "UF": Estados (ex: "RS,SC,PR,SP", "PR,SP,MS,MG,GO,DF,MT,TO,PA,MA,PI,RO")
           - "Região": Região (ex: "Sul", "Centro-Oeste,Norte,Sudeste")
        """
    
    # Colunas específicas para doenças
    if tipo_cultura == "Soja":
        doencas_prompt = """
        D. RESISTÊNCIAS A DOENÇAS (PARA SOJA):
           - "Cancro da haste": Procure por "Cancro" nas tabelas de resistência
           - "Pústula bacteriana": Procure por "Pústula" 
           - "Nematoide das galhas - M. javanica": Procure por "M. javanica"
           - "Nematóide de Cisto (Raça 3)": Procure por "Raça 3"
           - "Nematóide de Cisto (Raça 9)": Procure por "Raça 9"
           - "Nematóide de Cisto (Raça 10)": Procure por "Raça 10"
           - "Nematóide de Cisto (Raça 14)": Procure por "Raça 14"
           - "Fitóftora (Raça 1)": Procure por "Fitóftora"
           - Use R (Resistente), MR (Moderadamente Resistente), S (Suscetível)
        """
    else:  # Milho
        doencas_prompt = """
        D. RESISTÊNCIAS A DOENÇAS (PARA MILHO - NÃO PREENCHER COLUNAS DE SOJA):
           - "Cancro da haste": "NR"
           - "Pústula bacteriana": "NR" 
           - "Nematoide das galhas - M. javanica": "NR"
           - "Nematóide de Cisto (Raça 3)": "NR"
           - "Nematóide de Cisto (Raça 9)": "NR"
           - "Nematóide de Cisto (Raça 10)": "NR"
           - "Nematóide de Cisto (Raça 14)": "NR"
           - "Fitóftora (Raça 1)": "NR"
           - As doenças do milho no texto são específicas para milho
        """
    
    prompt_base = f"""
    ANALISE O TEXTO TRANSCRITO DE UM PDF SOBRE CULTIVARES DE {tipo_cultura.upper()}:

    TEXTO TRANSCRITO:
    {texto_transcrito}

    SUA TAREFA: Analisar este texto e extrair informações para preencher um CSV com estas colunas:

    {', '.join(COLUNAS_EXATAS)}

    INSTRUÇÕES ESPECÍFICAS PARA {tipo_cultura.upper()}:

    1. PRIMEIRO: Identifique todas as CULTIVARES únicas no texto.
       - Exemplos: "NS22PRO4", "NS66VIP3" (para milho)
       - Cada cultivar deve ser uma entrada separada

    2. INFORMAÇÕES BÁSICAS:
       - "Cultura": "{tipo_cultura}" (definido pelo usuário)
       - "Nome do produto": Nome da cultivar
       - "NOME TÉCNICO/ REG": Deixe como "NR"
       - "Descritivo para SEO": Descrição curta do produto
       - "Fertilidade": "NR"
       - "Grupo de maturação": "Hiper Precoce", "Precoce", etc.
       - "Lançamento": "lançamento" (se aparecer no texto)
       - "Slogan": Frase de marketing
       - "Tecnologia": "NR"
       - "Região (por extenso)": Regiões do mapa
       - "Estado (por extenso)": Estados do mapa
       - "Ciclo": Igual ao grupo de maturação
       - "Finalidade": "Grãos"
       - "URL da imagem do mapa": "NR"

    3. ÍCONES:
       - Extraia os URLs e títulos dos ícones quando aparecerem
       - Se não houver ícone, use "NR"

    4. CARACTERÍSTICAS TÉCNICAS:
       - "Exigência à fertilidade": "Alta", "Médio e alto", etc.
       - "Grupo de maturidade": Igual ao ciclo
       - "PMS MÉDIO": Valor como "385g", "390-400g", "SI", etc.
       - "Tipo de crescimento": "NR"
       - "Cor da flor": "NR" (para milho), para soja procure por cor da flor
       - "Cor da pubescência": "NR" (para soja)
       - "Cor do hilo": "NR" (para soja)
       - "Cor": "Amarelo", "Amarelo Alaranjado", etc. (do texto)
       - "Textura grãos": "Dentado", "Duro", "Semi duro", etc.
       - "Tolerância a glifosato": "Tolerante", "Não tolerante"
       - "Tolerância a glufosinato": "Tolerante", "Não tolerante"

    {doencas_prompt}

    5. RECOMENDAÇÕES:
       - "Recomendações": Texto sobre "Pode haver variação no ciclo..."

    6. RESULTADOS:
       - "Resultado 1 - Nome" até "Resultado 7 - Local": "NR" (não há no texto)

    {prompt_rec}

    7. TABELAS DE MESES:
       Para CADA LINHA da tabela que tem valores (como "60-65", "55-60", "75-82"):
       - Crie UMA LINHA NO CSV para cada combinação única
       - Para MILHO: cada linha tem seus próprios valores de meses
       - Para SOJA: cada REC tem seus próprios valores de meses
       - Preencha os meses com os valores EXATOS da tabela
       - Deixe as colunas de meses sem valor como ""

    8. REGRAS GERAIS:
       - Use "NR" para informações não encontradas
       - Mantenha valores EXATOS do texto
       - Não invente informações
       - Para múltiplas cultivares, crie uma entrada para cada

    9. FORMATO DE SAÍDA:
       Retorne APENAS um array JSON válido com TODAS as {len(COLUNAS_EXATAS)} propriedades.
    """
    
    return prompt_base

# Função para extrair dados
def extrair_dados_para_csv(texto_transcrito, tipo_cultura):
    # Criar prompt específico para o tipo de cultura
    prompt = criar_prompt_para_cultura(texto_transcrito, tipo_cultura)
    
    try:
        # Limitar o tamanho do texto
        if len(texto_transcrito) > 15000:
            st.info(f"Texto muito longo, usando as primeiras 15000 caracteres para análise de {tipo_cultura}...")
            texto_para_analise = texto_transcrito[:15000]
        else:
            texto_para_analise = texto_transcrito
        
        response = modelo_texto.generate_content(prompt)
        resposta = response.text.strip()
        
        # Limpar resposta
        resposta_limpa = resposta.replace('```json', '').replace('```', '').replace('JSON', '').strip()
        
        # Tentar parsear JSON
        try:
            dados = json.loads(resposta_limpa)
            if isinstance(dados, list):
                st.info(f"✅ Extraídos {len(dados)} registro(s) para {tipo_cultura}")
                return dados
            elif isinstance(dados, dict):
                st.info(f"✅ Extraído 1 registro para {tipo_cultura}")
                return [dados]
            else:
                st.warning(f"Formato inesperado: {type(dados)}")
                return []
                
        except json.JSONDecodeError as je:
            st.warning(f"JSONDecodeError: {str(je)}")
            
            # Tentar extrair JSON da resposta
            array_match = re.search(r'(\[\s*\{.*\}\s*\])', resposta_limpa, re.DOTALL)
            if array_match:
                try:
                    json_str = array_match.group(1)
                    # Corrigir JSON
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)
                    # Corrigir aspas
                    json_str = re.sub(r'([{,]\s*)(\w+)(\s*:)', r'\1"\2"\3', json_str)
                    dados = json.loads(json_str)
                    st.info(f"✅ Extraídos {len(dados)} registro(s) após limpeza")
                    return dados
                except Exception as e:
                    st.warning(f"Erro ao parsear array extraído: {str(e)}")
            
            # Tentar encontrar objetos individuais
            obj_matches = re.findall(r'\{[^{}]*\}', resposta_limpa)
            if obj_matches:
                dados = []
                for obj_str in obj_matches:
                    try:
                        obj_str_corrigido = re.sub(r'([{,]\s*)(\w+)(\s*:)', r'\1"\2"\3', obj_str)
                        obj = json.loads(obj_str_corrigido)
                        dados.append(obj)
                    except:
                        continue
                if dados:
                    st.info(f"✅ Extraídos {len(dados)} registro(s) de múltiplos objetos")
                    return dados
            
            st.error(f"Não foi possível extrair JSON válido para {tipo_cultura}")
            return []
            
    except Exception as e:
        st.error(f"Erro na extração para {tipo_cultura}: {str(e)}")
        return []

# Função para criar DataFrame com tratamento de cultura
def criar_dataframe(dados, tipo_cultura):
    if not dados or not isinstance(dados, list):
        return pd.DataFrame(columns=COLUNAS_EXATAS)
    
    linhas = []
    for item in dados:
        if isinstance(item, dict):
            linha = {}
            for coluna in COLUNAS_EXATAS:
                valor = "NR"
                
                # Buscar exatamente
                if coluna in item:
                    valor = item[coluna]
                else:
                    # Buscar por similaridade
                    for chave in item.keys():
                        if coluna.lower() == chave.lower().strip():
                            valor = item[chave]
                            break
                        elif coluna.lower() in chave.lower() or chave.lower() in coluna.lower():
                            valor = item[chave]
                            break
                
                # Processar valor
                if valor is None:
                    valor = "NR"
                elif isinstance(valor, (int, float)):
                    valor = str(valor)
                elif not isinstance(valor, str):
                    valor = str(valor)
                
                # Limpar valor
                if isinstance(valor, str):
                    valor = valor.strip()
                    if valor == "":
                        valor = "NR"
                
                # FORÇAR "NR" para REC se for Milho
                if coluna == "REC" and tipo_cultura == "Milho":
                    valor = "NR"
                
                linha[coluna] = valor
            
            # Garantir que a cultura está correta
            linha["Cultura"] = tipo_cultura
            
            # Verificar se tem dados válidos
            valores_nao_nr = [v for v in linha.values() if v != "NR"]
            if valores_nao_nr:
                linhas.append(linha)
    
    if linhas:
        df = pd.DataFrame(linhas)
        
        # Garantir todas as colunas
        for col in COLUNAS_EXATAS:
            if col not in df.columns:
                df[col] = "NR"
        
        # Ordenar colunas
        df = df[COLUNAS_EXATAS]
        
        # Ordenar por Nome do produto e REC (se houver)
        colunas_ordenacao = ['Nome do produto'] if 'Nome do produto' in df.columns else []
        if 'REC' in df.columns and tipo_cultura == "Soja":
            colunas_ordenacao.append('REC')
        
        if colunas_ordenacao:
            df = df.sort_values(colunas_ordenacao).reset_index(drop=True)
        
        return df
    else:
        return pd.DataFrame(columns=COLUNAS_EXATAS)

# Função para gerar CSV
def gerar_csv_para_gsheets(df):
    if df.empty:
        return ""
    
    output = io.StringIO()
    writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    
    # Escrever cabeçalho
    writer.writerow(COLUNAS_EXATAS)
    
    # Escrever dados
    for _, row in df.iterrows():
        linha = []
        for col in COLUNAS_EXATAS:
            valor = row.get(col)
            if pd.isna(valor) or valor is None:
                valor = ""
            elif isinstance(valor, str):
                valor = valor.strip()
            else:
                valor = str(valor).strip()
            
            if valor in ["nan", "None", "null", "NaN", "<NA>", "NaT", "NR"]:
                valor = ""
            
            linha.append(valor)
        writer.writerow(linha)
    
    return output.getvalue()

# Interface principal
def main():
    st.markdown("### 📤 Carregue um arquivo PDF com informações de cultivares")
    
    # Seletor de tipo de cultura
    st.markdown("### 🌽 Selecione o tipo de cultura:")
    tipo_cultura = st.radio(
        "Tipo de cultura:",
        ["Milho", "Soja"],
        horizontal=True,
        index=0 if st.session_state.tipo_cultura == "Milho" else 1
    )
    
    # Atualizar session state
    st.session_state.tipo_cultura = tipo_cultura
    
    st.markdown(f"**Configuração atual:** {tipo_cultura}")
    if tipo_cultura == "Soja":
        st.info("🔍 Para Soja: o sistema extrairá números de REC das tabelas")
    else:
        st.info("🌽 Para Milho: a coluna REC será sempre 'NR'")
    
    uploaded_file = st.file_uploader(
        f"Selecione um arquivo PDF de {tipo_cultura}:",
        type=["pdf"],
        help=f"PDF técnico sobre cultivares de {tipo_cultura}"
    )
    
    if uploaded_file:
        st.success(f"✅ Arquivo carregado: **{uploaded_file.name}**")
        
        col1, col2 = st.columns(2)
        with col1:
            processar = st.button("🚀 Processar PDF", type="primary", use_container_width=True)
        with col2:
            if st.button("🗑️ Limpar tudo", use_container_width=True):
                st.session_state.df = pd.DataFrame(columns=COLUNAS_EXATAS)
                st.session_state.csv_content = ""
                st.session_state.texto_transcrito = ""
                st.session_state.imagens_paginas = []
                st.rerun()
        
        # Campo para colar texto transcrito manualmente
        with st.expander("⚙️ Debug: Colar texto transcrito manualmente"):
            texto_manual = st.text_area("Cole o texto transcrito aqui para testar:", height=200)
            if st.button("Testar com este texto") and texto_manual:
                st.session_state.texto_transcrito = texto_manual
                st.success("Texto carregado para teste!")
        
        if processar:
            with st.spinner("Processando..."):
                # Limpar estado anterior
                st.session_state.df = pd.DataFrame(columns=COLUNAS_EXATAS)
                st.session_state.csv_content = ""
                st.session_state.texto_transcrito = ""
                st.session_state.imagens_paginas = []
                
                try:
                    # PASSO 1: Converter PDF para imagens
                    with st.spinner("🔄 Convertendo PDF para imagens..."):
                        imagens = pdf_para_imagens(uploaded_file.getvalue())
                        if not imagens:
                            st.error("❌ Falha ao converter PDF")
                            return
                        st.session_state.imagens_paginas = imagens
                    
                    # PASSO 2: Transcrever imagens
                    with st.spinner("🤖 Transcrevendo texto das páginas..."):
                        texto_completo = processar_imagens_em_lote(imagens, batch_size=2)
                        if texto_completo:
                            st.session_state.texto_transcrito = texto_completo
                            st.success(f"✅ Transcrição concluída para {tipo_cultura}")
                            
                            # Mostrar amostra do texto
                            with st.expander("📝 Ver texto transcrito (amostra)"):
                                st.text_area("Texto:", texto_completo[:3000], height=300)
                        else:
                            st.error("❌ Falha na transcrição")
                            return
                    
                    # PASSO 3: Extrair dados
                    with st.spinner(f"📊 Extraindo dados para {tipo_cultura}..."):
                        dados = extrair_dados_para_csv(texto_completo, tipo_cultura)
                        
                        if dados:
                            st.info(f"ℹ️ {len(dados)} registro(s) encontrado(s)")
                            
                            # Criar DataFrame
                            df = criar_dataframe(dados, tipo_cultura)
                            st.session_state.df = df
                            
                            if not df.empty:
                                # Gerar CSV
                                csv_content = gerar_csv_para_gsheets(df)
                                st.session_state.csv_content = csv_content
                                st.success(f"✅ {len(df)} linha(s) extraída(s) com sucesso!")
                                
                                # Mostrar estatísticas
                                st.markdown("### 📊 Estatísticas:")
                                col1, col2, col3, col4 = st.columns(4)
                                with col1:
                                    st.metric("Linhas", len(df))
                                with col2:
                                    if 'Cultura' in df.columns:
                                        st.metric("Cultura", tipo_cultura)
                                with col3:
                                    if 'Nome do produto' in df.columns:
                                        produtos = df['Nome do produto'].unique()
                                        st.metric("Produtos", len(produtos))
                                with col4:
                                    if 'REC' in df.columns:
                                        if tipo_cultura == "Soja":
                                            recs_validos = sum([1 for val in df['REC'] if str(val).strip() not in ['', 'NR']])
                                            st.metric("RECs", recs_validos)
                                        else:
                                            st.metric("RECs", "NR (Milho)")
                                
                                # Mostrar amostra dos dados
                                with st.expander("👀 Visualizar amostra dos dados"):
                                    st.dataframe(df.head(), use_container_width=True)
                            else:
                                st.warning("⚠️ DataFrame vazio após processamento")
                        else:
                            st.warning("⚠️ Nenhum dado estruturado encontrado no texto")
                
                except Exception as e:
                    st.error(f"❌ Erro no processamento: {str(e)}")
        
        # Mostrar resultados se existirem
        df = st.session_state.df
        
        if not df.empty:
            st.markdown("---")
            st.markdown(f"### 📋 Dados Extraídos para {tipo_cultura} ({len(df)} linha(s))")
            
            # Mostrar DataFrame completo
            st.markdown("### 📊 Tabela Completa de Dados")
            
            # Filtrar colunas com dados
            colunas_com_dados = []
            for col in COLUNAS_EXATAS:
                if col in df.columns:
                    valores_unicos = df[col].dropna().unique()
                    valores_validos = [v for v in valores_unicos if str(v).strip() not in ['', 'NR', 'nan']]
                    if valores_validos:
                        colunas_com_dados.append(col)
            
            if len(colunas_com_dados) < len(COLUNAS_EXATAS):
                st.info(f"Mostrando {len(colunas_com_dados)} colunas com dados")
            
            # Mostrar tabela
            st.dataframe(df[colunas_com_dados] if colunas_com_dados else df, use_container_width=True, height=400)
            
            # Verificação especial para REC
            if tipo_cultura == "Milho":
                if 'REC' in df.columns:
                    recs = df['REC'].unique()
                    if len(recs) == 1 and recs[0] == "NR":
                        st.success("✅ Coluna REC corretamente definida como 'NR' para Milho")
                    else:
                        st.warning(f"⚠️ Atenção: REC encontrados para Milho: {recs}")
            
            # Download
            st.markdown("---")
            st.markdown("### 📥 Download dos Dados")
            
            nome_base = uploaded_file.name.split('.')[0]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            if st.session_state.csv_content:
                col_dl1, col_dl2 = st.columns(2)
                
                with col_dl1:
                    st.download_button(
                        label="⬇️ Baixar CSV",
                        data=st.session_state.csv_content.encode('utf-8'),
                        file_name=f"{tipo_cultura.lower()}_cultivares_{nome_base}_{timestamp}.csv",
                        mime="text/csv",
                        type="primary",
                        use_container_width=True
                    )
                
                with col_dl2:
                    json_data = df.to_json(orient='records', indent=2, force_ascii=False)
                    st.download_button(
                        label="⬇️ Baixar JSON",
                        data=json_data.encode('utf-8'),
                        file_name=f"{tipo_cultura.lower()}_cultivares_{nome_base}_{timestamp}.json",
                        mime="application/json",
                        use_container_width=True
                    )
        
        elif st.session_state.texto_transcrito:
            st.info("📝 Texto transcrito disponível, mas nenhum dado estruturado foi extraído.")
            
            with st.expander("Ver texto transcrito completo"):
                st.text_area("Texto:", st.session_state.texto_transcrito, height=400)
    
    else:
        st.info("👆 **Carregue um arquivo PDF acima para começar**")
        
        with st.expander("ℹ️ Como usar esta ferramenta"):
            st.markdown(f"""
            ### 📋 Fluxo de Processamento:
            
            1. **Selecione o tipo de cultura**: Milho ou Soja
            2. **Carregue um PDF** com informações de cultivares
            3. **Conversão**: Cada página vira uma imagem
            4. **Transcrição**: IA extrai texto das imagens
            5. **Extração**: IA identifica dados nas {len(COLUNAS_EXATAS)} colunas
            6. **Download**: CSV e JSON disponíveis
            
            ### 🔍 Diferenças por cultura:
            
            **🌽 MILHO:**
            - Coluna REC sempre preenchida com "NR"
            - Doenças específicas do milho não preenchem colunas de soja
            - Cada linha representa uma cultivar com seus meses
            
            **🌱 SOJA:**
            - Extrai números de REC das tabelas
            - Preenche colunas de doenças específicas da soja
            - Cada REC gera uma linha separada
            - Valida resistências a nematoides e doenças
            
            ### ⚠️ Observações:
            - Processamento pode levar alguns minutos
            - Verifique sempre os dados extraídos
            - Para Milho, REC será sempre "NR"
            - Para Soja, verifique se os RECs foram extraídos corretamente
            """)

if __name__ == "__main__":
    main()
