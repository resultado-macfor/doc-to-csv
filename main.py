import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
from datetime import datetime
import tempfile
import docx
import io
import csv
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
    modelo_visao = genai.GenerativeModel("gemini-2.5-flash")
    modelo_texto = genai.GenerativeModel("gemini-2.5-flash")
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
        
        # Dividir em páginas
        paginas = []
        pagina_atual = []
        chars_por_pagina = 0
        
        for linha in texto_completo.split('\n'):
            pagina_atual.append(linha)
            chars_por_pagina += len(linha)
            
            if chars_por_pagina > 800:
                paginas.append("\n".join(pagina_atual))
                pagina_atual = []
                chars_por_pagina = 0
        
        if pagina_atual:
            paginas.append("\n".join(pagina_atual))
        
        # Criar imagens
        imagens = []
        for i, texto in enumerate(paginas):
            img = Image.new('RGB', (1200, 1600), color='white')
            draw = ImageDraw.Draw(img)
            
            try:
                font = ImageFont.truetype("arial.ttf", 14)
            except:
                font = ImageFont.load_default()
            
            y = 50
            for linha in texto.split('\n'):
                if linha.strip() and y < 1550:
                    # Quebrar linhas longas
                    for j in range(0, len(linha), 100):
                        if y < 1550:
                            parte = linha[j:j+100]
                            draw.text((50, y), parte, fill='black', font=font)
                            y += 25
            
            imagens.append(img)
        
        return imagens
        
    except Exception as e:
        st.error(f"Erro na conversão: {str(e)}")
        return []

# Função 2: Transcrever imagens com Gemini Vision
def transcrever_com_visao(imagens):
    """Transcreve imagens usando modelo de visão"""
    if not imagens:
        return ""
    
    texto_completo = ""
    
    for i, imagem in enumerate(imagens):
        try:
            # Converter para bytes
            img_bytes = io.BytesIO()
            imagem.save(img_bytes, format='PNG')
            img_bytes = img_bytes.getvalue()
            
            # Prompt para transcrição exata
            prompt = """Transcreva TODO o texto desta imagem EXATAMENTE como aparece.
            Inclua:
            - Tabelas completas
            - Listas
            - Números
            - Nomes de produtos
            - Estados
            - Características técnicas
            - Tudo que estiver escrito"""
            
            response = modelo_visao.generate_content([
                prompt,
                {"mime_type": "image/png", "data": img_bytes}
            ])
            
            texto_completo += f"\n\n=== PÁGINA {i+1} ===\n{response.text}\n"
            time.sleep(0.3)
            
        except Exception as e:
            texto_completo += f"\n\n=== ERRO PÁGINA {i+1} ===\n"
    
    return texto_completo

# Função 3: Extrair dados para CSV
def extrair_dados_para_csv(texto):
    """Extrai dados do texto para o formato CSV"""
    
    prompt = f"""
    ANALISE O TEXTO ABAIXO EXTRAÍDO DE UM DOCUMENTO SOBRE CULTIVARES.
    
    TEXTO:
    {texto}
    
    SUA TAREFA:
    1. Encontre TODAS as cultivares mencionadas
    2. Para CADA cultivar, extraia informações para estas colunas:
    
    COLUNAS DO CSV (81 colunas):
    {', '.join(COLUNAS)}
    
    RETORNE APENAS um array JSON onde cada objeto tem 81 propriedades com os nomes das colunas acima.
    Use "NR" para informações não encontradas. Separe múltiplos elementos identificados na mesma célula com ; (Você está gerando um csv, então é problematico vc usar vírgula)
    """
    
    try:
        response = modelo_texto.generate_content(prompt)
        resposta = response.text.strip()
        
        # Limpar resposta
        resposta_limpa = resposta.replace('```json', '').replace('```', '').strip()
        
        # Tentar extrair JSON
        import json
        import re
        
        # Encontrar array JSON
        match = re.search(r'\[.*\]', resposta_limpa, re.DOTALL)
        if match:
            json_str = match.group(0)
            dados = json.loads(json_str)
            return dados
        
        # Tentar encontrar objeto JSON
        match = re.search(r'\{.*\}', resposta_limpa, re.DOTALL)
        if match:
            json_str = match.group(0)
            dados = [json.loads(json_str)]
            return dados
        
        return []
        
    except Exception as e:
        st.error(f"Erro na extração: {str(e)}")
        return []

