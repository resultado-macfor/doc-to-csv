import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
import pandas as pd
import re
import os
from datetime import datetime

# Configuração da página
st.set_page_config(
    page_title="Extrator de Informações de Cultivares de Soja",
    page_icon="🌱",
    layout="wide"
)

# Título do aplicativo
st.title("🌱 Extrator de Informações de Cultivares de Soja")
st.markdown("""
**Carregue uma imagem com informações técnicas de cultivares de soja e o sistema extrairá e organizará os dados no formato desejado.**

O aplicativo usa o modelo Gemini Vision para análise e extração de informações.
""")

# Configuração da API do Gemini
st.sidebar.header("⚙️ Configuração")
gemini_api_key = st.sidebar.text_input(
    "API Key do Gemini",
    type="password",
    help="Insira sua API key do Google Gemini",
    value=os.getenv("GEMINI_API_KEY", "")
)

if not gemini_api_key:
    st.warning("⚠️ Por favor, insira sua API Key do Gemini na sidebar para usar o aplicativo.")
    st.info("Você pode obter uma API key em: https://aistudio.google.com/app/apikey")
    st.stop()

try:
    genai.configure(api_key=gemini_api_key)
    modelo_vision = genai.GenerativeModel("gemini-2.0-flash")
except Exception as e:
    st.error(f"❌ Erro ao configurar o Gemini: {str(e)}")
    st.stop()

# Função para extrair informações da imagem
def extrair_informacoes_imagem(imagem_bytes, nome_arquivo):
    """Extrai informações técnicas da imagem usando Gemini Vision"""
    
    prompt = """
    Você é um especialista em agricultura e culturas de soja. Analise esta imagem e extraia todas as informações técnicas sobre a cultivar de soja.

    A imagem contém informações sobre cultivares de soja. Extraia os seguintes dados:

    ### INFORMAÇÕES PRINCIPAIS:
    1. **Nome do produto** (ex: NS7524IPRO, NS6595I2X, etc.)
    2. **Exigência à fertilidade** (Alto, Médio, Baixo)
    3. **Grupo de maturação** (ex: 7.5, 6.5, etc.)
    4. **É lançamento?** (Sim ou Não)
    5. **Slogan/Descrição principal**
    6. **Tecnologia** (ex: IPRO, I2X, etc.)
    7. **Estados recomendados** (lista completa)
    8. **Benefícios/Características principais** (lista de 3-5 itens)

    ### INFORMAÇÕES FENOTÍPICAS:
    9. **PMS MÉDIO** (Peso de Mil Sementes)
    10. **Tipo de crescimento** (Indeterminado, Semideterminado, Determinado)
    11. **Cor da flor**
    12. **Cor da pubescência**
    13. **Cor do hilo**

    ### TOLERÂNCIA A DOENÇAS:
    Para cada doença, classifique como: S (Suscetível), MS (Mod. Suscetível), MR (Mod. Resistente), R (Resistente), X (Resistente)
    14. **Cancro da haste**
    15. **Pústula bacteriana**
    16. **Nematoide das galhas - M. javanica**
    17. **Nematóide de Cisto (Raça 3)**
    18. **Nematóide de Cisto (Raça 9)**
    19. **Nematóide de Cisto (Raça 10)**
    20. **Nematóide de Cisto (Raça 14)**
    21. **Fitóftora (Raça 1)**

    ### RESULTADOS (se houver na imagem):
    22. Extraia até 7 resultados com: Nome, Local, Produtividade (ex: 106,0 sc/ha)

    ### ÉPOCA DE SEMEADURA:
    23. Extraia os meses de semeadura recomendados

    IMPORTANTE:
    - Forneça as informações em formato estruturado
    - Se uma informação não estiver disponível, use "NR" (Não informado)
    - Para tecnologias: I2X significa Intacta 2 Xtend, IPRO é Intacta PRO
    - Para grupos de maturação: se houver variação por região (ex: 7.7 M3 | 7.8 M4), mantenha exatamente como está
    - Para estados: escreva por extenso separados por vírgula

    Formato de resposta:
    NOME_DO_PRODUTO: [valor]
    FERTILIDADE: [valor]
    GRUPO_MATURACAO: [valor]
    LANCAMENTO: [Sim/Não]
    SLOGAN: [valor]
    TECNOLOGIA: [valor]
    ESTADOS: [valor]
    BENEFICIOS: [item1; item2; item3]
    PMS_MEDIO: [valor]
    TIPO_CRESCIMENTO: [valor]
    COR_FLOR: [valor]
    COR_PUBESCENCIA: [valor]
    COR_HILO: [valor]
    CANCRO_HASTE: [valor]
    PUSTULA_BACTERIANA: [valor]
    NEMATOIDE_GALHAS: [valor]
    NEMATOIDE_CISTO_R3: [valor]
    NEMATOIDE_CISTO_R9: [valor]
    NEMATOIDE_CISTO_R10: [valor]
    NEMATOIDE_CISTO_R14: [valor]
    FITOFTORA_R1: [valor]
    RESULTADOS: [Nome1, Local1, Prod1; Nome2, Local2, Prod2; ...]
    MESES_SEMEADURA: [mes1, mes2, mes3, ...]
    """
    
    try:
        response = modelo_vision.generate_content([
            prompt,
            {"mime_type": "image/jpeg", "data": imagem_bytes}
        ])
        
        return response.text
    except Exception as e:
        return f"Erro na extração: {str(e)}"

