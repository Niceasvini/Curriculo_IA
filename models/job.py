from pydantic import BaseModel, Field, validator
from uuid import uuid4
from datetime import datetime
from typing import Optional, List
import re

class Job(BaseModel):
    """
    Modelo para representar uma vaga de emprego.

    Atributos:
        id: Identificador único (UUID)
        name: Título da vaga
        description: Descrição completa da vaga (incluindo atividades, requisitos)
        main_activities: Atividades principais (opcional, pode estar na description)
        prerequisites: Requisitos obrigatórios (opcional, pode estar na description)
        differentials: Diferenciais desejados (opcional, pode estar na description)
        created_at: Data de criação da vaga
        updated_at: Data da última atualização
        status: Status atual da vaga (active/inactive)
        salary_range: Faixa salarial (opcional)
        tags: Lista de tags para categorização
    """
    id: str = Field(default_factory=lambda: str(uuid4()), description="ID único da vaga")
    name: str = Field(..., description="Título/nome da vaga")
    description: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), 
                          description="Data de criação no formato ISO")
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(), 
                          description="Data de atualização no formato ISO")
    status: str = Field(default="active", pattern="^(active|inactive)$",
                      description="Status da vaga (active/inactive)")

    @validator('name')
    def validate_name(cls, value):
        """Validação do nome da vaga"""
        value = value.strip()
        if not value:
            raise ValueError("O nome da vaga não pode estar vazio")
        if len(value) > 100:
            raise ValueError("O nome da vaga não pode exceder 100 caracteres")
        return value

    @validator('description')
    def validate_description(cls, value):
        """Validação básica da descrição"""
        if value and len(value) > 10000:
            raise ValueError("A descrição não pode exceder 10.000 caracteres")
        return value
    

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Desenvolvedor Python Pleno",
                "description": "Vaga para desenvolvedor Python com experiência em Django...",
                "created_at": "2023-10-01T12:00:00Z",
                "updated_at": "2023-10-01T12:00:00Z",
                "status": "active",
            }
        }