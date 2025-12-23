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
import time

# Configuração
st.set_page_config(page_title="Extrator de Cultivares", page_icon="🌱", layout="wide")
st.title("🌱 Extrator de Cultivares - DOCX para Google Sheets")

# API Key
gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEM_API_KEY")
if not gemini_api_key:
    st.error("Configure GEMINI_API_KEY ou GEM_API_KEY")
    st.stop()

try:
    genai.configure(api_key=gemini_api_key)
    modelo_visao = genai.GenerativeModel("gemini-2.0-flash-exp")
    modelo_texto = genai.GenerativeModel("gemini-1.5-flash")
except Exception as e:
    st.error(f"Erro ao configurar Gemini: {str(e)}")
    st.stop()

# Colunas para Google Sheets (81 colunas)
COLUNAS = [
    "Cultura", "Nome do produto", "NOME TÉCNICO/ REG", "Descritivo para SEO", 
    "Fertilidade", "Grupo de maturação", "Lançamento", "Slogan", "Tecnologia", 
    "Região (por extenso)", "Estado (por extenso)", "Ciclo", "Finalidade", 
    "URL da imagem do mapa", "Número do ícone", "Titulo icone 1", "Descrição Icone 1", 
    "Número do ícone2", "Titulo icone 2", "Descrição Icone 2", "Número do ícone3", 
    "Titulo icone 3", "Descrição Icone 3", "Número do ícone4", "Título icone 4", 
    "Descrição Icone 4", "Número do ícone5", "Título icone 5", "Descrição Icone 5", 
    "Exigência à fertilidade", "Grupo de maturidade", "PMS MÉDIO", "Tipo de crescimento", 
    "Cor da flor", "Cor da pubescência", "Cor do hilo", "Cancro da haste", 
    "Pústula bacteriana", "Nematoide das galhas - M. javanica", 
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

# Inicializar session state
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=COLUNAS)
if 'csv_content' not in st.session_state:
    st.session_state.csv_content = ""
if 'imagens' not in st.session_state:
    st.session_state.imagens = []
if 'texto' not in st.session_state:
    st.session_state.texto = ""

# Função 1: Converter DOCX para imagens
def docx_para_imagens(docx_bytes):
    """Converte DOCX para lista de imagens (páginas)"""
    try:
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
            tmp.write(docx_bytes)
            docx_path = tmp.name
        
        doc = docx.Document(docx_path)
        
        # Extrair todo o texto
        textos = []
        for para in doc.paragraphs:
            if para.text.strip():
                textos.append(para.text.strip())
        
        for table in doc.tables:
            for row in table.rows:
                cells_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells_text:
                    textos.append(" | ".join(cells_text))
        
        texto_completo = "\n".join(textos)
        os.unlink(docx_path)
        
        # Dividir em páginas (máximo 1500 caracteres por página)
        paginas = []
        pagina_atual = []
        chars_contador = 0
        
        for linha in texto_completo.split('\n'):
            linha_comprimento = len(linha)
            if chars_contador + linha_comprimento > 1500 and pagina_atual:
                paginas.append("\n".join(pagina_atual))
                pagina_atual = [linha]
                chars_contador = linha_comprimento
            else:
                pagina_atual.append(linha)
                chars_contador += linha_comprimento
        
        if pagina_atual:
            paginas.append("\n".join(pagina_atual))
        
        # Criar imagens
        imagens = []
        for texto in paginas:
            # Criar imagem com fundo branco
            img = Image.new('RGB', (1200, 1600), color='white')
            draw = ImageDraw.Draw(img)
            
            # Tentar carregar fonte
            try:
                font = ImageFont.truetype("arial.ttf", 14)
            except:
                font = ImageFont.load_default()
            
            # Adicionar texto
            y = 50
            for linha in texto.split('\n'):
                if linha.strip() and y < 1550:
                    # Quebrar linhas muito longas
                    for i in range(0, len(linha), 100):
                        if y < 1550:
                            parte = linha[i:i+100]
                            draw.text((50, y), parte, fill='black', font=font)
                            y += 25
            
            imagens.append(img)
        
        return imagens
        
    except Exception as e:
        st.error(f"Erro na conversão DOCX: {str(e)}")
        return []

