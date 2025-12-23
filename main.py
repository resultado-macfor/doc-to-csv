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
    modelo_vision = genai.GenerativeModel("gemini-1.5-flash")  # Melhor para visão
    modelo_texto = genai.GenerativeModel("gemini-1.5-flash")
except Exception as e:
    st.error(f"Erro ao configurar o Gemini: {str(e)}")
    st.stop()

# Função para converter DOCX para imagens
def converter_docx_para_imagens(docx_bytes, nome_arquivo):
    """Converte um arquivo DOCX para uma lista de imagens PNG (uma por página)"""
    
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
                    dpi=150,
                    fmt='PNG'
                )
                imagens.extend(images_from_pdf)
                
            except Exception as e:
                st.warning(f"Erro com poppler: {str(e)}. Tentando método alternativo...")
                # Fallback: tentar sem poppler
                try:
                    images_from_pdf = pdf2image.convert_from_bytes(
                        open(tmp_pdf_path, 'rb').read(),
                        dpi=150,
                        fmt='PNG'
                    )
                    imagens.extend(images_from_pdf)
                except Exception as e2:
                    st.error(f"Erro na conversão PDF para imagens: {str(e2)}")
                    # Tentar extrair texto diretamente do DOCX
                    doc = docx.Document(tmp_docx_path)
                    texto_completo = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
                    
                    # Criar imagem com o texto
                    from PIL import ImageDraw, ImageFont
                    img = Image.new('RGB', (1200, 1600), color='white')
                    d = ImageDraw.Draw(img)
                    
                    try:
                        font = ImageFont.truetype("arial.ttf", 16)
                    except:
                        font = ImageFont.load_default()
                    
                    # Adicionar texto à imagem
                    lines = texto_completo.split('\n')
                    y = 50
                    for line in lines:
                        if y < 1550:
                            d.text((50, y), line[:150], fill='black', font=font)
                            y += 30
                    
                    imagens.append(img)
                
        except Exception as e:
            st.warning(f"Erro na conversão DOCX para PDF: {str(e)}")
            # Se docx2pdf falhar, extrair texto diretamente do DOCX
            doc = docx.Document(tmp_docx_path)
            texto_completo = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
            
            # Criar imagem com o texto
            from PIL import ImageDraw, ImageFont
            img = Image.new('RGB', (1200, 1600), color='white')
            d = ImageDraw.Draw(img)
            
            try:
                font = ImageFont.truetype("arial.ttf", 16)
            except:
                font = ImageFont.load_default()
            
            # Adicionar texto à imagem
            lines = texto_completo.split('\n')
            y = 50
            for line in lines:
                if y < 1550:
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

# Função para transcrever TODAS as imagens (páginas) em texto
def transcrever_todas_paginas(imagens):
    """Transcreve todas as imagens/páginas em texto usando modelo de visão"""
    
    texto_completo = ""
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, imagem in enumerate(imagens):
        pagina_num = i + 1
        total_paginas = len(imagens)
        
        status_text.text(f"Transcrevendo página {pagina_num}/{total_paginas}...")
        progress_bar.progress(pagina_num / total_paginas)
        
        prompt = """
        Você é um especialista em agricultura. 
        Analise esta imagem e transcreva COMPLETAMENTE todo o texto que você vê.
        
        Esta imagem foi convertida de um documento DOCX técnico sobre cultivares de soja ou milho.
        
        TRANSCREVA FIELMENTE:
        - Todo o texto visível
        - Tabelas completas (com todas as linhas e colunas)
        - Listas e itens
        - Cabeçalhos e títulos
        - Dados técnicos
        - Números e especificações
        - Estados recomendados
        - Grupos de maturação
        - Características das cultivares
        
        IMPORTANTE:
        1. Transcreva EXATAMENTE como aparece, sem interpretar
        2. Mantenha a formatação de tabelas quando possível
        3. Se houver múltiplas cultivares na mesma página, transcreva todas
        4. Não resuma, não omita informações
        5. Inclua tudo: desde o título até as notas de rodapé
        
        Formate o texto de maneira organizada, mas mantenha o conteúdo original.
        """
        
        try:
            # Converter imagem para bytes
            img_byte_arr = io.BytesIO()
            imagem.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()
            
            # Enviar para o modelo de visão
            response = modelo_vision.generate_content([
                prompt,
                {"mime_type": "image/png", "data": img_byte_arr}
            ])
            
            texto_pagina = f"\n\n{'='*60}\nPÁGINA {pagina_num}\n{'='*60}\n\n{response.text}"
            texto_completo += texto_pagina
            
            # Pequena pausa para não sobrecarregar a API
            time.sleep(1)
            
        except Exception as e:
            texto_erro = f"\n\n{'='*60}\nERRO na página {pagina_num}: {str(e)}\n{'='*60}\n"
            texto_completo += texto_erro
    
    progress_bar.empty()
    status_text.empty()
    
    return texto_completo