# Função 4: Criar DataFrame
def criar_dataframe_gsheets(dados):
    """Cria DataFrame pronto para Google Sheets"""
    if not dados:
        return pd.DataFrame(columns=COLUNAS)
    
    linhas = []
    for item in dados:
        if isinstance(item, dict):
            linha = {}
            for coluna in COLUNAS:
                valor = item.get(coluna, "NR")
                # Garantir que seja string
                if valor is None:
                    valor = "NR"
                linha[coluna] = str(valor).strip()
            linhas.append(linha)
    
    if linhas:
        df = pd.DataFrame(linhas, columns=COLUNAS)
        return df
    else:
        return pd.DataFrame(columns=COLUNAS)

# Função 5: Gerar CSV para Google Sheets
def gerar_csv_gsheets(df):
    """Gera CSV formatado para Google Sheets"""
    output = io.StringIO()
    
    # Usar csv.writer com quoting para lidar com vírgulas no texto
    writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    
    # Escrever cabeçalho
    writer.writerow(COLUNAS)
    
    # Escrever dados
    for _, row in df.iterrows():
        linha = []
        for col in COLUNAS:
            valor = str(row.get(col, "NR")).strip()
            # Escapar vírgulas e quebras de linha
            if ',' in valor or '\n' in valor or '"' in valor:
                valor = valor.replace('"', '""')  # Escapar aspas
                valor = f'"{valor}"'  # Colocar entre aspas
            linha.append(valor)
        writer.writerow(linha)
    
    return output.getvalue()