# Função para processar os dados extraídos
def processar_dados_extraidos(texto_extraido):
    """Processa o texto extraído e organiza em dicionário"""
    
    dados = {
        'Cultura': 'Soja',
        'Nome do produto': 'NR',
        'NOME TÉCNICO/ REG': 'NR',
        'Descritivo para SEO': 'NR',
        'Fertilidade': 'NR',
        'Grupo de maturação': 'NR',
        'Lançamento': 'NR',
        'Slogan': 'NR',
        'Tecnologia': 'NR',
        'Região (por extenso)': 'NR',
        'Estado (por extenso)': 'NR',
        'Ciclo': 'NR',
        'Finalidade': 'Grãos',
        'URL da imagem do mapa': 'NR',
        'Número do ícone': 'NR',
        'Titulo icone 1': 'NR',
        'Descrição Icone 1': 'NR',
        'Número do ícone': 'NR',
        'Titulo icone 2': 'NR',
        'Descrição Icone 2': 'NR',
        'Número do ícone': 'NR',
        'Título icone 3': 'NR',
        'Descrição Icone 3': 'NR',
        'Número do ícone': 'NR',
        'Título icone 4': 'NR',
        'Descrição Icone 4': 'NR',
        'Número do ícone': 'NR',
        'Título icone 5': 'NR',
        'Descrição Icone 5': 'NR',
        'Exigência à fertilidade': 'NR',
        'Grupo de maturidade': 'NR',
        'PMS MÉDIO': 'NR',
        'Tipo de crescimento': 'NR',
        'Cor da flor': 'NR',
        'Cor da pubescência': 'NR',
        'Cor do hilo': 'NR',
        'Cancro da haste': 'NR',
        'Pústula bacteriana': 'NR',
        'Nematoide das galhas - M. javanica': 'NR',
        'Nematóide de Cisto (Raça 3)': 'NR',
        'Nematóide de Cisto (Raça 9)': 'NR',
        'Nematóide de Cisto (Raça 10)': 'NR',
        'Nematóide de Cisto (Raça 14)': 'NR',
        'Fitóftora (Raça 1)': 'NR',
        'Recomendações': 'Pode haver variação no ciclo (dias) devido às condições edafoclimáticas, época de plantio e manejo aplicado. Recomendações de população final de plantas e de época de semeadura foram construídas com base em resultados de experimentos próprios conduzidos na região e servem como direcionamento da população ideal de plantas para cada talhão. Deve-se levar em consideração: condições edafoclimáticas; textura; fertilidade do solo; adubação; nível de manejo; germinação; vigor da semente; umidade do solo entre outros fatores. Consultar recomendação de Zoneamento Agrícola de Risco Climático para a cultura de acordo com Ministério da Agricultura, Pecuária e Abastecimento.',
        'Resultado 1 - Nome': 'NR',
        'Resultado 1 - Local': 'NR',
        'Resultado 1': 'NR',
        'Resultado 2 - Nome': 'NR',
        'Resultado 2 - Local': 'NR',
        'Resultado 2': 'NR',
        'Resultado 3 - Nome': 'NR',
        'Resultado 3 - Local': 'NR',
        'Resultado 3': 'NR',
        'Resultado 4 - Nome': 'NR',
        'Resultado 4 - Local': 'NR',
        'Resultado 4': 'NR',
        'Resultado 5 - Nome': 'NR',
        'Resultado 5 - Local': 'NR',
        'Resultado 5': 'NR',
        'Resultado 6 - Nome': 'NR',
        'Resultado 6 - Local': 'NR',
        'Resultado 6': 'NR',
        'Resultado 7 - Nome': 'NR',
        'Resultado 7 - Local': 'NR',
        'Resultado 7': 'NR',
    }
    
    # Mapear abreviações de estados para nomes completos
    estado_map = {
        'PR': 'Paraná',
        'SC': 'Santa Catarina', 
        'RS': 'Rio Grande do Sul',
        'SP': 'São Paulo',
        'MG': 'Minas Gerais',
        'MS': 'Mato Grosso do Sul',
        'GO': 'Goiás',
        'MT': 'Mato Grosso',
        'DF': 'Distrito Federal',
        'BA': 'Bahia',
        'TO': 'Tocantins',
        'MA': 'Maranhão',
        'PI': 'Piauí',
        'RO': 'Rondônia',
        'PA': 'Pará'
    }
    
    # Processar cada linha do texto extraído
    linhas = texto_extraido.split('\n')
    
    for linha in linhas:
        linha = linha.strip()
        
        # Nome do produto
        if linha.startswith('NOME_DO_PRODUTO:'):
            valor = linha.replace('NOME_DO_PRODUTO:', '').strip()
            dados['Nome do produto'] = valor
            dados['NOME TÉCNICO/ REG'] = valor
        
        # Fertilidade
        elif linha.startswith('FERTILIDADE:'):
            valor = linha.replace('FERTILIDADE:', '').strip()
            dados['Fertilidade'] = valor
            dados['Exigência à fertilidade'] = valor
        
        # Grupo de maturação
        elif linha.startswith('GRUPO_MATURACAO:'):
            valor = linha.replace('GRUPO_MATURACAO:', '').strip()
            dados['Grupo de maturação'] = valor
            dados['Grupo de maturidade'] = valor
        
        # Lançamento
        elif linha.startswith('LANCAMENTO:'):
            valor = linha.replace('LANCAMENTO:', '').strip()
            dados['Lançamento'] = 'Sim' if 'Sim' in valor else 'Não'
        
        # Slogan
        elif linha.startswith('SLOGAN:'):
            valor = linha.replace('SLOGAN:', '').strip()
            dados['Slogan'] = valor
            dados['Descritivo para SEO'] = valor
        
        # Tecnologia
        elif linha.startswith('TECNOLOGIA:'):
            valor = linha.replace('TECNOLOGIA:', '').strip()
            dados['Tecnologia'] = valor
        
        # Estados
        elif linha.startswith('ESTADOS:'):
            valor = linha.replace('ESTADOS:', '').strip()
            estados = [e.strip() for e in valor.split(',')]
            
            # Converter siglas para nomes completos
            estados_completos = []
            for estado in estados:
                if estado in estado_map:
                    estados_completos.append(estado_map[estado])
                else:
                    estados_completos.append(estado)
            
            dados['Estado (por extenso)'] = ', '.join(estados_completos)
            
            # Determinar região baseada nos estados
            regiao_sul = {'Paraná', 'Santa Catarina', 'Rio Grande do Sul'}
            regiao_sudeste = {'São Paulo', 'Minas Gerais', 'Espírito Santo', 'Rio de Janeiro'}
            regiao_centro_oeste = {'Mato Grosso', 'Mato Grosso do Sul', 'Goiás', 'Distrito Federal'}
            regiao_nordeste = {'Bahia', 'Maranhão', 'Piauí'}
            regiao_norte = {'Pará', 'Rondônia', 'Tocantins'}
            
            regioes = []
            estados_set = set(estados_completos)
            
            if estados_set.intersection(regiao_sul):
                regioes.append('Sul')
            if estados_set.intersection(regiao_sudeste):
                regioes.append('Sudeste')
            if estados_set.intersection(regiao_centro_oeste):
                regioes.append('Centro-Oeste')
            if estados_set.intersection(regiao_nordeste):
                regioes.append('Nordeste')
            if estados_set.intersection(regiao_norte):
                regioes.append('Norte')
            
            dados['Região (por extenso)'] = ', '.join(regioes) if regioes else 'NR'
        
        # Benefícios
        elif linha.startswith('BENEFICIOS:'):
            valor = linha.replace('BENEFICIOS:', '').strip()
            beneficios = [b.strip() for b in valor.split(';')]
            
            # Distribuir benefícios nos ícones
            for i, beneficio in enumerate(beneficios[:5], 1):
                if i == 1:
                    dados['Titulo icone 1'] = 'Benefício' if i == 1 else f'Benefício {i}'
                    dados['Descrição Icone 1'] = beneficio
                elif i == 2:
                    dados['Titulo icone 2'] = f'Benefício {i}'
                    dados['Descrição Icone 2'] = beneficio
                elif i == 3:
                    dados['Título icone 3'] = f'Benefício {i}'
                    dados['Descrição Icone 3'] = beneficio
                elif i == 4:
                    dados['Título icone 4'] = f'Benefício {i}'
                    dados['Descrição Icone 4'] = beneficio
                elif i == 5:
                    dados['Título icone 5'] = f'Benefício {i}'
                    dados['Descrição Icone 5'] = beneficio
        
        # PMS MÉDIO
        elif linha.startswith('PMS_MEDIO:'):
            valor = linha.replace('PMS_MEDIO:', '').strip()
            dados['PMS MÉDIO'] = valor
        
        # Tipo de crescimento
        elif linha.startswith('TIPO_CRESCIMENTO:'):
            valor = linha.replace('TIPO_CRESCIMENTO:', '').strip()
            dados['Tipo de crescimento'] = valor
        
        # Cor da flor
        elif linha.startswith('COR_FLOR:'):
            valor = linha.replace('COR_FLOR:', '').strip()
            dados['Cor da flor'] = valor
        
        # Cor da pubescência
        elif linha.startswith('COR_PUBESCENCIA:'):
            valor = linha.replace('COR_PUBESCENCIA:', '').strip()
            dados['Cor da pubescência'] = valor
        
        # Cor do hilo
        elif linha.startswith('COR_HILO:'):
            valor = linha.replace('COR_HILO:', '').strip()
            dados['Cor do hilo'] = valor
        
        # Doenças
        elif linha.startswith('CANCRO_HASTE:'):
            dados['Cancro da haste'] = linha.replace('CANCRO_HASTE:', '').strip()
        elif linha.startswith('PUSTULA_BACTERIANA:'):
            dados['Pústula bacteriana'] = linha.replace('PUSTULA_BACTERIANA:', '').strip()
        elif linha.startswith('NEMATOIDE_GALHAS:'):
            dados['Nematoide das galhas - M. javanica'] = linha.replace('NEMATOIDE_GALHAS:', '').strip()
        elif linha.startswith('NEMATOIDE_CISTO_R3:'):
            dados['Nematóide de Cisto (Raça 3)'] = linha.replace('NEMATOIDE_CISTO_R3:', '').strip()
        elif linha.startswith('NEMATOIDE_CISTO_R9:'):
            dados['Nematóide de Cisto (Raça 9)'] = linha.replace('NEMATOIDE_CISTO_R9:', '').strip()
        elif linha.startswith('NEMATOIDE_CISTO_R10:'):
            dados['Nematóide de Cisto (Raça 10)'] = linha.replace('NEMATOIDE_CISTO_R10:', '').strip()
        elif linha.startswith('NEMATOIDE_CISTO_R14:'):
            dados['Nematóide de Cisto (Raça 14)'] = linha.replace('NEMATOIDE_CISTO_R14:', '').strip()
        elif linha.startswith('FITOFTORA_R1:'):
            dados['Fitóftora (Raça 1)'] = linha.replace('FITOFTORA_R1:', '').strip()
        
        # Resultados
        elif linha.startswith('RESULTADOS:'):
            valor = linha.replace('RESULTADOS:', '').strip()
            if valor and valor != 'NR':
                resultados = [r.strip() for r in valor.split(';')]
                for i, resultado in enumerate(resultados[:7], 1):
                    partes = [p.strip() for p in resultado.split(',')]
                    if len(partes) >= 3:
                        dados[f'Resultado {i} - Nome'] = partes[0]
                        dados[f'Resultado {i} - Local'] = partes[1]
                        dados[f'Resultado {i}'] = partes[2]
        
        # Meses de semeadura
        elif linha.startswith('MESES_SEMEADURA:'):
            valor = linha.replace('MESES_SEMEADURA:', '').strip()
            if valor and valor != 'NR':
                meses = [m.strip() for m in valor.split(',')]
                meses_numeros = {
                    'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4,
                    'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8,
                    'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12
                }
                
                # Preencher meses no formato correto
                for mes_nome in meses:
                    if mes_nome.lower() in meses_numeros:
                        num_mes = meses_numeros[mes_nome.lower()]
                        dados[f'Mês {num_mes}'] = '180-260'  # População padrão
    
    return dados

