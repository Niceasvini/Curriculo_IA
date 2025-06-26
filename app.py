# app.py
import os
import sys
import re
import tempfile
import time
import fitz
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
from CONFIG.database import AnalyseDataBase
from SERVICES.analise import process_with_files
from SERVICES.create_job import JobCreator
from PIL import Image
from LOGS.log_config import setup_logger


# === CONFIG ===
st.set_page_config(layout="wide", page_title="Sistema de Recrutamento IA", page_icon="🧠")

# --- Início da Configuração de Logging ---
log = setup_logger(__name__, "app.log")
log.info("Log do app iniciado com sucesso.")
# --- Fim da Configuração de Logging ---


# Inicializa o banco de dados
try:
    database = AnalyseDataBase()
    log.info("Conexão com o banco de dados inicializada com sucesso.")
except Exception as e:
    log.error(f"Erro fatal ao inicializar banco de dados: {e}")
    st.error("Erro ao inicializar banco de dados: " + str(e))
    st.stop()


def normalize_filename(filename: str) -> str:
    # Normaliza Unicode (NFKD) e remove caracteres não ASCII
    nfkd_form = unicodedata.normalize('NFKD', filename)
    only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('ASCII')
    # Remove caracteres indesejados (exemplo: mantém letras, números, _, -, espaços)
    safe_name = re.sub(r'[^a-zA-Z0-9_\-\. ]', '', only_ascii)
    return safe_name.strip()

def traduzir_erro(erro_msg):
    """Traduz mensagens de erro comuns para português"""
    traducoes = {
        "User already registered": "Usuário já cadastrado com este email",
        "Invalid email or password": "Email ou senha inválidos",
        "Email not confirmed": "Email não confirmado. Verifique sua caixa de entrada",
        "Invalid login credentials": "Credenciais de login inválidas",
        "Password should be at least 6 characters": "A senha deve ter pelo menos 6 caracteres",
        "Unable to validate email address": "Não foi possível validar o endereço de email",
        "Email rate limit exceeded": "Limite de emails excedido. Tente novamente mais tarde",
        "Invalid email format": "Formato de email inválido",
        "Network error": "Erro de conexão. Verifique sua internet",
        "Database error": "Erro no banco de dados",
        "Authentication failed": "Falha na autenticação",
        "Session expired": "Sessão expirada. Faça login novamente",
        "Access denied": "Acesso negado",
        "Server error": "Erro no servidor",
        "Connection timeout": "Tempo limite de conexão excedido",
        "Invalid request": "Requisição inválida",
        "User not found": "Usuário não encontrado",
        "Email already exists": "Este email já está cadastrado",
        "Weak password": "Senha muito fraca",
        "Password mismatch": "As senhas não coincidem",
        "Required field": "Campo obrigatório",
        "Invalid characters": "Caracteres inválidos",
        "Too many requests": "Muitas tentativas. Aguarde um momento"
    }
    
    erro_str = str(erro_msg).lower()
    
    for eng, pt in traducoes.items():
        if eng.lower() in erro_str:
            return pt
    
    # Se não encontrou tradução específica, retorna a mensagem original
    return str(erro_msg)

