from googleapiclient.discovery import build, Resource
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from pathlib import Path
import os
import logging
import re
from typing import List, Dict

# Configuração de logging
logging.basicConfig(level=logging.INFO,encoding='utf-8')
logger = logging.getLogger(__name__)

# Constantes
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
FOLDER_ID = '1AkeQrEfjYx1inZdnYrcxDQ21jBVlcHKK'
OUTPUT_DIR = Path(__file__).parent.parent / 'curriculos'

def sanitize_filename(filename: str) -> str:
    """Remove caracteres inválidos para nomes de arquivo no sistema."""
    # Remove tudo que não for letra, número, espaço, ponto, hífen ou underline
    sanitized = re.sub(r'[^a-zA-Z0-9\s\.\-_]', '', filename)
    return sanitized.strip()

def initialize_service(token_path: str = 'token.json') -> Resource:
    """Inicializa o serviço do Google Drive."""
    if not Path(token_path).exists():
        raise FileNotFoundError(f"Arquivo de token não encontrado: {token_path}")
    
    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    return build('drive', 'v3', credentials=creds)

def get_files_from_folder(service: Resource, folder_id: str) -> List[Dict]:
    """Lista arquivos de uma pasta específica no Google Drive."""
    try:
        results = service.files().list(
            q=f"'{folder_id}' in parents and mimeType='application/pdf'",
            fields='files(id, name, mimeType)'
        ).execute()
        return results.get('files', [])
    except Exception as e:
        logger.error(f"Erro ao listar arquivos: {e}")
        raise

def download_file(service: Resource, file_id: str, file_name: str, output_dir: Path) -> str:
    """Faz download de um arquivo específico."""
    sanitized_name = sanitize_filename(file_name)
    file_path = output_dir / sanitized_name
    
    try:
        request = service.files().get_media(fileId=file_id)
        with open(file_path, 'wb') as file:
            downloader = MediaIoBaseDownload(file, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        return str(file_path)
    except Exception as e:
        logger.error(f"Erro ao baixar {file_name}: {e}")
        if file_path.exists():
            file_path.unlink()  # Remove arquivo parcialmente baixado
        raise

def main():
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        service = initialize_service()
        files = get_files_from_folder(service, FOLDER_ID)
        
        if not files:
            logger.warning("Nenhum arquivo PDF encontrado na pasta especificada")
            return
        
        for f in files:
            file_path = download_file(service, f['id'], f['name'], OUTPUT_DIR)
            logger.info(f"Arquivo baixado com sucesso: {file_path}")
            
    except Exception as e:
        logger.error(f"Erro no processo de download: {e}")
        raise

if __name__ == "__main__":
    main()
