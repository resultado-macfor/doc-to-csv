import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
from datetime import datetime
import tempfile
import docx
import io
import json

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
    modelo = genai.GenerativeModel("gemini-1.5-flash")
except Exception as e:
    st.error(f"Erro ao configurar Gemini: {str(e)}")
    st.stop()

# Colunas obrigatórias (81)
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

def extrair_texto_docx(docx_bytes):
    """Extrai texto de arquivo DOCX"""
    try:
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
            tmp.write(docx_bytes)
            tmp_path = tmp.name
        
        doc = docx.Document(tmp_path)
        texto = []
        
        for para in doc.paragraphs:
            if para.text.strip():
                texto.append(para.text.strip())
        
        for table in doc.tables:
            for row in table.rows:
                row_text = []
                for cell in row.cells:
                    if cell.text.strip():
                        row_text.append(cell.text.strip())
                if row_text:
                    texto.append(" | ".join(row_text))
        
        os.unlink(tmp_path)
        return "\n".join(texto)
        
    except Exception as e:
        st.error(f"Erro ao extrair texto: {str(e)}")
        return ""

def processar_documento(texto):
    """Processa documento com Gemini para extrair dados"""
    
    prompt = f"""
    Você é um especialista em análise de documentos técnicos agrícolas.
    
    ANALISE o seguinte texto extraído de um documento sobre cultivares.
    Sua tarefa é IDENTIFICAR TODAS AS CULTIVARES mencionadas e EXTRAIR AS INFORMAÇÕES
    para preencher um formato CSV específico.
    
    TEXTO DO DOCUMENTO:
    {texto[:20000]}
    
    FORMATO DE SAÍDA:
    Você deve retornar um ARRAY JSON onde cada objeto tem EXATAMENTE 81 propriedades,
    correspondendo às seguintes colunas (em ordem):
    
    {', '.join(COLUNAS)}
    
    INSTRUÇÕES DE PREENCHIMENTO:
    
    1. Para CADA cultivar DISTINTA encontrada no texto, crie um objeto JSON
    2. Use "NR" para qualquer informação NÃO ENCONTRADA no texto
    3. Extraia informações REAIS do texto - NÃO invente dados
    4. Se o texto mencionar "lançamento", coloque "Sim" na coluna Lançamento
    5. Para tecnologia: extraia do texto (IPRO, I2X, RR, etc.)
    6. Para estados: converta siglas para nomes completos
    7. Para regiões: determine baseado nos estados
    8. Para doenças: procure por tabelas ou menções específicas
    9. Para ícones: extraia benefícios mencionados na seção de benefícios
    10. Para resultados: procure por tabelas de produtividade
    
    REGRAS DE MAPEAMENTO:
    - Estados: PR → Paraná, SP → São Paulo, etc.
    - Regiões: PR/SC/RS → Sul, SP/MG/RJ/ES → Sudeste, MT/MS/GO/DF → Centro-Oeste
    - Ciclo: baseado no grupo de maturação
    - Meses de semeadura: inferir baseado no ciclo e região
    
    IMPORTANTE:
    - Analise TODO o texto para encontrar TODAS as cultivares
    - Documentos podem ter 1, 2, 3 ou mais cultivares
    - Cultivares podem estar em páginas diferentes
    - Procure por nomes como NS7524IPRO, TMG7262RR, etc.
    - Procure por seções técnicas, tabelas, características
    
    RETORNE APENAS o array JSON, sem explicações adicionais.
    """
    
    try:
        with st.spinner("Processando documento com IA..."):
            response = modelo.generate_content(prompt)
            resposta = response.text.strip()
            
            # Limpar e extrair JSON
            resposta_limpa = resposta.replace('```json', '').replace('```', '').strip()
            
            # Tentar encontrar e extrair JSON
            try:
                # Primeira tentativa: parse direto
                dados = json.loads(resposta_limpa)
            except json.JSONDecodeError:
                # Segunda tentativa: encontrar array JSON
                inicio = resposta_limpa.find('[')
                fim = resposta_limpa.rfind(']') + 1
                
                if inicio != -1 and fim > inicio:
                    json_str = resposta_limpa[inicio:fim]
                    dados = json.loads(json_str)
                else:
                    # Tentar encontrar qualquer estrutura JSON
                    # Remover texto antes do primeiro {
                    if '{' in resposta_limpa:
                        inicio = resposta_limpa.find('{')
                        fim = resposta_limpa.rfind('}') + 1
                        if fim > inicio:
                            json_str = resposta_limpa[inicio:fim]
                            # Verificar se é um array
                            if not json_str.startswith('['):
                                json_str = f'[{json_str}]'
                            dados = json.loads(json_str)
                    else:
                        st.error("Não foi possível extrair dados JSON da resposta")
                        st.text(f"Resposta recebida:\n{resposta[:1000]}")
                        return []
            
            return dados
            
    except Exception as e:
        st.error(f"Erro no processamento: {str(e)}")
        st.text(f"Resposta recebida (primeiros 1000 chars):\n{resposta[:1000]}")
        return []

