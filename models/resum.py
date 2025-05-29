from pydantic import BaseModel, Field, validator, EmailStr
from uuid import uuid4
from datetime import datetime
from typing import Optional
from pathlib import Path
import re

class Resum(BaseModel):
    """
    Modelo para representar o resumo de um currículo analisado.
    
    Atributos:
        id: Identificador único (UUID)
        job_id: ID da vaga relacionada
        content: Conteúdo do resumo formatado
        opinion: Análise crítica do currículo
        file: Caminho do arquivo original
        created_at: Data de criação do registro
        updated_at: Data da última atualização
        processed_at: Data de processamento do currículo
        candidate_name: Nome extraído do currículo (opcional)
        email: E-mail do candidato (opcional)
        score: Pontuação atribuída (opcional)
        status: Status do processo (received, analyzed, rejected, hired)
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    job_id: str
    content: str
    opinion: str = Field(default="Análise não disponível")
    file: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    processed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    candidate_name: str
    email: Optional[EmailStr] = None
    score: Optional[float] = Field(None, ge=0, le=10)
    status: str = Field(default="analyzed", pattern="^(received|analyzed|rejected|hired)$")

    @validator('file')
    def validate_file_path(cls, value):
        """Valida o caminho do arquivo"""
        path = Path(value)
        if not path.suffix:
            raise ValueError("O caminho do arquivo deve incluir a extensão")
        return str(path.absolute())

    @validator('content', 'opinion')
    def validate_text_fields(cls, value):
        """Valida campos de texto importantes"""
        if not value.strip():
            raise ValueError("Este campo não pode estar vazio")
        return value.strip()

    @validator('candidate_name')
    def validate_name(cls, value):
        """Limpa e valida nomes de candidatos"""
        if value:
            value = re.sub(r'\s+', ' ', value.strip())
           
        return value or None

    @validator('score')
    def round_score(cls, value):
        """Arredonda a pontuação para 1 casa decimal"""
        if value is not None:
            return round(float(value), 1)
        return None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                "content": "## Nome Completo\nJoão Silva\n...",
                "opinion": "### Pontos Fortes\n...",
                "file": "/caminho/para/curriculo.pdf",
                "created_at": "2023-10-01T12:00:00Z",
                "updated_at": "2023-10-01T12:00:00Z",
                "processed_at": "2023-10-01T12:01:00Z",
                "candidate_name": "João Silva",
                "email": "joao@email.com",
                "score": 8.5,
                "status": "analyzed"
            }
        }
