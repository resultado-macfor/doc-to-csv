import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
import pandas as pd
import os
from datetime import datetime
import time
import tempfile
from pathlib import Path
import docx
from docx2pdf import convert
import pdf2image

# Configuração da página
st.set_page_config(
    page_title="Extrator de Cultivares de DOCX",
    page_icon="🌱",
    layout="wide"
)

# Título
st.title("Extrator de Informações de Cultivares - DOCX para CSV")

# Obter API key das variáveis de ambiente
gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEM_API_KEY")

if not gemini_api_key:
    st.error("Configure as variáveis de ambiente GEMINI_API_KEY ou GEM_API_KEY")
    st.stop()

try:
    genai.configure(api_key=gemini_api_key)
    modelo_vision = genai.GenerativeModel("gemini-2.0-flash")
    modelo_texto = genai.GenerativeModel("gemini-2.0-flash")
except Exception as e:
    st.error(f"Erro ao configurar o Gemini: {str(e)}")
    st.stop()

# Função para converter DOCX para imagens
def converter_docx_para_imagens(docx_bytes, nome_arquivo):
    """Converte um arquivo DOCX para uma lista de imagens PNG"""
    
    imagens = []
    
    try:
        # Criar arquivo temporário DOCX
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp_docx:
            tmp_docx.write(docx_bytes)
            tmp_docx_path = tmp_docx.name
        
        # Converter DOCX para PDF
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_pdf:
            tmp_pdf_path = tmp_pdf.name
        
        try:
            convert(tmp_docx_path, tmp_pdf_path)
            
            # Converter PDF para imagens
            try:
                images_from_pdf = pdf2image.convert_from_path(
                    tmp_pdf_path, 
                    dpi=150
                )
                imagens.extend(images_from_pdf)
                
            except Exception as e:
                # Fallback: tentar sem poppler
                images_from_pdf = pdf2image.convert_from_bytes(
                    open(tmp_pdf_path, 'rb').read(),
                    dpi=150
                )
                imagens.extend(images_from_pdf)
                
        except Exception as e:
            # Se docx2pdf falhar, extrair texto diretamente do DOCX
            doc = docx.Document(tmp_docx_path)
            
            # Para cada parágrafo com texto, criar uma imagem
            texto_paginas = []
            pagina_atual = ""
            
            for para in doc.paragraphs:
                if para.text.strip():
                    pagina_atual += para.text + "\n"
                    
                    # Se a página ficar muito grande, dividir
                    if len(pagina_atual) > 1000:
                        texto_paginas.append(pagina_atual)
                        pagina_atual = ""
            
            if pagina_atual:
                texto_paginas.append(pagina_atual)
            
            # Converter texto para imagens
            for texto in texto_paginas:
                from PIL import ImageDraw, ImageFont
                img = Image.new('RGB', (1200, 1600), color='white')
                d = ImageDraw.Draw(img)
                
                try:
                    font = ImageFont.truetype("arial.ttf", 16)
                except:
                    font = ImageFont.load_default()
                
                # Adicionar texto à imagem
                lines = texto.split('\n')
                y = 50
                for line in lines:
                    if y < 1550:  # Limitar ao tamanho da página
                        d.text((50, y), line[:150], fill='black', font=font)
                        y += 30
                
                imagens.append(img)
        
        # Limpar arquivos temporários
        try:
            os.unlink(tmp_docx_path)
            if os.path.exists(tmp_pdf_path):
                os.unlink(tmp_pdf_path)
        except:
            pass
        
        return imagens
        
    except Exception as e:
        st.error(f"Erro na conversão DOCX: {str(e)}")
        return []