def criar_dataframe(dados):
    """Cria DataFrame a partir dos dados extraídos"""
    if not dados:
        return pd.DataFrame(columns=COLUNAS)
    
    linhas = []
    for item in dados:
        linha = {}
        for coluna in COLUNAS:
            # Usar valor do item ou "NR" se não existir
            if isinstance(item, dict):
                linha[coluna] = item.get(coluna, "NR")
            else:
                linha[coluna] = "NR"
        linhas.append(linha)
    
    return pd.DataFrame(linhas)

def gerar_csv_tab(df):
    """Gera string CSV com separador TAB"""
    output = io.StringIO()
    
    # Escrever cabeçalho
    output.write("\t".join(COLUNAS))
    output.write("\n")
    
    # Escrever dados
    for _, row in df.iterrows():
        linha = []
        for col in COLUNAS:
            valor = str(row[col]) if col in row else "NR"
            linha.append(valor)
        output.write("\t".join(linha))
        output.write("\n")
    
    return output.getvalue()

# Interface principal
def main():
    st.sidebar.header("📤 Upload do Documento")
    
    uploaded_file = st.sidebar.file_uploader(
        "Carregue um arquivo DOCX com informações de cultivares:",
        type=["docx"]
    )
    
    if uploaded_file:
        st.sidebar.info(f"📄 {uploaded_file.name} ({uploaded_file.size/1024:.1f} KB)")
        
        col1, col2 = st.sidebar.columns(2)
        with col1:
            processar = st.button("🚀 Processar Documento", type="primary", use_container_width=True)
        with col2:
            if st.button("🔄 Limpar", use_container_width=True):
                if 'df_cultivares' in st.session_state:
                    del st.session_state.df_cultivares
                if 'texto_original' in st.session_state:
                    del st.session_state.texto_original
                if 'nome_arquivo' in st.session_state:
                    del st.session_state.nome_arquivo
                st.rerun()
        
        if processar:
            with st.spinner("Extraindo texto do documento..."):
                # Extrair texto
                texto = extrair_texto_docx(uploaded_file.getvalue())
                
                if not texto:
                    st.error("Não foi possível extrair texto do documento")
                    return
                
                st.info(f"✅ Texto extraído ({len(texto):,} caracteres)")
                
                # Mostrar preview
                with st.expander("📝 Visualizar texto extraído", expanded=False):
                    st.text_area("Conteúdo:", texto[:3000] + ("..." if len(texto) > 3000 else ""), 
                               height=200, key="texto_preview")
                
                # Processar com Gemini
                dados = processar_documento(texto)
                
                if not dados:
                    st.warning("⚠️ Nenhuma cultivar encontrada no documento")
                    # Criar DataFrame vazio
                    st.session_state.df_cultivares = pd.DataFrame(columns=COLUNAS)
                else:
                    st.success(f"✅ {len(dados)} cultivar(s) identificada(s)")
                    
                    # Criar DataFrame
                    df = criar_dataframe(dados)
                    
                    # Salvar em session state
                    st.session_state.df_cultivares = df
                    st.session_state.texto_original = texto
                    st.session_state.nome_arquivo = uploaded_file.name
        
        # Mostrar resultados se disponíveis
        if 'df_cultivares' in st.session_state:
            df = st.session_state.df_cultivares
            
            if df.empty:
                st.warning("Nenhum dado disponível para exibição.")
                return
                
            st.header("📊 Resultados da Extração")
            
            # Estatísticas
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Cultivares Extraídas", len(df))
            with col2:
                if 'Cultura' in df.columns:
                    culturas = df['Cultura'].unique()
                    st.metric("Tipos de Cultura", len(culturas))
                else:
                    st.metric("Colunas", len(df.columns))
            with col3:
                if 'Tecnologia' in df.columns:
                    techs = df['Tecnologia'].unique()
                    techs_validos = [t for t in techs if t != "NR" and str(t) != "nan"]
                    st.metric("Tecnologias", len(techs_validos))
            
            # Visualização principal
            st.subheader("📋 Dados Extraídos")
            
            # Mostrar colunas principais
            colunas_para_mostrar = [
                'Cultura', 'Nome do produto', 'Tecnologia', 'Grupo de maturação',
                'Fertilidade', 'Lançamento', 'Estado (por extenso)'
            ]
            
            colunas_disponiveis = [c for c in colunas_para_mostrar if c in df.columns]
            
            if colunas_disponiveis:
                st.dataframe(df[colunas_disponiveis], use_container_width=True, height=300)
            else:
                st.dataframe(df.iloc[:, :10], use_container_width=True, height=300)
            
            # Visualização completa
            with st.expander("🔍 Visualizar TODAS as 81 colunas", expanded=False):
                st.dataframe(df, use_container_width=True, height=400)
            
            # Download
            st.subheader("📥 Download dos Arquivos")
            
            nome_base = st.session_state.get('nome_arquivo', 'cultivares').split('.')[0]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # CSV com TAB
                csv_content = gerar_csv_tab(df)
                st.download_button(
                    label="📄 Baixar CSV (TAB)",
                    data=csv_content,
                    file_name=f"{nome_base}_{timestamp}.csv",
                    mime="text/csv",
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
                    file_name=f"{nome_base}_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            
            with col3:
                # Texto original
                if 'texto_original' in st.session_state:
                    texto = st.session_state.texto_original
                    if texto:
                        st.download_button(
                            label="📝 Baixar Texto",
                            data=texto,
                            file_name=f"{nome_base}_texto_{timestamp}.txt",
                            mime="text/plain",
                            use_container_width=True
                        )
            
            # Informações técnicas
            with st.expander("⚙️ Informações Técnicas", expanded=False):
                st.write(f"**Total de colunas:** {len(df.columns)}")
                
                # Contar colunas preenchidas
                colunas_preenchidas = 0
                for coluna in df.columns:
                    if not df[coluna].isna().all() and not (df[coluna] == "NR").all():
                        colunas_preenchidas += 1
                
                st.write(f"**Colunas com dados:** {colunas_preenchidas}")
                
                if not df.empty:
                    st.write(f"**Primeira cultivar extraída:**")
                    primeira = df.iloc[0].to_dict()
                    # Mostrar apenas valores não "NR"
                    primeira_filtrada = {k: v for k, v in primeira.items() if v != "NR" and str(v) != "nan"}
                    st.json(primeira_filtrada)
    
    else:
        # Tela inicial
        st.markdown("""
        ## 🌱 Extrator Automático de Cultivares
        
        Este sistema extrai automaticamente informações de documentos DOCX sobre cultivares
        e gera um arquivo CSV com **81 colunas específicas**.
        
        ### 🎯 Como funciona:
        1. **Carregue** um DOCX com informações técnicas de cultivares
        2. **Processe** com IA para identificar todas as cultivares
        3. **Extraia** automaticamente informações para 81 colunas
        4. **Baixe** o CSV formatado ou Excel
        
        ### 📊 Colunas extraídas:
        - **Informações básicas**: Cultura, nome, tecnologia, fertilidade
        - **Características técnicas**: PMS, tipo de crescimento, cores
        - **Resistência a doenças**: 8 doenças diferentes
        - **Recomendações**: Texto técnico completo
        - **Região e época**: Estados, UF, meses de semeadura
        - **Ícones e benefícios**: Até 5 benefícios por cultivar
        - **Resultados**: Até 7 resultados de produtividade
        
        ### ⚡ Processamento inteligente:
        - Identifica **múltiplas cultivares** por documento
        - Extrai dados de **tabelas e textos**
        - Converte **siglas para nomes completos**
        - Determina **regiões automaticamente**
        - Infere **ciclo e meses de semeadura**
        
        ### ✅ Pronto para usar:
        Basta carregar seu DOCX na barra lateral e clicar em "Processar Documento"!
        """)

# Inicializar session state
if 'df_cultivares' not in st.session_state:
    st.session_state.df_cultivares = None
if 'texto_original' not in st.session_state:
    st.session_state.texto_original = ""
if 'nome_arquivo' not in st.session_state:
    st.session_state.nome_arquivo = ""

if __name__ == "__main__":
    main()
