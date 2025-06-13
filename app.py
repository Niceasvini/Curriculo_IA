import logging
import os
import sys
import re
import tempfile
import time
import pytz
from io import BytesIO
from pathlib import Path
from PyPDF2 import PdfReader
from docx import Document
import unicodedata
import streamlit as st
import pandas as pd
import altair as alt
import concurrent.futures
import hashlib
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from database import AnalyseDataBase
from analise import process_with_files
from create_job import JobCreator
from PIL import Image


def normalize_filename(filename: str) -> str:
    # Normaliza Unicode (NFKD) e remove caracteres não ASCII
    nfkd_form = unicodedata.normalize('NFKD', filename)
    only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('ASCII')
    # Remove caracteres indesejados (exemplo: mantém letras, números, _, -, espaços)
    safe_name = re.sub(r'[^a-zA-Z0-9_\-\. ]', '', only_ascii)
    return safe_name.strip()

# --- Início da Configuração de Logging ---

class AsciiOnlyFilter(logging.Filter):
    """
    Filtro de logging que remove todos os caracteres não-ASCII
    da mensagem final que será exibida no console.
    """
    def filter(self, record):
        record.msg = re.sub(r'[^\x00-\x7F]+', '', record.getMessage())
        record.args = ()
        return True

# 1. Pega o logger RAIZ para ter controle total.
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# 2. Remove handlers pré-existentes (do Streamlit, etc.) para evitar conflitos.
if logger.hasHandlers():
    logger.handlers.clear()


# ✅ Define o caminho absoluto de forma segura (compatível com Windows)
try:
    # Tenta usar o diretório atual
    current_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(current_dir, "app.log")
    file_handler = logging.FileHandler(log_path, mode='a', encoding='utf-8')
except (OSError, IOError):
    # Se falhar, usa diretório temporário
    fallback_log_path = os.path.join(tempfile.gettempdir(), "app.log")
    file_handler = logging.FileHandler(fallback_log_path, mode='a', encoding='utf-8')

# Formatter
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# 4. Cria nosso handler de CONSOLE (seguro, com o filtro ASCII)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(formatter)
stream_handler.addFilter(AsciiOnlyFilter())

# 5. Adiciona NOSSOS handlers ao logger raiz.
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

# Para usar no app
log = logging.getLogger(__name__)
log.info("Log iniciado com sucesso.")

# --- Fim da Configuração de Logging ---

# Inicializa o banco de dados
try:
    database = AnalyseDataBase()
    logger.info("Conexão com o banco de dados inicializada com sucesso.")
except Exception as e:
    logger.error(f"Erro fatal ao inicializar banco de dados: {e}")
    st.error("Erro ao inicializar banco de dados: " + str(e))
    st.stop()

