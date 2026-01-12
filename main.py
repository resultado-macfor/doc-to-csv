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
import pdf2image
from pdf2image import convert_from_bytes
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
    for num in ["1", "2", "3"]:  # Janeiro 1, Janeiro 2, Janeiro 3, etc.
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
] + meses_detalhados  # Adicionar os 36 meses detalhados (12 meses × 3)

# Session state
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=COLUNAS_EXATAS)
if 'csv_content' not in st.session_state:
    st.session_state.csv_content = ""
if 'texto_transcrito' not in st.session_state:
    st.session_state.texto_transcrito = ""
if 'imagens_paginas' not in st.session_state:
    st.session_state.imagens_paginas = []

# Função 1: Converter PDF para imagens (uma imagem por página)
def pdf_para_imagens(pdf_bytes):
    try:
        st.info("Convertendo PDF para imagens...")
        
        # Converter PDF para lista de imagens (uma por página)
        imagens = convert_from_bytes(
            pdf_bytes,
            dpi=300,
            fmt='PNG',
            thread_count=4,
            poppler_path=None
        )
        
        st.success(f"✅ PDF convertido em {len(imagens)} página(s)")
        return imagens
        
    except Exception as e:
        st.error(f"Erro ao converter PDF para imagens: {str(e)}")
        st.info("Tentando método alternativo...")
        
        try:
            imagens = []
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                mat = fitz.Matrix(300/72, 300/72)
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("ppm")
                img = Image.open(io.BytesIO(img_data))
                
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                imagens.append(img)
            
            doc.close()
            st.success(f"✅ PDF convertido em {len(imagens)} página(s) - Método alternativo")
            return imagens
            
        except Exception as e2:
            st.error(f"Erro no método alternativo: {str(e2)}")
            return []

# Função 2: Processar imagens em lote para transcrever
def processar_imagens_em_lote(imagens, batch_size=10):
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
                img_bytes = io.BytesIO()
                imagem.save(img_bytes, format='PNG', optimize=True)
                img_bytes = img_bytes.getvalue()
                
                prompt = """TRANSCREVA TODO o texto desta página EXATAMENTE como aparece.
                
                INSTRUÇÕES IMPORTANTES:
                1. Transcreva TODO o texto visível
                2. Mantenha a formatação original (linhas, espaços)
                3. Inclua tabelas, números, datas
                4. Especial atenção para:
                   - Nomes de cultivares
                   - Números de REC/Registro
                   - Características técnicas
                   - Regiões e estados
                   - Datas e períodos
                   - Dados de produtividade
                   - Valores em tabelas de meses
                5. Se houver texto em colunas, mantenha a ordem
                6. Se houver tabelas, transcreva linha por linha
                
                Retorne APENAS o texto transcrito."""
                
                response = modelo_visao.generate_content([
                    prompt,
                    {"mime_type": "image/png", "data": img_bytes}
                ])
                
                texto_pagina = response.text.strip()
                texto_completo += f"\n\n--- PÁGINA {pagina_num} ---\n{texto_pagina}\n"
                
                import time
                time.sleep(0.5)
                
            except Exception as e:
                texto_completo += f"\n\n--- ERRO PÁGINA {pagina_num}: {str(e)[:100]} ---\n"
                continue
        
        import time
        if batch_end < total_paginas:
            time.sleep(2)
    
    progress_bar.empty()
    status_text.empty()
    
    return texto_completo