# Função para transcrever informações da imagem
def transcrever_informacoes_imagem(imagem):
    """Transcreve informações de uma imagem PNG"""
    
    prompt = """
    Você é um especialista em agricultura. 
    Analise esta imagem e transcreva TODAS as informações técnicas sobre cultivares.
    
    Esta imagem foi convertida de um documento DOCX. Transcreva TUDO que você ver, incluindo:
    
    PARA CADA CULTIVAR/SEÇÃO DO DOCUMENTO:
    - Cultura (Soja, Milho, ou outra)
    - Nome do produto/cultivar
    - Exigência à fertilidade
    - Grupo de maturação
    - Se é lançamento ou não
    - Slogan ou descrição principal
    - Tecnologia utilizada
    - Estados recomendados
    - Benefícios e características
    - PMS (Peso de Mil Sementes) - se for soja
    - Tipo de crescimento - se for soja
    - Cor da flor, pubescência e hilo - se for soja
    - Tolerância a doenças (tabela completa)
    - Resultados de produtividade
    - Época de semeadura
    - Mapas de recomendação
    - Qualquer outro texto ou informação presente
    
    OBSERVAÇÃO: Este documento pode conter MÚLTIPLAS cultivares em uma única página.
    Se houver mais de uma cultivar na página, transcreva TODAS elas.
    
    IMPORTANTE: 
    1. Transcreva FIELMENTE tudo o que está escrito na imagem.
    2. Esta imagem veio de um DOCX, então pode ter formatação de tabelas.
    3. Não interprete, não resuma, apenas transcreva o texto exatamente como aparece.
    4. Se houver tabelas, transcreva-as completamente com todas as linhas e colunas.
    5. Se houver listas, transcreva todos os itens.
    6. Inclua cabeçalhos, títulos, subtítulos.
    7. Se houver múltiplas cultivares na mesma página, separe-as claramente.
    """
    
    try:
        # Converter imagem para bytes
        img_byte_arr = io.BytesIO()
        imagem.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        
        response = modelo_vision.generate_content([
            prompt,
            {"mime_type": "image/png", "data": img_byte_arr}
        ])
        
        return response.text
    except Exception as e:
        return f"ERRO_NA_TRANSCRICAO: {str(e)}"

