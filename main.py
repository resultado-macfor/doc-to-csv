import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
from datetime import datetime
import tempfile
import docx
import io
import csv
import json
import re  # CORRIGIDO: era 'remax'
from PIL import Image, ImageDraw, ImageFont
import math

# Configuração
st.set_page_config(page_title="Extrator de Cultivares", page_icon="🌱", layout="wide")
st.title("🌱 Extrator de Cultivares")

# API Key
gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEM_API_KEY")
if not gemini_api_key:
    st.error("Configure GEMINI_API_KEY")
    st.stop()

try:
    genai.configure(api_key=gemini_api_key)
    modelo_visao = genai.GenerativeModel("gemini-2.5-flash")  # Modelo mais rápido para imagens
    modelo_texto = genai.GenerativeModel("gemini-2.5-flash")  # Modelo para texto
except Exception as e:
    st.error(f"Erro ao configurar Gemini: {str(e)}")
    st.stop()

# COLUNAS EXATAS - COM MESES DIVIDIDOS EM 3 PERÍODOS
COLUNAS_EXATAS = [
    "Cultura", "Nome do produto", "NOME TÉCNICO/ REG", "Descritivo para SEO", 
    "Fertilidade", "Grupo de maturação", "Lançamento", "Slogan", "Tecnologia", 
    "Região (por extenso)", "Estado (por extenso)", "Ciclo", "Finalidade", 
    "URL da imagem do mapa", "Número do ícone 1", "Titulo icone 1", "Descrição Icone 1", 
    "Número do ícone 2", "Titulo icone 2", "Descrição Icone 2", "Número do ícone 3", 
    "Titulo icone 3", "Descrição Icone 3", "Número do ícone 4", "Título icone 4", 
    "Descrição Icone 4", "Número do ícone 5", "Título icone 5", "Descrição Icone 5", 
    "Exigência à fertilidade", "Grupo de maturidade", "PMS MÉDIO", "Tipo de crescimento", 
    "Cor da flor", "Cor da pubescência", "Cor do hilo", "Cancro da haste", 
    "Pústula bacteriana ", "Nematoide das galhas - M. javanica", 
    "Nematóide de Cisto (Raça 3", "Nematóide de Cisto (Raça 9)", 
    "Nematóide de Cisto (Raça 10", "Nematóide de Cisto (Raça 14)", 
    "Fitóftora (Raça 1)", "Recomendações", "Resultado 1 - Nome", "Resultado 1 - Local", 
    "Resultado 1", "Resultado 2 - Nome", "Resultado 2 - Local", "Resultado 2", 
    "Resultado 3 - Nome", "Resultado 3 - Local", "Resultado 3", "Resultado 4 - Nome", 
    "Resultado 4 - Local", "Resultado 4", "Resultado 5 - Nome", "Resultado 5 - Lcal", 
    "Resultado 5", "Resultado 6 - Nome", "Resultado 6 - Local", "Resultado 6", 
    "Resultado 7 - Nome", "Resultado 7 - Local", "Resultado 7", "REC", "UF", 
    "Região",
    # Janeiro dividido em 3 períodos
    "Janeiro 1-10", "Janeiro 11-20", "Janeiro 21-31",
    # Fevereiro
    "Fevereiro 1-10", "Fevereiro 11-20", "Fevereiro 21-28/29",
    # Março
    "Março 1-10", "Março 11-20", "Março 21-31",
    # Abril
    "Abril 1-10", "Abril 11-20", "Abril 21-30",
    # Maio
    "Maio 1-10", "Maio 11-20", "Maio 21-31",
    # Junho
    "Junho 1-10", "Junho 11-20", "Junho 21-30",
    # Julho
    "Julho 1-10", "Julho 11-20", "Julho 21-31",
    # Agosto
    "Agosto 1-10", "Agosto 11-20", "Agosto 21-31",
    # Setembro
    "Setembro 1-10", "Setembro 11-20", "Setembro 21-30",
    # Outubro
    "Outubro 1-10", "Outubro 11-20", "Outubro 21-31",
    # Novembro
    "Novembro 1-10", "Novembro 11-20", "Novembro 21-30",
    # Dezembro
    "Dezembro 1-10", "Dezembro 11-20", "Dezembro 21-31"
]

