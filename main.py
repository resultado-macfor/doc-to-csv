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
st.set_page_config(page_title="Extrator de Cultivares", page_icon="🌱")
st.title("Extrator de Cultivares")

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
if 'texto_transcrito' not in st.session_state:
    st.session_state.texto_transcrito = ""

# Função 1: Converter DOCX para imagens
def docx_para_imagens(docx_bytes):
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
            for row in table.rows:
                cells_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells_text:
                    textos.append(" | ".join(cells_text))
        
        texto_completo = "\n".join(textos)
        os.unlink(docx_path)
        
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
        
        imagens = []
        for texto in paginas:
            img = Image.new('RGB', (1200, 1600), color='white')
            draw = ImageDraw.Draw(img)
            
            try:
                font = ImageFont.truetype("arial.ttf", 14)
            except:
                font = ImageFont.load_default()
            
            y = 50
            for linha in texto.split('\n'):
                if linha.strip() and y < 1550:
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
    if not imagens:
        return ""
    
    texto_completo = ""
    
    for i, imagem in enumerate(imagens):
        try:
            img_bytes = io.BytesIO()
            imagem.save(img_bytes, format='PNG')
            img_bytes = img_bytes.getvalue()
            
            prompt = """TRANSCREVA TODO o texto desta imagem EXATAMENTE como aparece.
            Inclua tabelas, números, nomes, características técnicas, resultados de produtividade.
            Mantenha a formatação original quando possível."""
            
            response = modelo_visao.generate_content([
                prompt,
                {"mime_type": "image/png", "data": img_bytes}
            ])
            
            texto_completo += f"\n\n--- PÁGINA {i+1} ---\n{response.text}\n"
            
        except Exception as e:
            texto_completo += f"\n\n--- ERRO PÁGINA {i+1}: {str(e)[:100]} ---\n"
    
    return texto_completo

# Função 3: Extrair dados para CSV
def extrair_dados_para_csv(texto_transcrito):
    prompt = f"""
    ANALISE O TEXTO TRANSCRITO DE UM DOCUMENTO SOBRE CULTIVARES:

    TEXTO:
    {texto_transcrito[:10000]}

    EXTRAIA OS DADOS PARA ESTAS 81 COLUNAS EXATAS:

    {', '.join(COLUNAS_EXATAS)}

    REGRAS:
    1. Identifique TODAS as cultivares únicas no texto
    2. Para CADA cultivar, crie um objeto com as 81 propriedades
    3. Use "NR" para informações não encontradas
    4. Mantenha os nomes das colunas EXATAMENTE como estão acima
    5. Para resistências: use R (Resistente), MR (Moderadamente Resistente), S (Suscetível)
    6. Para produtividade: mantenha formato "XX,XX sc/ha"
    7. Para meses de plantio: use "180-260" ou "NR"

    Retorne APENAS um array JSON. Cada objeto deve ter 81 propriedades.
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
            if valor in ["", "nan", "None", "null"]:
                valor = "NR"
            linha.append(valor)
        writer.writerow(linha)
    
    return output.getvalue()

# Interface principal
def main():
    uploaded_file = st.file_uploader(
        "Carregue um arquivo DOCX:",
        type=["docx"],
        help="Documento técnico sobre cultivares"
    )
    
    if uploaded_file:
        st.write(f"**Arquivo:** {uploaded_file.name}")
        
        if st.button("Processar Documento", type="primary"):
            # Limpar estado anterior
            st.session_state.df = pd.DataFrame(columns=COLUNAS_EXATAS)
            st.session_state.csv_content = ""
            st.session_state.texto_transcrito = ""
            
            try:
                # PASSO 1: Converter DOCX para imagens
                with st.spinner("Convertendo DOCX para imagens..."):
                    imagens = docx_para_imagens(uploaded_file.getvalue())
                    if not imagens:
                        st.error("Falha na conversão do DOCX")
                        return
                
                # PASSO 2: Transcrever imagens
                with st.spinner("Transcrevendo imagens com IA Vision..."):
                    texto = transcrever_imagens(imagens)
                    if not texto:
                        st.error("Falha na transcrição")
                        return
                    st.session_state.texto_transcrito = texto
                
                # PASSO 3: Extrair dados
                with st.spinner("Extraindo dados para 81 colunas..."):
                    dados = extrair_dados_para_csv(texto)
                    if dados:
                        df = criar_dataframe(dados)
                        st.session_state.df = df
                        
                        # Gerar CSV
                        csv_content = gerar_csv_para_gsheets(df)
                        st.session_state.csv_content = csv_content
                    else:
                        st.warning("Nenhuma cultivar identificada")
                
            except Exception as e:
                st.error(f"Erro no processamento: {str(e)}")
        
        if st.button("Limpar"):
            st.session_state.df = pd.DataFrame(columns=COLUNAS_EXATAS)
            st.session_state.csv_content = ""
            st.session_state.texto_transcrito = ""
            st.rerun()
        
        # Mostrar resultados
        df = st.session_state.df
        
        if not df.empty:
            st.write(f"**{len(df)} cultivar(s) extraída(s)**")
            
            if st.checkbox("Mostrar texto transcrito"):
                st.text_area("Texto transcrito:", st.session_state.texto_transcrito[:2000], height=300)
            
            st.dataframe(df, use_container_width=True, height=400)
            
            # Download
            nome_base = uploaded_file.name.split('.')[0]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            if st.session_state.csv_content:
                st.download_button(
                    label="Baixar CSV",
                    data=st.session_state.csv_content.encode('utf-8'),
                    file_name=f"cultivares_{nome_base}_{timestamp}.csv",
                    mime="text/csv"
                )
        
        elif st.session_state.df is not None and df.empty and st.session_state.texto_transcrito:
            st.info("Nenhum dado extraído do documento.")
    
    else:
        st.info("Carregue um documento DOCX para começar.")

if __name__ == "__main__":
    main()
