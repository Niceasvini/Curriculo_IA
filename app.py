import os
import sys
import logging
import re
from pathlib import Path

import streamlit as st
import pandas as pd
import altair as alt
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

from database import AnalyseDataBase
from analise import process_with_files
from create_job import JobCreator
from PIL import Image

# --- Início da Configuração de Logging ---

class AsciiOnlyFilter(logging.Filter):
    """
    Filtro de logging que remove todos os caracteres não-ASCII
    da mensagem final que será exibida no console.
    """
    def filter(self, record):
        original_message = record.getMessage()
        record.msg = re.sub(r'[^\x00-\x7F]+', '', original_message)
        record.args = ()
        return True

# 1. Pega o logger RAIZ para ter controle total.
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# 2. Remove handlers pré-existentes (do Streamlit, etc.) para evitar conflitos.
if root_logger.hasHandlers():
    root_logger.handlers.clear()

# 3. Cria nosso handler de ARQUIVO (completo, com UTF-8)
file_handler = logging.FileHandler('app.log', mode='w', encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# 4. Cria nosso handler de CONSOLE (seguro, com o filtro ASCII)
stream_handler = logging.StreamHandler(stream=sys.stdout)
stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
stream_handler.addFilter(AsciiOnlyFilter())

# 5. Adiciona NOSSOS handlers ao logger raiz.
root_logger.addHandler(file_handler)
root_logger.addHandler(stream_handler)

# Pega o logger para usar no restante da aplicação.
logger = logging.getLogger(__name__)

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
    st.markdown("---")

    st.subheader("📄 Enviar Currículos para Análise")
    uploaded_files = st.file_uploader(
        "Selecione os arquivos de currículo (PDF, DOCX, TXT):",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True
    )

    if uploaded_files:
        with st.form("manual_resume_form"):
            texto_manual = st.text_area("Conteúdo da Vaga:")
            submitted = st.form_submit_button("Analisar Currículo")

        if submitted:
            if not texto_manual.strip():
                st.warning("Por favor, insira algum conteúdo para análise.")
            else:
                jc = JobCreator()
                vaga = jc.create_job(
                    name=texto_manual.strip().split("\n")[0]
                )
                logger.info(f"Nova vaga criada: {vaga}")
                process_with_files(uploaded_files, texto_manual, vaga["id"])

def get_job_selector(jobs=None):
    if jobs is None:
        jobs = database.get_jobs()

    if not jobs:
        st.warning("Nenhuma vaga cadastrada.")
        return None

    job_names = [job['name'] for job in jobs]
    selected_name = st.selectbox("Selecione a vaga:", job_names, key="vaga_selector")
    return next((job for job in jobs if job['name'] == selected_name), None)


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

def create_score_chart(df):
    df = df.rename(columns={'name': 'Nome', 'score': 'Score'})
    chart = alt.Chart(df.head(5)).mark_bar().encode(
        y=alt.Y('Nome:N', sort='-x'),
        x=alt.X('Score:Q', scale=alt.Scale(domain=[0, 10])),
        color=alt.Color('Score:Q', scale=alt.Scale(scheme='redyellowgreen', domain=[0, 10]))
    )
    text = alt.Chart(df.head(5)).mark_text(
        align='left', dx=3, baseline='middle'
    ).encode(
        y=alt.Y('Nome:N', sort='-x'),
        x='Score:Q',
        text=alt.Text('Score:Q', format='.1f')
    )
    return (chart + text).properties(height=500, title="Top 5 Candidatos por Pontuação")

def show_candidate_details(candidate):
    st.subheader(f"📄 Currículo de {candidate.get('name', 'Desconhecido')}")

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

    st.metric("Score", f"{candidate['score']:.1f}/10")

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
    st.altair_chart(create_score_chart(df), use_container_width=True)

    # Lista de Currículos com AgGrid
    st.subheader("📋 Lista de Currículos Analisados")
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_selection('single', use_checkbox=True)
    grid_options = gb.build()

    grid_response = AgGrid(
        df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        allow_unsafe_jscode=True
    )

    # Exibe análise se um candidato for selecionado
    selected_rows = grid_response.get("selected_rows", [])
    if selected_rows is not None and len(selected_rows) > 0:
        candidate = selected_rows.iloc[0].to_dict()
        show_candidate_details(candidate)

if __name__ == "__main__":
    main()