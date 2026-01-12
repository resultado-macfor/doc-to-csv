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
    modelo_texto = genai.GenerativeModel("gemini-1.5-flash")
except Exception as e:
    st.error(f"Erro ao configurar Gemini: {str(e)}")
    st.stop()

# COLUNAS EXATAS conforme o template
COLUNAS_EXATAS = [
    "Cultura", "Nome do produto", "NOME TÉCNICO/ REG", "Descritivo para SEO", 
    "Fertilidade", "Grupo de maturação", "Lançamento", "Slogan", "Tecnologia", 
    "Região (por extenso)", "Estado (por extenso)", "Ciclo", "Finalidade", 
    "URL da imagem do mapa", "Número do ícone", "Titulo icone 1", "Descrição Icone 1", 
    "Número do ícone", "Titulo icone 2", "Descrição Icone 2", "Número do ícone", 
    "Titulo icone 3", "Descrição Icone 3", "Número do ícone", "Título icone 4", 
    "Descrição Icone 4", "Número do ícone", "Título icone 5", "Descrição Icone 5", 
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

# Função 1: Converter DOCX para texto
def docx_para_texto(docx_bytes):
    try:
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
            tmp.write(docx_bytes)
            docx_path = tmp.name
        
        doc = docx.Document(docx_path)
        textos = []
        
        for para in doc.paragraphs:
            if para.text.strip():
                textos.append(para.text.strip())
        
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
                textos.append("--- TABELA ---")
                textos.extend(tabela_texto)
                textos.append("--- FIM TABELA ---")
        
        texto_completo = "\n".join(textos)
        os.unlink(docx_path)
        
        return texto_completo
        
    except Exception as e:
        raise Exception(f"Erro na conversão DOCX: {str(e)}")

# Função 2: Extrair dados para CSV
def extrair_dados_para_csv(texto_original):
    prompt = f"""
    ANALISE O TEXTO ABAIXO E EXTRAIA DADOS PARA 81 COLUNAS:

    TEXTO:
    {texto_original}

    COLOQUE OS DADOS EM UM ARRAY JSON COM ESTAS 81 COLUNAS EXATAS:
    {', '.join(COLUNAS_EXATAS)}

    PARA CADA CULTIVAR, CRIE UM OBJETO COM TODAS AS 81 PROPRIEDADES.
    USE "NR" PARA DADOS NÃO ENCONTRADOS.
    """
    
    try:
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
                dados = [json.loads(json_str)]
                return dados
            
            return []
            
    except Exception as e:
        raise Exception(f"Erro na extração: {str(e)}")

# Função 3: Criar DataFrame
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
            linhas.append(linha)
    
    if linhas:
        return pd.DataFrame(linhas, columns=COLUNAS_EXATAS)
    else:
        return pd.DataFrame(columns=COLUNAS_EXATAS)

# Função 4: Gerar CSV
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
            if valor in ["", "nan", "None", "null"]:
                valor = "NR"
            linha.append(valor)
        writer.writerow(linha)
    
    return output.getvalue()

# Interface principal
def main():
    st.sidebar.header("Upload do Documento")
    
    uploaded_file = st.sidebar.file_uploader(
        "Carregue um arquivo DOCX:",
        type=["docx"],
        help="Documento técnico sobre cultivares"
    )
    
    if uploaded_file:
        st.write(f"**Arquivo:** {uploaded_file.name}")
        
        col1, col2 = st.sidebar.columns(2)
        
        with col1:
            if st.button("Processar Documento", type="primary", use_container_width=True):
                try:
                    # Limpar estado anterior
                    st.session_state.df = pd.DataFrame(columns=COLUNAS_EXATAS)
                    st.session_state.csv_content = ""
                    
                    # Converter DOCX para texto
                    with st.spinner("Convertendo DOCX..."):
                        texto_original = docx_para_texto(uploaded_file.getvalue())
                        if not texto_original or len(texto_original) < 100:
                            st.error("Documento muito curto")
                            return
                    
                    # Extrair dados
                    with st.spinner("Extraindo dados..."):
                        dados = extrair_dados_para_csv(texto_original)
                        if dados:
                            df = criar_dataframe(dados)
                            st.session_state.df = df
                            
                            # Gerar CSV
                            csv_content = gerar_csv_para_gsheets(df)
                            st.session_state.csv_content = csv_content
                        else:
                            st.warning("Nenhuma cultivar identificada")
                            st.session_state.df = pd.DataFrame(columns=COLUNAS_EXATAS)
                    
                except Exception as e:
                    st.error(f"Erro no processamento: {str(e)}")
        
        with col2:
            if st.button("Limpar", use_container_width=True):
                st.session_state.df = pd.DataFrame(columns=COLUNAS_EXATAS)
                st.session_state.csv_content = ""
                st.rerun()
        
        # Mostrar resultados
        df = st.session_state.df
        
        if not df.empty:
            st.write(f"**{len(df)} cultivar(s) encontrada(s)**")
            
            # Visualizar dados
            st.dataframe(df, use_container_width=True, height=300)
            
            # Download
            nome_base = uploaded_file.name.split('.')[0]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            if st.session_state.csv_content:
                st.download_button(
                    label="Baixar CSV",
                    data=st.session_state.csv_content.encode('utf-8'),
                    file_name=f"cultivares_{nome_base}_{timestamp}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        
        elif st.session_state.df is not None and df.empty and 'texto_original' in locals():
            st.info("Nenhum dado extraído do documento.")
    
    else:
        st.info("Carregue um documento DOCX para começar.")

if __name__ == "__main__":
    main()