def setup_page():
    st.set_page_config(
        layout="wide",
        page_title="Sistema de Recrutamento IA",
        page_icon="🧠"
    )

    logo_path = Path("assets/VMC.png")
    if logo_path.exists():
        logo = Image.open(logo_path)
        st.image(logo, width=200)
    else:
        st.warning("Logo não encontrado no caminho: assets/VMC.png")
        logger.warning("Arquivo de logo não encontrado.")

    st.markdown("""
        <style>
        .stButton>button {
            background-color: #B93A3E;
            color: white;
            font-weight: bold;
        }
        .stButton>button:hover {
            background-color: #E4A230;
            color: black;
        }
        .css-18ni7ap {
            color: #B93A3E !important;
        }
        </style>
    """, unsafe_allow_html=True)

    st.title("📊 Painel de Recrutamento Inteligente")
    st.markdown("""
    ---  
    ### 🚀 Objetivo   
    Este aplicativo tem como objetivo otimizar o processo de recrutamento por meio da análise automática de currículos utilizando Inteligência Artificial. Ele auxilia na seleção de candidatos mais adequados para cada vaga, agilizando a triagem e fornecendo um ranking baseado em scores inteligentes.

    ### ⚙️ Como usar  
    1. Faça o upload dos currículos dos candidatos nos formatos PDF, DOCX ou TXT.  
    2. Insira a descrição da vaga ou o Documento de Conteúdo Funcional (DCF) para análise.  
    3. Aguarde o sistema processar e analisar os currículos automaticamente.  
    4. Selecione a vaga gerada para visualizar os resultados da análise.  
    5. Consulte o ranking dos candidatos com base no score gerado pela IA e realize a avaliação detalhada dos currículos.

    ---  
    """)

    # Função para sanitizar nomes (exemplo)
    def normalize_filename(filename):
        name = filename.strip()
        # Substitui qualquer caractere que não seja letra, número, _ . ou - por _
        name = re.sub(r'[^\w\.\-]', '_', name, flags=re.UNICODE)
        # Evita extensões repetidas tipo arquivo.pdf.pdf
        parts = name.split('.')
        if len(parts) > 2:
            ext = parts[-1]
            prev_ext = parts[-2]
            if ext == prev_ext:
                name = '.'.join(parts[:-1])
        # Garante que tenha extensão, adiciona .pdf por padrão
        if '.' not in name:
            name += '.pdf'
        # Limita tamanho total para 100 caracteres
        if len(name) > 100:
            base, ext = name.rsplit('.', 1)
            base = base[:95]
            name = base + '.' + ext
        return name.lower()
    
    def get_sanitized_name(file_hash, arquivos_sanitizados, file_name):
        # Tenta obter o nome do arquivo
        nome_original = Path(file_name).name if file_name else f"arquivo_sem_nome_{len(arquivos_sanitizados) + 1}.pdf"
        nome_original = normalize_filename(nome_original)
        # Evita nomes duplicados
        if nome_original not in arquivos_sanitizados.values():
            arquivos_sanitizados[file_hash] = nome_original
            return nome_original
        else:
            base = Path(nome_original).stem
            ext = Path(nome_original).suffix
            contador = 2
            novo_nome = f"{base}_{contador}{ext}"
            while novo_nome in arquivos_sanitizados.values():
                contador += 1
                novo_nome = f"{base}_{contador}{ext}"
            arquivos_sanitizados[file_hash] = novo_nome
            return novo_nome
        
    def hash_file_content(file):
        file.seek(0)
        content = file.read()
        file.seek(0)
        return hashlib.md5(content).hexdigest()
    
    def hash_bytes(content_bytes):
        return hashlib.md5(content_bytes).hexdigest()
    

    def main():
        st.subheader("📄 Enviar Currículos para Análise")

        extensoes_permitidas = [".pdf", ".docx", ".txt", ".doc", ".odt"]

        uploaded_files = st.file_uploader(
            "Selecione os arquivos de currículo (PDF, DOCX, TXT):",
            type=None,
            accept_multiple_files=True,
            key="uploader_curriculos"
        )

        if uploaded_files:
            arquivos_sanitizados = {}
            # 1. Ao carregar os arquivos, gere o hash e o nome sanitizado apenas 1 vez e guarde num dict:
            hash_para_nome = {}
            hash_para_arquivo = {}
            for file in uploaded_files:
                file_hash = hash_file_content(file)
                if file_hash not in hash_para_nome:
                    sanitized_name = get_sanitized_name(file_hash, hash_para_nome, file.name)
                    hash_para_nome[file_hash] = sanitized_name
                    hash_para_arquivo[file_hash] = file

            # 2. Filtra arquivos com extensões permitidas
            filtered_hashes = [
                h for h, nome in hash_para_nome.items()
                if any(nome.endswith(ext) for ext in extensoes_permitidas)
            ]
            filtered_files = [hash_para_arquivo[h] for h in filtered_hashes]

            
            arquivos_invalidos_extensao = [
                nome for h, nome in hash_para_nome.items()
                if not any(nome.endswith(ext) for ext in extensoes_permitidas)
            ]

            if arquivos_invalidos_extensao:
                st.warning(f"Alguns arquivos foram ignorados por terem extensões inválidas: {arquivos_invalidos_extensao}")

            arquivos_unicos = {}
            nomes_vistos = set()
            nomes_para_exibir = []

            for f in filtered_files:
                content_bytes = f.read()
                f.seek(0)
                file_hash = hash_bytes(content_bytes) # função que cria hash a partir de bytes
                sanitized_name = get_sanitized_name(file_hash, arquivos_sanitizados, f.name)
                if file_hash not in arquivos_unicos and sanitized_name not in nomes_vistos:
                    arquivos_unicos[file_hash] = BytesIO(content_bytes) # cria um novo stream limpo
                    arquivos_unicos[file_hash].name = sanitized_name # nome sanitizado
                    nomes_vistos.add(sanitized_name)
                    nomes_para_exibir.append(sanitized_name)
                    
            # Agora que nomes_para_exibir está definido, pode mostrar no expander
            st.success(f"{len(filtered_files)} arquivo(s) pronto(s) para análise:")

            with st.expander("📂 Clique para ver a lista de arquivos baixados"):
                for nome in nomes_para_exibir:
                    st.markdown(f"📄 `{f.name}`")

            filtered_files = list(arquivos_unicos.values())

            with st.form("manual_resume_form"):
                st.header("💼 Conteúdo da Vaga")
                texto_manual = st.text_area("Descreva quais são os requisitos da vaga e o que você busca de um candidato ideal:")
                submitted = st.form_submit_button("Analisar Currículo")

            if submitted:
                if not texto_manual.strip():
                    st.warning("Por favor, insira algum conteúdo para análise.")
                else:
                    if 'cache_analise_curriculos' not in st.session_state:
                        st.session_state['cache_analise_curriculos'] = {}

                    cache = st.session_state['cache_analise_curriculos']
                    # Exemplo: criação de vaga (JobCreator é parte externa)
                    jc = JobCreator()
                    vaga = jc.create_job(
                        name=texto_manual.strip().split("\n")[0],
                        description=texto_manual.strip()
                    )
                    logger.info(f"Nova vaga criada: {vaga}")

                    tempos = []
                    falhas = 0
                    sucessos = 0
                    arquivos_falha_analise = []

                    progresso_global = st.empty()

                    def analisar_curriculo(file, i, total, cache, filename):
                        file_hash = hash_file_content(file)
                        sanitized_name = get_sanitized_name(file_hash, arquivos_sanitizados, filename)
                        try:
                            if file_hash in cache:
                                return sanitized_name, "Cache", cache[file_hash], "Sucesso"

                            file_bytes = file.read()
                            file.seek(0)

                            if len(file_bytes) == 0:
                                raise ValueError("Arquivo vazio ou corrompido.")

                            texto_validacao = ""
                            if sanitized_name.endswith(".pdf"):
                                reader = PdfReader(file)
                                texto_validacao = "".join([page.extract_text() or "" for page in reader.pages])
                            elif sanitized_name.endswith((".docx", ".doc")):
                                doc = Document(file)
                                texto_validacao = "\n".join([para.text for para in doc.paragraphs])
                            elif sanitized_name.endswith((".txt", ".odt")):
                                texto_validacao = file_bytes.decode("utf-8", errors="ignore")
                            else:
                                raise ValueError("Extensão não suportada.")

                            if not texto_validacao.strip():
                                raise ValueError("Texto ilegível ou ausente.")

                            file.seek(0)
                            start = time.time()
                            result = process_with_files([file], texto_manual, vaga["id"])
                            end = time.time()

                            if not result or not result.get("sucesso", False):
                                raise ValueError("Falha na análise do currículo.")

                            duracao = max(end - start, 1)
                            cache[file_hash] = duracao  # Armazena tempo no cache
                            return sanitized_name, f"{duracao:.2f} seg", duracao, "Sucesso"

                        except Exception as e:
                            return sanitized_name, str(e), None, "Falha"

                    progresso_global = st.empty()
                    progresso_global.info("⏳ Iniciando análise...")

                    progresso_texto = st.empty()
                    barra_progresso = st.progress(0)
                    progresso_atual = 0
                    total_arquivos = len(filtered_files)
                    inicio_geral = time.time()

                    tempos = []
                    cache = {}
                    sucessos = 0
                    falhas = 0

                    # 🔽 Expander já aberto para acumular os logs
                    expander = st.expander("▶️ Detalhes da análise (clique para expandir)", expanded=True)
                    container_resultados = expander.container()

                    # 🔄 Processa arquivos em paralelo
                    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                        futuros = {
                            executor.submit(analisar_curriculo, f, i, total_arquivos, cache, f.name): f
                            for i, f in enumerate(filtered_files, start=1)
                        }

                        for future in concurrent.futures.as_completed(futuros):
                            sanitized_name, tempo_info, tempo_real, status = future.result()

                            progresso_atual += 1
                            percentual = int((progresso_atual / total_arquivos) * 100)

                            # 🟡 Atualiza barra e status em tempo real
                            progresso_texto.info(f"⏳ Analisando... ({progresso_atual}/{total_arquivos} - {percentual}%)")
                            barra_progresso.progress(progresso_atual / total_arquivos)

                            # 📦 Adiciona resultado ao container dentro do expander
                            with container_resultados:
                                if status == "Sucesso":
                                    tempos.append({
                                        "Currículo": sanitized_name,
                                        "Tempo": tempo_info,
                                        "Status": status
                                    })
                                    # ✅ Mostra mensagem temporária
                                    st.success(f"✅ `{sanitized_name}` analisado em {tempo_info}.")
                                    sucessos += 1
                                else:
                                    tempos.append({
                                        "Currículo": sanitized_name,
                                        "Tempo": "Falha",
                                        "Status": status
                                    })
                                    st.error(f"❌ `{sanitized_name}` falhou: {tempo_info}")
                                    arquivos_falha_analise.append(sanitized_name)
                                    falhas += 1

                    # 🟢 Limpa elementos temporários
                    barra_progresso.empty()
                    progresso_texto.empty()
                    progresso_global.empty()
                    fim_geral = time.time()
                    tempo_total_real = round((fim_geral - inicio_geral) / 60, 2)  # minutos reais


                    # Resumo final dentro da função main:
                total = len(uploaded_files)

                col1, col2, col3 = st.columns(3)
                col1.metric("📊 Total de Currículos", total)
                col2.metric("✅ Sucessos", sucessos)
                col3.metric("❌ Falhas", falhas)

                if arquivos_falha_analise:
                    st.write("### 📋 Resumo da Análise")
                    st.write("### Arquivos Inválidos ou com Falha:")
                    for nome in arquivos_falha_analise:
                        st.write(f"- {nome}")

                if sucessos > 0:
                    media = round(tempo_total_real / sucessos, 2)
                    st.success(
                        f"✅ {sucessos} currículo(s) analisado(s) com sucesso | "
                        f"❌ {falhas} falha(s) | "
                        f"⏱️ Tempo total real: {tempo_total_real} minuto(s)"
                    )
                    st.info(f"⏱️ Tempo médio por currículo (real): {media} minuto(s).")
                else:
                    st.error(f"❌ Todos os {total} currículos falharam na análise.")


    if __name__ == "__main__":
        main()


