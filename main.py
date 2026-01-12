import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
from datetime import datetime
import tempfile
import docx
import io
import csv
import json
import re
from PIL import Image, ImageDraw, ImageFont
import math

# Configuração
st.set_page_config(page_title="Extrator de Cultivares", page_icon="🌱", layout="wide")
st.title("🌱 Extrator de Cultivares")

# API Key
gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEM_API_KEY")
if not gemini_api_key:
    st.error("Configure GEMINI_API_KEY")
    st.stop()

try:
    genai.configure(api_key=gemini_api_key)
    modelo_visao = genai.GenerativeModel("gemini-1.5-pro-vision")
    modelo_texto = genai.GenerativeModel("gemini-1.5-flash")
except Exception as e:
    st.error(f"Erro ao configurar Gemini: {str(e)}")
    st.stop()

# COLUNAS EXATAS - COM MESES DIVIDIDOS EM 3 PERÍODOS
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
    "Nematóide de Cisto (Raça 3", "Nematóide de Cisto (Raça 9)", 
    "Nematóide de Cisto (Raça 10", "Nematóide de Cisto (Raça 14)", 
    "Fitóftora (Raça 1)", "Recomendações", "Resultado 1 - Nome", "Resultado 1 - Local", 
    "Resultado 1", "Resultado 2 - Nome", "Resultado 2 - Local", "Resultado 2", 
    "Resultado 3 - Nome", "Resultado 3 - Local", "Resultado 3", "Resultado 4 - Nome", 
    "Resultado 4 - Local", "Resultado 4", "Resultado 5 - Nome", "Resultado 5 - Lcal", 
    "Resultado 5", "Resultado 6 - Nome", "Resultado 6 - Local", "Resultado 6", 
    "Resultado 7 - Nome", "Resultado 7 - Local", "Resultado 7", "REC", "UF", 
    "Região",
    # Janeiro dividido em 3 períodos
    "Janeiro 1-10", "Janeiro 11-20", "Janeiro 21-31",
    # Fevereiro
    "Fevereiro 1-10", "Fevereiro 11-20", "Fevereiro 21-28/29",
    # Março
    "Março 1-10", "Março 11-20", "Março 21-31",
    # Abril
    "Abril 1-10", "Abril 11-20", "Abril 21-30",
    # Maio
    "Maio 1-10", "Maio 11-20", "Maio 21-31",
    # Junho
    "Junho 1-10", "Junho 11-20", "Junho 21-30",
    # Julho
    "Julho 1-10", "Julho 11-20", "Julho 21-31",
    # Agosto
    "Agosto 1-10", "Agosto 11-20", "Agosto 21-31",
    # Setembro
    "Setembro 1-10", "Setembro 11-20", "Setembro 21-30",
    # Outubro
    "Outubro 1-10", "Outubro 11-20", "Outubro 21-31",
    # Novembro
    "Novembro 1-10", "Novembro 11-20", "Novembro 21-30",
    # Dezembro
    "Dezembro 1-10", "Dezembro 11-20", "Dezembro 21-31"
]

# Session state
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=COLUNAS_EXATAS)
if 'csv_content' not in st.session_state:
    st.session_state.csv_content = ""
if 'texto_transcrito' not in st.session_state:
    st.session_state.texto_transcrito = ""
if 'paginas_processadas' not in st.session_state:
    st.session_state.paginas_processadas = 0