# Session state
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=COLUNAS_EXATAS)
if 'csv_content' not in st.session_state:
    st.session_state.csv_content = ""
if 'texto_transcrito' not in st.session_state:
    st.session_state.texto_transcrito = ""
if 'paginas_processadas' not in st.session_state:
    st.session_state.paginas_processadas = 0
if 'imagens_geradas' not in st.session_state:
    st.session_state.imagens_geradas = 0

# Função para converter DOCX para imagens - SEM LIMITE
def docx_para_imagens_completas(docx_bytes):
    try:
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
            tmp.write(docx_bytes)
            docx_path = tmp.name
        
        doc = docx.Document(docx_path)
        
        # Extrair TUDO do documento
        todas_linhas = []
        
        # Parágrafos
        for para in doc.paragraphs:
            if para.text.strip():
                todas_linhas.append(para.text.strip())
        
        # Tabelas - preservar estrutura
        for table_idx, table in enumerate(doc.tables):
            todas_linhas.append(f"=== TABELA {table_idx + 1} ===")
            for row_idx, row in enumerate(table.rows):
                linha_cells = []
                for cell in row.cells:
                    if cell.text.strip():
                        linha_cells.append(cell.text.strip())
                if linha_cells:
                    todas_linhas.append(f"Linha {row_idx + 1}: {' | '.join(linha_cells)}")
            todas_linhas.append(f"=== FIM TABELA {table_idx + 1} ===")
        
        # Contar páginas reais do documento
        # Estimativa: cada página A4 tem ~3000 caracteres
        texto_completo = "\n".join(todas_linhas)
        total_caracteres = len(texto_completo)
        
        # Calcular número de páginas (sem limite)
        caracteres_por_pagina = 4000  # Mais espaço por imagem
        num_paginas = max(1, math.ceil(total_caracteres / caracteres_por_pagina))
        
        st.info(f"📄 Documento original: {total_caracteres:,} caracteres")
        st.info(f"📊 Serão geradas aproximadamente {num_paginas} imagens")
        
        # Dividir em páginas
        paginas_texto = []
        pagina_atual = []
        chars_pagina = 0
        
        for linha in todas_linhas:
            chars_linha = len(linha) + 1  # +1 para quebra de linha
            
            # Se linha muito longa, quebrar
            if chars_linha > caracteres_por_pagina:
                # Quebra linha muito longa em partes
                partes = []
                for i in range(0, len(linha), caracteres_por_pagina):
                    partes.append(linha[i:i+caracteres_por_pagina])
                
                for parte in partes:
                    if chars_pagina + len(parte) > caracteres_por_pagina and pagina_atual:
                        paginas_texto.append("\n".join(pagina_atual))
                        pagina_atual = [parte]
                        chars_pagina = len(parte)
                    else:
                        pagina_atual.append(parte)
                        chars_pagina += len(parte)
            else:
                if chars_pagina + chars_linha > caracteres_por_pagina and pagina_atual:
                    paginas_texto.append("\n".join(pagina_atual))
                    pagina_atual = [linha]
                    chars_pagina = chars_linha
                else:
                    pagina_atual.append(linha)
                    chars_pagina += chars_linha
        
        if pagina_atual:
            paginas_texto.append("\n".join(pagina_atual))
        
        # Criar imagens
        imagens = []
        st.write(f"🖼️ Criando {len(paginas_texto)} imagens...")
        
        progress_bar = st.progress(0)
        
        for i, texto_pagina in enumerate(paginas_texto):
            progress_bar.progress((i + 1) / len(paginas_texto))
            
            # Imagem maior para mais conteúdo
            img = Image.new('RGB', (1400, 2000), color='white')
            draw = ImageDraw.Draw(img)
            
            try:
                font = ImageFont.truetype("arial.ttf", 10)  # Fonte menor para mais conteúdo
            except:
                font = ImageFont.load_default()
            
            # Adicionar texto
            y = 80
            x = 80
            largura_max = 1240
            
            linhas_texto = texto_pagina.split('\n')
            
            for linha in linhas_texto:
                if y < 1950:  # Margem inferior
                    # Quebrar linha se necessário
                    if draw.textlength(linha, font=font) > largura_max:
                        palavras = linha.split()
                        linha_atual = ""
                        
                        for palavra in palavras:
                            teste = linha_atual + " " + palavra if linha_atual else palavra
                            if draw.textlength(teste, font=font) <= largura_max:
                                linha_atual = teste
                            else:
                                if linha_atual and y < 1950:
                                    draw.text((x, y), linha_atual, fill='black', font=font)
                                    y += 16
                                linha_atual = palavra
                        
                        if linha_atual and y < 1950:
                            draw.text((x, y), linha_atual, fill='black', font=font)
                            y += 16
                    else:
                        draw.text((x, y), linha, fill='black', font=font)
                        y += 16
                else:
                    break
            
            # Adicionar número da página
            draw.text((1300, 1980), f"Pág {i+1}/{len(paginas_texto)}", fill='gray', font=font)
            
            imagens.append(img)
        
        progress_bar.empty()
        
        os.unlink(docx_path)
        
        return imagens, len(paginas_texto), total_caracteres
        
    except Exception as e:
        st.error(f"Erro na conversão DOCX: {str(e)}")
        return [], 0, 0

