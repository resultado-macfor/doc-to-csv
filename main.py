import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
from datetime import datetime
import tempfile
import docx
import io
import json
from PIL import Image, ImageDraw, ImageFont
import base64
import time

# Configuração
st.set_page_config(page_title="Extrator de Cultivares", page_icon="🌱", layout="wide")
st.title("🌱 Extrator de Cultivares - DOCX para CSV")

# API Key
gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEM_API_KEY")
if not gemini_api_key:
    st.error("Configure GEMINI_API_KEY ou GEM_API_KEY")
    st.stop()

try:
    genai.configure(api_key=gemini_api_key)
    modelo_visao = genai.GenerativeModel("gemini-2.5-flash")
    modelo_texto = genai.GenerativeModel("gemini-2.5-flash")
except Exception as e:
    st.error(f"Erro ao configurar Gemini: {str(e)}")
    st.stop()

# Colunas (81)
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

# Função 1: Converter DOCX para imagens
def docx_para_imagens(docx_bytes):
    """Converte DOCX para lista de imagens PNG"""
    imagens = []
    
    try:
        # Salvar DOCX temporariamente
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
            tmp.write(docx_bytes)
            docx_path = tmp.name
        
        # Abrir DOCX
        doc = docx.Document(docx_path)
        
        # Extrair todo o texto
        texto_completo = []
        for para in doc.paragraphs:
            if para.text.strip():
                texto_completo.append(para.text)
        
        # Extrair de tabelas
        for table in doc.tables:
            for row in table.rows:
                row_text = []
                for cell in row.cells:
                    if cell.text.strip():
                        row_text.append(cell.text.strip())
                if row_text:
                    texto_completo.append(" | ".join(row_text))
        
        texto_total = "\n".join(texto_completo)
        
        # Limpar arquivo temporário
        os.unlink(docx_path)
        
        # Dividir em "páginas" (aproximadamente 800 caracteres por página)
        paginas = []
        pagina_atual = ""
        
        for linha in texto_total.split('\n'):
            pagina_atual += linha + "\n"
            if len(pagina_atual) > 800:
                paginas.append(pagina_atual)
                pagina_atual = ""
        
        if pagina_atual:
            paginas.append(pagina_atual)
        
        # Criar imagens para cada página
        for i, texto_pagina in enumerate(paginas):
            # Criar imagem
            img = Image.new('RGB', (1200, 1600), color='white')
            draw = ImageDraw.Draw(img)
            
            # Tentar carregar fonte, usar default se falhar
            try:
                font = ImageFont.truetype("arial.ttf", 14)
            except:
                font = ImageFont.load_default()
            
            # Adicionar texto à imagem
            y = 50
            for linha in texto_pagina.split('\n'):
                if linha.strip() and y < 1550:
                    # Quebrar linha se muito longa
                    for parte in [linha[j:j+100] for j in range(0, len(linha), 100)]:
                        if y < 1550:
                            draw.text((50, y), parte, fill='black', font=font)
                            y += 25
            
            imagens.append(img)
        
        return imagens
        
    except Exception as e:
        st.error(f"Erro ao converter DOCX para imagens: {str(e)}")
        return []

# Função 2: Transcrever imagens com modelo de visão
def transcrever_imagens(imagens):
    """Transcreve imagens usando Gemini Vision"""
    texto_completo = ""
    
    if not imagens:
        return texto_completo
    
    progress_bar = st.progress(0)
    
    for i, imagem in enumerate(imagens):
        progresso = (i + 1) / len(imagens)
        progress_bar.progress(progresso)
        
        try:
            # Converter imagem para bytes
            img_bytes = io.BytesIO()
            imagem.save(img_bytes, format='PNG')
            img_bytes = img_bytes.getvalue()
            
            # Prompt para transcrição
            prompt = "Transcreva TODO o texto desta imagem exatamente como aparece, incluindo tabelas, números, nomes e todas as informações visíveis."
            
            # Enviar para Gemini Vision
            response = modelo_visao.generate_content([
                prompt,
                {"mime_type": "image/png", "data": img_bytes}
            ])
            
            texto_completo += f"\n\n=== PÁGINA {i+1} ===\n{response.text}\n"
            
            # Pequena pausa para não sobrecarregar API
            time.sleep(0.5)
            
        except Exception as e:
            texto_completo += f"\n\n=== ERRO PÁGINA {i+1}: {str(e)} ===\n"
    
    progress_bar.empty()
    return texto_completo

# Função 3: Processar texto para CSV
def processar_para_csv(texto_transcrito):
    """Processa texto transcrito para gerar CSV"""
    
    prompt = f"""
    ANALISE O TEXTO ABAIXO QUE FOI EXTRAÍDO DE UM DOCUMENTO SOBRE CULTIVARES.
    
    TEXTO EXTRAÍDO:
    {texto_transcrito}
    
    SUA TAREFA:
    1. Identificar TODAS as cultivares mencionadas no texto
    2. Para CADA cultivar, extrair informações para preencher um CSV
    3. Retornar os dados em formato JSON
    
    O CSV TEM ESTAS COLUNAS (81 no total):
    {json.dumps(COLUNAS, indent=2)}
    
    INSTRUÇÕES:
    - Analise o texto completo
    - Identifique cada cultivar distinta
    - Para cada cultivar, extraia informações do texto
    - Use "NR" para informações não encontradas
    - Mantenha os valores exatos do texto
    - Não invente dados
    
    Retorne APENAS um array JSON onde cada objeto tem as 81 propriedades correspondentes às colunas.
    """
    
    try:
        response = modelo_texto.generate_content(prompt)
        resposta = response.text.strip()
        
        # Tentar extrair JSON
        resposta_limpa = resposta.replace('```json', '').replace('```', '').strip()
        
        try:
            dados = json.loads(resposta_limpa)
            if isinstance(dados, list):
                return dados
            elif isinstance(dados, dict):
                return [dados]
        except:
            # Tentar encontrar JSON na resposta
            inicio = resposta_limpa.find('[')
            fim = resposta_limpa.rfind(']') + 1
            
            if inicio != -1 and fim > inicio:
                json_str = resposta_limpa[inicio:fim]
                return json.loads(json_str)
            
            return []
            
    except Exception as e:
        st.error(f"Erro ao processar texto: {str(e)}")
        return []