# Função para converter texto transcrito em CSV
def converter_texto_para_csv_completo(texto_transcrito):
    """Converte todo o texto transcrito em CSV com todas as colunas"""
    
    prompt = f"""
    Você recebeu a transcrição COMPLETA de um documento DOCX sobre cultivares de soja e milho.
    O documento foi convertido para imagens e transcrito página por página.
    
    TEXTO TRANSCRITO COMPLETO (todas as páginas):
    {texto_transcrito[:15000]}  # Limitar para caber no contexto
    
    SUA TAREFA:
    Analise TODO o texto acima e extraia informações sobre TODAS as cultivares mencionadas.
    Para CADA cultivar encontrada, crie UMA LINHA no formato CSV abaixo.
    
    FORMATO CSV REQUERIDO (colunas separadas por TAB - \t):
    Cultura	Nome do produto	NOME TÉCNICO/ REG	Descritivo para SEO	Fertilidade	Grupo de maturação	Lançamento	Slogan	Tecnologia	Região (por extenso)	Estado (por extenso)	Ciclo	Finalidade	URL da imagem do mapa	Número do ícone	Titulo icone 1	Descrição Icone 1	Número do ícone	Titulo icone 2	Descrição Icone 2	Número do ícone	Titulo icone 3	Descrição Icone 3	Número do ícone	Título icone 4	Descrição Icone 4	Número do ícone	Título icone 5	Descrição Icone 5	Exigência à fertilidade	Grupo de maturidade	PMS MÉDIO	Tipo de crescimento	Cor da flor	Cor da pubescência	Cor do hilo	Cancro da haste	Pústula bacteriana	Nematoide das galhas - M. javanica	Nematóide de Cisto (Raça 3)	Nematóide de Cisto (Raça 9)	Nematóide de Cisto (Raça 10)	Nematóide de Cisto (Raça 14)	Fitóftora (Raça 1)	Recomendações	Resultado 1 - Nome	Resultado 1 - Local	Resultado 1	Resultado 2 - Nome	Resultado 2 - Local	Resultado 2	Resultado 3 - Nome	Resultado 3 - Local	Resultado 3	Resultado 4 - Nome	Resultado 4 - Local	Resultado 4	Resultado 5 - Nome	Resultado 5 - Local	Resultado 5	Resultado 6 - Nome	Resultado 6 - Local	Resultado 6	Resultado 7 - Nome	Resultado 7 - Local	Resultado 7	REC	UF	Região	Mês 1	Mês 2	Mês 3	Mês 4	Mês 5	Mês 6	Mês 7	Mês 8	Mês 9	Mês 10	Mês 11	Mês 12

    INSTRUÇÕES DETALHADAS:
    
    1. IDENTIFICAÇÃO DAS CULTIVARES:
       - Procure por nomes de cultivares como NS7524IPRO, NS6595I2X, etc.
       - Cada cultivar DISTINTA deve ter sua própria linha
       - O documento pode ter dezenas de cultivares - extraia TODAS
    
    2. PREENCHIMENTO DAS COLUNAS:
    
    A. INFORMAÇÕES BÁSICAS:
       - Cultura: "Soja" ou "Milho" (inferir do contexto)
       - Nome do produto: Nome completo da cultivar (ex: NS7524IPRO)
       - NOME TÉCNICO/REG: Mesmo que nome do produto
       - Descritivo para SEO: Crie uma descrição de 10-15 palavras
       - Fertilidade: Alto, Médio ou Baixo
       - Grupo de maturação: Número (ex: 7.5, 6.5)
       - Lançamento: "Sim" se mencionar "lançamento", "nova", etc.
       - Slogan: Frase de marketing se houver
       - Tecnologia: IPRO, I2X, XtendFlex, etc.
    
    B. REGIÃO E CICLO:
       - Região (por extenso): Sul, Sudeste, Centro-Oeste, Nordeste, Norte
       - Estado (por extenso): Nomes completos dos estados recomendados
       - Ciclo: Precoce, Médio, Tardio
       - Finalidade: "Grãos"
       - URL da imagem do mapa: "NR"
    
    C. ÍCONES (até 5 benefícios):
       - Extraia os principais benefícios do texto
       - Use números de 1 a 5 para os ícones
    
    D. CARACTERÍSTICAS TÉCNICAS (soja):
       - PMS MÉDIO: Peso de mil sementes (ex: 150G)
       - Tipo de crescimento: Indeterminado, Semideterminado, Determinado
       - Cores: Flor, pubescência, hilo
       - Doenças: Use S (Suscetível), MS, MR, R (Resistente), X
    
    E. RESULTADOS DE PRODUTIVIDADE:
       - Extraia até 7 resultados se disponíveis
       - Formato: Nome do teste, Local, Produtividade
    
    F. EPOCA DE SEMEADURA (MESES):
       - Para meses com recomendação: "180-260"
       - Para outros: "NR"
    
    3. REGRAS GERAIS:
       - Use "NR" para informações não encontradas
       - Para estados: SP = São Paulo, PR = Paraná, etc.
       - Para regiões: 
         * Sul: PR, SC, RS
         * Sudeste: SP, MG, RJ, ES
         * Centro-Oeste: MT, MS, GO, DF
         * Nordeste: BA, MA, PI, etc.
         * Norte: PA, RO, TO, etc.
       - Mantenha valores exatos quando disponíveis
    
    4. FORMATO DE SAÍDA:
       - UMA LINHA POR CULTIVAR
       - Separar valores por TAB (\t)
       - Separar linhas por nova linha (\n)
       - SEM cabeçalho na saída
       - APENAS as linhas de dados
    
    EXEMPLO de duas linhas:
    Soja	NS7524IPRO	NS7524IPRO	Cultivar de soja IPRO com alto potencial produtivo	Alto	7.5	Sim	Excelente performance produtiva	IPRO	Sul, Sudeste	Paraná, Santa Catarina, São Paulo	Precoce	Grãos	NR	1	Alto potencial produtivo	Excelente performance em diversas regiões	2	Resistência a nematoides	Múltipla resistência a nematoides de cisto	3	NR	NR	4	NR	NR	5	NR	NR	Alto	7.5	150G	Semideterminado	Roxa	Marrom média	Preto	R	MR	R	R	MR	MR	MR	MR	Pode haver variação no ciclo (dias) devido às condições edafoclimáticas, época de plantio e manejo aplicado. Recomendações de população final de plantas e de época de semeadura foram construídas com base em resultados de experimentos próprios conduzidos na região e servem como direcionamento da população ideal de plantas para cada talhão. Deve-se levar em consideração: condições edafoclimáticas; textura; fertilidade do solo; adubação; nível de manejo; germinação; vigor da semente; umidade do solo entre outros fatores. Consultar recomendação de Zoneamento Agrícola de Risco Climático para a cultura de acordo com Ministério da Agricultura, Pecuária e Abastecimento.	Ensaio Regional	Paraná	85.5 sc/ha	Ensaio Estadual	Santa Catarina	82.3 sc/ha	Ensaio Regional	São Paulo	80.1 sc/ha	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	PR, SC, SP	Sul, Sudeste	NR	NR	180-260	180-260	180-260	180-260	180-260	180-260	180-260	180-260	180-260	NR
    Soja	NS6595I2X	NS6595I2X	Cultivar de soja I2X com tecnologia inovadora	Alto	6.5	Sim	O caminho da alta produtividade	I2X	Sul, Centro-Oeste	Paraná, Mato Grosso do Sul	Médio	Grãos	NR	1	Tecnologia I2X	Benefícios da tecnologia I2X	2	Alta produtividade	Potencial produtivo comprovado	3	NR	NR	4	NR	NR	5	NR	NR	Alto	6.5	155G	Indeterminado	Branca	Cinza	Marrom	MR	MS	MS	MS	S	S	S	S	Pode haver variação no ciclo (dias) devido às condições edafoclimáticas, época de plantio e manejo aplicado. Recomendações de população final de plantas e de época de semeadura foram construídas com base em resultados de experimentos próprios conduzidos na região e servem como direcionamento da população ideal de plantas para cada talhão. Deve-se levar em consideração: condições edafoclimáticas; textura; fertilidade do solo; adubação; nível de manejo; germinação; vigor da semente; umidade do solo entre outros fatores. Consultar recomendação de Zoneamento Agrícola de Risco Climático para a cultura de acordo com Ministério da Agricultura, Pecuária e Abastecimento.	Ensaio Estadual	Mato Grosso do Sul	78.5 sc/ha	Ensaio Regional	Paraná	76.2 sc/ha	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	NR	PR, MS	Sul, Centro-Oeste	NR	NR	180-260	180-260	180-260	180-260	NR	NR	NR	NR	NR	NR	NR
    
    Agora, analise TODO o texto transcrito e extraia TODAS as cultivares.
    Retorne APENAS as linhas CSV, sem explicações adicionais.
    """
    
    try:
        with st.spinner("Convertendo texto transcrito para CSV..."):
            response = modelo_texto.generate_content(prompt)
            resultado = response.text.strip()
        
        # Processar resultado
        linhas_csv = []
        for linha in resultado.split('\n'):
            linha = linha.strip()
            if linha and '\t' in linha:  # Linha válida deve ter tabs
                linhas_csv.append(linha)
        
        return linhas_csv
            
    except Exception as e:
        st.error(f"Erro na conversão para CSV: {str(e)}")
        st.write("Resposta do modelo:", resultado[:1000] if 'resultado' in locals() else "Nenhuma resposta")
        return []