# Função 3: Extrair dados do texto transcrito (ATUALIZADA)
def extrair_dados_para_csv(texto_transcrito):
    prompt = f"""
    ANALISE O TEXTO TRANSCRITO DE UM PDF SOBRE CULTIVARES AGRÍCOLAS:

    TEXTO TRANSCRITO:
    {texto_transcrito}

    SUA TAREFA: Extrair informações sobre cultivares e preencher estas {len(COLUNAS_EXATAS)} colunas:

    {', '.join(COLUNAS_EXATAS)}

    INSTRUÇÕES DETALHADAS:

    1. IDENTIFICAÇÃO DE CULTIVARES:
       - Procure por nomes de cultivares (ex: "BRS 8380", "SYN 136", "DM 595")
       - Cada cultivar única deve ter uma linha no CSV
       - Se houver múltiplas cultivares no mesmo texto, crie uma entrada para cada

    2. FOCO NO CAMPO "REC" (CRÍTICO):
       - Procure por números de REC como: 201, 300, 400, etc.
       - Geralmente são números de 2-5 dígitos
       - Se uma cultivar tiver MAIS DE UM REC, crie uma LINHA SEPARADA para cada REC
       - Se não encontrar REC, use "NR"

    3. PARA OS MESES (36 colunas detalhadas):
       - Formato: "Janeiro 1", "Janeiro 2", "Janeiro 3", "Fevereiro 1", ..., "Dezembro 3"
       - Preencha com os VALORES EXATOS que aparecem nas tabelas
       - Exemplos: "180-260", "90-120", "sc/ha", "kg/ha", números, faixas
       - Deixe em branco ("") se a informação não existir para aquele período
       - NÃO use "X", use os valores reais da tabela

    4. PARA OUTROS CAMPOS IMPORTANTES:
       - "Cultura": Soja, Milho, Feijão, Trigo, etc.
       - "Nome do produto": Nome comercial
       - "Região (por extenso)": Sul, Sudeste, Centro-Oeste, Nordeste, Norte
       - "Estado (por extenso)": Rio Grande do Sul, São Paulo, Mato Grosso, etc.
       - "Ciclo": Precoce, Médio, Tardio
       - "Lançamento": Ano (ex: 2020, 2023)
       - "PMS MÉDIO": Peso de mil sementes (ex: "150-160 g")
       - Resistências: R (Resistente), MR (Moderadamente Resistente), S (Suscetível)
       - Produtividade: Mantenha formato "XX,XX sc/ha" ou "kg/ha"

    5. REGRAS GERAIS:
       - Use "NR" para informações não encontradas
       - Mantenha os nomes das colunas EXATAMENTE como estão acima
       - Para campos numéricos, mantenha unidades quando aplicável
       - Para múltiplos valores, separe com vírgula
       - Para campos de texto, mantenha o texto original

    6. FORMATO DE SAÍDA:
       - Retorne APENAS um array JSON válido
       - Cada objeto representa uma cultivar + REC (uma linha no CSV)
       - Cada objeto deve ter {len(COLUNAS_EXATAS)} propriedades
       - Nomes das propriedades DEVEM ser exatos
       - Inclua TODAS as propriedades, mesmo que vazias

    EXEMPLO DE SAÍDA:
    [
      {{
        "Cultura": "Soja",
        "Nome do produto": "BRS 8380",
        "NOME TÉCNICO/ REG": "BRS 8380 IPRO",
        "REC": "201",
        "Região (por extenso)": "Sul,Sudeste",
        "Estado (por extenso)": "Rio Grande do Sul,Paraná",
        "Ciclo": "Médio",
        "Lançamento": "2020",
        "Janeiro 1": "180-260",
        "Janeiro 2": "200-280",
        "Janeiro 3": "",
        "Fevereiro 1": "190-270",
        "Fevereiro 2": "",
        "Fevereiro 3": "85,50 sc/ha",
        ... // outras colunas de meses com valores reais
        ... // todas as outras colunas
      }},
      {{
        "Cultura": "Soja",
        "Nome do produto": "BRS 8380",
        "NOME TÉCNICO/ REG": "BRS 8380 IPRO",
        "REC": "300",
        "Região (por extenso)": "Centro-Oeste",
        "Estado (por extenso)": "Mato Grosso,Goiás",
        "Ciclo": "Médio",
        "Lançamento": "2020",
        "Janeiro 1": "",
        "Janeiro 2": "150-230",
        "Janeiro 3": "170-250",
        "Fevereiro 1": "",
        "Fevereiro 2": "160-240",
        "Fevereiro 3": "",
        ... // outras colunas de meses com valores reais
        ... // todas as outras colunas
      }}
    ]
    """
    
    try:
        max_chars = 30000
        if len(prompt) > max_chars:
            texto_resumido = texto_transcrito[:max_chars - 20000]
            prompt = prompt.replace(texto_transcrito, f"{texto_resumido}\n...[texto continua além do limite de caracteres]")
        
        response = modelo_texto.generate_content(prompt)
        resposta = response.text.strip()
        
        resposta_limpa = resposta.replace('```json', '').replace('```', '').replace('JSON', '').strip()
        
        try:
            dados = json.loads(resposta_limpa)
            if isinstance(dados, list):
                st.info(f"✅ Extraídos {len(dados)} registro(s)")
                return dados
            elif isinstance(dados, dict):
                st.info(f"✅ Extraído 1 registro")
                return [dados]
            else:
                st.warning(f"Formato inesperado: {type(dados)}")
                return []
                
        except json.JSONDecodeError as je:
            st.warning(f"JSONDecodeError: {str(je)}")
            
            array_match = re.search(r'(\[\s*\{.*\}\s*\])', resposta_limpa, re.DOTALL)
            if array_match:
                try:
                    json_str = array_match.group(1)
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)
                    dados = json.loads(json_str)
                    st.info(f"✅ Extraídos {len(dados)} registro(s) após limpeza")
                    return dados
                except Exception as e:
                    st.warning(f"Erro ao parsear array extraído: {str(e)}")
            
            obj_pattern = r'\{\s*"[^"]*"\s*:[^}]*\}'
            obj_matches = re.findall(obj_pattern, resposta_limpa, re.DOTALL)
            
            if obj_matches:
                dados = []
                for obj_str in obj_matches:
                    try:
                        obj = json.loads(obj_str)
                        dados.append(obj)
                    except:
                        continue
                if dados:
                    st.info(f"✅ Extraídos {len(dados)} registro(s) de múltiplos objetos")
                    return dados
            
            try:
                if resposta_limpa.startswith('[') and resposta_limpa.endswith(']'):
                    corrigido = resposta_limpa.replace("'", '"')
                    corrigido = re.sub(r',\s*}', '}', corrigido)
                    corrigido = re.sub(r',\s*]', ']', corrigido)
                    
                    dados = json.loads(corrigido)
                    if isinstance(dados, list):
                        st.info(f"✅ Extraídos {len(dados)} registro(s) após correção")
                        return dados
            except:
                pass
            
            st.error(f"Não foi possível extrair JSON da resposta")
            return []
            
    except Exception as e:
        st.error(f"Erro na extração: {str(e)}")
        return []

