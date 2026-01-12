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
    "Nematóide de Cisto (Raça 3", "Nematóide de Cisto (Raça 9)", 
    "Nematóide de Cisto (Raça 10", "Nematóide de Cisto (Raça 14)", 
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

# Função 1: Converter DOCX para imagens - CORRIGIDA para todas as páginas
def docx_para_imagens(docx_bytes):
    try:
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
            tmp.write(docx_bytes)
            docx_path = tmp.name
        
        doc = docx.Document(docx_path)
        
        # Usar o número real de páginas do documento
        imagens = []
        
        # Para cada parágrafo e tabela, vamos criar imagens com mais conteúdo
        texto_completo = []
        
        # Coletar TODO o texto
        for para in doc.paragraphs:
            if para.text.strip():
                texto_completo.append(para.text.strip())
        
        for table in doc.tables:
            tabela_texto = []
            for row in table.rows:
                linha = []
                for cell in row.cells:
                    if cell.text.strip():
                        linha.append(cell.text.strip())
                if linha:
                    tabela_texto.append(" | ".join(linha))
            if tabela_texto:
                texto_completo.append("=== TABELA ===")
                texto_completo.extend(tabela_texto)
                texto_completo.append("=== FIM TABELA ===")
        
        todo_texto = "\n".join(texto_completo)
        os.unlink(docx_path)
        
        # Dividir em páginas maiores (3000 caracteres)
        paginas = []
        pagina_atual = []
        chars_contador = 0
        max_chars = 300000  # Aumentado para 3000 caracteres por página
        
        for linha in todo_texto.split('\n'):
            linha_comprimento = len(linha) + 1  # +1 para a quebra de linha
            if chars_contador + linha_comprimento > max_chars and pagina_atual:
                paginas.append("\n".join(pagina_atual))
                pagina_atual = [linha]
                chars_contador = linha_comprimento
            else:
                pagina_atual.append(linha)
                chars_contador += linha_comprimento
        
        if pagina_atual:
            paginas.append("\n".join(pagina_atual))
        
        # Criar imagens
        for i, texto_pagina in enumerate(paginas):
            # Tamanho maior para mais conteúdo
            img = Image.new('RGB', (1400, 2000), color='white')
            draw = ImageDraw.Draw(img)
            
            try:
                font = ImageFont.truetype("arial.ttf", 12)  # Fonte menor para caber mais
            except:
                font = ImageFont.load_default()
            
            y = 40
            for linha in texto_pagina.split('\n'):
                if linha.strip() and y < 1960:
                    # Quebrar linhas longas
                    for i in range(0, len(linha), 120):  # 120 caracteres por linha
                        if y < 1960:
                            parte = linha[i:i+120]
                            draw.text((40, y), parte, fill='black', font=font)
                            y += 20  # Espaçamento menor
            
            imagens.append(img)
        
        return imagens
        
    except Exception as e:
        st.error(f"Erro na conversão DOCX: {str(e)}")
        return []

# Função 2: Transcrever imagens com Gemini Vision - TODAS as imagens
def transcrever_imagens(imagens):
    if not imagens:
        return ""
    
    texto_completo = ""
    progresso = st.progress(0)
    
    for i, imagem in enumerate(imagens):
        try:
            # Atualizar progresso
            progresso.progress((i + 1) / len(imagens))
            
            img_bytes = io.BytesIO()
            imagem.save(img_bytes, format='PNG')
            img_bytes = img_bytes.getvalue()
            
            prompt = """TRANSCREVA TODO o texto desta imagem COMPLETAMENTE e PRECISAMENTE.
            INCLUA ABSOLUTAMENTE TUDO:
            - Nomes de produtos, cultivares, variedades
            - Tabelas completas com todas as células
            - Características técnicas (ciclo, fertilidade, PMG, etc.)
            - Resistências e tolerâncias a doenças
            - Resultados de produtividade com números exatos
            - Recomendações completas
            - Estados e regiões mencionados
            - URLs, links, referências
            - TUDO que estiver visível na imagem
            
            Mantenha a estrutura original e NÃO resuma nada."""
            
            response = modelo_visao.generate_content([
                prompt,
                {"mime_type": "image/png", "data": img_bytes}
            ])
            
            texto_completo += f"\n\n{'='*60}\nPÁGINA {i+1}/{len(imagens)}\n{'='*60}\n\n{response.text}\n"
            
        except Exception as e:
            texto_completo += f"\n\n{'='*60}\nERRO NA PÁGINA {i+1}: {str(e)}\n{'='*60}\n"
    
    progresso.empty()
    return texto_completo

