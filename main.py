import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
import pandas as pd
import os
from datetime import datetime
import time
import tempfile
import docx
import csv

# Configuração da página
st.set_page_config(
    page_title="Extrator Completo de Cultivares",
    page_icon="🌱",
    layout="wide"
)

# Título
st.title("🌱 Extrator Completo de Cultivares - DOCX para CSV 81 Colunas")

# Obter API key
gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEM_API_KEY")
if not gemini_api_key:
    st.error("Configure GEMINI_API_KEY ou GEM_API_KEY")
    st.stop()

try:
    genai.configure(api_key=gemini_api_key)
    modelo_vision = genai.GenerativeModel("gemini-1.5-flash")
    modelo_texto = genai.GenerativeModel("gemini-1.5-flash")
except Exception as e:
    st.error(f"Erro ao configurar Gemini: {str(e)}")
    st.stop()

# Cabeçalho EXATO com 81 colunas
CABECALHO_81_COLUNAS = [
    "Cultura", "Nome do produto", "NOME TÉCNICO/ REG", "Descritivo para SEO", 
    "Fertilidade", "Grupo de maturação", "Lançamento", "Slogan", "Tecnologia", 
    "Região (por extenso)", "Estado (por extenso)", "Ciclo", "Finalidade", 
    "URL da imagem do mapa", "Número do ícone", "Titulo icone 1", "Descrição Icone 1", 
    "Número do ícone", "Titulo icone 2", "Descrição Icone 2", "Número do ícone", 
    "Titulo icone 3", "Descrição Icone 3", "Número do ícone", "Título icone 4", 
    "Descrição Icone 4", "Número do ícone", "Título icone 5", "Descrição Icone 5", 
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

# Texto padrão para recomendações
TEXTO_RECOMENDACOES = """Pode haver variação no ciclo (dias) devido às condições edafoclimáticas, época de plantio e manejo aplicado. Recomendações de população final de plantas e de época de semeadura foram construídas com base em resultados de experimentos próprios conduzidos na região e servem como direcionamento da população ideal de plantas para cada talhão. Deve-se levar em consideração: condições edafoclimáticas; textura; fertilidade do solo; adubação; nível de manejo; germinação; vigor da semente; umidade do solo entre outros fatores. Consultar recomendação de Zoneamento Agrícola de Risco Climático para a cultura de acordo com Ministério da Agricultura, Pecuária e Abastecimento."""

# Função para extrair texto do DOCX
def extrair_texto_docx(docx_bytes):
    """Extrai texto direto do DOCX sem converter para imagens"""
    try:
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp_file:
            tmp_file.write(docx_bytes)
            tmp_path = tmp_file.name
        
        doc = docx.Document(tmp_path)
        texto_completo = []
        
        for para in doc.paragraphs:
            if para.text.strip():
                texto_completo.append(para.text)
        
        # Extrair texto de tabelas
        for table in doc.tables:
            for row in table.rows:
                row_text = []
                for cell in row.cells:
                    if cell.text.strip():
                        row_text.append(cell.text.strip())
                if row_text:
                    texto_completo.append(" | ".join(row_text))
        
        os.unlink(tmp_path)
        return "\n".join(texto_completo)
        
    except Exception as e:
        st.error(f"Erro ao extrair texto do DOCX: {str(e)}")
        return ""

# Função para processar imagem (fallback)
def processar_com_visao(docx_bytes):
    """Processa DOCX convertendo para imagem como fallback"""
    try:
        # Método simples: converter texto para imagem
        texto = extrair_texto_docx(docx_bytes)
        
        from PIL import ImageDraw, ImageFont
        img = Image.new('RGB', (1200, 1600), color='white')
        d = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("arial.ttf", 14)
        except:
            font = ImageFont.load_default()
        
        lines = texto.split('\n')
        y = 50
        for line in lines:
            if y < 1550:
                d.text((50, y), line[:100], fill='black', font=font)
                y += 25
        
        # Converter para bytes
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        
        # Transcrever com modelo de visão
        prompt = "Transcreva TODO o texto desta imagem exatamente como aparece."
        response = modelo_vision.generate_content([
            prompt,
            {"mime_type": "image/png", "data": img_byte_arr}
        ])
        
        return response.text
        
    except Exception as e:
        st.error(f"Erro no processamento por visão: {str(e)}")
        return ""

# Função principal para extrair cultivares
def extrair_cultivares_para_csv(texto_transcrito):
    """Extrai informações de cultivares e formata em CSV com 81 colunas"""
    
    prompt = f"""
    VOCÊ É UM ESPECIALISTA EM AGRONOMIA E EXTRATOR DE DADOS.
    
    ANALISE O TEXTO ABAIXO E IDENTIFIQUE TODAS AS CULTIVARES DE SOJA MENCIONADAS.
    PARA CADA CULTIVAR, PREENCHA TODAS AS 81 COLUNAS DO FORMATO CSV ESPECIFICADO.
    
    TEXTO PARA ANÁLISE:
    {texto_transcrito[:10000]}
    
    FORMATO DE SAÍDA EXIGIDO (81 COLUNAS SEPARADAS POR TAB):
    
    COLUNAS E COMO PREENCHER:
    
    1. Cultura: "Soja" (sempre)
    2. Nome do produto: Nome da cultivar (ex: N5659512X, NS802512X)
    3. NOME TÉCNICO/REG: Mesmo que nome do produto
    4. Descritivo para SEO: Descrição de 15-20 palavras
    5. Fertilidade: Alto, Médio, Baixo (extrair do texto)
    6. Grupo de maturação: Número (ex: 6.5, 8)
    7. Lançamento: "Sim" se mencionar lançamento
    8. Slogan: Frase de marketing
    9. Tecnologia: 12X, I2X, IPRO, etc.
    10. Região (por extenso): Sul, Sudeste, Centro-Oeste, Norte, Nordeste
    11. Estado (por extenso): Nomes completos dos estados
    12. Ciclo: Precoce, Médio, Tardio (baseado no grupo)
    13. Finalidade: "Grãos"
    14. URL da imagem do mapa: "NR"
    
    ÍCONES (colunas 15-29):
    15. Número do ícone: "1"
    16. Titulo icone 1: Primeiro benefício
    17. Descrição Icone 1: Descrição detalhada
    18. Número do ícone: "2"
    19. Titulo icone 2: Segundo benefício
    20. Descrição Icone 2: Descrição detalhada
    21. Número do ícone: "3"
    22. Titulo icone 3: Terceiro benefício
    23. Descrição Icone 3: Descrição detalhada
    24. Número do ícone: "4"
    25. Título icone 4: Quarto benefício ou "NR"
    26. Descrição Icone 4: Descrição ou "NR"
    27. Número do ícone: "5"
    28. Título icone 5: Quinto benefício ou "NR"
    29. Descrição Icone 5: Descrição ou "NR"
    
    CARACTERÍSTICAS TÉCNICAS (colunas 30-44):
    30. Exigência à fertilidade: Mesmo que coluna 5
    31. Grupo de maturidade: Mesmo que coluna 6
    32. PMS MÉDIO: Peso em gramas (ex: 165g, 157g)
    33. Tipo de crescimento: Indeterminado, Semideterminado, Determinado
    34. Cor da flor: Branca, Roxa, etc.
    35. Cor da pubescência: Marrom média, etc.
    36. Cor do hilo: Marrom, Preto, etc.
    37-44. Doenças: Preencher com S, M, MR, R, X (X para não mencionado)
    
    RECOMENDAÇÕES E RESULTADOS (colunas 45-71):
    45. Recomendações: Usar texto padrão completo
    46-71. Resultados: Preencher com "NR" (não há resultados no texto)
    
    REGIÃO E MESES (colunas 72-81):
    72. REC: "NR"
    73. UF: Siglas dos estados (PR, MS, SP, GO, MT, RO, TO)
    74. Região: Mesmo que coluna 10
    75-86. Mês 1 a Mês 12: "180-260" para meses de semeadura recomendados, "NR" para outros
    
    TEXTO PADRÃO PARA RECOMENDAÇÕES (COLUNA 45):
    {TEXTO_RECOMENDACOES}
    
    REGRAS CRÍTICAS:
    1. Você DEVE retornar EXATAMENTE 81 valores por linha
    2. Use "NR" para qualquer informação não encontrada
    3. Para doenças não mencionadas, use "X"
    4. Para ícones além dos disponíveis, use "NR"
    5. Para meses de semeadura: inferir baseado no ciclo e região
    
    INFORMAÇÕES DO TEXTO PARA USAR:
    - Cultivar N5659512X: Alto fertilidade, grupo 6.5, lançamento, tecnologia 12X, estados PR/MS/SP
    - Cultivar NS802512X: Médio e alto fertilidade, grupo 8, lançamento, tecnologia 12X, estados GO/MS/MT/RO/TO
    
    AGORA, GERE O CSV COM TODAS AS 81 COLUNAS PREENCHIDAS.
    
    FORMATO DE SAÍDA:
    Soja\tN5659512X\tN5659512X\t[descrição SEO]\tAlto\t6.5\tSim\t[slogan]\t12X\t[região]\t[estados]\t[ciclo]\tGrãos\tNR\t1\t[título1]\t[desc1]\t2\t[título2]\t[desc2]\t3\t[título3]\t[desc3]\t4\tNR\tNR\t5\tNR\tNR\tAlto\t6.5\t165g\tIndeterminado\tBranca\tMarrom média\tMarrom\tX\tX\tX\tX\tX\tX\tX\tX\t[texto recomendações]\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tPR, MS, SP\t[região]\tNR\tNR\t180-260\t180-260\t180-260\t180-260\t180-260\t180-260\t180-260\t180-260\t180-260\tNR
    
    Retorne APENAS as linhas CSV, UMA POR CULTIVAR, sem cabeçalho, sem explicações.
    """
    
    try:
        with st.spinner("Processando com IA para extrair todas as 81 colunas..."):
            response = modelo_texto.generate_content(prompt)
            resultado = response.text.strip()
        
        # Processar linhas do CSV
        linhas_processadas = []
        
        for linha in resultado.split('\n'):
            linha = linha.strip()
            if linha and '\t' in linha:
                # Separar por tab
                valores = linha.split('\t')
                
                # Garantir EXATAMENTE 81 valores
                if len(valores) < 81:
                    # Adicionar "NR" para colunas faltantes
                    valores.extend(["NR"] * (81 - len(valores)))
                elif len(valores) > 81:
                    # Manter apenas 81 colunas
                    valores = valores[:81]
                
                linhas_processadas.append(valores)
        
        return linhas_processadas
        
    except Exception as e:
        st.error(f"Erro na extração: {str(e)}")
        return []

# Função para criar DataFrame com 81 colunas
def criar_dataframe_completo(linhas_csv):
    """Cria DataFrame garantindo 81 colunas"""
    if not linhas_csv:
        return pd.DataFrame(columns=CABECALHO_81_COLUNAS)
    
    # Garantir que todas as linhas têm 81 colunas
    linhas_corrigidas = []
    for linha in linhas_csv:
        if len(linha) < 81:
            linha.extend(["NR"] * (81 - len(linha)))
        elif len(linha) > 81:
            linha = linha[:81]
        linhas_corrigidas.append(linha)
    
    return pd.DataFrame(linhas_corrigidas, columns=CABECALHO_81_COLUNAS)

# Função para gerar CSV com separador TAB
def gerar_csv_tab(df):
    """Gera string CSV com separador TAB"""
    output = io.StringIO()
    # Escrever cabeçalho
    output.write("\t".join(CABECALHO_81_COLUNAS))
    output.write("\n")
    
    # Escrever dados
    for _, row in df.iterrows():
        linha = []
        for col in CABECALHO_81_COLUNAS:
            valor = str(row[col]) if col in row else "NR"
            linha.append(valor)
        output.write("\t".join(linha))
        output.write("\n")
    
    return output.getvalue()

# Interface principal
def main():
    st.sidebar.header("📤 Upload do Documento")
    
    uploaded_file = st.sidebar.file_uploader(
        "Carregue um arquivo DOCX:",
        type=["docx"],
        help="Documento com informações de cultivares de soja"
    )
    
    if uploaded_file:
        st.sidebar.write(f"**Arquivo:** {uploaded_file.name}")
        st.sidebar.write(f"**Tamanho:** {uploaded_file.size / 1024:.1f} KB")
        
        if st.sidebar.button("🚀 Processar Documento", type="primary", use_container_width=True):
            with st.spinner("Processando documento..."):
                # Extrair texto do DOCX
                texto_extraido = extrair_texto_docx(uploaded_file.getvalue())
                
                if not texto_extraido:
                    st.error("Não foi possível extrair texto do documento")
                    return
                
                st.success(f"✅ Texto extraído ({len(texto_extraido):,} caracteres)")
                
                # Mostrar preview
                with st.expander("📝 Visualizar texto extraído", expanded=False):
                    st.text_area("Conteúdo:", texto_extraido[:2000] + ("..." if len(texto_extraido) > 2000 else ""), 
                               height=200)
                
                # Extrair cultivares com IA
                linhas_csv = extrair_cultivares_para_csv(texto_extraido)
                
                if not linhas_csv:
                    st.warning("Nenhuma cultivar encontrada no documento")
                    return
                
                st.success(f"✅ {len(linhas_csv)} cultivar(s) encontrada(s)")
                
                # Criar DataFrame
                df = criar_dataframe_completo(linhas_csv)
                
                # Armazenar em session state
                st.session_state.df_cultivares = df
                st.session_state.texto_original = texto_extraido
                
        # Mostrar resultados se disponíveis
        if 'df_cultivares' in st.session_state:
            df = st.session_state.df_cultivares
            
            st.header("📊 Resultados - CSV com 81 Colunas")
            
            # Estatísticas
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Cultivares", len(df))
            with col2:
                st.metric("Colunas", len(df.columns))
            with col3:
                if 'Tecnologia' in df.columns:
                    techs = df['Tecnologia'].unique()
                    st.metric("Tecnologias", len([t for t in techs if t != "NR"]))
            with col4:
                if 'Grupo de maturação' in df.columns:
                    grupos = df['Grupo de maturação'].unique()
                    st.metric("Grupos", len([g for g in grupos if g != "NR"]))
            
            # Visualização da tabela
            st.subheader("Visualização dos Dados")
            
            # Selecionar colunas para visualização
            colunas_principais = [
                'Cultura', 'Nome do produto', 'Tecnologia', 'Grupo de maturação',
                'Fertilidade', 'Lançamento', 'Estado (por extenso)', 'PMS MÉDIO'
            ]
            
            colunas_disponiveis = [c for c in colunas_principais if c in df.columns]
            
            if colunas_disponiveis:
                st.dataframe(df[colunas_disponiveis], use_container_width=True, height=300)
            else:
                st.dataframe(df.iloc[:, :10], use_container_width=True, height=300)
            
            # Visualizar todas as colunas
            with st.expander("🔍 Visualizar TODAS as 81 colunas", expanded=False):
                st.dataframe(df, use_container_width=True, height=400)
            
            # Download
            st.subheader("📥 Download dos Arquivos")
            
            col_dl1, col_dl2, col_dl3 = st.columns(3)
            
            with col_dl1:
                # CSV com TAB
                csv_tab = gerar_csv_tab(df)
                nome_base = uploaded_file.name.split('.')[0]
                
                st.download_button(
                    label="📄 Baixar CSV (TAB)",
                    data=csv_tab,
                    file_name=f"{nome_base}_81colunas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    help="CSV com separador TAB e 81 colunas"
                )
            
            with col_dl2:
                # Excel
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Cultivares')
                excel_data = excel_buffer.getvalue()
                
                st.download_button(
                    label="📊 Baixar Excel",
                    data=excel_data,
                    file_name=f"{nome_base}_81colunas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    help="Arquivo Excel com todas as 81 colunas"
                )
            
            with col_dl3:
                # Texto original
                if 'texto_original' in st.session_state:
                    st.download_button(
                        label="📝 Baixar Texto Extraído",
                        data=st.session_state.texto_original,
                        file_name=f"{nome_base}_texto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain",
                        use_container_width=True,
                        help="Texto completo extraído do DOCX"
                    )
            
            # Detalhes técnicos
            with st.expander("⚙️ Detalhes Técnicos", expanded=False):
                st.write(f"**Colunas geradas:** {len(df.columns)}/81")
                st.write(f"**Linhas:** {len(df)}")
                
                # Verificar colunas preenchidas
                colunas_nr = []
                colunas_preenchidas = []
                
                for col in df.columns:
                    if df[col].isna().all() or (df[col] == "NR").all():
                        colunas_nr.append(col)
                    else:
                        colunas_preenchidas.append(col)
                
                st.write(f"**Colunas preenchidas:** {len(colunas_preenchidas)}")
                st.write(f"**Colunas com 'NR':** {len(colunas_nr)}")
                
                if colunas_nr:
                    with st.expander("Ver colunas não preenchidas"):
                        st.write(", ".join(colunas_nr))
    
    else:
        # Tela inicial
        st.markdown("""
        ## 🌱 Extrator Completo de Cultivares
        
        Este sistema extrai informações de documentos DOCX sobre cultivares de soja
        e gera um CSV com **81 colunas específicas**.
        
        ### 📋 Colunas que serão geradas:
        
        1. **Informações Básicas** (13 colunas)
           - Cultura, Nome do produto, Nome técnico, SEO, Fertilidade, etc.
        
        2. **Ícones e Benefícios** (15 colunas)
           - Até 5 ícones com títulos e descrições
        
        3. **Características Técnicas** (15 colunas)
           - PMS, Tipo de crescimento, Cores, Resistência a doenças
        
        4. **Recomendações e Resultados** (27 colunas)
           - Texto de recomendações e até 7 resultados
        
        5. **Região e Época** (11 colunas)
           - Estados, UF, Região, Meses de semeadura
        
        ### 🚀 Como usar:
        1. Carregue um DOCX na barra lateral
        2. Clique em "Processar Documento"
        3. Visualize os dados extraídos
        4. Baixe o CSV com 81 colunas
        
        ### ✅ Exemplo de saída:
        Cada cultivar gera uma linha com 81 valores separados por TAB.
        """)
        
        # Exemplo de CSV
        with st.expander("📄 Exemplo do formato CSV gerado"):
            exemplo_csv = """Soja\tN5659512X\tN5659512X\tCultivar de soja com alta produtividade...\tAlto\t6.5\tSim\tO caminho da alta produtividade tem nome\t12X\tSul, Centro-Oeste, Sudeste\tParaná, Mato Grosso do Sul, São Paulo\tMédio\tGrãos\tNR\t1\tAlto retorno\tDescrição do benefício...\t2\tAlta produtividade\tDescrição...\t3\tFacilidade de manejo\tDescrição...\t4\tNR\tNR\t5\tNR\tNR\tAlto\t6.5\t165g\tIndeterminado\tBranca\tMarrom média\tMarrom\tX\tX\tX\tX\tX\tX\tX\tX\tTexto de recomendações completo...\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tNR\tPR, MS, SP\tSul, Centro-Oeste, Sudeste\tNR\tNR\t180-260\t180-260\t180-260\t180-260\t180-260\t180-260\t180-260\t180-260\t180-260\tNR"""
            
            # Separar em colunas para visualização
            partes = exemplo_csv.split('\t')
            df_exemplo = pd.DataFrame([partes[:20]], columns=CABECALHO_81_COLUNAS[:20])
            st.dataframe(df_exemplo, use_container_width=True)

if __name__ == "__main__":
    # Inicializar session state
    if 'df_cultivares' not in st.session_state:
        st.session_state.df_cultivares = None
    if 'texto_original' not in st.session_state:
        st.session_state.texto_original = ""
    
    main()