# Interface principal
def main():
    # Inicializar variáveis de sessão
    if 'imagens_convertidas' not in st.session_state:
        st.session_state.imagens_convertidas = []
    if 'texto_transcrito' not in st.session_state:
        st.session_state.texto_transcrito = ""
    if 'linhas_csv' not in st.session_state:
        st.session_state.linhas_csv = []
    
    # Sidebar para upload
    with st.sidebar:
        st.header("Upload do Documento")
        uploaded_file = st.file_uploader(
            "Carregue um arquivo DOCX:",
            type=["docx"],
            accept_multiple_files=False,
            key="file_uploader"
        )
        
        if uploaded_file:
            st.write(f"**Arquivo:** {uploaded_file.name}")
            st.write(f"**Tamanho:** {uploaded_file.size / 1024:.1f} KB")
            
            if st.button("🔍 Processar Documento", type="primary", use_container_width=True):
                with st.spinner("Iniciando processamento..."):
                    # Resetar estado
                    st.session_state.imagens_convertidas = []
                    st.session_state.texto_transcrito = ""
                    st.session_state.linhas_csv = []
                    
                    # 1. Converter DOCX para imagens
                    st.info("Convertendo DOCX para imagens...")
                    docx_bytes = uploaded_file.getvalue()
                    imagens = converter_docx_para_imagens(docx_bytes, uploaded_file.name)
                    
                    if not imagens:
                        st.error("Falha na conversão do DOCX")
                        return
                    
                    st.session_state.imagens_convertidas = imagens
                    st.success(f"✅ Convertido em {len(imagens)} página(s)")
                    
                    # 2. Transcrever todas as páginas
                    st.info("Transcrevendo páginas com modelo de visão...")
                    texto_transcrito = transcrever_todas_paginas(imagens)
                    st.session_state.texto_transcrito = texto_transcrito
                    
                    # Mostrar preview da transcrição
                    with st.expander("📝 Ver transcrição completa", expanded=False):
                        st.text_area("Texto transcrito:", texto_transcrito[:5000] + ("..." if len(texto_transcrito) > 5000 else ""), 
                                   height=300, key="preview_transcricao")
                    
                    st.success(f"✅ Transcrição concluída ({len(texto_transcrito)} caracteres)")
                    
                    # 3. Converter texto para CSV
                    st.info("Gerando CSV com todas as cultivares...")
                    linhas_csv = converter_texto_para_csv_completo(texto_transcrito)
                    st.session_state.linhas_csv = linhas_csv
                    
                    if linhas_csv:
                        st.success(f"✅ CSV gerado com {len(linhas_csv)} cultivar(s)")
                    else:
                        st.warning("⚠️ Nenhuma cultivar encontrada no documento")
    
    # Área principal para resultados
    st.header("Resultados")
    
    # Mostrar preview das imagens
    if st.session_state.imagens_convertidas:
        with st.expander(f"📄 Visualizar páginas convertidas ({len(st.session_state.imagens_convertidas)} páginas)", expanded=False):
            cols = st.columns(min(3, len(st.session_state.imagens_convertidas)))
            for idx, imagem in enumerate(st.session_state.imagens_convertidas):
                col_idx = idx % 3
                with cols[col_idx]:
                    st.image(imagem, caption=f"Página {idx+1}", use_container_width=True)
    
    # Mostrar CSV gerado
    if st.session_state.linhas_csv:
        st.subheader("📊 CSV Gerado")
        
        # Cabeçalho das colunas
        cabecalho = """Cultura	Nome do produto	NOME TÉCNICO/ REG	Descritivo para SEO	Fertilidade	Grupo de maturação	Lançamento	Slogan	Tecnologia	Região (por extenso)	Estado (por extenso)	Ciclo	Finalidade	URL da imagem do mapa	Número do ícone	Titulo icone 1	Descrição Icone 1	Número do ícone	Titulo icone 2	Descrição Icone 2	Número do ícone	Titulo icone 3	Descrição Icone 3	Número do ícone	Título icone 4	Descrição Icone 4	Número do ícone	Título icone 5	Descrição Icone 5	Exigência à fertilidade	Grupo de maturidade	PMS MÉDIO	Tipo de crescimento	Cor da flor	Cor da pubescência	Cor do hilo	Cancro da haste	Pústula bacteriana	Nematoide das galhas - M. javanica	Nematóide de Cisto (Raça 3)	Nematóide de Cisto (Raça 9)	Nematóide de Cisto (Raça 10)	Nematóide de Cisto (Raça 14)	Fitóftora (Raça 1)	Recomendações	Resultado 1 - Nome	Resultado 1 - Local	Resultado 1	Resultado 2 - Nome	Resultado 2 - Local	Resultado 2	Resultado 3 - Nome	Resultado 3 - Local	Resultado 3	Resultado 4 - Nome	Resultado 4 - Local	Resultado 4	Resultado 5 - Nome	Resultado 5 - Local	Resultado 5	Resultado 6 - Nome	Resultado 6 - Local	Resultado 6	Resultado 7 - Nome	Resultado 7 - Local	Resultado 7	REC	UF	Região	Mês 1	Mês 2	Mês 3	Mês 4	Mês 5	Mês 6	Mês 7	Mês 8	Mês 9	Mês 10	Mês 11	Mês 12"""
        
        # Criar conteúdo CSV
        conteudo_csv = cabecalho + "\n" + "\n".join(st.session_state.linhas_csv)
        
        # Criar DataFrame
        try:
            # Processar cada linha CSV
            todas_linhas = []
            for linha in st.session_state.linhas_csv:
                partes = linha.split('\t')
                # Garantir 76 colunas
                while len(partes) < 76:
                    partes.append("NR")
                todas_linhas.append(partes[:76])
            
            # Criar DataFrame
            cabecalho_partes = cabecalho.split('\t')
            df = pd.DataFrame(todas_linhas, columns=cabecalho_partes)
            
            # Mostrar preview
            st.write(f"**Total de cultivares:** {len(df)}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Cultivares de Soja", len(df[df['Cultura'] == 'Soja']) if 'Cultura' in df.columns else 0)
            with col2:
                st.metric("Cultivares de Milho", len(df[df['Cultura'] == 'Milho']) if 'Cultura' in df.columns else 0)
            
            # Visualização da tabela
            with st.expander("📋 Visualizar dados extraídos", expanded=True):
                st.dataframe(df[['Cultura', 'Nome do produto', 'Grupo de maturação', 'Lançamento', 'Tecnologia', 'Estado (por extenso)']], 
                           use_container_width=True, height=400)
            
            # Download
            st.subheader("📥 Download")
            
            col_dl1, col_dl2, col_dl3 = st.columns(3)
            
            with col_dl1:
                # Download CSV
                st.download_button(
                    label="📄 Baixar CSV",
                    data=conteudo_csv,
                    file_name=f"cultivares_{uploaded_file.name.split('.')[0]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            with col_dl2:
                # Download Excel
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Cultivares')
                excel_data = excel_buffer.getvalue()
                
                st.download_button(
                    label="📊 Baixar Excel",
                    data=excel_data,
                    file_name=f"cultivares_{uploaded_file.name.split('.')[0]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            
            with col_dl3:
                # Download Texto Transcrito
                st.download_button(
                    label="📝 Baixar Transcrição",
                    data=st.session_state.texto_transcrito,
                    file_name=f"transcricao_{uploaded_file.name.split('.')[0]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            
            # Detalhes técnicos
            with st.expander("🔧 Detalhes técnicos", expanded=False):
                st.write(f"**Páginas processadas:** {len(st.session_state.imagens_convertidas)}")
                st.write(f"**Tamanho da transcrição:** {len(st.session_state.texto_transcrito):,} caracteres")
                st.write(f"**Colunas no CSV:** {len(cabecalho_partes)}")
                st.code(conteudo_csv[:2000], language="text")
                
        except Exception as e:
            st.error(f"Erro ao processar CSV: {str(e)}")
            st.write("Conteúdo CSV bruto:")
            st.code(conteudo_csv[:3000], language="text")
    
    elif st.session_state.texto_transcrito and not st.session_state.linhas_csv:
        st.warning("Texto transcrito disponível, mas nenhuma cultivar foi encontrada.")
        with st.expander("Ver texto transcrito"):
            st.text_area("Texto completo:", st.session_state.texto_transcrito, height=400)
    
    elif not uploaded_file:
        st.info("👈 Carregue um arquivo DOCX na barra lateral para começar")
        
        # Exemplo do fluxo
        st.markdown("""
        ### Fluxo do Processamento:
        
        1. **Upload DOCX** → Carregue seu documento técnico
        2. **Conversão para imagens** → Cada página vira uma imagem PNG
        3. **Transcrição com IA** → Modelo de visão lê todas as imagens
        4. **Extração para CSV** → Modelo de texto analisa e formata os dados
        5. **Download** → Baixe o CSV com todas as colunas formatadas
        
        ### Formatos suportados:
        - Documentos DOCX com tabelas de cultivares
        - Catálogos técnicos de soja e milho
        - Fichas técnicas com múltiplas cultivares
        """)

if __name__ == "__main__":
    main()