# Layout principal
col1, col2 = st.columns([1, 2])

with col1:
    st.header("📤 Upload da Imagem")
    
    uploaded_file = st.file_uploader(
        "Carregue uma imagem com informações da cultivar:",
        type=["jpg", "jpeg", "png", "bmp", "webp"],
        help="Imagem contendo informações técnicas da cultivar de soja"
    )
    
    if uploaded_file is not None:
        # Exibir a imagem
        image = Image.open(uploaded_file)
        st.image(image, caption=f"Imagem carregada: {uploaded_file.name}", use_container_width=True)
        
        # Botão para processar
        if st.button("🔍 Extrair Informações da Imagem", type="primary", use_container_width=True):
            with st.spinner("Analisando imagem com IA..."):
                try:
                    # Converter imagem para bytes
                    img_bytes = uploaded_file.getvalue()
                    
                    # Extrair informações
                    texto_extraido = extrair_informacoes_imagem(img_bytes, uploaded_file.name)
                    
                    # Processar dados
                    dados_processados = processar_dados_extraidos(texto_extraido)
                    
                    # Armazenar na sessão
                    st.session_state.dados_extraidos = dados_processados
                    st.session_state.texto_bruto = texto_extraido
                    
                    st.success("✅ Informações extraídas com sucesso!")
                    
                except Exception as e:
                    st.error(f"❌ Erro ao processar imagem: {str(e)}")
    
    # Exemplo de formato esperado
    with st.expander("📋 Exemplo do Formato de Saída", expanded=False):
        st.markdown("""
        **Formato CSV com as seguintes colunas:**
        ```
        Cultura, Nome do produto, NOME TÉCNICO/ REG, Descritivo para SEO, Fertilidade, 
        Grupo de maturação, Lançamento, Slogan, Tecnologia, Região (por extenso), 
        Estado (por extenso), Ciclo, Finalidade, URL da imagem do mapa, 
        Número do ícone, Titulo icone 1, Descrição Icone 1, ...
        ```
        """)