# Função para converter DOCX para imagens
def docx_para_imagens_por_pagina(docx_bytes):
    try:
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
            tmp.write(docx_bytes)
            docx_path = tmp.name
        
        doc = docx.Document(docx_path)
        
        texto_total = ""
        
        for para in doc.paragraphs:
            if para.text.strip():
                texto_total += para.text.strip() + "\n"
        
        for table in doc.tables:
            for row in table.rows:
                cells_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells_text:
                    texto_total += " | ".join(cells_text) + "\n"
        
        caracteres_por_pagina = 2800
        num_paginas_estimado = max(1, math.ceil(len(texto_total) / caracteres_por_pagina))
        
        paginas_texto = []
        linhas = texto_total.split('\n')
        
        pagina_atual = []
        chars_pagina = 0
        
        for linha in linhas:
            chars_linha = len(linha)
            
            if (chars_pagina + chars_linha > caracteres_por_pagina and pagina_atual) or chars_linha > caracteres_por_pagina:
                paginas_texto.append("\n".join(pagina_atual))
                pagina_atual = [linha]
                chars_pagina = chars_linha
            else:
                pagina_atual.append(linha)
                chars_pagina += chars_linha
        
        if pagina_atual:
            paginas_texto.append("\n".join(pagina_atual))
        
        imagens = []
        
        for i, texto_pagina in enumerate(paginas_texto):
            img = Image.new('RGB', (1240, 1754), color='white')
            draw = ImageDraw.Draw(img)
            
            try:
                font = ImageFont.truetype("arial.ttf", 11)
            except:
                font = ImageFont.load_default()
            
            y = 100
            x = 100
            largura_max = 1040
            
            for linha in texto_pagina.split('\n'):
                if linha.strip():
                    if draw.textlength(linha, font=font) > largura_max:
                        palavras = linha.split()
                        linha_atual = ""
                        
                        for palavra in palavras:
                            teste = linha_atual + " " + palavra if linha_atual else palavra
                            if draw.textlength(teste, font=font) <= largura_max:
                                linha_atual = teste
                            else:
                                if y < 1650:
                                    draw.text((x, y), linha_atual, fill='black', font=font)
                                    y += 18
                                linha_atual = palavra
                        
                        if linha_atual and y < 1650:
                            draw.text((x, y), linha_atual, fill='black', font=font)
                            y += 18
                    else:
                        if y < 1650:
                            draw.text((x, y), linha, fill='black', font=font)
                            y += 18
                else:
                    y += 10
            
            draw.text((1100, 1720), f"Página {i+1}/{len(paginas_texto)}", fill='gray', font=font)
            
            imagens.append(img)
        
        os.unlink(docx_path)
        
        return imagens, len(paginas_texto)
        
    except Exception as e:
        st.error(f"Erro na conversão DOCX: {str(e)}")
        return [], 0

# Função para transcrever imagens - FOCO EM TABELAS TEMPORAIS
def transcrever_todas_imagens(imagens, total_paginas):
    if not imagens:
        return "", 0
    
    texto_completo = ""
    paginas_transcritas = 0
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, imagem in enumerate(imagens):
        try:
            progresso = (i + 1) / len(imagens)
            progress_bar.progress(progresso)
            status_text.text(f"Transcrevendo página {i+1} de {len(imagens)}...")
            
            img_bytes = io.BytesIO()
            imagem.save(img_bytes, format='PNG', quality=95)
            img_bytes = img_bytes.getvalue()
            
            prompt = """TRANSCREVA TODO o texto desta página, com ESPECIAL ATENÇÃO para TABELAS TEMPORAIS.

            IDENTIFIQUE TABELAS QUE CONTÊM:
            1. NOMES DOS MESES: Janeiro, Fevereiro, Março, Abril, Maio, Junho, Julho, Agosto, Setembro, Outubro, Novembro, Dezembro
            2. PERÍODOS DO MÊS: 1-10, 11-20, 21-31 (ou 21-28/29 para Fevereiro)
            3. VALORES: números como "180-260", "NR", ou outros valores

            EXEMPLO DE TABELA TEMPORAL:
            | Mês        | 1-10    | 11-20   | 21-31   |
            |------------|---------|---------|---------|
            | Janeiro    | 180-260 | NR      | 180-260 |
            | Fevereiro  | NR      | 180-260 | 180-260 |
            | ...        | ...     | ...     | ...     |

            OU:
            | REC | UF | Janeiro 1-10 | Janeiro 11-20 | Janeiro 21-31 | ... |

            TRANSCREVA TABELAS COMPLETAS COM TODAS AS LINHAS E COLUNAS.
            INCLUA OS CABEÇALHOS E TODOS OS VALORES.
            
            Também transcreva:
            - Tabelas de REC (números como 202, 203)
            - Tabelas de UF (estados: RS, SC, PR, etc.)
            - Tabelas de Região
            - Nomes de produtos (NK401VIP3, etc.)
            
            Use formato claro para tabelas.
            """
            
            response = modelo_visao.generate_content([
                prompt,
                {"mime_type": "image/png", "data": img_bytes}
            ])
            
            texto_completo += f"\n\n{'='*80}\nPÁGINA {i+1}/{len(imagens)}\n{'='*80}\n\n{response.text}\n"
            paginas_transcritas += 1
            
        except Exception as e:
            texto_completo += f"\n\n{'='*80}\nERRO na página {i+1}: {str(e)[:200]}\n{'='*80}\n"
    
    progress_bar.empty()
    status_text.empty()
    
    return texto_completo, paginas_transcritas