def get_job_selector(jobs=None):
    if jobs is None:
        jobs = database.get_jobs()

    if not jobs:
        st.warning("Nenhuma vaga cadastrada.")
        return None

    job_names = [job['name'] for job in jobs]
    selected_name = st.selectbox("Selecione a vaga:", job_names, key="vaga_selector")
    selected_job = next((job for job in jobs if job['name'] == selected_name), None)
    
    if selected_job:
        col1, col2 = st.columns([4, 1])
        with col1:
            st.write(f"**Vaga Selecionada:** {selected_job['name']}")
        with col2:
            edit_clicked = st.button("✏️ Editar Vaga")

        if edit_clicked:
            # Busca a descrição atual da vaga no banco de dados
            job_details = database.get_job_details(selected_job['id'])

            with st.form(f"edit_job_form_{selected_job['id']}"):
                novo_nome = st.text_input("Nome da vaga", value=job_details.get('name', ''))
                nova_desc = st.text_area("Descrição da vaga", 
                                         value=job_details.get('description', ''))
                salvar = st.form_submit_button("Salvar Alterações")

            if salvar:
                try:
                    updated_data = {
                        'name': novo_nome,
                        'description': nova_desc
                    }
                    database.update_job(selected_job['id'], updated_data)
                    st.success("✅ Vaga atualizada com sucesso.")
                    time.sleep(1) # Pequeno delay para visualização
                    st.rerun() # Recarrega a página para atualizar o seletor
                except Exception as e:
                    logger.error(f"Erro ao atualizar vaga: {e}")
                    st.error(f"❌ Erro ao atualizar a vaga: {e}")

    return selected_job