# Interface principal
def main():
    st.sidebar.header("📤 Upload do Documento")
    
    uploaded_file = st.sidebar.file_uploader(
        "Carregue um arquivo DOCX:",
        type=["docx"],
        help="Documento com informações de cultivares"
    )
    
    if uploaded_file:
        st.sidebar.info(f"**Arquivo:** {uploaded_file.name}")
        st.sidebar.info(f"**Tamanho:** {uploaded_file.size/1024:.1f} KB")
        
        if st.sidebar.button("🚀 Processar Documento", type="primary", use_container_width=True):
            # Limpar estado anterior
            for key in ['imagens', 'texto', 'df']:
                if key in st.session_state:
                    del st.session_state[key]
            
            # PASSO 1: DOCX → Imagens
            with st.spinner("🖼️ Convertendo DOCX para imagens..."):
                imagens = docx_para_imagens(uploaded_file.getvalue())
                if not imagens:
                    st.error("Falha na conversão do DOCX")
                    return
                
                st.session_state.imagens = imagens
                st.success(f"✅ {len(imagens)} página(s) convertida(s)")
            
            # PASSO 2: Imagens → Texto
            with st.spinner("👁️ Transcrevendo imagens com IA..."):
                texto = transcrever_com_visao(imagens)
                if not texto:
                    st.error("Falha na transcrição")
                    return
                
                st.session_state.texto = texto
                st.success(f"✅ Transcrição concluída")
                
                # Mostrar preview
                with st.expander("📝 Ver texto transcrito"):
                    st.text_area("Texto extraído:", texto[:3000] + ("..." if len(texto) > 3000 else ""), 
                               height=250)
            
            # PASSO 3: Texto → Dados estruturados
            with st.spinner("📊 Extraindo dados para CSV..."):
                dados = extrair_dados_para_csv(texto)
                if not dados:
                    st.warning("⚠️ Nenhuma cultivar identificada")
                    st.session_state.df = pd.DataFrame(columns=COLUNAS)
                else:
                    st.success(f"✅ {len(dados)} cultivar(s) encontrada(s)")
                    
                    # Criar DataFrame
                    df = criar_dataframe_gsheets(dados)
                    st.session_state.df = df
                    
                    # Gerar CSV
                    st.session_state.csv_content = gerar_csv_gsheets(df)
        
        # Mostrar resultados
        if 'df' in st.session_state:
            df = st.session_state.df
            
            if not df.empty:
                st.header("📊 Dados para Google Sheets")
                
                # Estatísticas
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Cultivares", len(df))
                with col2:
                    if 'Cultura' in df.columns:
                        culturas = df['Cultura'].unique()
                        st.metric("Culturas", len(culturas))
                with col3:
                    st.metric("Colunas", len(df.columns))
                
                # Visualização
                st.subheader("👁️ Visualização dos Dados")
                
                # Mostrar colunas principais
                colunas_visao = [
                    'Cultura', 'Nome do produto', 'Tecnologia', 
                    'Grupo de maturação', 'Fertilidade', 'Estado (por extenso)'
                ]
                
                colunas_disponiveis = [c for c in colunas_visao if c in df.columns]
                
                if colunas_disponiveis:
                    st.dataframe(df[colunas_disponiveis], use_container_width=True, height=300)
                else:
                    st.dataframe(df.iloc[:, :10], use_container_width=True, height=300)
                
                # Download
                st.subheader("📥 Download para Google Sheets")
                
                nome_base = uploaded_file.name.split('.')[0]
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # CSV para Google Sheets
                    csv_content = st.session_state.get('csv_content', '')
                    if csv_content:
                        st.download_button(
                            label="📄 Baixar CSV (Google Sheets)",
                            data=csv_content,
                            file_name=f"cultivares_{nome_base}_{timestamp}.csv",
                            mime="text/csv",
                            help="CSV formatado para importar no Google Sheets",
                            use_container_width=True
                        )
                
                with col2:
                    # Excel
                    excel_buffer = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Cultivares')
                    excel_data = excel_buffer.getvalue()
                    
                    st.download_button(
                        label="📊 Baixar Excel",
                        data=excel_data,
                        file_name=f"cultivares_{nome_base}_{timestamp}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        help="Arquivo Excel para edição offline",
                        use_container_width=True
                    )
                
                # Instruções para Google Sheets
                with st.expander("📋 Como importar no Google Sheets"):
                    st.markdown("""
                    1. **Vá para [Google Sheets](https://sheets.google.com)**
                    2. **Crie uma nova planilha**
                    3. **Arquivo → Importar → Fazer upload**
                    4. **Selecione o arquivo CSV baixado**
                    5. **Configurações de importação:**
                       - Separador: **Vírgula**
                       - Detectar automaticamente: **Sim**
                       - Converter texto para números/datas: **Sim**
                    6. **Clique em Importar**
                    
                    **Dica:** O CSV já está formatado com 81 colunas na ordem correta!
                    """)
                
                # Preview do CSV
                with st.expander("🔍 Preview do CSV gerado"):
                    if 'csv_content' in st.session_state:
                        linhas = st.session_state.csv_content.split('\n')[:5]
                        st.code("\n".join(linhas), language="csv")
                    
            else:
                st.warning("Nenhum dado extraído do documento.")
    
    else:
        # Tela inicial
        st.markdown("""
        ## 🌱 Pipeline de Extração para Google Sheets
        
        ### 🔄 **Fluxo Completo:**
        1. **📤 DOCX** → Carregue seu documento
        2. **🖼️ Imagens** → Cada página vira imagem PNG
        3. **👁️ Transcrição** → IA lê texto das imagens
        4. **📊 Extração** → IA identifica cultivares e dados
        5. **📄 CSV** → Gera arquivo pronto para Google Sheets
        
        ### ✅ **Formato de Saída:**
        - **CSV com vírgulas** (padrão Google Sheets)
        - **81 colunas** organizadas
        - **Cabeçalhos claros**
        - **Dados estruturados**
        - **"NR" para campos vazios**
        
        ### 🎯 **Pronto para Google Sheets:**
        - Importe direto no Sheets
        - 1 clique para visualizar
        - Formatação preservada
        - Fácil de filtrar e analisar
        
        **Comece carregando um DOCX na barra lateral!**
        """)

if __name__ == "__main__":
    # Inicializar session state
    if 'df' not in st.session_state:
        st.session_state.df = None
    if 'csv_content' not in st.session_state:
        st.session_state.csv_content = ""
    
    main()