# Função 3: Extrair dados para CSV - COM TODO O TEXTO
def extrair_dados_para_csv(texto_transcrito):
    # Usar TODO o texto, não apenas os primeiros caracteres
    prompt = f"""
    ANALISE ESTE TEXTO COMPLETO TRANSCRITO DE UM DOCUMENTO DE CULTIVARES:

    TEXTO COMPLETO (TODAS AS PÁGINAS):
    {texto_transcrito}

    INSTRUÇÕES:
    1. Analise TODO o texto acima
    2. Identifique TODOS os produtos/cultivares mencionados
    3. Para CADA produto único, extraia os dados para preencher estas 81 colunas:

    COLUNAS (81 no total):
    {', '.join(COLUNAS_EXATAS)}

    REGRAS DE EXTRAÇÃO:
    - "Nome do produto": Procure por siglas como NK401VIP3, NS7524IPRO, etc.
    - "Cultura": Identifique se é Soja, Milho, Algodão, etc.
    - "Tecnologia": Extraia da sigla (VIP3, IPRO, RR, etc.)
    - "Ciclo": Precoce, Médio, Tardio, Superprecoce
    - "Finalidade": Grãos, Silagem, etc.
    - "Estado (por extenso)": Extraia todos os estados mencionados
    - "Fertilidade": Alto, Médio, Baixo
    - Para ícones: Extraia quando encontrar "ÍCONE", "Icone", "ícone"
    - Para resistências: Mapeie M, MT, T, R, MR, S para as colunas correspondentes
    - "Recomendações": Extraia todo o texto de recomendações
    - "Resultados": Procure por tabelas de produtividade (sc/ha)
    - Para meses: Procure por tabelas de época de semeadura

    SE HOUVER APENAS UM PRODUTO NO DOCUMENTO: crie apenas um objeto
    SE HOUVER MÚLTIPLOS PRODUTOS: crie um objeto para cada um

    FORMATE AS RESISTÊNCIAS ASSIM:
    - R = Resistente
    - MR = Moderadamente Resistente  
    - S = Suscetível
    - M = Moderado
    - MT = Moderadamente Tolerante
    - T = Tolerante
    - X = Presente/Positivo

    Para dados não encontrados, use: "NR"

    Retorne APENAS um array JSON onde cada objeto tem 81 propriedades (uma para cada coluna).
    NÃO inclua texto explicativo, apenas o JSON.
    """
    
    try:
        with st.spinner("Analisando todo o texto extraído..."):
            response = modelo_texto.generate_content(prompt)
            resposta = response.text.strip()
            
            resposta_limpa = resposta.replace('```json', '').replace('```', '').replace('JSON', '').strip()
            
            try:
                # Tentar parse direto
                dados = json.loads(resposta_limpa)
                if isinstance(dados, list):
                    return dados
                elif isinstance(dados, dict):
                    return [dados]
                else:
                    return []
                    
            except json.JSONDecodeError:
                # Tentar extrair JSON com regex
                json_match = re.search(r'(\[.*\])', resposta_limpa, re.DOTALL)
                if json_match:
                    try:
                        json_str = json_match.group(1)
                        dados = json.loads(json_str)
                        return dados
                    except:
                        pass
                
                # Tentar objeto único
                obj_match = re.search(r'(\{.*\})', resposta_limpa, re.DOTALL)
                if obj_match:
                    try:
                        json_str = obj_match.group(1)
                        dados = json.loads(json_str)
                        return [dados]
                    except:
                        pass
                
                return []
            
    except Exception as e:
        st.error(f"Erro na extração de dados: {str(e)}")
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