# Função 4: Criar DataFrame com tratamento de múltiplos RECs
def criar_dataframe(dados):
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
                        if coluna.lower() == chave.lower():
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
                
                # Para REC, garantir que seja número ou NR
                if coluna == "REC":
                    if valor == "NR" or not valor.strip():
                        valor = "NR"
                    else:
                        # Extrair apenas números
                        numeros = re.findall(r'\d+', str(valor))
                        if numeros:
                            valor = numeros[0]  # Primeiro número encontrado
                        else:
                            valor = "NR"
                
                linha[coluna] = valor.strip() if isinstance(valor, str) and valor.strip() != "" else valor
            
            # Verificar se tem dados válidos
            valores_validos = [v for v in linha.values() if v != "NR" and v != "" and v is not None]
            if valores_validos:
                linhas.append(linha)
    
    if linhas:
        df = pd.DataFrame(linhas)
        
        # Garantir todas as colunas
        for col in COLUNAS_EXATAS:
            if col not in df.columns:
                df[col] = "NR"
        
        # Ordenar colunas
        df = df[COLUNAS_EXATAS]
        
        # Ordenar por Cultura e REC
        if 'Cultura' in df.columns and 'REC' in df.columns:
            df = df.sort_values(['Cultura', 'REC']).reset_index(drop=True)
        
        return df
    else:
        return pd.DataFrame(columns=COLUNAS_EXATAS)

# Função 5: Gerar CSV
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

# Função 6: Verificar dados
def verificar_dados(df):
    if df.empty:
        return
    
    st.markdown("### 🔍 Análise dos Dados:")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total de Linhas", len(df))
    
    with col2:
        if 'REC' in df.columns:
            rec_validos = sum([1 for val in df['REC'] if str(val).strip() not in ['', 'NR']])
            st.metric("RECs Válidos", rec_validos)
    
    with col3:
        if 'Cultura' in df.columns:
            culturas = df['Cultura'].nunique()
            st.metric("Tipos de Cultura", culturas)
    
    # Mostrar exemplos de valores de meses
    if any(mes in df.columns for mes in meses_detalhados):
        with st.expander("📊 Exemplos de valores de meses"):
            meses_com_dados = [col for col in meses_detalhados if col in df.columns and not df[col].isna().all()]
            if meses_com_dados:
                amostra = df[['Cultura', 'Nome do produto', 'REC'] + meses_com_dados[:5]].head(3)
                st.dataframe(amostra, use_container_width=True)