def process_candidate_data(data):
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)

    if 'resum_id' not in df.columns:
        st.warning("Dados sem 'resum_id'. Verifique a fonte de dados.")
        logger.warning("Dados de análise recebidos sem a coluna 'resum_id'.")
        return pd.DataFrame()

    df = df.sort_values('score', ascending=False)
    df = df.groupby('resum_id', as_index=False).first()
    df['score'] = pd.to_numeric(df['score'], errors='coerce').round(1)
    df = df.dropna(subset=['score'])
    return df

def create_modern_score_chart(df):
    df = df.rename(columns={'name': 'Nome', 'score': 'Score'})
    top_n = 15
    df_top = df.head(top_n)

    base = alt.Chart(df_top).encode(
        y=alt.Y('Nome:N', sort='-x', title=None, axis=alt.Axis(labelFontSize=12, labelColor='#444')),
        x=alt.X('Score:Q', scale=alt.Scale(domain=[0, 10]), title='Pontuação', axis=alt.Axis(labelFontSize=12, labelColor='#444')),
        tooltip=[
            alt.Tooltip('Nome:N', title='Candidato'),
            alt.Tooltip('Score:Q', title='Score', format='.2f')
        ]
    )

    bars = base.mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5).encode(
        color=alt.Color('Score:Q',
                        scale=alt.Scale(scheme='tealblues'),
                        legend=None)
    )

    text = base.mark_text(
        align='left',
        baseline='middle',
        dx=5,
        fontWeight='bold',
        fontSize=12,
        color='#333'
    ).encode(
        text=alt.Text('Score:Q', format='.1f')
    )

    chart = (bars + text).properties(
        width=600,
        height=30 * top_n,  # 30 px por linha
        title=alt.TitleParams(
            text=f"Top {top_n} Candidatos por Pontuação",
            fontSize=18,
            font='Segoe UI',
            anchor='start',
            color='#222'
        )
    ).configure_view(
        strokeWidth=0
    ).configure_axis(
        grid=False,
        domain=False
    ).configure_title(
        fontWeight='bold'
    )

    return chart


