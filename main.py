import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
import pandas as pd
import re
import os
import base64
from datetime import datetime
import tempfile
from pathlib import Path

# Configuração da página
st.set_page_config(
    page_title="Extrator de Informações de Cultivares de Soja",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Título do aplicativo
st.title("🌱 Extrator de Informações de Cultivares de Soja")
st.markdown("""
**Carregue múltiplas imagens com informações técnicas de cultivares de soja e o sistema extrairá e organizará os dados no formato desejado.**

O aplicativo usa o modelo Gemini Vision para análise e extração de informações.
""")

# ============================================================================
# CONFIGURAÇÃO DA API DO GEMINI
# ============================================================================
st.sidebar.header("⚙️ Configuração")

# Tentar obter API key das variáveis de ambiente
gemini_api_key_env = os.getenv("GEMINI_API_KEY") or os.getenv("GEM_API_KEY")

# Campo para API key na sidebar (com valor padrão das env vars)
gemini_api_key_input = st.sidebar.text_input(
    "API Key do Gemini",
    type="password",
    help="Insira sua API key do Google Gemini",
    value=gemini_api_key_env or "",
    key="gemini_api_key_input"
)

# Usar a API key da input ou das env vars
gemini_api_key = gemini_api_key_input if gemini_api_key_input else gemini_api_key_env

if not gemini_api_key:
    st.sidebar.warning("""
    ⚠️ API Key do Gemini não encontrada!
    
    Configure uma das seguintes variáveis de ambiente:
    1. **GEMINI_API_KEY** (preferencial)
    2. **GEM_API_KEY** (alternativa)
    
    Ou insira manualmente acima.
    """)
    
    with st.sidebar.expander("ℹ️ Como configurar", expanded=False):
        st.markdown("""
        **No terminal (Linux/Mac):**
        ```bash
        export GEMINI_API_KEY="sua-chave-aqui"
        ```
        
        **No terminal (Windows):**
        ```cmd
        set GEMINI_API_KEY="sua-chave-aqui"
        ```
        
        **No arquivo .env:**
        ```env
        GEMINI_API_KEY=sua-chave-aqui
        ```
        
        **No Streamlit Cloud:**
        - Settings → Secrets → Adicione sua chave como:
        ```toml
        GEMINI_API_KEY = "sua-chave-aqui"
        ```
        
        **Obtenha uma API key em:** https://aistudio.google.com/app/apikey
        """)
    
    modo_demo = st.sidebar.checkbox("Usar modo demonstração", value=False, 
                                    help="Mostrar dados de exemplo sem usar a API")
else:
    modo_demo = False
    try:
        genai.configure(api_key=gemini_api_key)
        modelo_vision = genai.GenerativeModel("gemini-2.0-flash")
        st.sidebar.success("✅ Gemini configurado com sucesso!")
    except Exception as e:
        st.sidebar.error(f"❌ Erro ao configurar o Gemini: {str(e)}")
        modo_demo = True

if modo_demo:
    st.sidebar.warning("⚠️ Modo demonstração ativado")
    st.info("""
    **Modo demonstração:** 
    - Você pode carregar imagens
    - Os dados serão simulados com base no nome do arquivo
    - Para extração real com IA, configure a API Key do Gemini
    """)

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def criar_dados_exemplo(nome_arquivo):
    """Cria dados de exemplo para modo demonstração"""
    
    # Extrair código do produto do nome do arquivo
    codigo_match = re.search(r'NS\d+[A-Z]*', nome_arquivo.upper())
    codigo = codigo_match.group(0) if codigo_match else "NS7524IPRO"
    
    dados_exemplo = {
        'Cultura': 'Soja',
        'Nome do produto': codigo,
        'NOME TÉCNICO/ REG': codigo,
        'Descritivo para SEO': f'{codigo} - Cultivar de soja de alto desempenho',
        'Fertilidade': 'Alto',
        'Grupo de maturação': '7.5',
        'Lançamento': 'Sim',
        'Slogan': f'Excelente performance produtiva da cultivar {codigo}',
        'Tecnologia': 'IPRO' if 'IPRO' in codigo else 'I2X',
        'Região (por extenso)': 'Sul, Sudeste, Centro-Oeste',
        'Estado (por extenso)': 'Paraná, Santa Catarina, Rio Grande do Sul, São Paulo, Mato Grosso do Sul, Goiás',
        'Ciclo': 'Precoce',
        'Finalidade': 'Grãos',
        'URL da imagem do mapa': 'https://www.niderasementes.com.br/wp-content/uploads/2025/12/mapa_soja_niderasementes-1000x1000.jpg',
        'Número do ícone 1': '1',
        'Titulo icone 1': 'Alto retorno ao investimento',
        'Descrição Icone 1': 'Altíssimo potencial produtivo; Indicada para alta tecnologia',
        'Número do ícone 2': '2',
        'Titulo icone 2': 'Facilidade do plantio à colheita',
        'Descrição Icone 2': 'Excelente estabelecimento inicial de plantas; Arquitetura de planta que facilita o manejo',
        'Número do ícone 3': '3',
        'Título icone 3': 'Estabilidade produtiva',
        'Descrição Icone 3': 'Ampla adaptação em diferentes ambientes',
        'Número do ícone 4': '4',
        'Título icone 4': 'Multi resistência',
        'Descrição Icone 4': 'Resistência a múltiplas doenças e nematoides',
        'Número do ícone 5': '5',
        'Título icone 5': 'Sanidade foliar',
        'Descrição Icone 5': 'Ótima sanidade foliar durante todo o ciclo',
        'Exigência à fertilidade': 'Médio e alto',
        'Grupo de maturidade': '7.7 M3 | 7.8 M4 | 7.8 M5',
        'PMS MÉDIO': '150G',
        'Tipo de crescimento': 'Semideterminado',
        'Cor da flor': 'Roxa',
        'Cor da pubescência': 'Marrom média',
        'Cor do hilo': 'Preto',
        'Cancro da haste': 'R',
        'Pústula bacteriana': 'MR',
        'Nematoide das galhas - M. javanica': 'R',
        'Nematóide de Cisto (Raça 3)': 'R',
        'Nematóide de Cisto (Raça 9)': 'MR',
        'Nematóide de Cisto (Raça 10)': 'MR',
        'Nematóide de Cisto (Raça 14)': 'MR',
        'Fitóftora (Raça 1)': 'MR',
        'Recomendações': 'Pode haver variação no ciclo (dias) devido às condições edafoclimáticas, época de plantio e manejo aplicado. Recomendações de população final de plantas e de época de semeadura foram construídas com base em resultados de experimentos próprios conduzidos na região e servem como direcionamento da população ideal de plantas para cada talhão. Deve-se levar em consideração: condições edafoclimáticas; textura; fertilidade do solo; adubação; nível de manejo; germinação; vigor da semente; umidade do solo entre outros fatores. Consultar recomendação de Zoneamento Agrícola de Risco Climático para a cultura de acordo com Ministério da Agricultura, Pecuária e Abastecimento.',
        'Resultado 1 - Nome': 'Fazenda Planalto',
        'Resultado 1 - Local': 'Costa Rica - MS',
        'Resultado 1': '106,0 sc/ha',
        'Resultado 2 - Nome': 'Clodemir Paholski',
        'Resultado 2 - Local': 'Cristalina - GO',
        'Resultado 2': '85,0 sc/ha',
        'Resultado 3 - Nome': 'Centro Sul Consultoria',
        'Resultado 3 - Local': 'Formosa – GO',
        'Resultado 3': '84,5 sc/ha',
        'Resultado 4 - Nome': 'Antério Mânica',
        'Resultado 4 - Local': 'Unaí - MG',
        'Resultado 4': '84,0 sc/ha',
        'Resultado 5 - Nome': 'Cislei Ribeiro dos Santos',
        'Resultado 5 - Local': 'Bonfinópolis de Minas - MG',
        'Resultado 5': '84,0 sc/ha',
        'Resultado 6 - Nome': 'Djonas Kogler',
        'Resultado 6 - Local': 'Formoso - MG',
        'Resultado 6': '81,0 sc/ha',
        'Resultado 7 - Nome': 'Cerrado Consultoria',
        'Resultado 7 - Local': 'Unaí - MG',
        'Resultado 7': '79,0 sc/ha',
        'REC': '202',
        'UF': 'RS, SC, PR, SP',
        'Região': 'Sul, Sudeste',
        'Mês 1': 'NR',
        'Mês 2': 'NR',
        'Mês 3': '180-260',
        'Mês 4': '180-260',
        'Mês 5': '180-260',
        'Mês 6': '180-260',
        'Mês 7': '180-260',
        'Mês 8': '180-260',
        'Mês 9': '180-260',
        'Mês 10': '180-260',
        'Mês 11': '180-260',
        'Mês 12': 'NR'
    }
    
    return dados_exemplo

def extrair_informacoes_imagem_real(imagem_bytes, nome_arquivo):
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
        return f"ERRO_NA_EXTRACAO: {str(e)}"

def processar_texto_extraido(texto_extraido, nome_arquivo):
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
        'Número do ícone 1': '1',
        'Titulo icone 1': 'NR',
        'Descrição Icone 1': 'NR',
        'Número do ícone 2': '2',
        'Titulo icone 2': 'NR',
        'Descrição Icone 2': 'NR',
        'Número do ícone 3': '3',
        'Título icone 3': 'NR',
        'Descrição Icone 3': 'NR',
        'Número do ícone 4': '4',
        'Título icone 4': 'NR',
        'Descrição Icone 4': 'NR',
        'Número do ícone 5': '5',
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
        'REC': 'NR',
        'UF': 'NR',
        'Região': 'NR',
        'Mês 1': 'NR',
        'Mês 2': 'NR',
        'Mês 3': 'NR',
        'Mês 4': 'NR',
        'Mês 5': 'NR',
        'Mês 6': 'NR',
        'Mês 7': 'NR',
        'Mês 8': 'NR',
        'Mês 9': 'NR',
        'Mês 10': 'NR',
        'Mês 11': 'NR',
        'Mês 12': 'NR'
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
        'PA': 'Pará',
        'SE': 'Sergipe',
        'AL': 'Alagoas',
        'PE': 'Pernambuco',
        'PB': 'Paraíba',
        'RN': 'Rio Grande do Norte',
        'CE': 'Ceará',
        'RR': 'Roraima',
        'AP': 'Amapá',
        'AM': 'Amazonas',
        'AC': 'Acre'
    }
    
    # Se houver erro na extração, retorna dados básicos
    if texto_extraido.startswith("ERRO_NA_EXTRACAO"):
        # Tentar extrair código do produto do nome do arquivo
        codigo_match = re.search(r'NS\d+[A-Z]*', nome_arquivo.upper())
        if codigo_match:
            dados['Nome do produto'] = codigo_match.group(0)
            dados['NOME TÉCNICO/ REG'] = codigo_match.group(0)
        return dados, texto_extraido
    
    # Processar cada linha do texto extraído
    linhas = texto_extraido.split('\n')
    texto_bruto = texto_extraido
    
    for linha in linhas:
        linha = linha.strip()
        
        # Nome do produto
        if linha.startswith('NOME_DO_PRODUTO:'):
            valor = linha.replace('NOME_DO_PRODUTO:', '').strip()
            dados['Nome do produto'] = valor
            dados['NOME TÉCNICO/ REG'] = valor
            dados['Descritivo para SEO'] = f'{valor} - Cultivar de soja de alto desempenho'
        
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
        
        # Tecnologia
        elif linha.startswith('TECNOLOGIA:'):
            valor = linha.replace('TECNOLOGIA:', '').strip()
            dados['Tecnologia'] = valor
        
        # Estados
        elif linha.startswith('ESTADOS:'):
            valor = linha.replace('ESTADOS:', '').strip()
            # Limpar o valor
            valor = valor.replace('Estados:', '').replace('Estado:', '').strip()
            
            # Separar estados (podem estar separados por vírgula, ponto e vírgula, ou "e")
            estados_raw = re.split(r'[,;]|\be\b', valor)
            estados = []
            for estado in estados_raw:
                estado = estado.strip()
                if estado:
                    estados.append(estado)
            
            # Converter siglas para nomes completos
            estados_completos = []
            for estado in estados:
                estado_limpo = estado.upper().replace('.', '').strip()
                if estado_limpo in estado_map:
                    estados_completos.append(estado_map[estado_limpo])
                else:
                    # Verificar se é um nome completo já
                    if estado.title() in estado_map.values():
                        estados_completos.append(estado.title())
                    else:
                        estados_completos.append(estado)
            
            dados['Estado (por extenso)'] = ', '.join(estados_completos)
            
            # Determinar região baseada nos estados
            regiao_sul = {'Paraná', 'Santa Catarina', 'Rio Grande do Sul'}
            regiao_sudeste = {'São Paulo', 'Minas Gerais', 'Espírito Santo', 'Rio de Janeiro'}
            regiao_centro_oeste = {'Mato Grosso', 'Mato Grosso do Sul', 'Goiás', 'Distrito Federal'}
            regiao_nordeste = {'Bahia', 'Maranhão', 'Piauí', 'Sergipe', 'Alagoas', 'Pernambuco', 'Paraíba', 'Rio Grande do Norte', 'Ceará'}
            regiao_norte = {'Pará', 'Rondônia', 'Tocantins', 'Roraima', 'Amapá', 'Amazonas', 'Acre'}
            
            regioes = []
            estados_set = set([e.strip() for e in estados_completos])
            
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
            
            # Determinar UF para coluna UF
            uf_list = []
            for estado in estados_completos:
                for sigla, nome in estado_map.items():
                    if nome == estado:
                        uf_list.append(sigla)
                        break
            dados['UF'] = ', '.join(uf_list) if uf_list else 'NR'
            dados['Região'] = ', '.join(regioes) if regioes else 'NR'
        
        # Benefícios
        elif linha.startswith('BENEFICIOS:'):
            valor = linha.replace('BENEFICIOS:', '').strip()
            beneficios = [b.strip() for b in valor.split(';') if b.strip()]
            
            # Distribuir benefícios nos ícones
            titulos_icones = [
                'Alto retorno ao investimento',
                'Facilidade do plantio à colheita',
                'Estabilidade produtiva',
                'Multi resistência',
                'Sanidade foliar'
            ]
            
            for i, beneficio in enumerate(beneficios[:5]):
                dados[f'Título icone {i+1}'] = titulos_icones[i] if i < len(titulos_icones) else f'Benefício {i+1}'
                dados[f'Descrição Icone {i+1}'] = beneficio
        
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
            if valor and valor != 'NR' and ';' in valor:
                resultados = [r.strip() for r in valor.split(';') if r.strip()]
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
                meses = [m.strip().lower() for m in valor.split(',') if m.strip()]
                meses_numeros = {
                    'janeiro': 1, 'fevereiro': 2, 'março': 3, 'marco': 3,
                    'abril': 4, 'maio': 5, 'junho': 6, 'julho': 7,
                    'agosto': 8, 'setembro': 9, 'outubro': 10,
                    'novembro': 11, 'dezembro': 12
                }
                
                # Preencher meses no formato correto
                for mes_nome in meses:
                    mes_chave = mes_nome.lower()
                    if mes_chave in meses_numeros:
                        num_mes = meses_numeros[mes_chave]
                        dados[f'Mês {num_mes}'] = '180-260'  # População padrão
    
    return dados, texto_bruto