# Interface principal
def main():
    st.markdown("### 📤 Carregue um arquivo PDF com informações de cultivares")
    st.markdown(f"**Total de colunas: {len(COLUNAS_EXATAS)}**")
    st.markdown(f"**Colunas de meses: {len(meses_detalhados)}** (Janeiro 1 a Dezembro 3)")
    
    uploaded_file = st.file_uploader(
        "Selecione um arquivo PDF:",
        type=["pdf"],
        help="PDF técnico sobre cultivares agrícolas"
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
        
        if processar:
            st.session_state.df = pd.DataFrame(columns=COLUNAS_EXATAS)
            st.session_state.csv_content = ""
            st.session_state.texto_transcrito = ""
            st.session_state.imagens_paginas = []
            
            try:
                with st.spinner("🔄 Convertendo PDF para imagens..."):
                    imagens = pdf_para_imagens(uploaded_file.getvalue())
                    if not imagens:
                        st.error("❌ Falha ao converter PDF")
                        return
                    st.session_state.imagens_paginas = imagens
                    st.success(f"✅ {len(imagens)} página(s) convertida(s)")
                
                with st.spinner("🤖 Transcrevendo texto das páginas..."):
                    texto_completo = processar_imagens_em_lote(imagens)
                    if texto_completo:
                        st.session_state.texto_transcrito = texto_completo
                        st.success(f"✅ Transcrição concluída ({len(texto_completo):,} caracteres)")
                    else:
                        st.error("❌ Falha na transcrição")
                        return
                
                with st.spinner("📊 Extraindo dados estruturados..."):
                    dados = extrair_dados_para_csv(texto_completo)
                    
                    if dados:
                        st.info(f"ℹ️ {len(dados)} registro(s) encontrado(s)")
                        
                        df = criar_dataframe(dados)
                        st.session_state.df = df
                        
                        if not df.empty:
                            csv_content = gerar_csv_para_gsheets(df)
                            st.session_state.csv_content = csv_content
                            st.success(f"✅ {len(df)} linha(s) extraída(s) com sucesso!")
                            verificar_dados(df)
                        else:
                            st.warning("⚠️ DataFrame vazio")
                    else:
                        st.warning("⚠️ Nenhum dado estruturado encontrado")
                
            except Exception as e:
                st.error(f"❌ Erro no processamento: {str(e)}")
        
        df = st.session_state.df
        
        if not df.empty:
            st.markdown("---")
            st.markdown(f"### 📋 Resultados: {len(df)} linha(s) encontrada(s)")
            
            verificar_dados(df)
            
            with st.expander("📝 Ver texto transcrito (resumido)"):
                texto_resumido = st.session_state.texto_transcrito[:5000] + "..." if len(st.session_state.texto_transcrito) > 5000 else st.session_state.texto_transcrito
                st.text_area("Texto extraído:", texto_resumido, height=300)
            
            st.markdown("### 📊 Dados Extraídos")
            
            colunas_com_dados = [col for col in COLUNAS_EXATAS if col in df.columns and not df[col].isna().all() and df[col].nunique() > 1]
            
            if len(colunas_com_dados) < len(COLUNAS_EXATAS):
                st.info(f"Mostrando {len(colunas_com_dados)} colunas com dados")
            
            st.dataframe(df[colunas_com_dados] if colunas_com_dados else df, use_container_width=True)
            
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
                        file_name=f"cultivares_{nome_base}_{timestamp}.csv",
                        mime="text/csv",
                        type="primary",
                        use_container_width=True
                    )
                
                with col_dl2:
                    json_data = df.to_json(orient='records', indent=2, force_ascii=False)
                    st.download_button(
                        label="⬇️ Baixar JSON",
                        data=json_data.encode('utf-8'),
                        file_name=f"cultivares_{nome_base}_{timestamp}.json",
                        mime="application/json",
                        use_container_width=True
                    )
        
        elif st.session_state.texto_transcrito:
            st.info("📝 Texto transcrito disponível, mas nenhum dado estruturado foi extraído.")
            
            with st.expander("Ver texto transcrito"):
                texto_resumido = st.session_state.texto_transcrito[:2000] + "..." if len(st.session_state.texto_transcrito) > 2000 else st.session_state.texto_transcrito
                st.text_area("Texto:", texto_resumido, height=300)
    
    else:
        st.info("👆 **Carregue um arquivo PDF acima para começar**")
        
        with st.expander("ℹ️ Como usar esta ferramenta"):
            st.markdown(f"""
            ### 📋 Fluxo de Processamento:
            
            1. **Carregue um PDF** com informações de cultivares
            2. **Conversão**: Cada página vira uma imagem
            3. **Transcrição**: IA extrai texto das imagens
            4. **Extração**: IA identifica dados em {len(COLUNAS_EXATAS)} colunas
            5. **Download**: CSV e JSON disponíveis
            
            ### 🔍 Dados extraídos:
            - **REC**: Números como 201, 300, 400 (cada REC em linha separada)
            - **Meses**: 36 períodos com valores reais das tabelas
            - **Cultivares**: Nomes e características
            - **Regiões**: Estados e regiões recomendados
            
            ### 📊 Formato dos meses:
            - Janeiro 1, Janeiro 2, Janeiro 3
            - Fevereiro 1, Fevereiro 2, Fevereiro 3
            - ... até Dezembro 3
            - **Valores reais**: "180-260", "sc/ha", números, etc.
            """)

if __name__ == "__main__":
    main()