# Função para converter texto em CSV no formato especificado
def converter_texto_para_csv(texto_transcrito, pagina_num):
    """Converte texto transcrito para linha(s) CSV"""
    
    prompt = f"""
    Você recebeu uma transcrição de informações sobre cultivares de uma página de documento.
    Converta essas informações para o formato CSV especificado abaixo.

    TEXTO TRANSCRITO (página {pagina_num}):
    {texto_transcrito[:8000]}

    FORMATO CSV REQUERIDO (colunas separadas por TAB - \t):
    Cultura	Nome do produto	NOME TÉCNICO/ REG	Descritivo para SEO	Fertilidade	Grupo de maturação	Lançamento	Slogan	Tecnologia	Região (por extenso)	Estado (por extenso)	Ciclo	Finalidade	URL da imagem do mapa	Número do ícone	Titulo icone 1	Descrição Icone 1	Número do ícone	Titulo icone 2	Descrição Icone 2	Número do ícone	Titulo icone 3	Descrição Icone 3	Número do ícone	Título icone 4	Descrição Icone 4	Número do ícone	Título icone 5	Descrição Icone 5	Exigência à fertilidade	Grupo de maturidade	PMS MÉDIO	Tipo de crescimento	Cor da flor	Cor da pubescência	Cor do hilo	Cancro da haste	Pústula bacteriana	Nematoide das galhas - M. javanica	Nematóide de Cisto (Raça 3)	Nematóide de Cisto (Raça 9)	Nematóide de Cisto (Raça 10)	Nematóide de Cisto (Raça 14)	Fitóftora (Raça 1)	Recomendações	Resultado 1 - Nome	Resultado 1 - Local	Resultado 1	Resultado 2 - Nome	Resultado 2 - Local	Resultado 2	Resultado 3 - Nome	Resultado 3 - Local	Resultado 3	Resultado 4 - Nome	Resultado 4 - Local	Resultado 4	Resultado 5 - Nome	Resultado 5 - Local	Resultado 5	Resultado 6 - Nome	Resultado 6 - Local	Resultado 6	Resultado 7 - Nome	Resultado 7 - Local	Resultado 7	REC	UF	Região	Mês 1	Mês 2	Mês 3	Mês 4	Mês 5	Mês 6	Mês 7	Mês 8	Mês 9	Mês 10	Mês 11	Mês 12

    INSTRUÇÕES CRÍTICAS:

    1. Esta página pode conter MÚLTIPLAS cultivares. Se houver mais de uma, gere UMA LINHA CSV PARA CADA CULTIVAR.
    2. Se houver 3 cultivares na página, gere 3 linhas CSV separadas por nova linha.
    3. Para cada cultivar, preencha as colunas baseado nas informações específicas dela.

    DETALHES DE PREENCHIMENTO POR COLUNA:
    1. CULTURA: "Soja" ou "Milho" (extraia do texto) - OBRIGATÓRIO
    2. NOME DO PRODUTO: Extraia o nome da cultivar (ex: NS7524IPRO, NS6595I2X) - OBRIGATÓRIO
    3. NOME TÉCNICO/REG: Mesmo que nome do produto
    4. DESCRITIVO PARA SEO: Crie uma descrição breve para SEO baseada nas informações
    5. FERTILIDADE: Alto, Médio ou Baixo (extraia do texto)
    6. GRUPO DE MATURAÇÃO: Número (ex: 7.5, 6.5) - se for soja
    7. LANÇAMENTO: "Sim" ou "Não" (procure por palavras como "lançamento", "nova")
    8. SLOGAN: Frase principal de marketing
    9. TECNOLOGIA: IPRO, I2X, ou outra mencionada
    10. REGIÃO (POR EXTENSO): Sul, Sudeste, Centro-Oeste, Nordeste, Norte (baseado nos estados)
    11. ESTADO (POR EXTENSO): Nomes completos dos estados recomendados
    12. CICLO: Precoce, Médio, Tardio (ou estimativa baseada no grupo de maturação)
    13. FINALIDADE: "Grãos"
    14. URL DA IMAGEM DO MAPA: "NR"
    15. ÍCONES 1-5: Extraia os principais benefícios do texto
    16. EXIGÊNCIA À FERTILIDADE: Mesmo que "Fertilidade"
    17. GRUPO DE MATURIDADE: Mesmo que "Grupo de maturação"
    18. PMS MÉDIO: Extraia o peso de mil sementes (ex: 150G, 165g) - se for soja, senão "NR"
    19. TIPO DE CRESCIMENTO: Indeterminado, Semideterminado, Determinado - se for soja, senão "NR"
    20. CORES: Flor, pubescência, hilo - se for soja, senão "NR"
    21. DOENÇAS: S (Suscetível), MS (Mod. Suscetível), MR (Mod. Resistente), R (Resistente), X (Resistente) - se for soja, senão "NR"
    22. RECOMENDAÇÕES: "Pode haver variação no ciclo (dias) devido às condições edafoclimáticas, época de plantio e manejo aplicado. Recomendações de população final de plantas e de época de semeadura foram construídas com base em resultados de experimentos próprios conduzidos na região e servem como direcionamento da população ideal de plantas para cada talhão. Deve-se levar em consideração: condições edafoclimáticas; textura; fertilidade do solo; adubação; nível de manejo; germinação; vigor da semente; umidade do solo entre outros fatores. Consultar recomendação de Zoneamento Agrícola de Risco Climático para a cultura de acordo com Ministério da Agricultura, Pecuária e Abastecimento."
    23. RESULTADOS: Extraia até 7 resultados de produtividade se houver
    24. REC: "NR"
    25. UF: Siglas dos estados (PR, SC, RS, etc.)
    26. REGIÃO: Mesmo que "Região (por extenso)"
    27. MESES: Para meses com semeadura recomendada, preencha com "180-260", outros "NR"

    REGRAS IMPORTANTES:
    - Use "NR" para informações não encontradas
    - Para estados: converta siglas para nomes completos
    - Para regiões: Sul (PR, SC, RS), Sudeste (SP, MG, RJ, ES), Centro-Oeste (MT, MS, GO, DF), Nordeste (BA, MA, PI, etc.), Norte (PA, RO, TO, etc.)
    - Para meses: janeiro=1, fevereiro=2, etc.
    - Mantenha valores exatos como aparecem (ex: 7.7 M3 | 7.8 M4 | 7.8 M5)
    - Se for milho, colunas específicas de soja ficam como "NR"
    - Se a página não tiver informações de cultivares, retorne "SEM_CULTIVAR"
    - Se encontrar múltiplas cultivares, retorne UMA LINHA POR CULTIVAR
    
    Forneça APENAS as linhas CSV no formato especificado, sem cabeçalho, sem explicações.
    Separe os valores por TAB (\t).
    Separe diferentes cultivares por NOVA LINHA (\n).
    Exemplo de saída para 2 cultivares:
    Soja	NS6595I2X	NS6595I2X	NS6595I2X - Cultivar de soja	Alto	6.5	Sim	O caminho da alta produtividade tem nome	I2X	Sul, Sudeste	Paraná, Mato Grosso do Sul, São Paulo	Precoce	Grãos	NR	1	Alto retorno ao investimento	Altíssimo potencial produtivo; Indicada para alta tecnologia	2	Facilidade do plantio à colheita	Excelente estabelecimento inicial de plantas; Arquitetura de planta que facilita o manejo	3	NR	NR	4	NR	NR	5	NR	NR	Alto	6.5	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR
    Soja	NS7524IPRO	NS7524IPRO	NS7524IPRO - Cultivar de soja	Alto	7.5	Sim	Excelente performance produtiva com múltipla resistência a nematoides de cisto	IPRO	Sul, Sudeste	Paraná, Santa Catarina	Precoce	Grãos	NR	1	Alto retorno ao investimento	Altíssimo potencial produtivo; Indicada para alta tecnologia	2	Facilidade do plantio à colheita	Excelente estabelecimento inicial de plantas; Arquitetura de planta que facilita o manejo	3	NR	NR	4	NR	NR	5	NR	NR	Médio e alto	7.7 M3 | 7.8 M4 | 7.8 M5	150G	Semideterminado	Roxa	Marrom média	Preto	R	MR	R	R	MR	MR	MR	MR	Pode haver variação no ciclo (dias) devido às condições edafoclimáticas, época de plantio e manejo aplicado. Recomendações de população final de plantas e de época de semeadura foram construídas com base em resultados de experimentos próprios conduzidos na região e servem como direcionamento da população ideal de plantas para cada talhão. Deve-se levar em consideração: condições edafoclimáticas; textura; fertilidade do solo; adubação; nível de manejo; germinação; vigor da semente; umidade do solo entre outros fatores. Consultar recomendação de Zoneamento Agrícola de Risco Climático para a cultura de acordo com Ministério da Agricultura, Pecuária e Abastecimento.	Fazenda Planalto	Costa Rica - MS	106,0 sc/ha	Clodemir Paholski	Cristalina - GO	85,0 sc/ha	Centro Sul Consultoria	Formosa – GO	84,5 sc/ha	Antério Mânica	Unaí - MG	84,0 sc/ha	Cislei Ribeiro dos Santos	Bonfinópolis de Minas - MG	84,0 sc/ha	Djonas Kogler	Formoso - MG	81,0 sc/ha	Cerrado Consultoria	Unaí - MG	79,0 sc/ha	NR	PR, SC, RS, SP	Sul, Sudeste	NR	NR	180-260	180-260	180-260	180-260	180-260	180-260	180-260	180-260	180-260	NR
    """
    
    try:
        response = modelo_texto.generate_content(prompt)
        resultado = response.text.strip()
        
        if resultado == "SEM_CULTIVAR":
            return []
        
        # Separar em linhas (cada linha é uma cultivar)
        linhas = [linha.strip() for linha in resultado.split('\n') if linha.strip()]
        
        linhas_validas = []
        for linha in linhas:
            # Verificar se é uma linha CSV válida
            if '\t' in linha and len(linha.split('\t')) >= 10:
                linhas_validas.append(linha)
        
        return linhas_validas
            
    except Exception as e:
        return []

