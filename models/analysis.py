from pydantic import BaseModel, Field, validator, EmailStr
from typing import List, Optional
from uuid import uuid4
from datetime import datetime

class Analysis(BaseModel):
    """
    Modelo de dados para análise de currículos.

    Atributos:
        id: Identificador único (UUID)
        job_id: ID da vaga relacionada
        resum_id: ID do resumo do currículo
        name: Nome do candidato
        email: E-mail do candidato (opcional)
        skills: Lista de habilidades
        education: Lista de formações acadêmicas
        language: Lista de idiomas
        score: Pontuação do candidato (0-10)
        created_at: Data de criação do registro
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    job_id: str
    resum_id: str
    name: str
    email: Optional[EmailStr] = None
    skills: List[str] = Field(default_factory=list)
    education: List[str] = Field(default_factory=list)
    language: List[str] = Field(default_factory=list)
    score: float = Field(ge=0, le=10)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    @validator('name')
    def validate_name(cls, value):
        if not value.strip():
            raise ValueError("O nome não pode estar vazio")
        return value.strip()

    @validator('skills', 'education', 'language', each_item=True)
    def validate_list_items(cls, value):
        if not value.strip():
            raise ValueError("Itens da lista não podem ser vazios")
        return value.strip()

    @validator('score')
    def round_score(cls, value):
        return round(value, 1)

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                "resum_id": "123e4567-e89b-12d3-a456-426614174001",
                "name": "João Silva",
                "email": "joao@email.com",
                "skills": ["Python", "Análise Financeira"],
                "education": ["Bacharelado em Administração"],
                "language": ["Inglês Avançado"],
                "score": 8.5,
                "created_at": "2023-10-01T12:00:00Z"
            }
        }
