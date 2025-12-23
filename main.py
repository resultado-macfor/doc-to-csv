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
    modelo_vision = genai.GenerativeModel("gemini-2.5-flash")
    modelo_texto = genai.GenerativeModel("gemini-2.5-flash")
except Exception as e:
    st.error(f"Erro ao configurar o Gemini: {str(e)}")
    st.stop()

# Função para converter DOCX para imagens (Linux compatível)
def converter_docx_para_imagens(docx_bytes, nome_arquivo):
    """Converte DOCX para imagens usando python-docx e PIL (Linux compatível)"""
    
    imagens = []
    
    try:
        # Salvar em arquivo temporário
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp_docx:
            tmp_docx.write(docx_bytes)
            tmp_docx_path = tmp_docx.name
        
        try:
            # Tentar converter para PDF primeiro (se funcionar no sistema)
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_pdf:
                tmp_pdf_path = tmp_pdf.name
            
            try:
                convert(tmp_docx_path, tmp_pdf_path)
                
                # Converter PDF para imagens
                images_from_pdf = pdf2image.convert_from_path(
                    tmp_pdf_path, 
                    dpi=150,
                    fmt='PNG'
                )
                imagens.extend(images_from_pdf)
                
            except Exception as e:
                # Fallback: extrair texto diretamente do DOCX
                st.info("Usando método alternativo de extração de texto...")
                doc = docx.Document(tmp_docx_path)
                
                # Agrupar parágrafos em páginas (aproximadamente 800 caracteres por página)
                texto_completo = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
                
                # Dividir texto em "páginas" para processamento
                paginas_texto = []
                pag_atual = ""
                
                for linha in texto_completo.split('\n'):
                    pag_atual += linha + "\n"
                    if len(pag_atual) > 800:  # Limite por "página"
                        paginas_texto.append(pag_atual)
                        pag_atual = ""
                
                if pag_atual:
                    paginas_texto.append(pag_atual)
                
                # Criar imagens a partir do texto
                for i, texto_pagina in enumerate(paginas_texto):
                    from PIL import ImageDraw, ImageFont
                    # Tamanho da página A4 em pixels (150 DPI)
                    img = Image.new('RGB', (1240, 1754), color='white')
                    d = ImageDraw.Draw(img)
                    
                    try:
                        font = ImageFont.truetype("arial.ttf", 14)
                    except:
                        font = ImageFont.load_default()
                    
                    # Adicionar texto à imagem
                    lines = texto_pagina.split('\n')
                    y = 100
                    for line in lines:
                        if line.strip() and y < 1650:
                            # Quebrar linhas muito longas
                            max_chars = 120
                            for i in range(0, len(line), max_chars):
                                if y < 1650:
                                    d.text((100, y), line[i:i+max_chars], fill='black', font=font)
                                    y += 25
                    
                    imagens.append(img)
        
        finally:
            # Limpar arquivos temporários
            try:
                os.unlink(tmp_docx_path)
                if 'tmp_pdf_path' in locals() and os.path.exists(tmp_pdf_path):
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
            time.sleep(0.5)
            
        except Exception as e:
            texto_erro = f"\n\n{'='*60}\nERRO na página {pagina_num}: {str(e)}\n{'='*60}\n"
            texto_completo += texto_erro
    
    progress_bar.empty()
    status_text.empty()
    
    return texto_completo