def processar_imagem(imagem_bytes, nome_arquivo, idx, total):
    """Processa uma única imagem"""
    
    with st.spinner(f"Processando imagem {idx}/{total}: {nome_arquivo[:30]}..."):
        try:
            # Abrir imagem para mostrar preview
            image = Image.open(io.BytesIO(imagem_bytes))
            
            if modo_demo:
                # Modo demonstração
                dados = criar_dados_exemplo(nome_arquivo)
                texto_bruto = "Modo demonstração: dados simulados com base no nome do arquivo"
                status = "✅ (Demo)"
            else:
                # Modo real com Gemini
                texto_extraido = extrair_informacoes_imagem_real(imagem_bytes, nome_arquivo)
                dados, texto_bruto = processar_texto_extraido(texto_extraido, nome_arquivo)
                status = "✅"
            
            return {
                'nome_arquivo': nome_arquivo,
                'dados': dados,
                'texto_bruto': texto_bruto,
                'imagem': image,
                'status': status
            }
            
        except Exception as e:
            return {
                'nome_arquivo': nome_arquivo,
                'dados': criar_dados_exemplo(nome_arquivo) if modo_demo else {'Nome do produto': 'ERRO'},
                'texto_bruto': f"ERRO: {str(e)}",
                'imagem': None,
                'status': f"❌ {str(e)[:50]}"
            }

