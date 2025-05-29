from pydantic import BaseModel, Field, validator
from uuid import uuid4
from datetime import datetime
from typing import List, Optional
import re

class Job(BaseModel):
    """
    Modelo para representar uma vaga de emprego.

    Atributos:
        id: Identificador único (UUID)
        name: Título da vaga
        main_activities: Descrição das atividades principais
        prerequisites: Requisitos obrigatórios
        differentials: Diferenciais desejados
        created_at: Data de criação da vaga
        updated_at: Data da última atualização
        status: Status atual da vaga (active/inactive)
        salary_range: Faixa salarial (opcional)
        tags: Lista de tags para categorização
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    status: str = Field(default="active", pattern="^(active|inactive)$")

    @validator('name')
    def validate_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("O nome da vaga não pode estar vazio")
        
        return value

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Desenvolvedor Python Pleno",
                "created_at": "2023-10-01T12:00:00Z",
                "updated_at": "2023-10-01T12:00:00Z",
                "status": "active"
            }
        }