# Função 5: Gerar CSV
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
        help="Documento técnico com informações de cultivares"
    )
    
    if uploaded_file:
        st.sidebar.write(f"**Arquivo:** {uploaded_file.name}")
        st.sidebar.write(f"**Tamanho:** {uploaded_file.size/1024:.0f} KB")
        
        col1, col2 = st.sidebar.columns(2)
        
        with col1:
            if st.sidebar.button("🚀 Processar TUDO", type="primary", use_container_width=True):
                # Limpar estado anterior
                st.session_state.df = pd.DataFrame(columns=COLUNAS_EXATAS)
                st.session_state.csv_content = ""
                st.session_state.texto_transcrito = ""
                
                try:
                    # PASSO 1: Converter DOCX para imagens
                    with st.spinner(f"📄 Convertendo DOCX para imagens..."):
                        imagens = docx_para_imagens(uploaded_file.getvalue())
                        if not imagens:
                            st.error("Falha na conversão do DOCX")
                            return
                        st.success(f"✅ Convertido em {len(imagens)} imagem(s)")
                
                    # PASSO 2: Transcrever TODAS as imagens
                    with st.spinner(f"👁️ Transcrevendo {len(imagens)} página(s) com IA Vision..."):
                        texto = transcrever_imagens(imagens)
                        if not texto:
                            st.error("Falha na transcrição")
                            return
                        st.session_state.texto_transcrito = texto
                        st.success(f"✅ Transcrição concluída")
                
                    # PASSO 3: Extrair dados de TODO o texto
                    with st.spinner("📊 Extraindo dados para 81 colunas..."):
                        dados = extrair_dados_para_csv(texto)
                        if dados:
                            st.info(f"📋 {len(dados)} produto(s) identificado(s)")
                            
                            df = criar_dataframe(dados)
                            st.session_state.df = df
                            
                            if not df.empty:
                                csv_content = gerar_csv_para_gsheets(df)
                                st.session_state.csv_content = csv_content
                                st.success(f"✅ {len(df)} linha(s) gerada(s) no CSV")
                            else:
                                st.warning("⚠️ Nenhum dado estruturado extraído")
                        else:
                            st.warning("⚠️ Nenhum produto identificado no texto")
                
                except Exception as e:
                    st.error(f"❌ Erro no processamento: {str(e)}")
        
        with col2:
            if st.sidebar.button("🔄 Limpar", use_container_width=True):
                st.session_state.df = pd.DataFrame(columns=COLUNAS_EXATAS)
                st.session_state.csv_content = ""
                st.session_state.texto_transcrito = ""
                st.rerun()
        
        # Mostrar resultados
        df = st.session_state.df
        
        if not df.empty:
            st.header("📊 Resultados")
            
            # Estatísticas
            col_stat1, col_stat2, col_stat3 = st.columns(3)
            with col_stat1:
                st.metric("Produtos", len(df))
            with col_stat2:
                st.metric("Colunas", len(df.columns))
            with col_stat3:
                if 'Cultura' in df.columns:
                    culturas = df['Cultura'].unique()
                    st.metric("Culturas", len(culturas))
            
            # Visualização
            st.subheader("👁️ Visualização dos Dados")
            
            # Mostrar colunas principais
            colunas_principais = [
                'Cultura', 'Nome do produto', 'Tecnologia', 
                'Ciclo', 'Finalidade', 'Fertilidade', 'Estado (por extenso)'
            ]
            
            colunas_disponiveis = [c for c in colunas_principais if c in df.columns]
            
            if colunas_disponiveis:
                st.dataframe(df[colunas_disponiveis], use_container_width=True, height=300)
            
            # Mostrar texto transcrito
            with st.expander("📝 Ver texto transcrito COMPLETO", expanded=False):
                if st.session_state.texto_transcrito:
                    st.text_area("Texto completo:", 
                               st.session_state.texto_transcrito, 
                               height=400)
                    st.caption(f"Total: {len(st.session_state.texto_transcrito):,} caracteres")
            
            # Mostrar todas as colunas
            with st.expander("📋 Ver todas as 81 colunas", expanded=False):
                st.dataframe(df, use_container_width=True, height=400)
            
            # Download
            st.subheader("📥 Download")
            
            nome_base = uploaded_file.name.split('.')[0]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            if st.session_state.csv_content:
                st.download_button(
                    label="💾 Baixar CSV (81 colunas)",
                    data=st.session_state.csv_content.encode('utf-8'),
                    file_name=f"cultivares_{nome_base}_{timestamp}.csv",
                    mime="text/csv",
                    type="primary",
                    use_container_width=True
                )
            
            # Preview do CSV
            with st.expander("🔍 Preview do CSV", expanded=False):
                if st.session_state.csv_content:
                    linhas = st.session_state.csv_content.split('\n')[:5]
                    st.code("\n".join(linhas), language="csv")
        
        elif st.session_state.df is not None and df.empty and st.session_state.texto_transcrito:
            st.info("📭 Nenhum produto identificado no documento.")
            
            with st.expander("🔍 Ver texto transcrito para depuração"):
                if st.session_state.texto_transcrito:
                    st.text(st.session_state.texto_transcrito[:5000])
    
    else:
        # Tela inicial
        st.markdown("""
        ## 🌱 Extrator de Cultivares
        
        ### 🔄 **Fluxo Completo:**
        1. **📄 DOCX** → Conversão para imagens (TODAS as páginas)
        2. **🖼️ Imagens** → Transcrição com Gemini Vision (TUDO o texto)
        3. **📝 Texto** → Extração para 81 colunas (TODOS os produtos)
        4. **📊 CSV** → Geração para Google Sheets
        
        ### ✅ **Características:**
        - Processa **TODAS** as páginas do documento
        - Extrai **TODOS** os produtos encontrados
        - Gera **81 colunas exatas** conforme template
        - Cada produto = uma linha no CSV
        
        **Para começar, carregue um DOCX na barra lateral.**
        """)

if __name__ == "__main__":
    main()