# Função 2: Transcrever imagens com Gemini Vision
def transcrever_imagens(imagens):
    """Transcreve imagens usando modelo de visão"""
    if not imagens:
        return ""
    
    texto_completo = ""
    progress_bar = st.progress(0)
    
    for i, imagem in enumerate(imagens):
        progresso = (i + 1) / len(imagens)
        progress_bar.progress(progresso)
        
        try:
            # Converter imagem para bytes
            img_bytes = io.BytesIO()
            imagem.save(img_bytes, format='PNG')
            img_bytes = img_bytes.getvalue()
            
            # Prompt para transcrição completa
            prompt = """TRANSCREVA TODO o texto desta imagem. Inclua:
            - Tabelas completas
            - Números e valores
            - Nomes de produtos/cultivares
            - Estados e regiões
            - Características técnicas
            - Benefícios mencionados
            - Resultados de produtividade
            - Tudo que estiver escrito na imagem"""
            
            response = modelo_visao.generate_content([
                prompt,
                {"mime_type": "image/png", "data": img_bytes}
            ])
            
            texto_completo += f"\n\n--- PÁGINA {i+1} ---\n{response.text}\n"
            time.sleep(0.5)  # Pausa para não sobrecarregar API
            
        except Exception as e:
            texto_completo += f"\n\n--- ERRO PÁGINA {i+1}: {str(e)[:100]} ---\n"
    
    progress_bar.empty()
    return texto_completo

