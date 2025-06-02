import uuid
import logging
import re
from typing import List, Optional, Dict, Union
from pathlib import Path
from database import AnalyseDataBase
from models.job import Job

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    encoding='utf-8',
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class JobCreator:
    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        """Inicializa a conexão com o banco de dados."""
        self.db = AnalyseDataBase(db_path) if db_path else AnalyseDataBase()
    
    def create_job(
        self,
        name: str,
    ) -> Dict:
        """
        Cria uma nova vaga de emprego e salva no banco.
        Retorna um dicionário com os dados da vaga criada ou existente.
        """
        try:
            cleaned_data = self._clean_job_data(
                name or []
            )
            
            # Verifica se já existe vaga com esse nome
            existing_job = self.db.get_job_by_name(cleaned_data['name'])
            if existing_job:
                logger.info(f"Vaga já existente: {cleaned_data['name']}")
                return existing_job
            
            # Cria a vaga
            new_job = Job(**cleaned_data)
            self.db.insert_job(new_job.model_dump())
            logger.info(f"Vaga criada com ID: {new_job.id}")
            return new_job.model_dump()
        
        except Exception as e:
            logger.error(f"Erro ao criar vaga: {e}", exc_info=True)
            raise

    def _clean_job_data(
        self,
        name: str
    ) -> Dict:
        """Valida e limpa os dados da vaga."""
        cleaned = {
            'id': str(uuid.uuid4()),
            'name': self._clean_name(name)
        }
        
        # Checa campos obrigatórios
        if not all([cleaned['name']]):
            raise ValueError("Campos obrigatórios (nome, atividades, pré-requisitos, diferenciais) não podem estar vazios.")
        
        return cleaned
    
    @staticmethod
    def _clean_name(name: str) -> str:
        name = re.sub(r'\s+', ' ', name.strip())
        if not name:
            raise ValueError("Nome da vaga não pode ser vazio")
        
        return name
    
    @staticmethod
    def _clean_text(text: str) -> str:
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        return '\n'.join(lines) or ''
    
    @staticmethod
    def _validate_salary(salary: Optional[str]) -> Optional[str]:
        if salary:
            pattern = r'^R?\$?\s*\d+[\d.,]*(?:\s*-\s*R?\$?\s*\d+[\d.,]*)?$'
            if not re.match(pattern, salary):
                raise ValueError("Formato de salário inválido. Exemplo válido: 'R$ 3000 - R$ 5000'")
        return salary
    
    @staticmethod
    def _clean_tag(tag: str) -> str:
        tag = tag.strip().lower()
        return tag

# Teste rápido (opcional) - se rodar diretamente
if __name__ == "__main__":
    jc = JobCreator()
    vaga = jc.create_job(
        name="Analista de Dados"
        
    )
    jc.create_job(
        name="Diretor Comercial"
    )
    print("Vaga criada:", vaga)
