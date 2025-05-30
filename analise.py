import uuid
import os
import re
import logging
import re
from tinydb import Query
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from dotenv import load_dotenv
from database import AnalyseDataBase
from ai import DeepSeekClient
from models.resum import Resum
from models.file import File
from models.analysis import Analysis
from time import sleep
import fitz  # PyMuPDF

# Carrega variáveis de ambiente
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('analysis.log', mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

File = Query()

def extract_text_from_pdf(uploaded_file) -> str:
    try:
        # uploaded_file é um UploadedFile do Streamlit
        file_bytes = uploaded_file.read()  # lê os bytes
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        
        text = ""
        for page in doc:
            text += page.get_text()
        return text.strip()

    except Exception as e:
        logger.error(f"Erro ao extrair texto do PDF: {str(e)}")
        return ""

def format_nome(nome_cru: str) -> str:
    # Remove underscores, hífens, pontos, se houver
    nome_limpo = re.sub(r'[_\-.]', ' ', nome_cru)

    # Tenta separar nomes colados em camelCase ou PascalCase
    nome_formatado = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', nome_limpo)

    # Quebra também nomes compostos com maiúsculas seguidas (ex: SouzaCorreia)
    nome_formatado = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', ' ', nome_formatado)

    # Substitui múltiplos espaços por um único
    nome_formatado = re.sub(r'\s+', ' ', nome_formatado)

    # Corrige acentuação comum
    correcoes = {
        'Antonio': 'Antônio',
        'Jose': 'José',
        'Joao': 'João',
        'De': 'de',
        'Da': 'da',
        'Do': 'do',
        'Dos': 'dos',
        'Das': 'das',
    }
    # Substitui palavras com correção de maiúsculas e minúsculas
    palavras = nome_formatado.split(' ')
    palavras_corrigidas = [correcoes.get(palavra.capitalize(), palavra) for palavra in palavras]

    # Junta tudo com espaços e capitaliza somente a primeira letra de nomes próprios, preservando preposições minúsculas
    nome_final = []
    for palavra in palavras_corrigidas:
        if palavra.lower() in ['de', 'da', 'do', 'dos', 'das']:
            nome_final.append(palavra.lower())
        else:
            nome_final.append(palavra.capitalize())

    return ' '.join(nome_final).strip()

def extract_name(content: str, fallback: str, uploaded_file) -> str:
    if uploaded_file and uploaded_file.name:
        filename = uploaded_file.name
        name = os.path.splitext(filename)[0]

        # Remove prefixo "Currículo" ou "curriculo" com ou sem acento
        name = re.sub(r'(?i)^curr[ií]culo', '', name).strip()

        return format_nome(name)

    return fallback


def extract_email(content: str) -> str:
    match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', content)
    return match.group(0) if match else ""

def process_candidate(ai: DeepSeekClient, database: AnalyseDataBase, job: Dict, file) -> Optional[Dict]:
    
    try:
        logger.info(f"📄 Processando: {file.name}")
        
        

        # # ✅ Verifica se já foi processado antes
        # existing_resum = database.files.search(File.file_path == abs_path )
        # if any(resum.get("job_id") == job['id'] for resum in existing_resum):
        #     logger.warning(f"⚠️ Arquivo já processado anteriormente. Ignorando: {filename}")
        #     return {
        #         'file': filename,
        #         'resum_id': existing_resum["resum_id"],
        #         'status': 'skipped'
        #     } 

        content = extract_text_from_pdf(file)
        if not content or len(content.strip()) < 50:
            raise ValueError("❌ PDF vazio ou ilegível")

        name = extract_name(content, file.name.split('.')[0], uploaded_file=file)
        email = extract_email(content)

        # 🔍 Geração via IA
        resum_text, opinion, score = ai.analyze_cv(content, job)

        if score is None:
            raise ValueError("❌ Score retornou None")

        # 🔢 Geração de IDs
        resum_id = str(uuid.uuid4())

        job_id = job['id']

        # ✅ Dados estruturados
        resum_data = Resum(
            id=resum_id,
            job_id=job['id'],
            content=resum_text,
            file=file.name,
            opinion=opinion,
            candidate_name=name,
            email=email,
            score=round(float(score), 1),
            processed_at=datetime.now().isoformat()
        )

        analysis_data = Analysis(
            id=str(uuid.uuid4()),
            resum_id=resum_id,
            job_id=job['id'],
            name=name,
            email=email,
            score=round(float(score), 1),
            created_at=datetime.now().isoformat(),
            skills=[],
            education=[],
            language=[]
        )

        file_data = {
            "id":str(uuid.uuid4()),
            "job_id":job_id,
            "resum_id":resum_id,
            "original_name":file.name,
            "file_path":file.name,
            "created_at":datetime.now().isoformat()
        }

        # 💾 Inserção no banco
        database.insert_resum(resum_data.model_dump())
        database.insert_analysis(analysis_data.model_dump())
        database.insert_file(file_data)

        logger.info(f"✅ Currículo '{name}' processado e salvo com ID: {resum_id}")

        return {
            'file': file.name,
            'score': score,
            'resum_id': resum_id,
            'status': 'success'
        }

    except Exception as e:
        logger.error(f"❌ Erro ao processar {file.name}: {str(e)}", exc_info=True)
        return {
            'file': file.name,
            'error': str(e),
            'status': 'failed'
        }


def process_with_files(files, job_description: str,job_id):
    ai = DeepSeekClient()
    database = AnalyseDataBase()
    job = {"id":job_id,
           "name": job_description}
    
    for file in files:
        process_candidate(ai, database, job, file)


def main():
    ai = DeepSeekClient()
    database = AnalyseDataBase()

    # 📌 Buscar vaga
    jobs = database.get_jobs()
    if not jobs:
        raise ValueError("❌ Nenhum job foi encontrado no banco de dados.")

    # 📁 Coletar arquivos PDF
    pdf_dir = 'curriculos'
    files = [os.path.join(pdf_dir, f) for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]

    if not files:
        print("⚠️ Nenhum currículo encontrado na pasta 'curriculos'")
        return

    print(f"📥 {len(files)} currículo(s) encontrado(s). Iniciando processamento...\n")

    success_count = 0
    failure_count = 0
    skipped_count = 0
    results = []

    for i, file in enumerate(files, 1):
        print(f"🔄 [{i}/{len(files)}] Processando: {os.path.basename(file)}")
        for job in jobs:
            print(f" {job} - Vaga: {job['name']}")
            result = process_candidate(ai, database, job, file)
            results.append(result)

            if result["status"] == "success":
                success_count += 1
            elif result["status"] == "skipped":
                skipped_count += 1
                print(f"⏩ Pulado: {result['file']} (já processado)")
            else:
                failure_count += 1
                print(f"❌ Erro no arquivo {result['file']}: {result.get('error', 'Erro desconhecido')}")

            sleep(1.5)  # Evita sobrecarga na API

    print("\n✅ Processamento finalizado!")
    print(f"✔️ Sucesso: {success_count}")
    print(f"⏩ Pulados: {skipped_count}")
    print(f"❌ Falhas: {failure_count}")

    if failure_count > 0:
        print("\n🧾 Resumo de falhas:")
        for r in results:
            if r["status"] == "failed":
                print(f"- {r['file']}: {r.get('error')}")

if __name__ == "__main__":
    main()