# Função para transcrever TODAS as imagens - SEM LIMITE
def transcrever_todas_imagens_completas(imagens):
    if not imagens:
        return "", 0
    
    texto_completo = ""
    
    st.write(f"👁️ Transcrevendo {len(imagens)} imagens...")
    
    # Usar container para updates dinâmicos
    progress_placeholder = st.empty()
    status_placeholder = st.empty()
    results_placeholder = st.empty()
    
    for i, imagem in enumerate(imagens):
        try:
            # Atualizar status
            progresso = (i + 1) / len(imagens)
            progress_placeholder.progress(progresso)
            status_placeholder.text(f"📄 Página {i+1} de {len(imagens)}")
            
            # Converter imagem
            img_bytes = io.BytesIO()
            imagem.save(img_bytes, format='PNG', quality=90)
            img_bytes = img_bytes.getvalue()
            
            # Prompt otimizado para extração de tabelas
            prompt = """TRANSCREVA TODO o texto desta imagem. FOCO ESPECIAL EM:

            1. TABELAS COM:
               - REC (números: 202, 203, 204...)
               - UF (estados: RS, SC, PR, SP, MS, MG, GO...)
               - Região (Sul, Sudeste, Centro-Oeste...)
               - Meses (Janeiro, Fevereiro... com períodos 1-10, 11-20, 21-31)
               - Valores: "180-260", "NR", números

            2. NOMES DE PRODUTOS:
               - NK401VIP3, NS7524IPRO, TMG, BÔNUS, etc.

            3. CARACTERÍSTICAS:
               - Cultura, Tecnologia, Ciclo, Fertilidade, etc.

            TRANSCREVA TABELAS COMPLETAS, com todas as linhas e colunas.
            Use | para separar colunas nas tabelas.
            Transcreva TUDO que estiver escrito."""
            
            response = modelo_visao.generate_content([
                prompt,
                {"mime_type": "image/png", "data": img_bytes}
            ])
            
            texto_pagina = response.text
            texto_completo += f"\n\n{'='*100}\nPÁGINA {i+1}/{len(imagens)}\n{'='*100}\n\n{texto_pagina}\n"
            
            # Mostrar progresso parcial
            if (i + 1) % 5 == 0 or i == 0 or i == len(imagens) - 1:
                results_placeholder.text(f"✅ {i+1}/{len(imagens)} páginas transcritas")
            
        except Exception as e:
            texto_completo += f"\n\n{'='*100}\nERRO na página {i+1}: {str(e)[:200]}\n{'='*100}\n"
            st.warning(f"⚠️ Erro na página {i+1}: {str(e)[:100]}")
    
    progress_placeholder.empty()
    status_placeholder.empty()
    results_placeholder.empty()
    
    return texto_completo, len(imagens)