def show_candidate_details(candidate):
    st.subheader(f"📄 Currículo de {candidate.get('Nome', 'Desconhecido')}")

    try:
        resum = database.get_resum_by_id(candidate['resum_id'])
        if not resum:
            st.warning("Currículo não encontrado.")
            logger.warning(f"Tentativa de buscar currículo com resum_id {candidate['resum_id']} falhou.")
            return
    except Exception as e:
        st.error(f"Erro ao buscar currículo: {e}")
        logger.error(f"Exceção ao buscar currículo com resum_id {candidate['resum_id']}: {e}")
        return

    st.markdown(resum.get('content', 'Sem conteúdo'))

    st.markdown("### 🔍 Análise da IA")
    opinion = resum.get('opinion', 'Sem análise')

    if isinstance(opinion, str):
        st.markdown(opinion, unsafe_allow_html=True)
    else:
        st.text(str(opinion))

    st.metric("Pontuação", f"{candidate['Pontuação']:.1f}/10")

    file_path = resum.get('file')
    if file_path and Path(file_path).exists():
        with open(file_path, 'rb') as f:
            st.download_button("⬇️ Baixar Currículo", f, file_name=Path(file_path).name)

def main():
    setup_page()

    jobs = database.get_jobs()
    job = get_job_selector(jobs)

    if job:
        with st.expander("⚠️ Excluir vaga e currículos analisados"):
            st.warning("Esta ação é irreversível. Todos os dados relacionados serão perdidos.")
            if st.button("🗑️ Excluir esta vaga"):
                sucesso = database.delete_job_and_related_data(job['id'])
                if sucesso:
                    st.success("Vaga e dados excluídos com sucesso.")
                    logger.info(f"Vaga '{job['name']}' (ID: {job['id']}) e dados relacionados foram excluídos.")
                    st.rerun()
                else:
                    st.error("Erro ao excluir os dados. Verifique os logs.")
                    logger.error(f"Falha ao tentar excluir a vaga '{job['name']}' (ID: {job['id']}).")

    if not job:
        return

    # Buscar e processar dados
    data = database.get_analysis_by_job_id(job['id'])
    df = process_candidate_data(data)

    if df.empty:
        st.info("Nenhum currículo analisado para essa vaga.")
        return

    # Gráfico de Score
    st.subheader("🎯 Score dos Candidatos")
    st.altair_chart(create_modern_score_chart(df), use_container_width=True)

    # Lista de Currículos com AgGrid
    st.subheader("📋 Lista de Currículos Analisados")

    # Copia do df original com todas as colunas (inclusive resum_id, id, job_id)
    df_original = df.copy()

    # Renomear colunas para português, se quiser
    df_original = df_original.rename(columns={
        'name': 'Nome',
        'email': 'Email',
        'created_at': 'Data de Criação',
        'score': 'Pontuação'
    })

    # Converta para datetime e force timezone UTC (caso não tenha)
    df_original['Data de Criação'] = pd.to_datetime(df_original['Data de Criação'], errors='coerce')

    # Se não tiver timezone, defina como UTC
    if df_original['Data de Criação'].dt.tz is None:
        df_original['Data de Criação'] = df_original['Data de Criação'].dt.tz_localize('UTC')

    # Converta para fuso horário de São Paulo
    df_original['Data de Criação'] = df_original['Data de Criação'].dt.tz_convert('America/Sao_Paulo')

    # Formate para exibir no padrão desejado
    df_original['Data de Criação'] = df_original['Data de Criação'].dt.strftime('%d/%m/%Y - %H:%M')

    # Cria a versão para exibição (removendo colunas técnicas)
    df_display = df_original.drop(columns=['resum_id', 'id', 'job_id','skills', 'education', 'language'])

    # Configurações do AgGrid
    gb = GridOptionsBuilder.from_dataframe(df_display)
    gb.configure_selection('single', use_checkbox=True)
    gb.configure_default_column(sortable=True)

    # Força ordenação por pontuação decrescente
    grid_options = gb.build()
    grid_options['sortModel'] = [{'colId': 'Pontuação', 'sort': 'desc'}]

    # Exibe a tabela
    grid_response = AgGrid(
        df_display,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        allow_unsafe_jscode=True,
        fit_columns_on_grid_load=True
    )

   # Verifica e exibe detalhes se alguém for selecionado
    selected_rows = grid_response.get('selected_rows')

    if selected_rows is not None:
        if isinstance(selected_rows, pd.DataFrame):
            selected_rows = selected_rows.to_dict(orient='records')

        if isinstance(selected_rows, list) and len(selected_rows) > 0:
            selected_nome = selected_rows[0].get('Nome')
            if selected_nome:
                selected_index = df_display[df_display['Nome'] == selected_nome].index[0]
                candidate = df_original.iloc[selected_index]
                show_candidate_details(candidate)

if __name__ == "__main__":
    main()