# Processar uma imagem (página do DOCX)
def processar_imagem_pagina(imagem, pagina_num, total_paginas):
    """Processa uma imagem (página convertida do DOCX)"""
    
    with st.spinner(f"Transcrevendo página {pagina_num}/{total_paginas}..."):
        try:
            # Passo 1: Transcrever informações da imagem
            texto_transcrito = transcrever_informacoes_imagem(imagem)
            
            # Passo 2: Converter texto para CSV
            with st.spinner(f"Convertendo página {pagina_num}/{total_paginas} para CSV..."):
                time.sleep(1)
                linhas_csv = converter_texto_para_csv(texto_transcrito, pagina_num)
            
            if linhas_csv:
                return {
                    'pagina_num': pagina_num,
                    'imagem': imagem,
                    'texto_transcrito': texto_transcrito,
                    'linhas_csv': linhas_csv,
                    'status': f'✅ {len(linhas_csv)} cultivar(s)'
                }
            else:
                return {
                    'pagina_num': pagina_num,
                    'imagem': imagem,
                    'texto_transcrito': texto_transcrito,
                    'linhas_csv': [],
                    'status': '⚠️ Nenhuma cultivar encontrada'
                }
            
        except Exception as e:
            return {
                'pagina_num': pagina_num,
                'imagem': None,
                'texto_transcrito': f"ERRO: {str(e)}",
                'linhas_csv': [],
                'status': f'❌ Erro: {str(e)[:30]}'
            }

