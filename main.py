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
    "Região", "Mês 1", "Mês 2", "Mês 3", "Mês 4", "Mês 5", "Mês 6", "Mês 7", 
    "Mês 8", "Mês 9", "Mês 10", "Mês 11", "Mês 12"
]

# Session state
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=COLUNAS_EXATAS)
if 'csv_content' not in st.session_state:
    st.session_state.csv_content = ""
if 'texto_transcrito' not in st.session_state:
    st.session_state.texto_transcrito = ""
if 'imagens_paginas' not in st.session_state:
    st.session_state.imagens_paginas = []
if 'pagina_atual' not in st.session_state:
    st.session_state.pagina_atual = 1

# Função 1: Converter PDF para imagens (uma imagem por página)
def pdf_para_imagens(pdf_bytes):
    try:
        st.info("Convertendo PDF para imagens...")
        
        # Converter PDF para lista de imagens (uma por página)
        imagens = convert_from_bytes(
            pdf_bytes,
            dpi=300,  # DPI para boa qualidade de OCR
            fmt='PNG',
            thread_count=4,  # Usar múltiplas threads para processamento mais rápido
            poppler_path=None  # Se tiver poppler instalado, pode especificar o caminho
        )
        
        st.success(f"✅ PDF convertido em {len(imagens)} página(s)")
        return imagens
        
    except Exception as e:
        st.error(f"Erro ao converter PDF para imagens: {str(e)}")
        st.info("Tentando método alternativo...")
        
        # Método alternativo com PyMuPDF
        try:
            imagens = []
            
            # Abrir PDF com PyMuPDF
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # Definir matriz para renderização em alta qualidade
                mat = fitz.Matrix(300/72, 300/72)  # 300 DPI
                
                # Renderizar página como imagem
                pix = page.get_pixmap(matrix=mat)
                
                # Converter para PIL Image
                img_data = pix.tobytes("ppm")
                img = Image.open(io.BytesIO(img_data))
                
                # Converter para RGB se necessário
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
    """Processa imagens em lotes para evitar rate limits"""
    if not imagens:
        return ""
    
    texto_completo = ""
    total_paginas = len(imagens)
    
    # Criar barra de progresso
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
                # Converter imagem para bytes
                img_bytes = io.BytesIO()
                imagem.save(img_bytes, format='PNG', optimize=True)
                img_bytes = img_bytes.getvalue()
                
                # Prompt específico para transcrever texto de cultivares
                prompt = """TRANSCREVA TODO o texto desta página EXATAMENTE como aparece.
                
                INSTRUÇÕES IMPORTANTES:
                1. Transcreva TODO o texto visível
                2. Mantenha a formatação original (linhas, espaços)
                3. Inclua tabelas, números, datas
                4. Especial atenção para:
                   - Nomes de cultivares (ex: Soja XYZ, Milho ABC)
                   - Números de registro (REC, Registro, RDC)
                   - Características técnicas
                   - Regiões e estados
                   - Datas e períodos
                   - Dados de produtividade
                5. Se houver texto em colunas, mantenha a ordem
                6. Se houver tabelas, transcreva linha por linha
                
                Retorne APENAS o texto transcrito."""
                
                response = modelo_visao.generate_content([
                    prompt,
                    {"mime_type": "image/png", "data": img_bytes}
                ])
                
                texto_pagina = response.text.strip()
                texto_completo += f"\n\n--- PÁGINA {pagina_num} ---\n{texto_pagina}\n"
                
                # Pequena pausa para evitar rate limit
                import time
                time.sleep(0.5)
                
            except Exception as e:
                texto_completo += f"\n\n--- ERRO PÁGINA {pagina_num}: {str(e)[:100]} ---\n"
                continue
        
        # Pequena pausa entre lotes
        import time
        if batch_end < total_paginas:
            time.sleep(2)
    
    progress_bar.empty()
    status_text.empty()
    
    return texto_completo

