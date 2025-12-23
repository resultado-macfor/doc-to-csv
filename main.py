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
import base64

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
        except:
            # Se docx2pdf falhar, tentar extrair texto diretamente
            doc = docx.Document(tmp_docx_path)
            texto = "\n".join([para.text for para in doc.paragraphs])
            
            # Criar uma imagem com o texto
            from PIL import ImageDraw, ImageFont
            img = Image.new('RGB', (800, 1200), color='white')
            d = ImageDraw.Draw(img)
            
            try:
                font = ImageFont.truetype("arial.ttf", 14)
            except:
                font = ImageFont.load_default()
            
            # Adicionar texto à imagem
            lines = texto.split('\n')
            y = 10
            for line in lines[:50]:  # Limitar a 50 linhas
                d.text((10, y), line[:100], fill='black', font=font)
                y += 20
            
            imagens.append(img)
            
            # Limpar arquivos temporários
            os.unlink(tmp_docx_path)
            
            return imagens
        
        # Converter PDF para imagens
        try:
            poppler_path = None
            
            # Tentar encontrar poppler no sistema
            possible_paths = [
                r'C:\Program Files\poppler-23.11.0\Library\bin',
                r'C:\poppler\bin',
                '/usr/bin',
                '/usr/local/bin'
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    poppler_path = path
                    break
            
            if poppler_path:
                images_from_pdf = pdf2image.convert_from_path(
                    tmp_pdf_path, 
                    dpi=150,
                    poppler_path=poppler_path
                )
            else:
                images_from_pdf = pdf2image.convert_from_path(
                    tmp_pdf_path, 
                    dpi=150
                )
            
            imagens.extend(images_from_pdf)
            
        except Exception as e:
            st.warning(f"PDF para imagem falhou: {str(e)}")
            
            # Fallback: criar imagem de erro
            img = Image.new('RGB', (800, 200), color='white')
            from PIL import ImageDraw, ImageFont
            d = ImageDraw.Draw(img)
            
            try:
                font = ImageFont.truetype("arial.ttf", 16)
            except:
                font = ImageFont.load_default()
            
            d.text((10, 10), f"Erro na conversão: {str(e)[:50]}", fill='red', font=font)
            d.text((10, 40), f"Arquivo: {nome_arquivo}", fill='black', font=font)
            d.text((10, 70), "Processando texto extraído...", fill='black', font=font)
            
            imagens.append(img)
        
        # Limpar arquivos temporários
        os.unlink(tmp_docx_path)
        os.unlink(tmp_pdf_path)
        
        return imagens
        
    except Exception as e:
        st.error(f"Erro na conversão DOCX: {str(e)}")
        return []

# Função para transcrever informações da imagem
def transcrever_informacoes_imagem(imagem):
    """Transcreve informações de uma imagem PNG"""
    
    prompt = """
    Você é um especialista em agricultura. 
    Analise esta imagem e transcreva TODAS as informações técnicas sobre a cultivar.
    
    Esta imagem foi convertida de um documento DOCX. Transcreva TUDO que você ver, incluindo:
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
    
    IMPORTANTE: 
    1. Transcreva FIELMENTE tudo o que está escrito na imagem.
    2. Esta imagem veio de um DOCX, então pode ter formatação de tabelas.
    3. Não interprete, não resuma, apenas transcreva o texto exatamente como aparece.
    4. Se houver tabelas, transcreva-as completamente com todas as linhas e colunas.
    5. Se houver listas, transcreva todos os itens.
    6. Inclua cabeçalhos, títulos, subtítulos.
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
    """Converte texto transcrito para linha CSV"""
    
    prompt = f"""
    Você recebeu uma transcrição de informações sobre uma cultivar.
    Converta essas informações para o formato CSV especificado abaixo.

    TEXTO TRANSCRITO (página {pagina_num}):
    {texto_transcrito[:8000]}

    FORMATO CSV REQUERIDO (colunas separadas por TAB):
    Cultura	Nome do produto	NOME TÉCNICO/ REG	Descritivo para SEO	Fertilidade	Grupo de maturação	Lançamento	Slogan	Tecnologia	Região (por extenso)	Estado (por extenso)	Ciclo	Finalidade	URL da imagem do mapa	Número do ícone	Titulo icone 1	Descrição Icone 1	Número do ícone	Titulo icone 2	Descrição Icone 2	Número do ícone	Titulo icone 3	Descrição Icone 3	Número do ícone	Título icone 4	Descrição Icone 4	Número do ícone	Título icone 5	Descrição Icone 5	Exigência à fertilidade	Grupo de maturidade	PMS MÉDIO	Tipo de crescimento	Cor da flor	Cor da pubescência	Cor do hilo	Cancro da haste	Pústula bacteriana	Nematoide das galhas - M. javanica	Nematóide de Cisto (Raça 3)	Nematóide de Cisto (Raça 9)	Nematóide de Cisto (Raça 10)	Nematóide de Cisto (Raça 14)	Fitóftora (Raça 1)	Recomendações	Resultado 1 - Nome	Resultado 1 - Local	Resultado 1	Resultado 2 - Nome	Resultado 2 - Local	Resultado 2	Resultado 3 - Nome	Resultado 3 - Local	Resultado 3	Resultado 4 - Nome	Resultado 4 - Local	Resultado 4	Resultado 5 - Nome	Resultado 5 - Local	Resultado 5	Resultado 6 - Nome	Resultado 6 - Local	Resultado 6	Resultado 7 - Nome	Resultado 7 - Local	Resultado 7	REC	UF	Região	Mês 1	Mês 2	Mês 3	Mês 4	Mês 5	Mês 6	Mês 7	Mês 8	Mês 9	Mês 10	Mês 11	Mês 12

    INSTRUÇÕES DE PREENCHIMENTO:

    1. CULTURA: "Soja" ou "Milho" (extraia do texto)
    2. NOME DO PRODUTO: Extraia o nome da cultivar (ex: NS7524IPRO, NS6595I2X)
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
    22. RECOMENDAÇÕES: Use o texto padrão se não houver específico
    23. RESULTADOS: Extraia até 7 resultados de produtividade se houver
    24. REC: "NR"
    25. UF: Siglas dos estados (PR, SC, RS, etc.)
    26. REGIÃO: Mesmo que "Região (por extenso)"
    27. MESES: Para meses com semeadura recomendada, preencha com "180-260", outros "NR"

    REGRAS:
    - Use "NR" para informações não encontradas
    - Para estados: converta siglas para nomes completos
    - Para regiões: Sul (PR, SC, RS), Sudeste (SP, MG, RJ, ES), Centro-Oeste (MT, MS, GO, DF), Nordeste (BA, MA, PI, etc.), Norte (PA, RO, TO, etc.)
    - Para meses: janeiro=1, fevereiro=2, etc.
    - Mantenha valores exatos como aparecem (ex: 7.7 M3 | 7.8 M4 | 7.8 M5)
    - Se for milho, colunas específicas de soja ficam como "NR"
    - Se não conseguir extrair informações suficientes, retorne APENAS "ERRO"
    
    Forneça APENAS a linha CSV no formato especificado, sem cabeçalho, sem explicações.
    Separe os valores por TAB (\t).
    """
    
    try:
        response = modelo_texto.generate_content(prompt)
        linha_csv = response.text.strip()
        
        # Verificar se é uma linha CSV válida e não é "ERRO"
        if linha_csv != "ERRO" and '\t' in linha_csv and len(linha_csv.split('\t')) > 10:
            return linha_csv
        else:
            return ""
            
    except Exception as e:
        return ""

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
                linha_csv = converter_texto_para_csv(texto_transcrito, pagina_num)
            
            if linha_csv:
                return {
                    'pagina_num': pagina_num,
                    'imagem': imagem,
                    'texto_transcrito': texto_transcrito,
                    'linha_csv': linha_csv,
                    'status': '✅'
                }
            else:
                return {
                    'pagina_num': pagina_num,
                    'imagem': imagem,
                    'texto_transcrito': texto_transcrito,
                    'linha_csv': '',
                    'status': '❌ (Falha na conversão)'
                }
            
        except Exception as e:
            return {
                'pagina_num': pagina_num,
                'imagem': None,
                'texto_transcrito': f"ERRO: {str(e)}",
                'linha_csv': '',
                'status': f'❌ (Erro: {str(e)[:30]})'
            }

# Interface
if 'resultados' not in st.session_state:
    st.session_state.resultados = []
if 'linhas_csv' not in st.session_state:
    st.session_state.linhas_csv = []
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
            st.session_state.linhas_csv = []
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
                for idx, imagem in enumerate(imagens):
                    resultado = processar_imagem_pagina(
                        imagem,
                        idx + 1,
                        len(imagens)
                    )
                    resultados.append(resultado)
                    
                    # Adicionar linha CSV se válida
                    if resultado['linha_csv']:
                        st.session_state.linhas_csv.append(resultado['linha_csv'])
                
                st.session_state.resultados = resultados
                
                sucesso = sum(1 for r in resultados if '✅' in r['status'])
                st.write(f"Processado: {sucesso}/{len(imagens)} página(s) com sucesso")
            else:
                st.error("Falha na conversão do DOCX para imagens")

with col2:
    if st.session_state.imagens_convertidas:
        st.write(f"Páginas convertidas: {len(st.session_state.imagens_convertidas)}")
        
        # Mostrar preview das primeiras 3 páginas
        cols = st.columns(min(3, len(st.session_state.imagens_convertidas)))
        for idx, imagem in enumerate(st.session_state.imagens_convertidas[:3]):
            with cols[idx]:
                st.image(imagem, caption=f"Página {idx+1}", use_container_width=True)
    
    if st.session_state.resultados:
        # Mostrar resumo do processamento
        st.write("Resultados do processamento:")
        
        for resultado in st.session_state.resultados:
            col_status, col_info = st.columns([1, 4])
            
            with col_status:
                st.write(f"{resultado['status']}")
            
            with col_info:
                st.write(f"Página {resultado['pagina_num']}")
                
                if resultado['texto_transcrito']:
                    with st.expander(f"Ver transcrição página {resultado['pagina_num']}"):
                        st.text_area("", resultado['texto_transcrito'][:500] + "...", 
                                   height=100, key=f"transc_{resultado['pagina_num']}")
                
                if resultado['linha_csv']:
                    with st.expander(f"Ver linha CSV página {resultado['pagina_num']}"):
                        st.code(resultado['linha_csv'])
        
        # Gerar CSV completo
        if st.session_state.linhas_csv:
            # Cabeçalho das colunas
            cabecalho = """Cultura	Nome do produto	NOME TÉCNICO/ REG	Descritivo para SEO	Fertilidade	Grupo de maturação	Lançamento	Slogan	Tecnologia	Região (por extenso)	Estado (por extenso)	Ciclo	Finalidade	URL da imagem do mapa	Número do ícone	Titulo icone 1	Descrição Icone 1	Número do ícone	Titulo icone 2	Descrição Icone 2	Número do ícone	Titulo icone 3	Descrição Icone 3	Número do ícone	Título icone 4	Descrição Icone 4	Número do ícone	Título icone 5	Descrição Icone 5	Exigência à fertilidade	Grupo de maturidade	PMS MÉDIO	Tipo de crescimento	Cor da flor	Cor da pubescência	Cor do hilo	Cancro da haste	Pústula bacteriana	Nematoide das galhas - M. javanica	Nematóide de Cisto (Raça 3)	Nematóide de Cisto (Raça 9)	Nematóide de Cisto (Raça 10)	Nematóide de Cisto (Raça 14)	Fitóftora (Raça 1)	Recomendações	Resultado 1 - Nome	Resultado 1 - Local	Resultado 1	Resultado 2 - Nome	Resultado 2 - Local	Resultado 2	Resultado 3 - Nome	Resultado 3 - Local	Resultado 3	Resultado 4 - Nome	Resultado 4 - Local	Resultado 4	Resultado 5 - Nome	Resultado 5 - Local	Resultado 5	Resultado 6 - Nome	Resultado 6 - Local	Resultado 6	Resultado 7 - Nome	Resultado 7 - Local	Resultado 7	REC	UF	Região	Mês 1	Mês 2	Mês 3	Mês 4	Mês 5	Mês 6	Mês 7	Mês 8	Mês 9	Mês 10	Mês 11	Mês 12"""
            
            # Criar conteúdo CSV
            conteudo_csv = cabecalho + "\n" + "\n".join(st.session_state.linhas_csv)
            
            # Converter para DataFrame para visualização
            linhas = [cabecalho.split('\t')] + [linha.split('\t') for linha in st.session_state.linhas_csv if linha]
            df = pd.DataFrame(linhas[1:], columns=linhas[0])
            
            st.write("CSV Gerado:")
            st.dataframe(df, use_container_width=True, height=400)
            
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