# Função para extrair dados com tabelas temporais detalhadas
def extrair_dados_com_tabelas_temporais(texto_transcrito):
    prompt = f"""
    ANALISE ESTE TEXTO COMPLETO DE UM DOCUMENTO AGRÍCOLA:

    TEXTO:
    ```
    {texto_transcrito}
    ```

    SUA TAREFA: Extrair dados para o CSV, com ATENÇÃO ESPECIAL às TABELAS TEMPORAIS.

    COLUNAS DO CSV (total: {len(COLUNAS_EXATAS)} colunas):
    {', '.join(COLUNAS_EXATAS)}

    REGRAS CRÍTICAS PARA TABELAS TEMPORAIS:

    1. ESTRUTURA DAS COLUNAS DE MÊS:
       - Cada mês tem TRÊS colunas: "1-10", "11-20", "21-31"
       - Fevereiro tem "21-28/29" na terceira coluna
       - Exemplo: "Janeiro 1-10", "Janeiro 11-20", "Janeiro 21-31"

    2. IDENTIFICAÇÃO DE TABELAS TEMPORAIS:
       - Procure tabelas com CABEÇALHOS contendo nomes de meses
       - Procure tabelas com PERÍODOS (1-10, 11-20, 21-31)
       - Valores típicos: "180-260", "NR", números, faixas

    3. TIPOS DE TABELAS TEMPORAIS:
       TIPO A (Vertical):
       | Mês       | 1-10    | 11-20   | 21-31   |
       |-----------|---------|---------|---------|
       | Janeiro   | 180-260 | NR      | 180-260 |
       | Fevereiro | NR      | 180-260 | 180-260 |

       TIPO B (Horizontal):
       | REC | UF | Jan 1-10 | Jan 11-20 | Jan 21-31 | Fev 1-10 | ... |

    4. MAPEAMENTO DOS DADOS:
       - Para cada linha (produto + REC), extraia os valores dos 12 meses
       - Cada mês: preencha as 3 colunas correspondentes
       - Use "NR" para períodos sem informação

    5. IDENTIFICAÇÃO DE PRODUTOS E RECs:
       - Produtos: NK401VIP3, NS7524IPRO, TMG, etc.
       - RECs: números como 202, 203, 204
       - UFs: RS, SC, PR, SP, MS, MG, GO, etc.
       - Regiões: Sul, Sudeste, Centro-Oeste, etc.

    6. CRIAÇÃO DE LINHAS MÚLTIPLAS:
       - CADA combinação PRODUTO + REC = UMA LINHA
       - Se um produto tem REC 202, 203, 204 → 3 linhas
       - Cada linha com seus próprios valores temporais

    7. EXEMPLO DE SAÍDA:
       Linha 1:
       - Nome do produto: NK401VIP3
       - REC: 202
       - UF: RS,SC
       - Região: Sul
       - Janeiro 1-10: 180-260
       - Janeiro 11-20: NR
       - Janeiro 21-31: 180-260
       - ... (todos os meses)

       Linha 2 (mesmo produto, REC diferente):
       - Nome do produto: NK401VIP3
       - REC: 203
       - UF: SP,MS
       - Região: Sudeste
       - Janeiro 1-10: 190-270
       - ... (valores diferentes)

    8. SE NÃO HOUVER TABELAS TEMPORAIS:
       - Preencha todas as colunas de meses com "NR"
       - Mantenha as outras informações

    9. FORMATAÇÃO:
       - Valores temporais: "180-260" ou "NR"
       - UF múltiplo: "RS, SC, PR"
       - REC: apenas número "202"
       - Região: "Sul, Sudeste"

    Retorne APENAS um array JSON.
    Cada objeto = uma linha no CSV.
    Cada objeto deve ter {len(COLUNAS_EXATAS)} propriedades (uma para cada coluna).
    """
    
    try:
        with st.spinner("🔍 Analisando tabelas temporais detalhadas..."):
            response = modelo_texto.generate_content(prompt)
            resposta = response.text.strip()
            
            resposta_limpa = resposta.replace('```json', '').replace('```', '').replace('JSON', '').strip()
            
            try:
                dados = json.loads(resposta_limpa)
                if isinstance(dados, list):
                    return dados
                elif isinstance(dados, dict):
                    return [dados]
                else:
                    return []
                    
            except json.JSONDecodeError:
                json_match = re.search(r'(\[.*\])', resposta_limpa, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    dados = json.loads(json_str)
                    return dados
                
                obj_match = re.search(r'(\{.*\})', resposta_limpa, re.DOTALL)
                if obj_match:
                    json_str = obj_match.group(1)
                    dados = json.loads(json_str)
                    return [dados]
                
                return []
            
    except Exception as e:
        st.error(f"Erro na extração de dados: {str(e)}")
        return []

# Função para criar DataFrame
def criar_dataframe_com_tabelas_temporais(dados):
    if not dados or not isinstance(dados, list):
        return pd.DataFrame(columns=COLUNAS_EXATAS)
    
    linhas = []
    for item in dados:
        if isinstance(item, dict):
            linha = {}
            for coluna in COLUNAS_EXATAS:
                valor = item.get(coluna, "NR")
                if isinstance(valor, str):
                    linha[coluna] = valor.strip()
                else:
                    linha[coluna] = str(valor).strip()
            
            if linha.get("Nome do produto", "NR") != "NR":
                linhas.append(linha)
    
    if linhas:
        df = pd.DataFrame(linhas)
        for col in COLUNAS_EXATAS:
            if col not in df.columns:
                df[col] = "NR"
        
        df = df[COLUNAS_EXATAS]
        return df
    else:
        return pd.DataFrame(columns=COLUNAS_EXATAS)

# Função para gerar CSV
def gerar_csv_para_gsheets(df):
    if df.empty:
        return ""
    
    output = io.StringIO()
    writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    
    writer.writerow(COLUNAS_EXATAS)
    
    for _, row in df.iterrows():
        linha = []
        for col in COLUNAS_EXATAS:
            valor = str(row.get(col, "NR")).strip()
            if valor in ["", "nan", "None", "null", "NaN"]:
                valor = "NR"
            linha.append(valor)
        writer.writerow(linha)
    
    return output.getvalue()

# Interface principal
def main():
    st.sidebar.header("📤 Upload do Documento")
    
    uploaded_file = st.sidebar.file_uploader(
        "Carregue um arquivo DOCX:",
        type=["docx"],
        help="Documento com tabelas temporais detalhadas"
    )
    
    if uploaded_file:
        file_size_mb = uploaded_file.size / (1024 * 1024)
        st.sidebar.write(f"**Arquivo:** {uploaded_file.name}")
        st.sidebar.write(f"**Tamanho:** {file_size_mb:.2f} MB")
        
        # Info sobre estrutura temporal
        with st.sidebar.expander("ℹ️ Sobre estrutura temporal"):
            st.write("""
            **Cada mês tem 3 colunas:**
            - 1-10: Dias 1 a 10
            - 11-20: Dias 11 a 20  
            - 21-31: Dias 21 a 31
            - Fevereiro: 21-28/29
            
            **Total: 36 colunas temporais**
            """)
        
        col1, col2 = st.sidebar.columns(2)
        
        with col1:
            if st.sidebar.button("🚀 Processar Tabelas Temporais", type="primary", use_container_width=True):
                st.session_state.df = pd.DataFrame(columns=COLUNAS_EXATAS)
                st.session_state.csv_content = ""
                st.session_state.texto_transcrito = ""
                st.session_state.paginas_processadas = 0
                
                try:
                    with st.spinner("📄 Convertendo documento..."):
                        imagens, num_paginas = docx_para_imagens_por_pagina(uploaded_file.getvalue())
                        
                        if not imagens:
                            st.error("❌ Falha na conversão")
                            return
                        
                        st.success(f"✅ {num_paginas} página(s) convertida(s)")
                        st.session_state.paginas_processadas = num_paginas
                    
                    with st.spinner(f"👁️ Transcrevendo tabelas temporais..."):
                        texto, paginas_transcritas = transcrever_todas_imagens(imagens, num_paginas)
                        
                        if not texto:
                            st.error("❌ Falha na transcrição")
                            return
                        
                        st.session_state.texto_transcrito = texto
                        st.success(f"✅ {paginas_transcritas} página(s) transcrita(s)")
                    
                    with st.spinner("📊 Extraindo dados temporais detalhados..."):
                        dados = extrair_dados_com_tabelas_temporais(texto)
                        
                        if dados:
                            st.info(f"📋 {len(dados)} combinação(ões) identificada(s)")
                            
                            df = criar_dataframe_com_tabelas_temporais(dados)
                            st.session_state.df = df
                            
                            if not df.empty:
                                # Contar colunas temporais preenchidas
                                colunas_temporais = [col for col in COLUNAS_EXATAS if any(mes in col for mes in [
                                    'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                                    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
                                ])]
                                
                                colunas_preenchidas = sum([1 for col in colunas_temporais if col in df.columns and df[col].astype(str).str.contains('NR').mean() < 1.0])
                                
                                st.success(f"✅ {colunas_preenchidas}/36 colunas temporais preenchidas")
                                st.success(f"✅ CSV com {len(df)} linha(s) gerado")
                                
                                csv_content = gerar_csv_para_gsheets(df)
                                st.session_state.csv_content = csv_content
                            else:
                                st.warning("⚠️ Nenhum dado estruturado")
                        else:
                            st.warning("⚠️ Nenhum dado extraído")
                
                except Exception as e:
                    st.error(f"❌ Erro: {str(e)}")
        
        with col2:
            if st.sidebar.button("🔄 Limpar Tudo", use_container_width=True):
                st.session_state.df = pd.DataFrame(columns=COLUNAS_EXATAS)
                st.session_state.csv_content = ""
                st.session_state.texto_transcrito = ""
                st.session_state.paginas_processadas = 0
                st.rerun()
        
        # Mostrar resultados
        df = st.session_state.df
        
        if not df.empty:
            st.header("📊 Resultados - Tabelas Temporais Detalhadas")
            
            # Estatísticas
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Linhas Geradas", len(df))
            with col2:
                produtos_unicos = df['Nome do produto'].nunique()
                st.metric("Produtos Únicos", produtos_unicos)
            with col3:
                recs_unicos = df['REC'].nunique() if 'REC' in df.columns else 0
                st.metric("RECs Diferentes", recs_unicos)
            with col4:
                # Contar colunas temporais
                colunas_temporais = [col for col in df.columns if any(mes in col for mes in [
                    'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
                ])]
                st.metric("Colunas Temporais", len(colunas_temporais))
            
            # Visualização dos dados
            st.subheader("👁️ Dados Extraídos")
            
            # Mostrar colunas principais incluindo temporais
            colunas_para_mostrar = [
                'Nome do produto', 'Cultura', 'REC', 'UF', 'Região'
            ]
            
            # Adicionar algumas colunas temporais de exemplo
            meses_exemplo = ['Janeiro 1-10', 'Janeiro 11-20', 'Janeiro 21-31', 
                           'Fevereiro 1-10', 'Julho 1-10', 'Dezembro 21-31']
            
            for mes in meses_exemplo:
                if mes in df.columns:
                    colunas_para_mostrar.append(mes)
            
            colunas_disponiveis = [c for c in colunas_para_mostrar if c in df.columns]
            
            if colunas_disponiveis:
                st.dataframe(df[colunas_disponiveis], use_container_width=True, height=300)
            
            # Visualizar dados temporais completos para um produto
            with st.expander("📅 Visualizar Dados Temporais Completos", expanded=False):
                if 'Nome do produto' in df.columns:
                    produtos = df['Nome do produto'].unique()
                    produto_selecionado = st.selectbox("Selecione um produto:", produtos)
                    
                    if produto_selecionado:
                        df_produto = df[df['Nome do produto'] == produto_selecionado]
                        
                        # Criar tabela temporal organizada
                        meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                                'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
                        
                        for rec in df_produto['REC'].unique() if 'REC' in df_produto.columns else ['Único']:
                            st.write(f"**{produto_selecionado} - REC: {rec}**")
                            
                            # Criar DataFrame temporal
                            dados_temporais = []
                            for mes in meses:
                                linha = {'Mês': mes}
                                for periodo in ['1-10', '11-20', '21-31']:
                                    coluna = f"{mes} {periodo}"
                                    if periodo == '21-31' and mes == 'Fevereiro':
                                        coluna = f"{mes} 21-28/29"
                                    
                                    if coluna in df_produto.columns:
                                        valor = df_produto[df_produto['REC'] == rec][coluna].iloc[0] if 'REC' in df_produto.columns else df_produto[coluna].iloc[0]
                                        linha[periodo] = valor
                                    else:
                                        linha[periodo] = "NR"
                                
                                dados_temporais.append(linha)
                            
                            df_temporal = pd.DataFrame(dados_temporais)
                            st.dataframe(df_temporal, use_container_width=True)
            
            # Mostrar texto transcrito
            with st.expander("📝 Ver texto transcrito", expanded=False):
                if st.session_state.texto_transcrito:
                    st.text_area("Texto:", 
                               st.session_state.texto_transcrito[:5000], 
                               height=300)
            
            # Download
            st.subheader("📥 Download do CSV")
            
            nome_base = uploaded_file.name.split('.')[0]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            if st.session_state.csv_content:
                st.download_button(
                    label=f"💾 Baixar CSV ({len(df)} linha(s), {len(COLUNAS_EXATAS)} colunas)",
                    data=st.session_state.csv_content.encode('utf-8'),
                    file_name=f"cultivares_temporal_{nome_base}_{timestamp}.csv",
                    mime="text/csv",
                    type="primary",
                    use_container_width=True
                )
            
            # Preview do CSV
            with st.expander("🔍 Preview do CSV", expanded=False):
                if st.session_state.csv_content:
                    linhas = st.session_state.csv_content.split('\n')[:4]
                    st.code("\n".join(linhas), language="csv")
        
        elif st.session_state.df is not None and df.empty and st.session_state.texto_transcrito:
            st.info("📭 Nenhum dado extraído do documento.")
    
    else:
        # Tela inicial
        st.markdown("""
        ## 🌱 Extrator de Cultivares - Tabelas Temporais Detalhadas
        
        ### 📅 **Nova Estrutura Temporal:**
        
        **Cada mês dividido em 3 períodos:**
        ```
        Janeiro 1-10    | Janeiro 11-20   | Janeiro 21-31
        Fevereiro 1-10  | Fevereiro 11-20 | Fevereiro 21-28/29
        Março 1-10      | Março 11-20     | Março 21-31
        ... (todos os 12 meses)
        ```
        
        **Total: 36 colunas temporais**
        
        ### 🔄 **Processamento:**
        1. Identifica **tabelas com meses e períodos**
        2. Extrai **valores para cada período (1-10, 11-20, 21-31)**
        3. Cria **múltiplas linhas** para diferentes RECs
        4. Gera CSV com **{len(COLUNAS_EXATAS)} colunas** no total
        
        ### 📊 **Exemplo de Saída:**
        ```
        Produto: NK401VIP3, REC: 202
        Janeiro 1-10: 180-260
        Janeiro 11-20: NR
        Janeiro 21-31: 180-260
        Fevereiro 1-10: NR
        ... (todos os períodos)
        ```
        
        **Carregue um DOCX com tabelas temporais detalhadas para começar.**
        """)

if __name__ == "__main__":
    main()