# Interface
if 'resultados' not in st.session_state:
    st.session_state.resultados = []
if 'todas_linhas_csv' not in st.session_state:
    st.session_state.todas_linhas_csv = []
if 'imagens_convertidas' not in st.session_state:
    st.session_state.imagens_convertidas = []

col1, col2 = st.columns([1, 2])

with col1:
    uploaded_file = st.file_uploader(
        "Carregue um arquivo DOCX:",
        type=["docx"],
        accept_multiple_files=False
    )
    
    if uploaded_file:
        st.write(f"Arquivo: {uploaded_file.name}")
        st.write(f"Tamanho: {uploaded_file.size / 1024:.1f} KB")
        
        if st.button("Processar DOCX", type="primary"):
            st.session_state.resultados = []
            st.session_state.todas_linhas_csv = []
            st.session_state.imagens_convertidas = []
            
            # Converter DOCX para imagens
            with st.spinner("Convertendo DOCX para imagens..."):
                docx_bytes = uploaded_file.getvalue()
                imagens = converter_docx_para_imagens(docx_bytes, uploaded_file.name)
                st.session_state.imagens_convertidas = imagens
            
            if imagens:
                st.write(f"Documento convertido em {len(imagens)} página(s)")
                
                # Processar cada imagem (página)
                resultados = []
                total_cultivares = 0
                
                for idx, imagem in enumerate(imagens):
                    resultado = processar_imagem_pagina(
                        imagem,
                        idx + 1,
                        len(imagens)
                    )
                    resultados.append(resultado)
                    
                    # Adicionar linhas CSV se válidas
                    if resultado['linhas_csv']:
                        st.session_state.todas_linhas_csv.extend(resultado['linhas_csv'])
                        total_cultivares += len(resultado['linhas_csv'])
                
                st.session_state.resultados = resultados
                
                st.write(f"Processado: {total_cultivares} cultivar(s) encontrada(s)")
            else:
                st.error("Falha na conversão do DOCX para imagens")

