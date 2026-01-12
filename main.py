import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
import tempfile
import docx
import io
import csv
import json
import re
from PIL import Image, ImageDraw, ImageFont
import time

st.set_page_config(page_title="Extrator de Cultivares", layout="wide")
st.title("Extrator de Cultivares")

gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEM_API_KEY")
if not gemini_api_key:
    st.error("Configure GEMINI_API_KEY")
    st.stop()

try:
    genai.configure(api_key=gemini_api_key)
    modelo_visao = genai.GenerativeModel("gemini-2.0-flash-exp")
    modelo_texto = genai.GenerativeModel("gemini-1.5-flash")
except Exception as e:
    st.error(f"Erro: {str(e)}")
    st.stop()

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
    "Janeiro 1-10", "Janeiro 11-20", "Janeiro 21-31",
    "Fevereiro 1-10", "Fevereiro 11-20", "Fevereiro 21-28/29",
    "Março 1-10", "Março 11-20", "Março 21-31",
    "Abril 1-10", "Abril 11-20", "Abril 21-30",
    "Maio 1-10", "Maio 11-20", "Maio 21-31",
    "Junho 1-10", "Junho 11-20", "Junho 21-30",
    "Julho 1-10", "Julho 11-20", "Julho 21-31",
    "Agosto 1-10", "Agosto 11-20", "Agosto 21-31",
    "Setembro 1-10", "Setembro 11-20", "Setembro 21-30",
    "Outubro 1-10", "Outubro 11-20", "Outubro 21-31",
    "Novembro 1-10", "Novembro 11-20", "Novembro 21-30",
    "Dezembro 1-10", "Dezembro 11-20", "Dezembro 21-31"
]

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=COLUNAS_EXATAS)
if 'csv_content' not in st.session_state:
    st.session_state.csv_content = ""
if 'paginas_processadas' not in st.session_state:
    st.session_state.paginas_processadas = 0
if 'total_paginas' not in st.session_state:
    st.session_state.total_paginas = 0