# Função 3: Extrair dados para CSV
def extrair_dados_para_csv(texto_transcrito):
    """Extrai dados do texto para o formato CSV"""
    
    prompt = f"""
    ANALISE O TEXTO ABAIXO QUE FOI EXTRAÍDO DE UM DOCUMENTO SOBRE CULTIVARES.
    
    TEXTO TRANSCRITO:
    {texto_transcrito[:12000]}
    
    SUA TAREFA:
    1. Identifique TODAS as cultivares mencionadas
    2. Para CADA cultivar, extraia informações para estas 81 colunas:
    
    LISTA DE COLUNAS:
    {', '.join(COLUNAS)}
    
    RETORNE APENAS um array JSON. Cada objeto no array deve ter 81 propriedades
    correspondentes às colunas acima. Use "NR" para informações não encontradas.
    """
    
    try:
        with st.spinner("Processando texto para extrair dados..."):
            response = modelo_texto.generate_content(prompt)
            resposta = response.text.strip()
            
            # Limpar resposta
            resposta_limpa = resposta.replace('```json', '').replace('```', '').strip()
            
            # Tentar encontrar JSON
            json_match = re.search(r'(\[.*\])', resposta_limpa, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                dados = json.loads(json_str)
                return dados
            
            # Tentar encontrar objeto único
            obj_match = re.search(r'(\{.*\})', resposta_limpa, re.DOTALL)
            if obj_match:
                json_str = obj_match.group(1)
                dados = [json.loads(json_str)]
                return dados
            
            st.warning("Não foi possível extrair dados estruturados da resposta.")
            return []
            
    except Exception as e:
        st.error(f"Erro na extração de dados: {str(e)}")
        return []

# Função 4: Criar DataFrame
def criar_dataframe(dados):
    """Cria DataFrame a partir dos dados extraídos"""
    if not dados or not isinstance(dados, list):
        return pd.DataFrame(columns=COLUNAS)
    
    linhas = []
    for item in dados:
        if isinstance(item, dict):
            linha = {}
            for coluna in COLUNAS:
                valor = item.get(coluna)
                if valor is None or valor == "":
                    linha[coluna] = "NR"
                else:
                    linha[coluna] = str(valor).strip()
            linhas.append(linha)
    
    if linhas:
        return pd.DataFrame(linhas, columns=COLUNAS)
    else:
        return pd.DataFrame(columns=COLUNAS)

# Função 5: Gerar CSV para Google Sheets
def gerar_csv_para_gsheets(df):
    """Gera CSV formatado para Google Sheets"""
    if df.empty:
        return ""
    
    output = io.StringIO()
    writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    
    # Escrever cabeçalho
    writer.writerow(COLUNAS)
    
    # Escrever dados
    for _, row in df.iterrows():
        linha = []
        for col in COLUNAS:
            valor = str(row.get(col, "NR")).strip()
            # Tratar valores especiais
            if valor in ["", "nan", "None", "null"]:
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
        help="Documento técnico sobre cultivares"
    )
    
    if uploaded_file:
        st.sidebar.info(f"**Arquivo:** {uploaded_file.name}")
        st.sidebar.info(f"**Tamanho:** {uploaded_file.size/1024:.1f} KB")
        
        col1, col2 = st.sidebar.columns(2)
        
        with col1:
            if st.button("🚀 Processar Documento", type="primary", use_container_width=True):
                # Limpar estado anterior
                st.session_state.imagens = []
                st.session_state.texto = ""
                st.session_state.df = pd.DataFrame(columns=COLUNAS)
                st.session_state.csv_content = ""
                
                # PASSO 1: Converter DOCX para imagens
                with st.spinner("🖼️ Convertendo DOCX para imagens..."):
                    imagens = docx_para_imagens(uploaded_file.getvalue())
                    if imagens:
                        st.session_state.imagens = imagens
                        st.success(f"✅ {len(imagens)} página(s) criada(s)")
                    else:
                        st.error("Falha na conversão do DOCX")
                        return
                
                # PASSO 2: Transcrever imagens
                with st.spinner("👁️ Transcrevendo imagens com IA..."):
                    texto = transcrever_imagens(imagens)
                    if texto:
                        st.session_state.texto = texto
                        st.success(f"✅ Transcrição concluída")
                        
                        # Mostrar preview
                        with st.expander("📝 Ver texto transcrito", expanded=False):
                            st.text_area("Conteúdo:", texto[:2000] + ("..." if len(texto) > 2000 else ""), 
                                       height=200, key="texto_preview")
                    else:
                        st.error("Falha na transcrição")
                        return
                
                # PASSO 3: Extrair dados
                with st.spinner("📊 Extraindo dados para CSV..."):
                    dados = extrair_dados_para_csv(texto)
                    if dados:
                        df = criar_dataframe(dados)
                        st.session_state.df = df
                        st.success(f"✅ {len(df)} cultivar(s) extraída(s)")
                        
                        # Gerar CSV
                        csv_content = gerar_csv_para_gsheets(df)
                        st.session_state.csv_content = csv_content
                    else:
                        st.warning("⚠️ Nenhuma cultivar identificada")
                        st.session_state.df = pd.DataFrame(columns=COLUNAS)
        
        with col2:
            if st.button("🔄 Limpar", use_container_width=True):
                st.session_state.imagens = []
                st.session_state.texto = ""
                st.session_state.df = pd.DataFrame(columns=COLUNAS)
                st.session_state.csv_content = ""
                st.rerun()
        
        # Mostrar resultados
        df = st.session_state.df
        
        # Verificar se temos dados para mostrar
        if df is not None and not df.empty:
            st.header("📊 Resultados - Pronto para Google Sheets")
            
            # Estatísticas
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Cultivares", len(df))
            with col2:
                if 'Cultura' in df.columns:
                    culturas = [c for c in df['Cultura'].unique() if c != "NR"]
                    st.metric("Tipos", len(culturas))
            with col3:
                st.metric("Colunas", len(df.columns))
            
            # Visualização dos dados
            st.subheader("👁️ Visualização dos Dados")
            
            # Selecionar colunas para mostrar
            colunas_principais = [
                'Cultura', 'Nome do produto', 'Tecnologia', 
                'Grupo de maturação', 'Fertilidade', 'Estado (por extenso)'
            ]
            
            colunas_disponiveis = [c for c in colunas_principais if c in df.columns]
            
            if colunas_disponiveis:
                st.dataframe(df[colunas_disponiveis], use_container_width=True, height=300)
            else:
                # Mostrar primeiras 10 colunas
                st.dataframe(df.iloc[:, :10], use_container_width=True, height=300)
            
            # Download
            st.subheader("📥 Download")
            
            nome_base = uploaded_file.name.split('.')[0]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            col_dl1, col_dl2 = st.columns(2)
            
            with col_dl1:
                # CSV para Google Sheets
                if st.session_state.csv_content:
                    st.download_button(
                        label="📄 Baixar CSV (Google Sheets)",
                        data=st.session_state.csv_content,
                        file_name=f"cultivares_{nome_base}_{timestamp}.csv",
                        mime="text/csv",
                        help="CSV pronto para importar no Google Sheets",
                        use_container_width=True
                    )
            
            with col_dl2:
                # Excel
                if not df.empty:
                    excel_buffer = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Cultivares')
                    excel_data = excel_buffer.getvalue()
                    
                    st.download_button(
                        label="📊 Baixar Excel",
                        data=excel_data,
                        file_name=f"cultivares_{nome_base}_{timestamp}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        help="Arquivo Excel para edição",
                        use_container_width=True
                    )
            
            # Instruções para Google Sheets
            with st.expander("📋 Como usar no Google Sheets", expanded=False):
                st.markdown("""
                1. **Vá para [Google Sheets](https://sheets.google.com)**
                2. **Crie uma planilha em branco**
                3. **Arquivo → Importar → Fazer upload**
                4. **Selecione o arquivo CSV baixado**
                5. **Configurações de importação:**
                   - Separador: **Vírgula**
                   - Codificação: **UTF-8**
                   - Detectar automaticamente: **Sim**
                6. **Clique em Importar dados**
                
                **Pronto!** Seus dados serão organizados em 81 colunas.
                """)
            
            # Preview do CSV
            with st.expander("🔍 Preview do CSV gerado", expanded=False):
                if st.session_state.csv_content:
                    linhas = st.session_state.csv_content.split('\n')[:3]
                    st.code("\n".join(linhas), language="csv")
        
        elif df is not None and df.empty:
            st.info("📭 Nenhum dado extraído do documento.")
        
        # Mostrar status do processamento
        with st.expander("⚙️ Status do Processamento", expanded=False):
            if st.session_state.imagens:
                st.write(f"✅ **Imagens:** {len(st.session_state.imagens)} página(s)")
            if st.session_state.texto:
                st.write(f"✅ **Transcrição:** {len(st.session_state.texto):,} caracteres")
            if st.session_state.df is not None:
                st.write(f"✅ **DataFrame:** {len(st.session_state.df)} linha(s)")
    
    else:
        # Tela inicial
        st.markdown("""
        ## 🌱 Pipeline Completo: DOCX → Google Sheets
        
        ### 🔄 **Fluxo de Processamento:**
        
        1. **📤 DOCX**  
           → Carrega documento técnico
        
        2. **🖼️ Conversão para Imagens**  
           → Cada página vira imagem PNG  
           → Preserva formatação e tabelas
        
        3. **👁️ Transcrição com IA Vision**  
           → Usa Gemini 2.0 Flash Exp  
           → Lê TODO o texto das imagens  
           → Captura tabelas, números, dados técnicos
        
        4. **📊 Extração de Dados**  
           → Usa Gemini 1.5 Flash  
           → Identifica cultivares  
           → Extrai dados para 81 colunas
        
        5. **📄 CSV para Google Sheets**  
           → Gera arquivo pronto para importar  
           → 81 colunas formatadas  
           → Compatível com qualquer planilha
        
        ### ✅ **Resultado Final:**
        - **CSV pronto para Google Sheets**
        - **81 colunas organizadas**
        - **Dados estruturados automaticamente**
        - **Importação com 1 clique**
        
        **Para começar, carregue um DOCX na barra lateral!**
        """)

if __name__ == "__main__":
    main()