def login_page():
    """Página de login profissional e limpa"""
    
    # CSS limpo para login
    st.markdown("""
        <style>
        .stDeployButton {display: none !important;}
        footer {display: none !important;}
        .stDecoration {display: none !important;}
        
        .main .block-container {
            padding-top: 3rem;
            padding-bottom: 2rem;
            max-width: 500px;
            margin: 0 auto;
        }
        
        .login-card {
            background: white;
            padding: 3rem;
            border-radius: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            border: 1px solid #e1e5e9;
            text-align: center;
            margin: 2rem auto;
        }
        
        .login-title {
            color: #333;
            font-size: 1.8rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }
        
        .login-subtitle {
            color: #666;
            margin-bottom: 2rem;
            font-size: 1rem;
        }
        
        .stButton > button {
            width: 100%;
            background: linear-gradient(45deg, #B93A3E, #E4A230);
            color: white;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: 10px;
            font-weight: 600;
            font-size: 1rem;
            margin: 0.5rem 0;
            transition: all 0.3s ease;
        }
        
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 15px rgba(185, 58, 62, 0.3);
        }
        
        .stTextInput > div > div > input {
            border-radius: 10px;
            border: 2px solid #e1e5e9;
            padding: 0.75rem;
            font-size: 1rem;
        }
        
        .stTextInput > div > div > input:focus {
            border-color: #B93A3E;
            box-shadow: 0 0 0 3px rgba(185, 58, 62, 0.1);
        }
        </style>
    """, unsafe_allow_html=True)

    # Container centralizado
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    
    # Logo
    logo_path = Path("assets/VMC.png")
    if logo_path.exists():
        logo = Image.open(logo_path)
        st.image(logo, width=200)
    else:
        st.markdown("### 🏢 Viana & Moura")
    
    # Título
    st.markdown('<h1 class="login-title">Sistema de Recrutamento IA</h1>', unsafe_allow_html=True)
    st.markdown('<p class="login-subtitle">Faça login para acessar o sistema</p>', unsafe_allow_html=True)
    
    # Inicializa estados
    if 'show_register' not in st.session_state:
        st.session_state.show_register = False
    if 'show_forgot_password' not in st.session_state:
        st.session_state.show_forgot_password = False
    if 'email_input' not in st.session_state:
        st.session_state.email_input = ""
    if 'password_input' not in st.session_state:
        st.session_state.password_input = ""

    # 🔄 1️⃣ FORMULÁRIO DE RECUPERAÇÃO DE SENHA
    if st.session_state.show_forgot_password:
        st.markdown("### 🔄 Recuperar Senha")
        with st.form("forgot_password_form", clear_on_submit=True):
            email = st.text_input("📧 Email", placeholder="Digite seu email para recuperação")
            
            col_send, col_back = st.columns(2)
            
            with col_send:
                send_submitted = st.form_submit_button("📧 Enviar", use_container_width=True)

            with col_back:
                back_clicked = st.form_submit_button("⬅️ Voltar", use_container_width=True)

        if back_clicked:
            st.session_state.show_forgot_password = False
            st.rerun()

        if send_submitted:
            if not email:
                st.error("⚠️ Por favor, digite seu email.")
            else:
                try:
                    with st.spinner("📧 Enviando email de recuperação..."):
                        result = database.reset_password(email)
                        if result.get("success"):
                            st.success(result.get("message"))
                            time.sleep(3)
                            st.session_state.show_forgot_password = False
                            st.rerun()
                        else:
                            st.error("❌ Erro ao enviar email de recuperação.")
                except Exception as e:
                    st.error(f"❌ {str(e)}")
    
    # Formulário de Login
    elif not st.session_state.show_register:
        st.markdown("### 🔐 Entrar no Sistema")
        
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("📧 Email", placeholder="Digite seu email")
            password = st.text_input("🔒 Senha", type="password", placeholder="Digite sua senha")
            
            col_login, col_register = st.columns(2)
            
            with col_login:
                login_submitted = st.form_submit_button("🚀 Entrar", use_container_width=True)
            
            with col_register:
                register_clicked = st.form_submit_button("📝 Cadastrar", use_container_width=True)
        
        if register_clicked:
            st.session_state.show_register = True
            st.rerun()
        
        if login_submitted:
            if not email or not password:
                st.error("⚠️ Por favor, preencha todos os campos.")
            else:
                try:
                    with st.spinner("🔄 Verificando credenciais..."):
                        result = database.sign_in(email, password)
                        if result.get("success"):
                            st.session_state.user = result["user"].email
                            st.session_state.logged_in = True
                            st.success("✅ Login realizado com sucesso! Redirecionando...")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ Email ou senha incorretos.")
                except Exception as e:
                    st.error(f"❌ {str(e)}")

        # 👉 ADICIONE O BOTÃO DE ESQUECI MINHA SENHA AQUI
        st.markdown("---")  # linha para separar
        if st.button("Esqueci minha senha?"):
            st.session_state.show_forgot_password = True
            st.rerun()

    else:
        # Formulário de Cadastro
        st.markdown("### 📝 Criar Nova Conta")
        
        with st.form("register_form", clear_on_submit=False):
            email = st.text_input("📧 Email", placeholder="Digite seu email", value=st.session_state.email_input)
            password = st.text_input("🔒 Senha", type="password", placeholder="Digite sua senha", value=st.session_state.password_input)
            password_confirm = st.text_input("🔒 Confirme a Senha", type="password", placeholder="Confirme sua senha")

            # Validação visual da senha em tempo real
            if password:
                st.markdown('<div class="password-requirements">', unsafe_allow_html=True)
                st.markdown("**Requisitos da senha:**")
                
                # Verifica cada requisito
                req_length = len(password) >= 6
                req_not_only_numbers = not password.isdigit()
                req_not_only_letters = not (password.lower() == password and password.isalpha())
                
                st.markdown(f'<div class="requirement {"valid" if req_length else "invalid"}">{"✅" if req_length else "❌"} Pelo menos 6 caracteres</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="requirement {"valid" if req_not_only_numbers else "invalid"}">{"✅" if req_not_only_numbers else "❌"} Não pode conter apenas números</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="requirement {"valid" if req_not_only_letters else "invalid"}">{"✅" if req_not_only_letters else "❌"} Deve conter números ou caracteres especiais</div>', unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)

            
            col_register, col_back = st.columns(2)
            
            with col_register:
                register_submitted = st.form_submit_button("✅ Criar Conta", use_container_width=True)
            
            with col_back:
                back_clicked = st.form_submit_button("⬅️ Voltar", use_container_width=True)
        
        if back_clicked:
            st.session_state.show_register = False
            # ✅ LIMPAR CAMPOS AO VOLTAR
            st.session_state.email_input = ""
            st.session_state.password_input = ""
            st.rerun()
        
        if register_submitted:
            # ✅ ATUALIZAR SESSION STATE COM VALORES ATUAIS
            st.session_state.email_input = email
            st.session_state.password_input = password
            # Validações
            if not email or not password or not password_confirm:
                st.error("⚠️ Por favor, preencha todos os campos.")
            elif password != password_confirm:
                st.error("❌ As senhas não coincidem.")
            else:
                try:
                    # Verifica se o email já está cadastrado
                            with st.spinner("📝 Criando conta..."):
                                result = database.sign_up(email, password)
                                if result.get("success"):
                                    st.success(result.get("message", "Conta criada com sucesso!"))
                                    log.info(f"Nova conta criada para: {email}")
                                    # ✅ LIMPAR CAMPOS APÓS SUCESSO
                                    st.session_state.email_input = ""
                                    st.session_state.password_input = ""
                                    time.sleep(3)
                                    st.session_state.show_register = False
                                    st.rerun()
                                else:
                                    st.error("❌ Erro ao criar conta. Tente novamente.")
                except Exception as e:
                    st.error(f"❌ {str(e)}")
                    log.error(f"Erro no cadastro para {email}: {e}")
            
    st.markdown('</div>', unsafe_allow_html=True)