# ============================================================================
# INTERFACE PRINCIPAL
# ============================================================================

# Inicializar session state
if 'resultados_processamento' not in st.session_state:
    st.session_state.resultados_processamento = []
if 'dados_consolidados' not in st.session_state:
    st.session_state.dados_consolidados = pd.DataFrame()

# Layout principal
col1, col2 = st.columns([1, 2])

with col1:
    st.header("📤 Upload de Imagens")
    
    uploaded_files = st.file_uploader(
        "Carregue uma ou mais imagens com informações de cultivares:",
        type=["jpg", "jpeg", "png", "bmp", "webp", "gif"],
        accept_multiple_files=True,
        help="Selecione múltiplas imagens para processamento em lote"
    )
    
    if uploaded_files:
        st.success(f"✅ {len(uploaded_files)} imagem(ns) carregada(s)")
        
        # Mostrar preview das imagens
        with st.expander("👁️ Visualizar Imagens Carregadas", expanded=False):
            cols = st.columns(3)
            for idx, uploaded_file in enumerate(uploaded_files[:6]):  # Mostrar até 6 imagens
                with cols[idx % 3]:
                    try:
                        image = Image.open(uploaded_file)
                        st.image(image, caption=f"{uploaded_file.name[:20]}...", use_container_width=True)
                    except:
                        st.write(f"📄 {uploaded_file.name[:20]}...")
        
        # Configurações de processamento
        st.subheader("⚙️ Opções de Processamento")
        
        processar_todas = st.button(
            "🔍 Processar Todas as Imagens",
            type="primary",
            use_container_width=True,
            help="Extrair informações de todas as imagens carregadas"
        )
        
        limpar_dados = st.button(
            "🗑️ Limpar Dados Processados",
            type="secondary",
            use_container_width=True,
            help="Remover todos os dados processados anteriormente"
        )
        
        if limpar_dados:
            st.session_state.resultados_processamento = []
            st.session_state.dados_consolidados = pd.DataFrame()
            st.rerun()
        
        if processar_todas and uploaded_files:
            # Limpar resultados anteriores
            st.session_state.resultados_processamento = []
            
            # Processar cada imagem
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            resultados = []
            for idx, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"Processando {idx+1}/{len(uploaded_files)}: {uploaded_file.name}")
                progress_bar.progress((idx + 1) / len(uploaded_files))
                
                resultado = processar_imagem(
                    uploaded_file.getvalue(),
                    uploaded_file.name,
                    idx + 1,
                    len(uploaded_files)
                )
                resultados.append(resultado)
            
            progress_bar.empty()
            status_text.empty()
            
            # Armazenar resultados
            st.session_state.resultados_processamento = resultados
            
            # Consolidar dados em DataFrame
            if resultados:
                dados_list = [r['dados'] for r in resultados if 'dados' in r]
                if dados_list:
                    st.session_state.dados_consolidados = pd.DataFrame(dados_list)
            
            st.success(f"✅ {len(resultados)} imagem(ns) processada(s) com sucesso!")