# Função para criar DataFrame
def criar_dataframe(dados):
    """Cria DataFrame dos dados extraídos"""
    if not dados:
        return pd.DataFrame(columns=COLUNAS)
    
    linhas = []
    for item in dados:
        if isinstance(item, dict):
            linha = {}
            for col in COLUNAS:
                linha[col] = str(item.get(col, "NR")).strip()
            linhas.append(linha)
    
    if linhas:
        return pd.DataFrame(linhas, columns=COLUNAS)
    else:
        return pd.DataFrame(columns=COLUNAS)

# Interface
def main():
    st.sidebar.header("📤 Upload do Documento")
    
    uploaded_file = st.sidebar.file_uploader(
        "Carregue um arquivo DOCX:",
        type=["docx"]
    )
    
    if uploaded_file:
        st.sidebar.info(f"📄 {uploaded_file.name}")
        
        if st.sidebar.button("🚀 Processar Documento", type="primary"):
            # Limpar estado anterior
            for key in ['imagens', 'texto', 'dados', 'df']:
                if key in st.session_state:
                    del st.session_state[key]
            
            # PASSO 1: Converter DOCX para imagens
            with st.spinner("Convertendo DOCX para imagens..."):
                imagens = docx_para_imagens(uploaded_file.getvalue())
                if imagens:
                    st.session_state.imagens = imagens
                    st.success(f"✅ Convertido em {len(imagens)} página(s)")
                else:
                    st.error("Falha na conversão")
                    return
            
            # PASSO 2: Transcrever imagens
            with st.spinner("Transcrevendo imagens com IA..."):
                texto = transcrever_imagens(imagens)
                if texto:
                    st.session_state.texto = texto
                    st.success(f"✅ Transcrição concluída")
                    
                    # Mostrar preview
                    with st.expander("📝 Ver texto transcrito"):
                        st.text_area("Texto:", texto[:2000] + ("..." if len(texto) > 2000 else ""), height=200)
                else:
                    st.error("Falha na transcrição")
                    return
            
            # PASSO 3: Processar para CSV
            with st.spinner("Extraindo dados para CSV..."):
                dados = processar_para_csv(texto)
                if dados:
                    st.session_state.dados = dados
                    st.success(f"✅ {len(dados)} cultivar(s) encontrada(s)")
                else:
                    st.warning("Nenhum dado extraído")
                    return
            
            # PASSO 4: Criar DataFrame
            df = criar_dataframe(dados)
            if not df.empty:
                st.session_state.df = df
    
    # Mostrar resultados
    if 'df' in st.session_state and st.session_state.df is not None:
        df = st.session_state.df
        
        if not df.empty:
            st.header("📊 Resultados")
            
            # Estatísticas
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Cultivares", len(df))
            with col2:
                st.metric("Colunas", len(df.columns))
            
            # Visualizar dados
            st.subheader("Dados Extraídos")
            
            # Mostrar algumas colunas principais
            colunas_para_mostrar = ['Cultura', 'Nome do produto', 'Tecnologia', 
                                   'Grupo de maturação', 'Fertilidade', 'Estado (por extenso)']
            colunas_disponiveis = [c for c in colunas_para_mostrar if c in df.columns]
            
            if colunas_disponiveis:
                st.dataframe(df[colunas_disponiveis], use_container_width=True)
            else:
                st.dataframe(df, use_container_width=True)
            
            # Download
            st.subheader("📥 Download")
            
            nome_base = uploaded_file.name.split('.')[0] if uploaded_file else "cultivares"
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # CSV com TAB
            csv_content = "\t".join(COLUNAS) + "\n"
            for _, row in df.iterrows():
                linha = [str(row.get(col, "NR")).strip() for col in COLUNAS]
                csv_content += "\t".join(linha) + "\n"
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.download_button(
                    label="📄 Baixar CSV",
                    data=csv_content,
                    file_name=f"{nome_base}_{timestamp}.csv",
                    mime="text/csv"
                )
            
            with col2:
                # Excel
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                excel_data = excel_buffer.getvalue()
                
                st.download_button(
                    label="📊 Baixar Excel",
                    data=excel_data,
                    file_name=f"{nome_base}_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    
    elif 'imagens' in st.session_state:
        # Mostrar que o processamento está incompleto
        st.info("Processamento concluído, mas nenhuma cultivar foi identificada.")
    
    else:
        # Tela inicial
        st.markdown("""
        ## 🌱 Pipeline de Extração de Cultivares
        
        **Fluxo do processamento:**
        
        1. **📤 Upload DOCX** - Carregue seu documento
        2. **🖼️ DOCX → Imagens** - Cada página vira uma imagem
        3. **👁️ Imagens → Texto** - Modelo de visão transcreve tudo
        4. **📝 Texto → CSV** - Modelo de texto extrai dados para 81 colunas
        5. **📊 Resultados** - Visualize e baixe os dados
        
        **Por que converter para imagens?**
        - Captura formatação original
        - Lê tabelas e gráficos
        - Funciona com qualquer layout
        - Preserva informações visuais
        
        **Pronto para começar?** Carregue um DOCX na barra lateral!
        """)

if __name__ == "__main__":
    main()
