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
    page_title="Extrator de Cultivares de Soja",
    page_icon="🌱",
    layout="wide"
)

# Título
st.title("Extrator de Informações de Cultivares de Soja")

# Obter API key das variáveis de ambiente
gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEM_API_KEY")

if not gemini_api_key:
    st.error("Configure as variáveis de ambiente GEMINI_API_KEY ou GEM_API_KEY")
    st.stop()

try:
    genai.configure(api_key=gemini_api_key)
    modelo_vision = genai.GenerativeModel("gemini-2.0-flash")
except Exception as e:
    st.error(f"Erro ao configurar o Gemini: {str(e)}")
    st.stop()

def extrair_informacoes_imagem(imagem_bytes, nome_arquivo):
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
    
    if texto_extraido.startswith("ERRO_NA_EXTRACAO"):
        codigo_match = re.search(r'NS\d+[A-Z]*', nome_arquivo.upper())
        if codigo_match:
            dados['Nome do produto'] = codigo_match.group(0)
            dados['NOME TÉCNICO/ REG'] = codigo_match.group(0)
        return dados, texto_extraido
    
    linhas = texto_extraido.split('\n')
    texto_bruto = texto_extraido
    
    for linha in linhas:
        linha = linha.strip()
        
        if linha.startswith('NOME_DO_PRODUTO:'):
            valor = linha.replace('NOME_DO_PRODUTO:', '').strip()
            dados['Nome do produto'] = valor
            dados['NOME TÉCNICO/ REG'] = valor
            dados['Descritivo para SEO'] = f'{valor} - Cultivar de soja de alto desempenho'
        
        elif linha.startswith('FERTILIDADE:'):
            valor = linha.replace('FERTILIDADE:', '').strip()
            dados['Fertilidade'] = valor
            dados['Exigência à fertilidade'] = valor
        
        elif linha.startswith('GRUPO_MATURACAO:'):
            valor = linha.replace('GRUPO_MATURACAO:', '').strip()
            dados['Grupo de maturação'] = valor
            dados['Grupo de maturidade'] = valor
        
        elif linha.startswith('LANCAMENTO:'):
            valor = linha.replace('LANCAMENTO:', '').strip()
            dados['Lançamento'] = 'Sim' if 'Sim' in valor else 'Não'
        
        elif linha.startswith('SLOGAN:'):
            valor = linha.replace('SLOGAN:', '').strip()
            dados['Slogan'] = valor
        
        elif linha.startswith('TECNOLOGIA:'):
            valor = linha.replace('TECNOLOGIA:', '').strip()
            dados['Tecnologia'] = valor
        
        elif linha.startswith('ESTADOS:'):
            valor = linha.replace('ESTADOS:', '').strip()
            valor = valor.replace('Estados:', '').replace('Estado:', '').strip()
            
            estados_raw = re.split(r'[,;]|\be\b', valor)
            estados = []
            for estado in estados_raw:
                estado = estado.strip()
                if estado:
                    estados.append(estado)
            
            estados_completos = []
            for estado in estados:
                estado_limpo = estado.upper().replace('.', '').strip()
                if estado_limpo in estado_map:
                    estados_completos.append(estado_map[estado_limpo])
                else:
                    if estado.title() in estado_map.values():
                        estados_completos.append(estado.title())
                    else:
                        estados_completos.append(estado)
            
            dados['Estado (por extenso)'] = ', '.join(estados_completos)
            
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
            
            uf_list = []
            for estado in estados_completos:
                for sigla, nome in estado_map.items():
                    if nome == estado:
                        uf_list.append(sigla)
                        break
            dados['UF'] = ', '.join(uf_list) if uf_list else 'NR'
            dados['Região'] = ', '.join(regioes) if regioes else 'NR'
        
        elif linha.startswith('BENEFICIOS:'):
            valor = linha.replace('BENEFICIOS:', '').strip()
            beneficios = [b.strip() for b in valor.split(';') if b.strip()]
            
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
        
        elif linha.startswith('PMS_MEDIO:'):
            valor = linha.replace('PMS_MEDIO:', '').strip()
            dados['PMS MÉDIO'] = valor
        
        elif linha.startswith('TIPO_CRESCIMENTO:'):
            valor = linha.replace('TIPO_CRESCIMENTO:', '').strip()
            dados['Tipo de crescimento'] = valor
        
        elif linha.startswith('COR_FLOR:'):
            valor = linha.replace('COR_FLOR:', '').strip()
            dados['Cor da flor'] = valor
        
        elif linha.startswith('COR_PUBESCENCIA:'):
            valor = linha.replace('COR_PUBESCENCIA:', '').strip()
            dados['Cor da pubescência'] = valor
        
        elif linha.startswith('COR_HILO:'):
            valor = linha.replace('COR_HILO:', '').strip()
            dados['Cor do hilo'] = valor
        
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
                
                for mes_nome in meses:
                    mes_chave = mes_nome.lower()
                    if mes_chave in meses_numeros:
                        num_mes = meses_numeros[mes_chave]
                        dados[f'Mês {num_mes}'] = '180-260'
    
    return dados, texto_bruto

