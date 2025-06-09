import os
import pytz
import time
import sys
import logging
import re
import threading
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

    st.subheader("📄 Enviar Currículos para Análise")
    uploaded_files = st.file_uploader(
        "Selecione os arquivos de currículo (PDF, DOCX, TXT):",
        type=["pdf", "PDF", "docx", "DOCX", "txt", "TXT", "doc", "DOC", "odt", "ODT"],
        accept_multiple_files=True
    )

    
    

    if uploaded_files:
        with st.form("manual_resume_form"):
            st.header("💼 Conteúdo da Vaga")
            texto_manual = st.text_area("Descreva quais são os requisitos da vaga e o que você busca de um candidato ideal:")
            submitted = st.form_submit_button("Analisar Currículo")

        def simulate_progress(duration_seconds, progress_placeholder):
            """Simula progresso de 0 a 100% durante a duração estimada"""
            steps = 20  # número de passos para a barra
            sleep_time = duration_seconds / steps
            for i in range(steps + 1):
                percent = int(i * 100 / steps)
                progress_placeholder.progress(percent)
                time.sleep(sleep_time)

        if submitted:
            if not texto_manual.strip():
                st.warning("Por favor, insira algum conteúdo para análise.")
            else:
                jc = JobCreator()
                vaga = jc.create_job(
                    name=texto_manual.strip().split("\n")[0]
                )
                logger.info(f"Nova vaga criada: {vaga}")

                tempos = []  # Lista para armazenar dados
                falhas = 0

                # Interação visual durante análise
                for i, file in enumerate(uploaded_files, start=1):
                    progresso_barra = st.progress(0, text=f"📄 Currículo {i}/{len(uploaded_files)}: `{file.name}` - Iniciando...")
                    status_placeholder = st.empty()

                    start = time.time()

                    try:
                        # Processamento real (bloqueante)
                        process_with_files([file], texto_manual, vaga["id"])

                        end = time.time()
                        duracao = end - start
                        duracao = max(duracao, 1)  # garantir tempo mínimo de 1s

                        # Simula a porcentagem com base no tempo real
                        for p in range(101):
                            progresso_barra.progress(p, text=f"📄 Currículo {i}/{len(uploaded_files)}: `{file.name}` - Analisando... ({p}%)")
                            time.sleep(duracao / 100, 0.03)

                        progresso_barra.empty()

                        # Formata o tempo
                        if duracao >= 60:
                            tempo_formatado = f"{duracao / 60:.2f} min"
                        else:
                            tempo_formatado = f"{duracao:.2f} seg"

                        tempos.append({"Currículo": file.name, "Tempo": tempo_formatado})
                        logger.info(f"⏱️ Currículo `{file.name}` analisado em {tempo_formatado}.")

                        # Exibe mensagem de sucesso por 2 segundos e limpa depois
                        status_placeholder.success(f"✅ `{file.name}` analisado em {tempo_formatado}.")
                        time.sleep(2)
                        status_placeholder.empty()

                    except Exception as e:
                        falhas += 1
                        logger.error(f"❌ Erro ao analisar `{file.name}`: {e}")
                        tempos.append({"Currículo": file.name, "Tempo": "Falha"})
                        progresso_barra.empty()
                        status_placeholder.error(f"❌ Falha ao analisar `{file.name}`.")
                        time.sleep(3)
                        status_placeholder.empty()

                # Ao final, mostra resumo
                total = len(uploaded_files)
                col1, col2 = st.columns(2)
                col1.metric("Currículos analisados", total)
                col2.metric("Falhas na análise", falhas)

                # Tempo total em minutos (somando só os que tiveram sucesso)
                tempo_total = round(
                    sum(
                        float(x["Tempo"].replace(" min", ""))
                        for x in tempos if "min" in x["Tempo"]
                    ) +
                    sum(
                        float(x["Tempo"].replace(" seg", "")) / 60
                        for x in tempos if "seg" in x["Tempo"]
                    )
                )

                st.success(f"✅ Todos os currículos foram analisados em {tempo_total} minuto(s) somados.")

                curriculos_sucesso = [x for x in tempos if x["Tempo"] != "Falha"]
                if curriculos_sucesso:  # evitar divisão por zero
                    media = round(tempo_total / len(curriculos_sucesso), 2)
                    st.info(f"⏱️ Tempo médio por currículo: {media} minuto(s).")


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
            with st.form(f"edit_job_form_{selected_job['id']}"):
                novo_nome = st.text_input("Nome da vaga", value=selected_job['name'])
                nova_desc = st.text_area("Descrição da vaga", value=selected_job.get('description', ''))
                salvar = st.form_submit_button("Salvar Alterações")

            if salvar:
                try:
                    database.update_job(
                        job_id=selected_job['id'],
                        name=novo_nome,
                        description=nova_desc
                    )
                    st.success("✅ Vaga atualizada com sucesso.")
                    st.experimental_rerun()  # Recarrega a página para atualizar o seletor
                except Exception as e:
                    logger.error(f"Erro ao atualizar vaga: {e}")
                    st.error(f"❌ Erro ao atualizar a vaga: {e}")

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

    # Ajustar formato da data para dd/mm/yyyy - HH:MM
    # Ajustar Data de Criação para datetime com timezone UTC (ou o timezone original correto)
    df_original['Data de Criação'] = pd.to_datetime(df_original['Data de Criação'], utc=True)
    # Converter para timezone de São Paulo
    df_original['Data de Criação'] = df_original['Data de Criação'].dt.tz_convert('America/Sao_Paulo')
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