with col2:
    st.header("📊 Dados Extraídos e Formatados")
    
    if 'dados_extraidos' in st.session_state:
        # Mostrar dados em formato tabular
        st.subheader("📋 Dados Formatados")
        
        # Converter para DataFrame
        df = pd.DataFrame([st.session_state.dados_extraidos])
        
        # Transpor para melhor visualização
        df_transposto = df.T.reset_index()
        df_transposto.columns = ['Campo', 'Valor']
        
        # Mostrar tabela
        st.dataframe(df_transposto, use_container_width=True, height=400)
        
        # Mostrar texto bruto extraído
        with st.expander("📝 Texto Bruto Extraído pela IA", expanded=False):
            st.text_area("Texto extraído:", st.session_state.texto_bruto, height=200)
        
        # Botões de download
        st.subheader("💾 Exportar Dados")
        
        col_dl1, col_dl2, col_dl3 = st.columns(3)
        
        with col_dl1:
            # Download CSV
            csv_data = df.to_csv(index=False, sep=';', encoding='utf-8-sig')
            st.download_button(
                label="📥 Baixar CSV",
                data=csv_data,
                file_name=f"cultivar_{st.session_state.dados_extraidos.get('Nome do produto', 'desconhecido')}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        
        with col_dl2:
            # Download Excel
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Dados Cultivar')
            excel_data = excel_buffer.getvalue()
            
            st.download_button(
                label="📊 Baixar Excel",
                data=excel_data,
                file_name=f"cultivar_{st.session_state.dados_extraidos.get('Nome do produto', 'desconhecido')}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        with col_dl3:
            # Download JSON
            json_data = df.to_json(orient='records', indent=2, force_ascii=False)
            st.download_button(
                label="📄 Baixar JSON",
                data=json_data,
                file_name=f"cultivar_{st.session_state.dados_extraidos.get('Nome do produto', 'desconhecido')}_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json"
            )
        
        # Visualização prévia do CSV
        st.subheader("👁️ Prévia do CSV Formatado")
        st.dataframe(df, use_container_width=True)
        
    else:
        st.info("""
        **ℹ️ Instruções:**
        1. Carregue uma imagem com informações da cultivar de soja
        2. Clique em **"Extrair Informações da Imagem"**
        3. Os dados serão extraídos e formatados automaticamente
        
        **📷 Tipos de imagens aceitas:**
        - Catálogos de cultivares
        - Fichas técnicas
        - Páginas de produtos
        - Materiais promocionais com especificações técnicas
        """)

# Rodapé
st.markdown("---")
st.caption(f"🌱 Extrator de Cultivares de Soja v1.0 | {datetime.now().strftime('%d/%m/%Y %H:%M')}")

# Instruções detalhadas
with st.sidebar:
    st.markdown("---")
    st.subheader("ℹ️ Sobre o Aplicativo")
    
    st.markdown("""
    **Funcionalidades:**
    
    ✅ **Extração automática** de dados de imagens
    ✅ **Reconhecimento** de cultivares de soja
    ✅ **Formatação** no padrão solicitado
    ✅ **Exportação** em múltiplos formatos
    
    **Tecnologia utilizada:**
    - Google Gemini Vision AI
    - Streamlit para interface
    - Processamento de imagens
    
    **Campos extraídos:**
    - Informações básicas da cultivar
    - Características fenotípicas
    - Tolerância a doenças
    - Resultados de produtividade
    - Época de semeadura
    """)
    
    # Botão para limpar dados
    if st.button("🗑️ Limpar Dados Extraídos"):
        if 'dados_extraidos' in st.session_state:
            del st.session_state.dados_extraidos
        if 'texto_bruto' in st.session_state:
            del st.session_state.texto_bruto
        st.rerun()

# Estilos CSS
st.markdown("""
<style>
    .stButton > button {
        width: 100%;
    }
    .stDownloadButton > button {
        width: 100%;
    }
    .stDataFrame {
        font-size: 0.9rem;
    }
    div[data-testid="stExpander"] div[role="button"] p {
        font-size: 1.1rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)