def processar_imagem(imagem_bytes, nome_arquivo, idx, total):
    with st.spinner(f"Processando imagem {idx}/{total}: {nome_arquivo[:30]}..."):
        try:
            image = Image.open(io.BytesIO(imagem_bytes))
            
            texto_extraido = extrair_informacoes_imagem(imagem_bytes, nome_arquivo)
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
                'dados': {'Nome do produto': 'ERRO'},
                'texto_bruto': f"ERRO: {str(e)}",
                'imagem': None,
                'status': f"❌ {str(e)[:50]}"
            }

# Interface principal
if 'resultados_processamento' not in st.session_state:
    st.session_state.resultados_processamento = []
if 'dados_consolidados' not in st.session_state:
    st.session_state.dados_consolidados = pd.DataFrame()

col1, col2 = st.columns([1, 2])

with col1:
    uploaded_files = st.file_uploader(
        "Carregue uma ou mais imagens:",
        type=["jpg", "jpeg", "png", "bmp", "webp", "gif"],
        accept_multiple_files=True
    )
    
    if uploaded_files:
        st.write(f"{len(uploaded_files)} imagem(ns) carregada(s)")
        
        if st.button("Processar Todas as Imagens", type="primary"):
            st.session_state.resultados_processamento = []
            
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
            
            st.session_state.resultados_processamento = resultados
            
            if resultados:
                dados_list = [r['dados'] for r in resultados if 'dados' in r]
                if dados_list:
                    st.session_state.dados_consolidados = pd.DataFrame(dados_list)
            
            st.write(f"{len(resultados)} imagem(ns) processada(s)")

with col2:
    if st.session_state.resultados_processamento:
        col_res1, col_res2 = st.columns(2)
        with col_res1:
            st.write(f"Imagens Processadas: {len(st.session_state.resultados_processamento)}")
        with col_res2:
            sucesso = sum(1 for r in st.session_state.resultados_processamento if '✅' in r.get('status', ''))
            st.write(f"Processadas com Sucesso: {sucesso}")
        
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
                st.write(f"{nome_produto}")
                st.write(f"Arquivo: {resultado['nome_arquivo'][:40]}")
            
            with col_status:
                st.write(resultado['status'])
        
        if not st.session_state.dados_consolidados.empty:
            st.dataframe(st.session_state.dados_consolidados, 
                       use_container_width=True,
                       height=400)
            
            col_exp1, col_exp2 = st.columns(2)
            
            with col_exp1:
                csv_data = st.session_state.dados_consolidados.to_csv(index=False, sep=';', encoding='utf-8-sig')
                st.download_button(
                    label="Baixar CSV",
                    data=csv_data,
                    file_name=f"cultivares_soja_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            with col_exp2:
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    st.session_state.dados_consolidados.to_excel(writer, index=False, sheet_name='Cultivares')
                excel_data = excel_buffer.getvalue()
                
                st.download_button(
                    label="Baixar Excel",
                    data=excel_data,
                    file_name=f"cultivares_soja_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

st.write(f"Extrator de Cultivares de Soja | {datetime.now().strftime('%d/%m/%Y %H:%M')}")