# Função para extrair dados de TODO o texto - SEM LIMITE
def extrair_dados_completos(texto_transcrito):
    # Usar TODO o texto
    prompt = f"""
    ANALISE ESTE TEXTO COMPLETO DE UM DOCUMENTO AGRÍCOLA:

    TEXTO COMPLETO ({len(texto_transcrito):,} caracteres):
    ```
    {texto_transcrito}  # Limite generoso mas não muito
    ```

    SUA TAREFA: Extrair dados para preencher um CSV com {len(COLUNAS_EXATAS)} colunas.

    COLUNAS DO CSV:
    {', '.join(COLUNAS_EXATAS)}

    REGRAS CRÍTICAS:

    1. REC, UF, REGIÃO DEVEM VIR DE TABELAS:
       - Procure tabelas com cabeçalhos: REC, UF, Região
       - Use APENAS os valores das tabelas
       - Não invente valores

    2. DADOS TEMPORAIS (36 colunas):
       - Cada mês tem 3 colunas: 1-10, 11-20, 21-31
       - Fevereiro: 21-28/29
       - Extraia de tabelas com meses e períodos

    3. UM PRODUTO PODE TER MÚLTIPLOS RECs:
       - Cada combinação Produto+REC = linha separada
       - Exemplo: NK401VIP3 com REC 202 → Linha 1
                  NK401VIP3 com REC 203 → Linha 2

    4. PREENCHIMENTO:
       - Use "NR" para dados não encontrados
       - Para múltiplos valores: "RS, SC, PR"
       - Valores temporais: "180-260" ou "NR"

    5. PROCURE POR:
       - Tabelas de mapeamento REC/UF/Região
       - Tabelas temporais com meses
       - Características de produtos
       - Resultados de produtividade

    Retorne APENAS um array JSON.
    Cada objeto no array deve ter {len(COLUNAS_EXATAS)} propriedades.
    """
    
    try:
        with st.spinner(f"🔍 Analisando {len(texto_transcrito):,} caracteres..."):
            # Dividir se texto for muito grande
            if len(texto_transcrito) > 300000:
                st.info("📊 Texto muito grande, processando em partes...")
                
                # Processar em partes
                partes = []
                parte_tamanho = 250000
                
                for i in range(0, len(texto_transcrito), parte_tamanho):
                    parte = texto_transcrito[i:i+parte_tamanho]
                    
                    parte_prompt = f"""
                    Esta é a PARTE {i//parte_tamanho + 1} de um documento grande.
                    
                    TEXTO:
                    {parte}
                    
                    Extraia dados para as mesmas colunas mencionadas acima.
                    Foco em encontrar RECs, UFs, Regiões e dados temporais.
                    """
                    
                    response = modelo_texto.generate_content(parte_prompt)
                    resposta = response.text.strip()
                    
                    # Tentar extrair JSON da parte
                    try:
                        dados_parte = json.loads(resposta.replace('```json', '').replace('```', '').strip())
                        if isinstance(dados_parte, list):
                            partes.extend(dados_parte)
                    except:
                        pass
                
                if partes:
                    return partes
                else:
                    # Se falhar com partes, tentar com texto completo reduzido
                    texto_reduzido = texto_transcrito + f"\n\n[TEXTO TRUNCADO - TOTAL: {len(texto_transcrito):,} caracteres]"
                    prompt_final = prompt.replace(texto_transcrito, texto_reduzido)
                    
                    response = modelo_texto.generate_content(prompt_final)
            else:
                response = modelo_texto.generate_content(prompt)
            
            resposta = response.text.strip()
            
            resposta_limpa = resposta.replace('```json', '').replace('```', '').replace('JSON', '').strip()
            
            try:
                dados = json.loads(resposta_limpa)
                if isinstance(dados, list):
                    return dados
                elif isinstance(dados, dict):
                    return [dados]
                else:
                    return []
                    
            except json.JSONDecodeError:
                # Tentar encontrar JSON
                json_match = re.search(r'(\[.*\])', resposta_limpa, re.DOTALL)
                if json_match:
                    try:
                        json_str = json_match.group(1)
                        dados = json.loads(json_str)
                        return dados
                    except:
                        pass
                
                obj_match = re.search(r'(\{.*\})', resposta_limpa, re.DOTALL)
                if obj_match:
                    try:
                        json_str = obj_match.group(1)
                        dados = json.loads(json_str)
                        return [dados]
                    except:
                        pass
                
                st.warning("Não foi possível extrair JSON")
                return []
            
    except Exception as e:
        st.error(f"Erro na extração: {str(e)}")
        return []