with col2:
    st.header("📊 Resultados do Processamento")
    
    if st.session_state.resultados_processamento:
        # Resumo do processamento
        st.subheader("📋 Resumo do Processamento")
        
        col_res1, col_res2, col_res3 = st.columns(3)
        with col_res1:
            st.metric("Imagens Processadas", len(st.session_state.resultados_processamento))
        with col_res2:
            sucesso = sum(1 for r in st.session_state.resultados_processamento if '✅' in r.get('status', ''))
            st.metric("Processadas com Sucesso", sucesso)
        with col_res3:
            if modo_demo:
                st.metric("Modo", "Demonstração")
            else:
                st.metric("Modo", "IA Real")
        
        # Lista de imagens processadas
        with st.expander("📋 Detalhes por Imagem", expanded=True):
            for idx, resultado in enumerate(st.session_state.resultados_processamento):
                col_img, col_info, col_status = st.columns([2, 3, 1])
                
                with col_img:
                    if resultado.get('imagem'):
                        st.image(resultado['imagem'], 
                               caption=f"{resultado['nome_arquivo'][:30]}...", 
                               width=100)
                    else:
                        st.write("🖼️")
                
                with col_info:
                    nome_produto = resultado['dados'].get('Nome do produto', 'N/A')
                    st.write(f"**{nome_produto}**")
                    st.caption(f"Arquivo: {resultado['nome_arquivo'][:40]}")
                
                with col_status:
                    st.write(resultado['status'])
                
                # Expandir para ver detalhes
                with st.expander(f"Ver detalhes da imagem {idx+1}", expanded=False):
                    tab1, tab2 = st.tabs(["📊 Dados Extraídos", "📝 Texto Bruto"])
                    
                    with tab1:
                        df_detalhe = pd.DataFrame([resultado['dados']])
                        st.dataframe(df_detalhe.T.rename(columns={0: 'Valor'}), 
                                   use_container_width=True)
                    
                    with tab2:
                        st.text_area("Texto extraído pela IA:", 
                                   resultado['texto_bruto'], 
                                   height=200,
                                   key=f"texto_bruto_{idx}")
        
        # Dados consolidados
        if not st.session_state.dados_consolidados.empty:
            st.subheader("📦 Dados Consolidados (Todas as Imagens)")
            
            # Mostrar DataFrame consolidado
            st.dataframe(st.session_state.dados_consolidados, 
                       use_container_width=True,
                       height=400)
            
            # Estatísticas dos dados
            with st.expander("📈 Estatísticas dos Dados", expanded=False):
                col_stat1, col_stat2, col_stat3 = st.columns(3)
                with col_stat1:
                    st.metric("Cultivares Únicas", 
                            st.session_state.dados_consolidados['Nome do produto'].nunique())
                with col_stat2:
                    st.metric("Colunas", 
                            len(st.session_state.dados_consolidados.columns))
                with col_stat3:
                    st.metric("Linhas", 
                            len(st.session_state.dados_consolidados))
            
            # Opções de exportação
            st.subheader("💾 Exportar Dados")
            
            col_exp1, col_exp2, col_exp3, col_exp4 = st.columns(4)
            
            with col_exp1:
                # Download CSV
                csv_data = st.session_state.dados_consolidados.to_csv(index=False, sep=';', encoding='utf-8-sig')
                st.download_button(
                    label="📥 CSV Completo",
                    data=csv_data,
                    file_name=f"cultivares_soja_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            with col_exp2:
                # Download Excel
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    st.session_state.dados_consolidados.to_excel(writer, index=False, sheet_name='Cultivares')
                excel_data = excel_buffer.getvalue()
                
                st.download_button(
                    label="📊 Excel",
                    data=excel_data,
                    file_name=f"cultivares_soja_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            
            with col_exp3:
                # Download JSON
                json_data = st.session_state.dados_consolidados.to_json(orient='records', indent=2, force_ascii=False)
                st.download_button(
                    label="📄 JSON",
                    data=json_data,
                    file_name=f"cultivares_soja_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                    mime="application/json",
                    use_container_width=True
                )
            
            with col_exp4:
                # Download por cultivar
                cultivars_unicas = st.session_state.dados_consolidados['Nome do produto'].unique()
                cultivar_selecionada = st.selectbox(
                    "Selecionar cultivar para download individual:",
                    cultivars_unicas,
                    key="select_cultivar_download"
                )
                
                if cultivar_selecionada:
                    dados_cultivar = st.session_state.dados_consolidados[
                        st.session_state.dados_consolidados['Nome do produto'] == cultivar_selecionada
                    ]
                    csv_individual = dados_cultivar.to_csv(index=False, sep=';', encoding='utf-8-sig')
                    
                    st.download_button(
                        label=f"📋 {cultivar_selecionada}",
                        data=csv_individual,
                        file_name=f"cultivar_{cultivar_selecionada}_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
            
            # Visualização específica do formato
            st.subheader("👁️ Prévia do Formato CSV")
            
            col_format1, col_format2 = st.columns(2)
            
            with col_format1:
                st.markdown("**Colunas Principais:**")
                colunas_principais = [
                    'Cultura', 'Nome do produto', 'Fertilidade', 
                    'Grupo de maturação', 'Lançamento', 'Slogan',
                    'Tecnologia', 'Estado (por extenso)', 'Ciclo'
                ]
                df_previa = st.session_state.dados_consolidados[colunas_principais].head()
                st.dataframe(df_previa, use_container_width=True)
            
            with col_format2:
                st.markdown("**Características Fenotípicas:**")
                colunas_fenotipicas = [
                    'PMS MÉDIO', 'Tipo de crescimento', 'Cor da flor',
                    'Cor da pubescência', 'Cor do hilo'
                ]
                # Filtrar colunas que existem
                colunas_existentes = [c for c in colunas_fenotipicas if c in st.session_state.dados_consolidados.columns]
                if colunas_existentes:
                    df_fenotipo = st.session_state.dados_consolidados[colunas_existentes].head()
                    st.dataframe(df_fenotipo, use_container_width=True)
    
    else:
        # Instruções quando não há dados
        st.info("""
        **📋 Instruções para uso:**
        
        1. **Carregue imagens** → Selecione uma ou mais imagens de cultivares de soja
        2. **Configure a API** → Insira sua API Key do Gemini (ou use modo demo)
        3. **Processe** → Clique em "Processar Todas as Imagens"
        4. **Exporte** → Baixe os dados nos formatos disponíveis
        
        **🖼️ Tipos de imagens aceitas:**
        - Catálogos técnicos de cultivares
        - Fichas técnicas de produtos
        - Páginas de catálogos impressos
        - Materiais promocionais com especificações
        - Qualquer imagem contendo dados técnicos de soja
        
        **📊 Formato de saída:**
        - CSV com 76 colunas conforme especificado
        - Excel formatado
        - JSON para integração
        - Dados individuais por cultivar
        """)
        
        # Exemplo de formato de saída
        with st.expander("📋 Exemplo do Formato de Saída Completo", expanded=False):
            exemplo_dados = criar_dados_exemplo("NS7524IPRO.jpg")
            df_exemplo = pd.DataFrame([exemplo_dados])
            st.dataframe(df_exemplo.T.head(30).rename(columns={0: 'Valor Exemplo'}))

# ============================================================================
# SIDEBAR ADICIONAL
# ============================================================================

with st.sidebar:
    st.markdown("---")
    st.subheader("📚 Sobre o Aplicativo")
    
    st.markdown("""
    **Versão:** 2.0 (Multi-imagens)
    
    **Funcionalidades:**
    - ✅ Processamento em lote de múltiplas imagens
    - ✅ Extração automática com Gemini Vision AI
    - ✅ Formatação no padrão CSV de 76 colunas
    - ✅ Modo demonstração (sem API key)
    - ✅ Exportação em múltiplos formatos
    
    **Campos extraídos:**
    - Informações básicas da cultivar
    - Características fenotípicas
    - Tolerância a doenças
    - Resultados de produtividade
    - Época de semeadura por mês
    
    **Uso recomendado:**
    1. Digitalize catálogos de cultivares
    2. Tire fotos de fichas técnicas
    3. Processe em lote para eficiência
    4. Exporte para sistemas de gestão
    """)
    
    st.markdown("---")
    
    # Informações do sistema
    st.subheader("⚙️ Informações do Sistema")
    
    st.write(f"**Data/Hora:** {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    st.write(f"**Modo:** {'Demonstração' if modo_demo else 'IA Real'}")
    
    if 'dados_consolidados' in st.session_state and not st.session_state.dados_consolidados.empty:
        st.write(f"**Cultivares processadas:** {len(st.session_state.dados_consolidados)}")
        st.write(f"**Último processamento:** {len(st.session_state.resultados_processamento)} imagens")
    
    # Botão para limpar cache
    if st.button("🔄 Limpar Cache Completo", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# ============================================================================
# RODAPÉ E ESTILOS
# ============================================================================

# Rodapé
st.markdown("---")
st.caption(f"🌱 Extrator de Cultivares de Soja v2.0 | Processamento Multi-imagens | {datetime.now().strftime('%d/%m/%Y %H:%M')}")

# Estilos CSS
st.markdown("""
<style>
    /* Botões principais */
    .stButton > button {
        width: 100%;
        margin-top: 10px;
        margin-bottom: 10px;
    }
    
    /* Download buttons */
    .stDownloadButton > button {
        width: 100%;
    }
    
    /* Dataframes */
    .stDataFrame {
        font-size: 0.85rem;
    }
    
    /* Expanders */
    div[data-testid="stExpander"] div[role="button"] p {
        font-size: 1.1rem;
        font-weight: 600;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f0f2f6;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    
    /* Metric cards */
    [data-testid="stMetricValue"] {
        font-size: 1.5rem;
    }
    
    /* Sidebar */
    .css-1d391kg {
        padding-top: 2rem;
    }
    
    /* Status colors */
    .status-success {
        color: #00cc00;
        font-weight: bold;
    }
    
    .status-error {
        color: #ff3333;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Inicialização final
if __name__ == "__main__":
    # Verificação final da API key
    if not modo_demo and 'modelo_vision' not in locals():
        st.error("""
        ❌ Não foi possível inicializar o modelo Gemini.
        
        Verifique:
        1. Sua API key está correta
        2. A API key tem permissões para o Gemini Vision
        3. Sua conexão com a internet está ativa
        
        O aplicativo continuará em modo demonstração.
        """)