def setup_page():
    """Configuração da página principal (apenas quando logado)"""
    logo_path = Path("assets/VMC.png")
    if logo_path.exists():
        logo = Image.open(logo_path)
        st.image(logo, width=200)
    else:
        st.warning("Logo não encontrado no caminho: assets/VMC.png")
        log.warning("Arquivo de logo não encontrado.")

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
        </style>
    """, unsafe_allow_html=True)

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

def main_page_authenticated():
    # Header com logout
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        setup_page()
    
    with col3:
        st.markdown(f"**👤 Usuário:** {st.session_state.user}")
        if st.button("🚪 Sair", use_container_width=True):
            # Limpa session state
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

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

    extensoes_permitidas = [".pdf", ".docx", ".txt", ".doc", ".odt"]

    uploaded_files = st.file_uploader(
        "Selecione os arquivos de currículo (PDF, DOCX, TXT):",
        type=None,
        accept_multiple_files=True,
        key="uploader_curriculos"
    )

    # Inicializa estados de sessão
    if 'mostrar_form_vaga' not in st.session_state:
        st.session_state.mostrar_form_vaga = False
    if 'vaga_selecionada_id' not in st.session_state:
        st.session_state.vaga_selecionada_id = None
    if 'mostrar_edicao' not in st.session_state:
        st.session_state.mostrar_edicao = False
    if 'mostrar_exclusao' not in st.session_state:
        st.session_state.mostrar_exclusao = False
    if 'analise_concluida' not in st.session_state:
        st.session_state.analise_concluida = False

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
                st.markdown(f"📄 `{nome}`")

        filtered_files = list(arquivos_unicos.values())

        # 🔧 FORMULÁRIO DE VAGA (só aparece quando necessário)
        if st.session_state.mostrar_form_vaga:
            with st.form("manual_resume_form"):
                st.header("💼 Conteúdo da Vaga")
                texto_manual = st.text_area("Descreva quais são os requisitos da vaga e o que você busca de um candidato ideal:")
                
                col1, col2 = st.columns(2)
                with col1:
                    submitted = st.form_submit_button("✅ Criar Vaga e Analisar")
                with col2:
                    cancelar = st.form_submit_button("❌ Cancelar")

            if cancelar:
                st.session_state.mostrar_form_vaga = False
                st.rerun()

            if submitted:
                if not texto_manual.strip():
                    st.warning("Por favor, insira algum conteúdo para análise.")
                else:
                    # 🔧 LIMPAR CACHE ANTES DE CRIAR NOVA VAGA
                    if 'cache_analise_curriculos' in st.session_state:
                        del st.session_state['cache_analise_curriculos']
                    
                    # Criar nova vaga
                    jc = JobCreator()
                    vaga = jc.create_job(
                        name=texto_manual.strip().split("\n")[0],
                        description=texto_manual.strip()
                    )
                    log.info(f"Nova vaga criada: {vaga}")
                    
                    # Definir como vaga selecionada
                    st.session_state.vaga_selecionada_id = vaga["id"]
                    st.session_state.mostrar_form_vaga = False
                    st.session_state.analise_concluida = False
                    
                    # Processar análise SEM RERUN IMEDIATO
                    sucesso = processar_analise(filtered_files, texto_manual, vaga["id"], arquivos_sanitizados)
                    
                    if sucesso:
                        st.session_state.analise_concluida = True
                        st.balloons()
                        # Aguarda um pouco antes do rerun para garantir que tudo foi salvo
                        time.sleep(2)
                        st.rerun()

    # 🔧 SEÇÃO ÚNICA DE ANÁLISE DE VAGAS (sempre aparece aqui)
    st.markdown("---")
    st.subheader("📊 Análise de Vagas")
    
    jobs = database.get_jobs()
    
    if not jobs:
        st.info("Nenhuma vaga cadastrada.")
        if uploaded_files:
            if st.button("➕ Criar Nova Vaga", use_container_width=True):
                st.session_state.mostrar_form_vaga = True
                st.rerun()
    else:
        # 🔧 LAYOUT MELHORADO DOS BOTÕES
        # Linha 1: Seletor de vagas
        selected_job = None
        job_names = [job['name'] for job in jobs]
        
        # Define índice padrão baseado na vaga selecionada
        default_index = 0
        if st.session_state.vaga_selecionada_id:
            for i, job in enumerate(jobs):
                if job['id'] == st.session_state.vaga_selecionada_id:
                    default_index = i
                    break
        
        selected_name = st.selectbox(
            "Selecione a vaga:", 
            job_names, 
            index=default_index,
            key="vaga_selector"
        )
        selected_job = next((job for job in jobs if job['name'] == selected_name), None)
        
        if selected_job:
            # Linha 2: Informações da vaga + botões de ação
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"**Vaga Selecionada:** {selected_job['name']}")
            
            with col2:
                # Botões organizados verticalmente
                if uploaded_files:
                    if st.button("➕ Nova Vaga", use_container_width=True):
                        st.session_state.mostrar_form_vaga = True
                        st.rerun()
                
                if st.button("✏️ Editar Vaga", use_container_width=True):
                    st.session_state.mostrar_edicao = True
                    st.session_state.mostrar_exclusao = False
                    st.rerun()
                
                if st.button("🗑️ Excluir Vaga", use_container_width=True):
                    st.session_state.mostrar_exclusao = True
                    st.session_state.mostrar_edicao = False
                    st.rerun()

        # 🔧 FORMULÁRIOS DE EDIÇÃO E EXCLUSÃO
        if st.session_state.mostrar_edicao and selected_job:
            editar_vaga(selected_job)
        
        if st.session_state.mostrar_exclusao and selected_job:
            excluir_vaga(selected_job)

        # 🔧 RESULTADOS ÚNICOS (atualizam conforme vaga selecionada)
        if selected_job and not st.session_state.mostrar_edicao and not st.session_state.mostrar_exclusao:
            show_analysis_results(selected_job['id'])

def processar_analise(filtered_files, texto_manual, vaga_id, arquivos_sanitizados):
    """Processa a análise dos currículos - RETORNA SUCESSO/FALHA"""
    
    try:
        # 🔧 CACHE LIMPO PARA NOVA VAGA
        if 'cache_analise_curriculos' not in st.session_state:
            st.session_state['cache_analise_curriculos'] = {}

        # 🔧 NÃO USA CACHE PARA NOVA VAGA - FORÇA ANÁLISE REAL
        cache = {}  # Cache vazio para forçar análise real
        
        tempos = []
        falhas = 0
        sucessos = 0
        arquivos_falha_analise = []

        def analisar_curriculo(file, i, total, cache, filename):
            file_hash = hash_file_content(file)
            sanitized_name = get_sanitized_name(file_hash, arquivos_sanitizados, filename)
            try:
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
                
                # 🔧 LOG PARA DEBUG
                log.info(f"Iniciando análise do arquivo {sanitized_name} para vaga ID {vaga_id}")
                
                result = process_with_files([file], texto_manual, vaga_id)
                end = time.time()

                # 🔧 LOG PARA DEBUG
                log.info(f"Resultado da análise: {result}")

                if not result or not result.get("sucesso", False):
                    raise ValueError("Falha na análise do currículo.")

                duracao = max(end - start, 1)
                return sanitized_name, f"{duracao:.2f} seg", duracao, "Sucesso"

            except Exception as e:
                log.error(f"Erro ao analisar {sanitized_name}: {e}")
                return sanitized_name, str(e), None, "Falha"

        progresso_global = st.empty()
        progresso_global.info("⏳ Iniciando análise...")

        progresso_texto = st.empty()
        barra_progresso = st.progress(0)
        progresso_atual = 0
        total_arquivos = len(filtered_files)
        inicio_geral = time.time()

        # 🔽 Expander já aberto para acumular os logs
        expander = st.expander("▶️ Detalhes da análise (clique para expandir)", expanded=False)
        container_resultados = expander.container()

        # 🔄 Processa arquivos em paralelo
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:  # Reduzido para 4 workers
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

        # Resumo final
        total = len(filtered_files)

        if arquivos_falha_analise:
            st.write("### 📋 Resumo da Análise")
            st.write("### Arquivos Inválidos ou com Falha:")
            for nome in arquivos_falha_analise:
                st.write(f"- {nome}")

        col1, col2, col3 = st.columns(3)
        col1.metric("📊 Total de Currículos", total)
        col2.metric("✅ Sucessos", sucessos)
        col3.metric("❌ Falhas", falhas)

        if sucessos > 0:
            media = round(tempo_total_real / sucessos, 2)
            st.success(
                f"✅ {sucessos} currículo(s) analisado(s) com sucesso | "
                f"❌ {falhas} falha(s) | "
                f"⏱️ Tempo total real: {tempo_total_real} minuto(s)"
            )
            st.info(f"⏱️ Tempo médio por currículo (real): {media} minuto(s).")
            
            # 🔧 LOG PARA DEBUG
            log.info(f"Análise concluída com sucesso. Vaga ID: {vaga_id}, Sucessos: {sucessos}")
            
            return True
        else:
            st.error(f"❌ Todos os {total} currículos falharam na análise.")
            return False
            
    except Exception as e:
        log.error(f"Erro geral na análise: {e}")
        st.error(f"❌ Erro durante a análise: {e}")
        return False

def editar_vaga(selected_job):
    """Edita uma vaga existente"""
    job_details = database.get_job_details(selected_job['id'])

    with st.form(f"edit_job_form_{selected_job['id']}"):
        st.header("✏️ Editar Vaga")
        novo_nome = st.text_input("Nome da vaga", value=job_details.get('name', ''))
        nova_desc = st.text_area("Descrição da vaga", 
                                 value=job_details.get('description', ''))
        
        col1, col2 = st.columns(2)
        with col1:
            salvar = st.form_submit_button("✅ Salvar Alterações")
        with col2:
            cancelar_edit = st.form_submit_button("❌ Cancelar")

    if cancelar_edit:
        st.session_state.mostrar_edicao = False
        st.rerun()

    if salvar:
        try:
            updated_data = {
                'name': novo_nome,
                'description': nova_desc
            }
            database.update_job(selected_job['id'], updated_data)
            st.success("✅ Vaga atualizada com sucesso.")
            st.session_state.mostrar_edicao = False
            time.sleep(1)
            st.rerun()
        except Exception as e:
            log.error(f"Erro ao atualizar vaga: {e}")
            st.error(f"❌ Erro ao atualizar a vaga: {e}")

def excluir_vaga(selected_job):
    """Exclui uma vaga"""
    with st.form(f"delete_job_form_{selected_job['id']}"):
        st.header("🗑️ Excluir Vaga")
        st.warning("⚠️ Esta ação é irreversível. Todos os dados relacionados serão perdidos.")
        st.write(f"**Vaga a ser excluída:** {selected_job['name']}")
        
        col1, col2 = st.columns(2)
        with col1:
            confirmar = st.form_submit_button("🗑️ Confirmar Exclusão")
        with col2:
            cancelar_del = st.form_submit_button("❌ Cancelar")

    if cancelar_del:
        st.session_state.mostrar_exclusao = False
        st.rerun()

    if confirmar:
        try:
            sucesso = database.delete_job_and_related_data(selected_job['id'])
            if sucesso:
                st.success("✅ Vaga e dados excluídos com sucesso.")
                log.info(f"Vaga '{selected_job['name']}' (ID: {selected_job['id']}) e dados relacionados foram excluídos.")
                st.session_state.vaga_selecionada_id = None
                st.session_state.mostrar_exclusao = False
                # 🔧 LIMPAR CACHE APÓS EXCLUSÃO
                if 'cache_analise_curriculos' in st.session_state:
                    del st.session_state['cache_analise_curriculos']
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Erro ao excluir os dados. Verifique os logs.")
                log.error(f"Falha ao tentar excluir a vaga '{selected_job['name']}' (ID: {selected_job['id']}).")
        except Exception as e:
            st.error(f"❌ Erro ao excluir vaga: {e}")
            log.error(f"Exceção ao excluir vaga: {e}")

def process_candidate_data(data):
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)

    if 'resum_id' not in df.columns:
        st.warning("Dados sem 'resum_id'. Verifique a fonte de dados.")
        log.warning("Dados de análise recebidos sem a coluna 'resum_id'.")
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
            log.warning(f"Tentativa de buscar currículo com resum_id {candidate['resum_id']} falhou.")
            return
    except Exception as e:
        st.error(f"Erro ao buscar currículo: {e}")
        log.error(f"Exceção ao buscar currículo com resum_id {candidate['resum_id']}: {e}")
        return

    st.markdown("### 📋 Conteúdo do Currículo")
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

def show_analysis_results(job_id):
    """Mostra os resultados da análise para a vaga selecionada"""
    
    # 🔧 LOG PARA DEBUG
    log.info(f"Buscando resultados para vaga ID: {job_id}")
    
    # Buscar e processar dados
    data = database.get_analysis_by_job_id(job_id)
    
    # 🔧 LOG PARA DEBUG
    log.info(f"Dados encontrados: {len(data) if data else 0} registros")
    
    df = process_candidate_data(data)

    if df.empty:
        st.info("Nenhum currículo analisado para essa vaga.")
        return

    st.markdown("---")
    st.markdown("## 📊 Resultados da Análise")

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

    # Key único
    grid_response = AgGrid(
        df_display,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        allow_unsafe_jscode=True,
        fit_columns_on_grid_load=True,
        key=f"aggrid_results_{job_id}"
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

def main():
    # Inicializa variáveis de sessão
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "user" not in st.session_state:
        st.session_state.user = None
    if "show_register" not in st.session_state:
        st.session_state.show_register = False

    # Página de login/cadastro
    if not st.session_state.logged_in:
        login_page()
        return
    
    # Se chegou aqui, o usuário está logado - mostra TODO o conteúdo
    main_page_authenticated()

if __name__ == "__main__":
    main()