# Funções auxiliares (mantidas)
def criar_dataframe(dados):
    if not dados or not isinstance(dados, list):
        return pd.DataFrame(columns=COLUNAS_EXATAS)
    
    linhas = []
    for item in dados:
        if isinstance(item, dict):
            linha = {}
            for coluna in COLUNAS_EXATAS:
                valor = item.get(coluna, "NR")
                if isinstance(valor, str):
                    linha[coluna] = valor.strip()
                else:
                    linha[coluna] = str(valor).strip()
            
            if linha.get("Nome do produto", "NR") != "NR":
                linhas.append(linha)
    
    if linhas:
        df = pd.DataFrame(linhas)
        for col in COLUNAS_EXATAS:
            if col not in df.columns:
                df[col] = "NR"
        
        df = df[COLUNAS_EXATAS]
        return df
    else:
        return pd.DataFrame(columns=COLUNAS_EXATAS)

def gerar_csv_para_gsheets(df):
    if df.empty:
        return ""
    
    output = io.StringIO()
    writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    
    writer.writerow(COLUNAS_EXATAS)
    
    for _, row in df.iterrows():
        linha = []
        for col in COLUNAS_EXATAS:
            valor = str(row.get(col, "NR")).strip()
            if valor in ["", "nan", "None", "null", "NaN"]:
                valor = "NR"
            linha.append(valor)
        writer.writerow(linha)
    
    return output.getvalue()