with col2:
    if st.session_state.imagens_convertidas:
        st.write(f"Páginas convertidas: {len(st.session_state.imagens_convertidas)}")
    
    if st.session_state.resultados:
        # Mostrar resumo do processamento
        st.write("Resultados do processamento por página:")
        
        for resultado in st.session_state.resultados:
            with st.expander(f"Página {resultado['pagina_num']} - {resultado['status']}", expanded=False):
                col_img, col_text = st.columns([1, 2])
                
                with col_img:
                    if resultado.get('imagem'):
                        st.image(resultado['imagem'], use_container_width=True)
                
                with col_text:
                    if resultado['texto_transcrito']:
                        st.text_area("Transcrição:", 
                                   resultado['texto_transcrito'][:1000] + ("..." if len(resultado['texto_transcrito']) > 1000 else ""), 
                                   height=200, 
                                   key=f"transc_{resultado['pagina_num']}")
                    
                    if resultado['linhas_csv']:
                        st.write(f"Encontradas {len(resultado['linhas_csv'])} cultivar(s):")
                        for i, linha in enumerate(resultado['linhas_csv']):
                            with st.expander(f"Cultivar {i+1}", expanded=False):
                                partes = linha.split('\t')
                                if len(partes) > 1:
                                    st.write(f"Nome: {partes[1]}")
                                    st.write(f"Cultura: {partes[0]}")
                                    st.code(linha)
        
        # Gerar CSV completo
        if st.session_state.todas_linhas_csv:
            # Cabeçalho das colunas
            cabecalho = """Cultura	Nome do produto	NOME TÉCNICO/ REG	Descritivo para SEO	Fertilidade	Grupo de maturação	Lançamento	Slogan	Tecnologia	Região (por extenso)	Estado (por extenso)	Ciclo	Finalidade	URL da imagem do mapa	Número do ícone	Titulo icone 1	Descrição Icone 1	Número do ícone	Titulo icone 2	Descrição Icone 2	Número do ícone	Titulo icone 3	Descrição Icone 3	Número do ícone	Título icone 4	Descrição Icone 4	Número do ícone	Título icone 5	Descrição Icone 5	Exigência à fertilidade	Grupo de maturidade	PMS MÉDIO	Tipo de crescimento	Cor da flor	Cor da pubescência	Cor do hilo	Cancro da haste	Pústula bacteriana	Nematoide das galhas - M. javanica	Nematóide de Cisto (Raça 3)	Nematóide de Cisto (Raça 9)	Nematóide de Cisto (Raça 10)	Nematóide de Cisto (Raça 14)	Fitóftora (Raça 1)	Recomendações	Resultado 1 - Nome	Resultado 1 - Local	Resultado 1	Resultado 2 - Nome	Resultado 2 - Local	Resultado 2	Resultado 3 - Nome	Resultado 3 - Local	Resultado 3	Resultado 4 - Nome	Resultado 4 - Local	Resultado 4	Resultado 5 - Nome	Resultado 5 - Local	Resultado 5	Resultado 6 - Nome	Resultado 6 - Local	Resultado 6	Resultado 7 - Nome	Resultado 7 - Local	Resultado 7	REC	UF	Região	Mês 1	Mês 2	Mês 3	Mês 4	Mês 5	Mês 6	Mês 7	Mês 8	Mês 9	Mês 10	Mês 11	Mês 12"""
            
            # Criar conteúdo CSV
            conteudo_csv = cabecalho + "\n" + "\n".join(st.session_state.todas_linhas_csv)
            
            # Criar DataFrame corretamente
            todas_linhas = []
            
            # Processar cada linha CSV
            for linha in st.session_state.todas_linhas_csv:
                partes = linha.split('\t')
                # Garantir que temos 76 colunas (preencher com "NR" se faltar)
                while len(partes) < 76:
                    partes.append("NR")
                todas_linhas.append(partes[:76])  # Pegar apenas as primeiras 76 colunas
            
            # Cabeçalho com 76 colunas
            cabecalho_partes = cabecalho.split('\t')
            
            # Criar DataFrame
            if todas_linhas:
                df = pd.DataFrame(todas_linhas, columns=cabecalho_partes)
                
                st.write(f"CSV Gerado: {len(todas_linhas)} cultivar(s)")
                st.dataframe(df[['Cultura', 'Nome do produto', 'Fertilidade', 'Grupo de maturação', 'Lançamento', 'Estado (por extenso)']], 
                           use_container_width=True, height=400)
                
                # Botões de download
                col_dl1, col_dl2 = st.columns(2)
                
                with col_dl1:
                    st.download_button(
                        label="Baixar CSV",
                        data=conteudo_csv,
                        file_name=f"cultivares_{uploaded_file.name.split('.')[0]}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                
                with col_dl2:
                    excel_buffer = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Cultivares')
                    excel_data = excel_buffer.getvalue()
                    
                    st.download_button(
                        label="Baixar Excel",
                        data=excel_data,
                        file_name=f"cultivares_{uploaded_file.name.split('.')[0]}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
            else:
                st.warning("Nenhuma linha CSV válida foi gerada.")