# Função 3: Extrair dados do texto transcrito
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
       - Procure por: "REC", "Registro", "RDC", "Nº", "No.", "Número"
       - Padrões: "REC 20205", "Registro: 30456", "RDC 12345", "Nº 67890"
       - Geralmente são 5 dígitos: 12345, 20205, 30456
       - Extraia APENAS os números: "REC 20205" → "20205"

    3. PARA OUTROS CAMPOS IMPORTANTES:
       - "Cultura": Soja, Milho, Feijão, Trigo, etc.
       - "Nome do produto": Nome comercial
       - "Região (por extenso)": Sul, Sudeste, Centro-Oeste, Nordeste, Norte
       - "Estado (por extenso)": Rio Grande do Sul, São Paulo, Mato Grosso, etc.
       - "Ciclo": Precoce, Médio, Tardio
       - "Lançamento": Ano (ex: 2020, 2023)
       - "PMS MÉDIO": Peso de mil sementes (ex: "150-160 g")
       - Resistências: R (Resistente), MR (Moderadamente Resistente), S (Suscetível)
       - Produtividade: Mantenha formato "XX,XX sc/ha" ou "kg/ha"

    4. PARA OS MESES (Mês 1 a Mês 12):
       - Procure por "Época de plantio", "Semeadura", "Período"
       - Formato: "outubro-novembro" ou "10-11"
       - Se for intervalo: "setembro a dezembro" → preencher Mês 9, 10, 11, 12
       - Use "X" para meses recomendados, "" para não recomendados

    5. REGRAS GERAIS:
       - Use "NR" para informações não encontradas
       - Mantenha os nomes das colunas EXATAMENTE como estão
       - Para campos numéricos, mantenha unidades quando aplicável
       - Para múltiplos valores, separe com vírgula

    6. FORMATO DE SAÍDA:
       - Retorne APENAS um array JSON válido
       - Cada objeto representa uma cultivar
       - Cada objeto deve ter {len(COLUNAS_EXATAS)} propriedades
       - Nomes das propriedades DEVEM ser exatos

    EXEMPLO DE SAÍDA:
    [
      {{
        "Cultura": "Soja",
        "Nome do produto": "BRS 8380",
        "NOME TÉCNICO/ REG": "BRS 8380 IPRO",
        "REC": "20205",
        "Região (por extenso)": "Sul,Sudeste",
        "Estado (por extenso)": "Rio Grande do Sul,Paraná,São Paulo",
        "Ciclo": "Médio",
        "Lançamento": "2020",
        "Mês 1": "X",
        "Mês 2": "X",
        "Mês 3": "",
        ... // todas as outras colunas
      }}
    ]
    """
    
    try:
        # Dividir prompt se for muito longo
        max_chars = 30000
        if len(prompt) > max_chars:
            # Manter as instruções completas e parte do texto
            texto_resumido = texto_transcrito[:max_chars - 20000]
            prompt = prompt.replace(texto_transcrito, f"{texto_resumido}\n...[texto continua além do limite de caracteres]")
        
        response = modelo_texto.generate_content(prompt)
        resposta = response.text.strip()
        
        # Limpar resposta
        resposta_limpa = resposta.replace('```json', '').replace('```', '').replace('JSON', '').strip()
        
        # Tentar parsear JSON
        try:
            dados = json.loads(resposta_limpa)
            if isinstance(dados, list):
                return dados
            elif isinstance(dados, dict):
                return [dados]
            else:
                st.warning(f"Formato inesperado: {type(dados)}")
                return []
                
        except json.JSONDecodeError as je:
            st.warning(f"JSONDecodeError: {str(je)}")
            
            # Tentar extrair JSON da resposta
            # Procurar por array JSON
            array_match = re.search(r'(\[\s*\{.*\}\s*\])', resposta_limpa, re.DOTALL)
            if array_match:
                try:
                    json_str = array_match.group(1)
                    # Limpar possíveis problemas
                    json_str = re.sub(r',\s*}', '}', json_str)  # Remover vírgulas antes de }
                    json_str = re.sub(r',\s*]', ']', json_str)  # Remover vírgulas antes de ]
                    dados = json.loads(json_str)
                    return dados
                except Exception as e:
                    st.warning(f"Erro ao parsear array extraído: {str(e)}")
            
            # Procurar por múltiplos objetos
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
                    return dados
            
            # Última tentativa: usar eval com segurança
            try:
                # Verificar se parece JSON
                if resposta_limpa.startswith('[') and resposta_limpa.endswith(']'):
                    # Substituir aspas simples por duplas
                    corrigido = resposta_limpa.replace("'", '"')
                    # Corrigir vírgulas finais
                    corrigido = re.sub(r',\s*}', '}', corrigido)
                    corrigido = re.sub(r',\s*]', ']', corrigido)
                    
                    dados = json.loads(corrigido)
                    if isinstance(dados, list):
                        return dados
            except:
                pass
            
            st.error(f"Não foi possível extrair JSON da resposta")
            return []
            
    except Exception as e:
        st.error(f"Erro na extração: {str(e)}")
        return []

# Função 4: Criar DataFrame
def criar_dataframe(dados):
    if not dados or not isinstance(dados, list):
        return pd.DataFrame(columns=COLUNAS_EXATAS)
    
    linhas = []
    for item in dados:
        if isinstance(item, dict):
            linha = {}
            for coluna in COLUNAS_EXATAS:
                # Procurar valor
                valor = "NR"
                
                # Buscar exatamente
                if coluna in item:
                    valor = item[coluna]
                else:
                    # Buscar por similaridade (case insensitive)
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
                
                linha[coluna] = valor.strip() if valor.strip() != "" else "NR"
            
            # Adicionar apenas se tiver dados válidos
            valores_validos = [v for v in linha.values() if v != "NR"]
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
            valor = str(row.get(col, "NR")).strip()
            if valor in ["", "nan", "None", "null", "NaN", "<NA>", "NaT"]:
                valor = "NR"
            linha.append(valor)
        writer.writerow(linha)
    
    return output.getvalue()

# Função 6: Pré-visualizar páginas
def mostrar_previa_paginas(imagens, max_preview=5):
    st.markdown("### 📄 Pré-visualização das Páginas")
    
    cols = st.columns(min(len(imagens[:max_preview]), 5))
    
    for idx, (col, img) in enumerate(zip(cols, imagens[:max_preview])):
        with col:
            # Redimensionar para pré-visualização
            preview = img.copy()
            preview.thumbnail((200, 300))
            st.image(preview, caption=f"Página {idx + 1}", use_column_width=True)
    
    if len(imagens) > max_preview:
        st.info(f"... e mais {len(imagens) - max_preview} página(s)")

# Interface principal
def main():
    st.markdown("### 📤 Carregue um arquivo PDF com informações de cultivares")
    
    uploaded_file = st.file_uploader(
        "Selecione um arquivo PDF:",
        type=["pdf"],
        help="PDF técnico sobre cultivares agrícolas"
    )
    
    if uploaded_file:
        st.success(f"✅ Arquivo carregado: **{uploaded_file.name}** ({uploaded_file.size:,} bytes)")
        
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
                        st.error("❌ Falha ao converter PDF para imagens")
                        return
                    
                    st.session_state.imagens_paginas = imagens
                    st.success(f"✅ {len(imagens)} página(s) convertida(s) com sucesso")
                
                # Mostrar prévia das páginas
                mostrar_previa_paginas(imagens)
                
                # PASSO 2: Transcrever imagens
                with st.spinner("🤖 Transcrevendo texto das páginas..."):
                    texto_completo = processar_imagens_em_lote(imagens)
                    
                    if texto_completo:
                        st.session_state.texto_transcrito = texto_completo
                        st.success(f"✅ Transcrição concluída ({len(texto_completo):,} caracteres)")
                    else:
                        st.error("❌ Falha na transcrição")
                        return
                
                # PASSO 3: Extrair dados
                with st.spinner("📊 Extraindo dados estruturados..."):
                    dados = extrair_dados_para_csv(texto_completo)
                    
                    if dados:
                        st.info(f"ℹ️ {len(dados)} registro(s) encontrado(s)")
                        
                        # Criar DataFrame
                        df = criar_dataframe(dados)
                        st.session_state.df = df
                        
                        if not df.empty:
                            # Gerar CSV
                            csv_content = gerar_csv_para_gsheets(df)
                            st.session_state.csv_content = csv_content
                            st.success(f"✅ {len(df)} cultivar(s) extraída(s) com sucesso!")
                            
                            # Verificar campos importantes
                            campos_importantes = ['REC', 'Cultura', 'Nome do produto', 'Região (por extenso)']
                            for campo in campos_importantes:
                                if campo in df.columns:
                                    valores_unicos = df[campo].unique()
                                    valores_validos = [v for v in valores_unicos if v != "NR"]
                                    if valores_validos:
                                        st.info(f"**{campo}**: {len(valores_validos)} valor(es) encontrado(s)")
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
            st.markdown(f"### 📋 Resultados: {len(df)} cultivar(s) encontrada(s)")
            
            # Estatísticas
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total de Cultivares", len(df))
            with col2:
                campos_preenchidos = sum([1 for col in df.columns if df[col].nunique() > 1])
                st.metric("Campos Preenchidos", f"{campos_preenchidos}/{len(COLUNAS_EXATAS)}")
            with col3:
                if 'REC' in df.columns:
                    rec_validos = sum([1 for val in df['REC'] if val != 'NR'])
                    st.metric("RECs Válidos", rec_validos)
            with col4:
                if 'Cultura' in df.columns:
                    culturas = df['Cultura'].nunique()
                    st.metric("Tipos de Cultura", culturas)
            
            # Mostrar texto transcrito (resumido)
            with st.expander("📝 Ver texto transcrito (resumido)"):
                texto_resumido = st.session_state.texto_transcrito[:5000] + "..." if len(st.session_state.texto_transcrito) > 5000 else st.session_state.texto_transcrito
                st.text_area("Texto extraído:", texto_resumido, height=300)
            
            # Mostrar DataFrame
            st.markdown("### 📊 Dados Extraídos")
            st.dataframe(df, use_container_width=True)
            
            # Mostrar valores únicos de REC se existirem
            if 'REC' in df.columns:
                rec_values = df['REC'].unique()
                valid_recs = [v for v in rec_values if v != 'NR']
                if valid_recs:
                    st.markdown("### 🔍 Valores de REC Encontrados:")
                    for rec in valid_recs[:10]:  # Mostrar apenas os primeiros 10
                        st.code(f"REC: {rec}", language="text")
                    if len(valid_recs) > 10:
                        st.info(f"... e mais {len(valid_recs) - 10} outros")
            
            # Download
            st.markdown("---")
            st.markdown("### 📥 Download dos Dados")
            
            nome_base = uploaded_file.name.split('.')[0]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            if st.session_state.csv_content:
                col_dl1, col_dl2, col_dl3 = st.columns(3)
                
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
                    # JSON
                    json_data = df.to_json(orient='records', indent=2, force_ascii=False)
                    st.download_button(
                        label="⬇️ Baixar JSON",
                        data=json_data.encode('utf-8'),
                        file_name=f"cultivares_{nome_base}_{timestamp}.json",
                        mime="application/json",
                        use_container_width=True
                    )
                
                with col_dl3:
                    # Excel
                    excel_buffer = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Cultivares')
                    excel_buffer.seek(0)
                    
                    st.download_button(
                        label="⬇️ Baixar Excel",
                        data=excel_buffer.getvalue(),
                        file_name=f"cultivares_{nome_base}_{timestamp}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
        
        elif st.session_state.texto_transcrito:
            st.info("📝 Texto transcrito disponível, mas nenhum dado estruturado foi extraído.")
            
            with st.expander("Ver texto transcrito"):
                texto_resumido = st.session_state.texto_transcrito[:2000] + "..." if len(st.session_state.texto_transcrito) > 2000 else st.session_state.texto_transcrito
                st.text_area("Texto:", texto_resumido, height=300)
    
    else:
        st.info("👆 **Carregue um arquivo PDF acima para começar**")
        
        # Exemplo de uso
        with st.expander("ℹ️ Como usar esta ferramenta"):
            st.markdown("""
            ### 📋 Fluxo de Processamento:
            
            1. **Carregue um PDF** com informações de cultivares agrícolas
            2. **Conversão automática**: Cada página vira uma imagem
            3. **Transcrição com IA**: Gemini Vision extrai texto das imagens
            4. **Extração estruturada**: IA identifica e organiza os dados
            5. **Geração de CSV**: Dados formatados para 81 colunas específicas
            
            ### 🔍 O que buscar no PDF:
            - **Nomes de cultivares** (BRS, SYN, DM, etc.)
            - **Números de REC/Registro** (5 dígitos, ex: 20205)
            - **Características técnicas** (ciclo, fertilidade, resistências)
            - **Regiões e estados** recomendados
            - **Épocas de plantio** (meses)
            - **Dados de produtividade** (sc/ha, kg/ha)
            
            ### ⚠️ Observações:
            - Processamento pode levar alguns minutos para PDFs grandes
            - Imagens de melhor qualidade = melhor reconhecimento
            - Verifique sempre os dados extraídos
            """)

if __name__ == "__main__":
    main()