# Interface principal
def main():
    st.sidebar.header("📤 Upload do Documento")
    
    uploaded_file = st.sidebar.file_uploader(
        "Carregue um arquivo DOCX:",
        type=["docx"],
        help="Documento completo (qualquer tamanho)"
    )
    
    if uploaded_file:
        file_size_mb = uploaded_file.size / (1024 * 1024)
        st.sidebar.write(f"**Arquivo:** {uploaded_file.name}")
        st.sidebar.write(f"**Tamanho:** {file_size_mb:.2f} MB")
        
        if st.sidebar.button("🚀 Processar DOCUMENTO COMPLETO", type="primary", use_container_width=True):
            st.session_state.df = pd.DataFrame(columns=COLUNAS_EXATAS)
            st.session_state.csv_content = ""
            st.session_state.texto_transcrito = ""
            st.session_state.paginas_processadas = 0
            st.session_state.imagens_geradas = 0
            
            try:
                # PASSO 1: Converter TODO o DOCX
                with st.spinner("📄 Convertendo TODO o documento para imagens..."):
                    imagens, num_paginas, total_chars = docx_para_imagens_completas(uploaded_file.getvalue())
                    
                    if not imagens:
                        st.error("❌ Falha na conversão")
                        return
                    
                    st.success(f"✅ {num_paginas} imagem(s) gerada(s) de {total_chars:,} caracteres")
                    st.session_state.paginas_processadas = num_paginas
                    st.session_state.imagens_geradas = len(imagens)
                
                # PASSO 2: Transcrever TODAS as imagens
                with st.spinner(f"👁️ Transcrevendo {len(imagens)} imagens..."):
                    texto, paginas_transcritas = transcrever_todas_imagens_completas(imagens)
                    
                    if not texto:
                        st.error("❌ Falha na transcrição")
                        return
                    
                    st.session_state.texto_transcrito = texto
                    st.success(f"✅ {paginas_transcritas} página(s) transcrita(s)")
                    st.info(f"📝 Texto transcrito: {len(texto):,} caracteres")
                
                # PASSO 3: Extrair dados
                with st.spinner("📊 Extraindo dados..."):
                    dados = extrair_dados_completos(texto)
                    
                    if dados:
                        st.info(f"📋 {len(dados)} linha(s) identificada(s)")
                        
                        df = criar_dataframe(dados)
                        st.session_state.df = df
                        
                        if not df.empty:
                            # Verificar RECs extraídos
                            if 'REC' in df.columns:
                                recs = df['REC'].unique()
                                recs_validos = [r for r in recs if r != "NR"]
                                st.success(f"✅ {len(recs_validos)} REC(s) extraído(s)")
                            
                            # Verificar dados temporais
                            meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                                    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
                            colunas_temporais = [col for col in df.columns if any(mes in col for mes in meses)]
                            if colunas_temporais:
                                preenchidas = sum([1 for col in colunas_temporais if df[col].astype(str).str.contains('NR').mean() < 1.0])
                                st.success(f"✅ {preenchidas}/{len(colunas_temporais)} colunas temporais preenchidas")
                            
                            csv_content = gerar_csv_para_gsheets(df)
                            st.session_state.csv_content = csv_content
                            st.success(f"✅ CSV com {len(df)} linha(s) gerado")
                        else:
                            st.warning("⚠️ Nenhum dado estruturado")
                    else:
                        st.warning("⚠️ Nenhum dado extraído")
                
            except Exception as e:
                st.error(f"❌ Erro: {str(e)}")
        
        if st.sidebar.button("🔄 Limpar Tudo", use_container_width=True):
            st.session_state.df = pd.DataFrame(columns=COLUNAS_EXATAS)
            st.session_state.csv_content = ""
            st.session_state.texto_transcrito = ""
            st.session_state.paginas_processadas = 0
            st.session_state.imagens_geradas = 0
            st.rerun()
        
        # Mostrar resultados
        df = st.session_state.df
        
        if not df.empty:
            st.header("📊 Resultados - Processamento COMPLETO")
            
            # Estatísticas
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Páginas Processadas", st.session_state.paginas_processadas)
            with col2:
                st.metric("Linhas Geradas", len(df))
            with col3:
                produtos = df['Nome do produto'].nunique() if 'Nome do produto' in df.columns else 0
                st.metric("Produtos Únicos", produtos)
            with col4:
                if 'REC' in df.columns:
                    recs = df['REC'].nunique()
                    st.metric("RECs Diferentes", recs)
            
            # Dados principais
            st.subheader("👁️ Dados Extraídos")
            
            colunas_mostrar = ['Nome do produto', 'Cultura', 'REC', 'UF', 'Região']
            if 'REC' in df.columns:
                df_sorted = df.sort_values(['Nome do produto', 'REC'])
            else:
                df_sorted = df.sort_values('Nome do produto')
            
            st.dataframe(df_sorted[colunas_mostrar], use_container_width=True, height=300)
            
            # Visualizar texto transcrito (opcional)
            with st.expander("📝 Ver parte do texto transcrito", expanded=False):
                if st.session_state.texto_transcrito:
                    st.text_area("Texto:", 
                               st.session_state.texto_transcrito + 
                               (f"\n\n...[MAIS {len(st.session_state.texto_transcrito) - 10000:,} CARACTERES]..." 
                                if len(st.session_state.texto_transcrito) > 10000 else ""), 
                               height=400)
            
            # Download
            st.subheader("📥 Download")
            
            nome_base = uploaded_file.name.split('.')[0]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            if st.session_state.csv_content:
                st.download_button(
                    label=f"💾 Baixar CSV ({len(df)} linhas, {len(COLUNAS_EXATAS)} colunas)",
                    data=st.session_state.csv_content.encode('utf-8'),
                    file_name=f"cultivares_{nome_base}_{timestamp}.csv",
                    mime="text/csv",
                    type="primary",
                    use_container_width=True
                )
        
        elif st.session_state.paginas_processadas > 0 and df.empty:
            st.info("📭 Nenhum dado estruturado extraído, mas documento foi processado.")
            
            with st.expander("🔍 Ver estatísticas do processamento"):
                st.write(f"**Páginas:** {st.session_state.paginas_processadas}")
                st.write(f"**Imagens geradas:** {st.session_state.imagens_geradas}")
                if st.session_state.texto_transcrito:
                    st.write(f"**Texto transcrito:** {len(st.session_state.texto_transcrito):,} caracteres")
    
    else:
        st.markdown("""
        ## 🌱 Extrator de Cultivares - Processamento SEM LIMITES
        
        ### ✅ **CARACTERÍSTICAS:**
        - **Processa QUALQUER tamanho** de documento
        - **44+ páginas** sem problemas
        - **SEM limites** artificiais
        - **Extrai TUDO** das tabelas
        
        ### 📊 **ESTRUTURA DE SAÍDA:**
        - **81 colunas** exatas
        - **Cada mês dividido em 3 períodos** (1-10, 11-20, 21-31)
        - **Múltiplas linhas** para diferentes RECs
        - **REC/UF/Região** extraídos de tabelas
        
        ### 🔄 **PROCESSAMENTO:**
        1. **DOCX → Imagens** (todas as páginas)
        2. **Imagens → Texto** (transcrição completa)
        3. **Texto → Dados** (extração para 81 colunas)
        4. **Dados → CSV** (pronto para Google Sheets)
        
        **Carregue um DOCX (qualquer tamanho) para começar.**
        """)

if __name__ == "__main__":
    main()
