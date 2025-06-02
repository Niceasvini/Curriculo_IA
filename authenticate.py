import os
import logging
from pathlib import Path
from typing import Optional, Tuple
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    encoding='utf-8',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Escopos de acesso otimizados (drive.readonly já inclui os outros)
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

def authenticate_google_drive(
    credentials_path: str,
    token_path: str = 'token.json',
    port: int = 0
) -> Tuple[Optional[Credentials], bool]:
    """
    Autentica com a API do Google Drive usando OAuth 2.0 com tratamento robusto de erros.
    
    Args:
        credentials_path: Caminho para o arquivo credentials.json
        token_path: Caminho para salvar/ler o token (default: token.json)
        port: Porta para o servidor local (0 = porta aleatória)
        
    Returns:
        Tuple contendo:
        - Credenciais válidas (ou None se falhar)
        - Booleano indicando se foi necessário novo login
        
    Raises:
        FileNotFoundError: Se credentials.json não existir
    """
    creds = None
    token_path = Path(token_path)
    credentials_path = Path(credentials_path)
    new_auth = False

    # 1. Tentar carregar token existente
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            logger.info("Token carregado do arquivo")
            
            # Verificar se o token está expirado
            if creds.expired:
                logger.info("Token expirado, tentando renovar...")
                try:
                    creds.refresh(Request())
                    logger.info("Token renovado com sucesso")
                except RefreshError as e:
                    logger.warning(f"Falha ao renovar token: {e}")
                    logger.info("Removendo token inválido...")
                    token_path.unlink(missing_ok=True)
                    creds = None
                except Exception as e:
                    logger.error(f"Erro inesperado ao renovar token: {e}")
                    creds = None
        except Exception as e:
            logger.error(f"Erro ao carregar token: {e}")
            token_path.unlink(missing_ok=True)
            creds = None

    # 2. Se não temos credenciais válidas, fazer novo login
    if not creds or not creds.valid:
        if not credentials_path.exists():
            raise FileNotFoundError(
                f"Arquivo de credenciais não encontrado: {credentials_path}"
            )

        logger.info("Iniciando novo fluxo de autenticação...")
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, SCOPES
            )
            creds = flow.run_local_server(
                port=port,
                authorization_prompt_message='Por favor, autorize o acesso visitando esta URL: {url}',
                success_message='Autenticação concluída! Você pode fechar esta janela.',
                open_browser=True
            )
            new_auth = True
            logger.info("Novo token gerado com sucesso")
        except Exception as e:
            logger.error(f"Falha na autenticação: {e}")
            return None, False

        # Salvar o novo token
        try:
            with open(token_path, 'w') as token_file:
                token_file.write(creds.to_json())
            logger.info(f"Token salvo em {token_path}")
        except Exception as e:
            logger.error(f"Erro ao salvar token: {e}")

    return creds, new_auth

def main():
    """Exemplo de uso da autenticação"""
    try:
        # Caminhos dos arquivos (usando resolução absoluta)
        base_dir = Path(__file__).parent
        credentials_path = base_dir / 'credenciaisgoogle.json'
        token_path = base_dir / 'token.json'
        
        creds, is_new = authenticate_google_drive(
            credentials_path=str(credentials_path),
            token_path=str(token_path)
        )
        
        if creds:
            logger.info("\nAutenticação bem-sucedida!")
            logger.info(f"Token expira em: {creds.expiry}")
            if is_new:
                logger.info("Foi necessário realizar novo login")
        else:
            logger.error("Falha na autenticação")
            
    except Exception as e:
        logger.error(f"Erro fatal na autenticação: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()