# Função para converter texto transcrito em CSV
def converter_texto_para_csv_completo(texto_transcrito):
    """Converte todo o texto transcrito em CSV com todas as colunas"""
    
    # Remover limite do texto - processar TUDO
    prompt = f"""
    VOCÊ É UM ESPECIALISTA EM AGRICULTURA E EXTRATOR DE DADOS.
    
    VOCÊ RECEBEU A TRANSCRIÇÃO COMPLETA DE UM DOCUMENTO TÉCNICO SOBRE CULTIVARES DE SOJA.
    ANALISE TODO O TEXTO E EXTRAIA INFORMAÇÕES SOBRE TODAS AS CULTIVARES MENCIONADAS.
    
    TEXTO TRANSCRITO COMPLETO:
    {texto_transcrito}
    
    SUA TAREFA CRÍTICA:
    Para CADA cultivar encontrada, crie UMA LINHA no formato CSV abaixo com TODAS as 81 colunas.
    
    FORMATO CSV EXATO (81 colunas separadas por TAB):
    Cultura	Nome do produto	NOME TÉCNICO/ REG	Descritivo para SEO	Fertilidade	Grupo de maturação	Lançamento	Slogan	Tecnologia	Região (por extenso)	Estado (por extenso)	Ciclo	Finalidade	URL da imagem do mapa	Número do ícone	Titulo icone 1	Descrição Icone 1	Número do ícone	Titulo icone 2	Descrição Icone 2	Número do ícone	Titulo icone 3	Descrição Icone 3	Número do ícone	Título icone 4	Descrição Icone 4	Número do ícone	Título icone 5	Descrição Icone 5	Exigência à fertilidade	Grupo de maturidade	PMS MÉDIO	Tipo de crescimento	Cor da flor	Cor da pubescência	Cor do hilo	Cancro da haste	Pústula bacteriana	Nematoide das galhas - M. javanica	Nematóide de Cisto (Raça 3)	Nematóide de Cisto (Raça 9)	Nematóide de Cisto (Raça 10)	Nematóide de Cisto (Raça 14)	Fitóftora (Raça 1)	Recomendações	Resultado 1 - Nome	Resultado 1 - Local	Resultado 1	Resultado 2 - Nome	Resultado 2 - Local	Resultado 2	Resultado 3 - Nome	Resultado 3 - Local	Resultado 3	Resultado 4 - Nome	Resultado 4 - Local	Resultado 4	Resultado 5 - Nome	Resultado 5 - Local	Resultado 5	Resultado 6 - Nome	Resultado 6 - Local	Resultado 6	Resultado 7 - Nome	Resultado 7 - Local	Resultado 7	REC	UF	Região	Mês 1	Mês 2	Mês 3	Mês 4	Mês 5	Mês 6	Mês 7	Mês 8	Mês 9	Mês 10	Mês 11	Mês 12
    
    INSTRUÇÕES DETALHADAS PARA CADA COLUNA (81 colunas no total):
    
    COLUNAS 1-13 (Informações básicas):
    1. Cultura: "Soja"
    2. Nome do produto: Nome completo da cultivar (ex: N5659512X, NS802512X)
    3. NOME TÉCNICO/REG: Mesmo que nome do produto
    4. Descritivo para SEO: Crie uma descrição de 15-20 palavras
    5. Fertilidade: Extraia do texto (Alto, Médio e alto, etc.)
    6. Grupo de maturação: Número (ex: 6.5, 8)
    7. Lançamento: "Sim" se mencionar "lançamento"
    8. Slogan: Frase de marketing
    9. Tecnologia: 12X, IPRO, I2X, etc.
    10. Região (por extenso): Baseado nos estados
    11. Estado (por extenso): Nomes completos
    12. Ciclo: Precoce, Médio, Tardio (inferir do grupo)
    13. Finalidade: "Grãos"
    
    COLUNAS 14-28 (Ícones e descrições):
    14. URL da imagem do mapa: "NR"
    15. Número do ícone: "1"
    16. Titulo icone 1: Primeiro benefício
    17. Descrição Icone 1: Descrição do primeiro benefício
    18. Número do ícone: "2"
    19. Titulo icone 2: Segundo benefício
    20. Descrição Icone 2: Descrição do segundo benefício
    21. Número do ícone: "3"
    22. Titulo icone 3: Terceiro benefício
    23. Descrição Icone 3: Descrição do terceiro benefício
    24. Número do ícone: "4"
    25. Título icone 4: Quarto benefício (ou "NR")
    26. Descrição Icone 4: Descrição (ou "NR")
    27. Número do ícone: "5"
    28. Título icone 5: Quinto benefício (ou "NR")
    29. Descrição Icone 5: Descrição (ou "NR")
    
    COLUNAS 30-41 (Características técnicas):
    30. Exigência à fertilidade: Mesmo que coluna 5
    31. Grupo de maturidade: Mesmo que coluna 6
    32. PMS MÉDIO: Peso em gramas (ex: 165g, 157g)
    33. Tipo de crescimento: Indeterminado, Semideterminado, Determinado
    34. Cor da flor: Branca, Roxa, etc.
    35. Cor da pubescência: Marrom média, etc.
    36. Cor do hilo: Marrom, etc.
    37. Cancro da haste: S, M, MR, R, X
    38. Pústula bacteriana: S, M, MR, R, X
    39. Nematoide das galhas - M. javanica: S, M, MR, R, X
    40. Nematóide de Cisto (Raça 3): S, M, MR, R, X
    41. Nematóide de Cisto (Raça 9): S, M, MR, R, X
    42. Nematóide de Cisto (Raça 10): S, M, MR, R, X
    43. Nematóide de Cisto (Raça 14): S, M, MR, R, X
    44. Fitóftora (Raça 1): S, M, MR, R, X
    
    COLUNAS 45-71 (Recomendações e resultados):
    45. Recomendações: Texto padrão sobre condições edafoclimáticas
    46-58. Resultados 1-7: Nome, Local, Produtividade (preencher "NR" se não houver)
    
    COLUNAS 72-81 (Regiões e meses):
    72. REC: "NR"
    73. UF: Siglas dos estados
    74. Região: Mesmo que coluna 10
    75-86. Mês 1 a Mês 12: "180-260" para meses de semeadura, "NR" para outros
    
    REGRAS IMPORTANTES:
    1. Você DEVE retornar EXATAMENTE 81 colunas por linha
    2. Se não encontrar informação, use "NR"
    3. Para doenças: use X quando não mencionado
    4. Para ícones: preencha até 5, use "NR" para extras não existentes
    5. Recomendações: Texto padrão completo
    
    TEXTO PADRÃO PARA RECOMENDAÇÕES (coluna 45):
    "Pode haver variação no ciclo (dias) devido às condições edafoclimáticas, época de plantio e manejo aplicado. Recomendações de população final de plantas e de época de semeadura foram construídas com base em resultados de experimentos próprios conduzidos na região e servem como direcionamento da população ideal de plantas para cada talhão. Deve-se levar em consideração: condições edafoclimáticas; textura; fertilidade do solo; adubação; nível de manejo; germinação; vigor da semente; umidade do solo entre outros fatores. Consultar recomendação de Zoneamento Agrícola de Risco Climático para a cultura de acordo com Ministério da Agricultura, Pecuária e Abastecimento."
    
    BASEADO NO TEXTO QUE VOCÊ TEM, IDENTIFIQUE TODAS AS CULTIVARES E PREENCHA TODAS AS 81 COLUNAS.
    
    Retorne APENAS as linhas CSV, UMA LINHA POR CULTIVAR, sem cabeçalho, sem explicações.
    Separe valores por TAB.
    Separe linhas por nova linha.
    
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
                # Contar colunas
                num_colunas = len(linha.split('\t'))
                if num_colunas < 81:
                    # Adicionar colunas faltantes com "NR"
                    partes = linha.split('\t')
                    while len(partes) < 81:
                        partes.append("NR")
                    linha = '\t'.join(partes)
                elif num_colunas > 81:
                    # Remover colunas extras
                    partes = linha.split('\t')
                    linha = '\t'.join(partes[:81])
                
                linhas_csv.append(linha)
        
        return linhas_csv
            
    except Exception as e:
        st.error(f"Erro na conversão para CSV: {str(e)}")
        if 'resultado' in locals():
            st.write("Resposta do modelo:", resultado[:2000])
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
    if 'uploaded_file_name' not in st.session_state:
        st.session_state.uploaded_file_name = ""
    
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
            st.session_state.uploaded_file_name = uploaded_file.name
            st.write(f"**Arquivo:** {uploaded_file.name}")
            st.write(f"**Tamanho:** {uploaded_file.size / 1024:.1f} KB")
            
            col1, col2 = st.columns(2)
            with col1:
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
                        
                        st.success(f"✅ Transcrição concluída ({len(texto_transcrito):,} caracteres)")
                        
                        # 3. Converter texto para CSV
                        st.info("Gerando CSV com todas as cultivares...")
                        linhas_csv = converter_texto_para_csv_completo(texto_transcrito)
                        st.session_state.linhas_csv = linhas_csv
                        
                        if linhas_csv:
                            st.success(f"✅ CSV gerado com {len(linhas_csv)} cultivar(s)")
                        else:
                            st.warning("⚠️ Nenhuma cultivar encontrada no documento")
            
            with col2:
                if st.button("🔄 Limpar Processamento", use_container_width=True):
                    st.session_state.imagens_convertidas = []
                    st.session_state.texto_transcrito = ""
                    st.session_state.linhas_csv = []
                    st.rerun()
    
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
    
    # Mostrar transcrição se disponível
    if st.session_state.texto_transcrito:
        with st.expander("📝 Ver transcrição completa", expanded=False):
            st.text_area("Texto transcrito:", st.session_state.texto_transcrito, 
                       height=300, key="preview_transcricao")
    
    # Mostrar CSV gerado
    if st.session_state.linhas_csv:
        st.subheader("📊 CSV Gerado")
        
        # Cabeçalho das colunas (81 colunas)
        cabecalho = """Cultura	Nome do produto	NOME TÉCNICO/ REG	Descritivo para SEO	Fertilidade	Grupo de maturação	Lançamento	Slogan	Tecnologia	Região (por extenso)	Estado (por extenso)	Ciclo	Finalidade	URL da imagem do mapa	Número do ícone	Titulo icone 1	Descrição Icone 1	Número do ícone	Titulo icone 2	Descrição Icone 2	Número do ícone	Titulo icone 3	Descrição Icone 3	Número do ícone	Título icone 4	Descrição Icone 4	Número do ícone	Título icone 5	Descrição Icone 5	Exigência à fertilidade	Grupo de maturidade	PMS MÉDIO	Tipo de crescimento	Cor da flor	Cor da pubescência	Cor do hilo	Cancro da haste	Pústula bacteriana	Nematoide das galhas - M. javanica	Nematóide de Cisto (Raça 3)	Nematóide de Cisto (Raça 9)	Nematóide de Cisto (Raça 10)	Nematóide de Cisto (Raça 14)	Fitóftora (Raça 1)	Recomendações	Resultado 1 - Nome	Resultado 1 - Local	Resultado 1	Resultado 2 - Nome	Resultado 2 - Local	Resultado 2	Resultado 3 - Nome	Resultado 3 - Local	Resultado 3	Resultado 4 - Nome	Resultado 4 - Local	Resultado 4	Resultado 5 - Nome	Resultado 5 - Local	Resultado 5	Resultado 6 - Nome	Resultado 6 - Local	Resultado 6	Resultado 7 - Nome	Resultado 7 - Local	Resultado 7	REC	UF	Região	Mês 1	Mês 2	Mês 3	Mês 4	Mês 5	Mês 6	Mês 7	Mês 8	Mês 9	Mês 10	Mês 11	Mês 12"""
        
        # Criar conteúdo CSV
        conteudo_csv = cabecalho + "\n" + "\n".join(st.session_state.linhas_csv)
        
        # Criar DataFrame com tratamento correto
        try:
            # Processar cada linha CSV e garantir 81 colunas
            todas_linhas = []
            for linha in st.session_state.linhas_csv:
                partes = linha.split('\t')
                # Garantir EXATAMENTE 81 colunas
                if len(partes) < 81:
                    partes.extend(["NR"] * (81 - len(partes)))
                elif len(partes) > 81:
                    partes = partes[:81]
                
                todas_linhas.append(partes)
            
            # Criar DataFrame
            cabecalho_partes = cabecalho.split('\t')
            
            # Verificar compatibilidade
            if len(cabecalho_partes) != 81:
                st.warning(f"Cabeçalho tem {len(cabecalho_partes)} colunas, ajustando para 81...")
                while len(cabecalho_partes) < 81:
                    cabecalho_partes.append(f"Coluna_{len(cabecalho_partes)+1}")
                cabecalho_partes = cabecalho_partes[:81]
            
            df = pd.DataFrame(todas_linhas, columns=cabecalho_partes)
            
            # Mostrar estatísticas
            st.write(f"**Total de cultivares:** {len(df)}")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                if 'Cultura' in df.columns:
                    soja_count = len(df[df['Cultura'] == 'Soja'])
                    st.metric("Cultivares de Soja", soja_count)
                else:
                    st.metric("Cultivares", len(df))
            
            with col2:
                if 'Grupo de maturação' in df.columns:
                    grupos = df['Grupo de maturação'].unique()
                    st.metric("Grupos distintos", len(grupos))
                else:
                    st.metric("Linhas processadas", len(df))
            
            with col3:
                if 'Tecnologia' in df.columns:
                    techs = df['Tecnologia'].unique()
                    st.metric("Tecnologias", len(techs))
                else:
                    st.metric("Colunas", len(df.columns))
            
            # Visualização da tabela
            with st.expander("📋 Visualizar dados extraídos", expanded=True):
                # Selecionar colunas principais para visualização
                colunas_visuais = ['Cultura', 'Nome do produto', 'Grupo de maturação', 
                                 'Lançamento', 'Tecnologia', 'Estado (por extenso)', 
                                 'Fertilidade', 'PMS MÉDIO']
                colunas_disponiveis = [c for c in colunas_visuais if c in df.columns]
                
                if colunas_disponiveis:
                    st.dataframe(df[colunas_disponiveis], use_container_width=True, height=400)
                else:
                    st.dataframe(df.iloc[:, :10], use_container_width=True, height=400)
            
            # Download
            st.subheader("📥 Download")
            
            col_dl1, col_dl2, col_dl3 = st.columns(3)
            
            with col_dl1:
                # Download CSV
                nome_base = st.session_state.uploaded_file_name.split('.')[0] if st.session_state.uploaded_file_name else "cultivares"
                st.download_button(
                    label="📄 Baixar CSV (TAB)",
                    data=conteudo_csv,
                    file_name=f"{nome_base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    help="CSV separado por TAB com 81 colunas"
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
                    file_name=f"{nome_base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    help="Arquivo Excel com todas as colunas"
                )
            
            with col_dl3:
                # Download Texto Transcrito
                if st.session_state.texto_transcrito:
                    st.download_button(
                        label="📝 Baixar Transcrição",
                        data=st.session_state.texto_transcrito,
                        file_name=f"transcricao_{nome_base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain",
                        use_container_width=True,
                        help="Texto completo transcrito do documento"
                    )
            
            # Detalhes técnicos
            with st.expander("🔧 Detalhes técnicos", expanded=False):
                st.write(f"**Páginas processadas:** {len(st.session_state.imagens_convertidas)}")
                st.write(f"**Tamanho da transcrição:** {len(st.session_state.texto_transcrito):,} caracteres")
                st.write(f"**Colunas no CSV:** {len(df.columns)}")
                st.write(f"**Cultivares extraídas:** {len(df)}")
                
                # Mostrar algumas linhas do CSV
                st.write("**Primeiras linhas do CSV:**")
                st.code("\n".join(conteudo_csv.split('\n')[:4]), language="text")
                
        except Exception as e:
            st.error(f"Erro ao processar CSV: {str(e)}")
            st.write("**Conteúdo CSV bruto (primeiras 2000 caracteres):**")
            st.code(conteudo_csv[:2000], language="text")
            
            # Tentar diagnóstico
            st.write("**Diagnóstico:**")
            if st.session_state.linhas_csv:
                primeira_linha = st.session_state.linhas_csv[0]
                num_colunas = len(primeira_linha.split('\t'))
                st.write(f"Primeira linha tem {num_colunas} colunas")
                st.write(f"Cabeçalho tem {len(cabecalho.split('\t'))} colunas")
    
    elif st.session_state.texto_transcrito and not st.session_state.linhas_csv:
        st.warning("Texto transcrito disponível, mas nenhuma cultivar foi encontrada.")
        with st.expander("Ver texto transcrito"):
            st.text_area("Texto completo:", st.session_state.texto_transcrito, height=400)
    
    elif not st.session_state.uploaded_file_name:
        st.info("👈 Carregue um arquivo DOCX na barra lateral para começar")
        
        # Exemplo do fluxo
        st.markdown("""
        ### 🚀 Fluxo do Processamento:
        
        1. **📤 Upload DOCX** → Carregue seu documento técnico
        2. **🖼️ Conversão para imagens** → Cada página vira uma imagem PNG
        3. **👁️ Transcrição com IA** → Modelo de visão lê TODAS as imagens
        4. **📝 Extração para CSV** → Modelo de texto analisa e formata 81 colunas
        5. **💾 Download** → Baixe CSV, Excel e transcrição
        
        ### 📊 Saída Gerada:
        - **CSV com 81 colunas** formatado com TAB
        - **Arquivo Excel** pronto para uso
        - **Transcrição completa** do documento
        
        ### ✅ Funcionalidades:
        - Processa **TODAS** as páginas do documento
        - Detecta **MÚLTIPLAS** cultivares por página
        - Extrai **TODAS** as 81 colunas especificadas
        - Compatível com **Linux** (sem necessidade de Microsoft Word)
        - Interface amigável com feedback visual
        """)

if __name__ == "__main__":
    main()