def contar_paginas_docx(docx_bytes):
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
        
        total_caracteres = len(texto_total)
        paginas_estimadas = max(1, total_caracteres // 2500)
        
        os.unlink(docx_path)
        return paginas_estimadas
        
    except Exception as e:
        return 1

def extrair_conteudo_por_pagina(docx_bytes, total_paginas):
    try:
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
            tmp.write(docx_bytes)
            docx_path = tmp.name
        
        doc = docx.Document(docx_path)
        
        conteudo_completo = []
        for para in doc.paragraphs:
            if para.text.strip():
                conteudo_completo.append(para.text.strip())
        
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
                conteudo_completo.append("[TABELA]")
                conteudo_completo.extend(tabela_texto)
        
        os.unlink(docx_path)
        
        paginas = []
        if total_paginas <= 1:
            paginas.append("\n".join(conteudo_completo))
        else:
            linhas_por_pagina = max(1, len(conteudo_completo) // total_paginas)
            for i in range(0, len(conteudo_completo), linhas_por_pagina):
                paginas.append("\n".join(conteudo_completo[i:i+linhas_por_pagina]))
                if len(paginas) >= total_paginas:
                    break
        
        return paginas[:total_paginas]
        
    except Exception as e:
        st.error(f"Erro: {str(e)}")
        return []

def criar_imagem_pagina(texto_pagina, num_pagina, total_paginas):
    img = Image.new('RGB', (1400, 2000), color='white')
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except:
        font = ImageFont.load_default()
    
    y = 100
    x = 100
    
    linhas = texto_pagina.split('\n')
    for linha in linhas:
        if y < 1900:
            if len(linha) > 120:
                partes = [linha[i:i+120] for i in range(0, len(linha), 120)]
                for parte in partes:
                    if y < 1900:
                        draw.text((x, y), parte, fill='black', font=font)
                        y += 20
            else:
                draw.text((x, y), linha, fill='black', font=font)
                y += 20
    
    draw.text((1250, 1950), f"Pág {num_pagina}/{total_paginas}", fill='gray', font=font)
    return img

def extrair_tabelas_da_imagem(imagem):
    try:
        img_bytes = io.BytesIO()
        imagem.save(img_bytes, format='PNG')
        img_bytes = img_bytes.getvalue()
        
        prompt = """EXTRAIA TODAS AS TABELAS desta imagem. FOCAR EM:
        - Tabelas com REC (202, 203, 204...)
        - Tabelas com UF (RS, SC, PR, SP, MS, MG, GO...)
        - Tabelas com Região (Sul, Sudeste...)
        - Tabelas com Meses (Janeiro, Fevereiro...)
        - Tabelas com períodos (1-10, 11-20, 21-31)
        - Tabelas com valores (180-260, NR...)
        - Tabelas com nomes de produtos
        
        Retorne as tabelas no formato:
        | Coluna1 | Coluna2 | Coluna3 |
        |---------|---------|---------|
        | Valor1  | Valor2  | Valor3  |
        """
        
        response = modelo_visao.generate_content([
            prompt,
            {"mime_type": "image/png", "data": img_bytes}
        ])
        
        return response.text
        
    except Exception as e:
        return f"ERRO: {str(e)[:100]}"

def processar_todas_tabelas(texto_tabelas):
    prompt = f"""
    ANALISE ESTAS TABELAS EXTRAÍDAS DE IMAGENS DE DOCUMENTO:

    TABELAS:
    {texto_tabelas[:200000]}

    EXTRAIA DADOS PARA ESTAS {len(COLUNAS_EXATAS)} COLUNAS:
    {', '.join(COLUNAS_EXATAS)}

    REGRAS:
    1. REC, UF, Região DEVEM vir das tabelas
    2. Dados temporais (Janeiro 1-10 até Dezembro 21-31) DEVEM vir das tabelas
    3. Cada Produto+REC = linha separada
    4. Use "NR" para dados não encontrados
    5. UF múltiplo: "RS, SC, PR"
    6. Valores temporais: "180-260" ou "NR"

    PROCURE POR:
    - | REC | UF | Região |
    - | Mês | 1-10 | 11-20 | 21-31 |
    - | Produto | REC | UF | Região |
    - Tabelas com meses e períodos

    Retorne JSON array com {len(COLUNAS_EXATAS)} propriedades por objeto.
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
                try:
                    json_str = json_match.group(1)
                    dados = json.loads(json_str)
                    return dados
                except:
                    pass
            
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
        st.error(f"Erro: {str(e)}")
        return []

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

def gerar_csv(df):
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

uploaded_file = st.file_uploader("Carregue DOCX:", type=["docx"])

if uploaded_file:
    if st.button("Processar Documento"):
        st.session_state.df = pd.DataFrame(columns=COLUNAS_EXATAS)
        st.session_state.csv_content = ""
        
        with st.spinner("Analisando documento..."):
            st.session_state.total_paginas = contar_paginas_docx(uploaded_file.getvalue())
        
        st.write(f"📄 Documento identificado: {st.session_state.total_paginas} página(s)")
        
        if st.session_state.total_paginas > 0:
            todas_tabelas = []
            progress_bar = st.progress(0)
            
            for pagina_num in range(st.session_state.total_paginas):
                progresso = (pagina_num + 1) / st.session_state.total_paginas
                progress_bar.progress(progresso)
                
                st.write(f"📖 Processando página {pagina_num + 1}/{st.session_state.total_paginas}")
                
                try:
                    paginas = extrair_conteudo_por_pagina(uploaded_file.getvalue(), st.session_state.total_paginas)
                    if pagina_num < len(paginas):
                        imagem = criar_imagem_pagina(paginas[pagina_num], pagina_num + 1, st.session_state.total_paginas)
                        tabelas = extrair_tabelas_da_imagem(imagem)
                        
                        if tabelas and "ERRO" not in tabelas:
                            todas_tabelas.append(f"\n--- Página {pagina_num + 1} ---\n{tabelas}")
                
                except Exception as e:
                    st.error(f"Erro na página {pagina_num + 1}: {str(e)}")
            
            progress_bar.empty()
            
            if todas_tabelas:
                texto_tabelas = "\n".join(todas_tabelas)
                st.session_state.paginas_processadas = len(todas_tabelas)
                
                with st.spinner("Processando tabelas extraídas..."):
                    dados = processar_todas_tabelas(texto_tabelas)
                    
                    if dados:
                        df = criar_dataframe(dados)
                        st.session_state.df = df
                        
                        if not df.empty:
                            csv_content = gerar_csv(df)
                            st.session_state.csv_content = csv_content
                            
                            st.write(f"✅ {st.session_state.paginas_processadas}/{st.session_state.total_paginas} páginas processadas")
                            st.write(f"📊 {len(df)} linha(s) extraída(s)")
            else:
                st.warning("Nenhuma tabela encontrada nas imagens")
    
    if st.button("Limpar"):
        st.session_state.df = pd.DataFrame(columns=COLUNAS_EXATAS)
        st.session_state.csv_content = ""
        st.session_state.paginas_processadas = 0
        st.session_state.total_paginas = 0
        st.rerun()
    
    df = st.session_state.df
    
    if not df.empty:
        st.dataframe(df, use_container_width=True, height=400)
        
        if st.session_state.csv_content:
            st.download_button(
                label="Baixar CSV",
                data=st.session_state.csv_content.encode('utf-8'),
                file_name=f"cultivares_{uploaded_file.name.split('.')[0]}.csv",
                mime="text/csv"
            )
    
    elif st.session_state.df is not None and df.empty and uploaded_file:
        st.info("Nenhum dado extraído.")
