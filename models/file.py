from pydantic import BaseModel, Field, validator
from uuid import uuid4
from datetime import datetime
from typing import Optional
from pathlib import Path
import re

class File(BaseModel):
    """
    Modelo para armazenar metadados de arquivos de currículos.

    Atributos:
        file_id: Identificador único do arquivo (UUID)
        job_id: ID da vaga relacionada (opcional)
        resum_id: ID do resumo vinculado (opcional)
        original_name: Nome original do arquivo
        file_path: Caminho completo do arquivo no sistema
        file_type: Tipo do arquivo (pdf, docx, etc.)
        created_at: Data de criação do registro
        size_kb: Tamanho do arquivo em KB (opcional)
    """
    file_id: str = Field(default_factory=lambda: str(uuid4()))
    job_id: Optional[str] = None
    resum_id: str
    original_name: str
    file_path: str
    file_type: str = "pdf"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    size_kb: Optional[float] = None

    @validator('file_path')
    def validate_file_path(cls, value):
        """Valida o caminho e a extensão do arquivo"""
        path = Path(value)
        if not path.suffix:
            raise ValueError("O caminho do arquivo deve incluir a extensão")
        if not path.exists():
            raise ValueError("Arquivo não encontrado no caminho especificado")
        return str(path.absolute())

    @validator('file_type')
    def validate_file_type(cls, value, values):
        """Verifica se o tipo de arquivo é suportado e coerente com a extensão"""
        supported_types = ['pdf', 'docx', 'txt']
        file_type = value.lower()

        if file_type not in supported_types:
            raise ValueError(f"Tipo de arquivo não suportado. Use: {', '.join(supported_types)}")

        file_path = values.get('file_path')
        if file_path:
            ext = Path(file_path).suffix[1:].lower()
            if ext and ext != file_type:
                raise ValueError(f"Tipo de arquivo '{file_type}' não corresponde à extensão '.{ext}'")

        return file_type

    @validator('original_name')
    def validate_original_name(cls, value):
        """Remove caracteres inválidos do nome original do arquivo"""
        cleaned = re.sub(r'[\\/*?:"<>|]', "", value).strip()
        if not cleaned:
            raise ValueError("Nome do arquivo não pode ser vazio")
        return cleaned

    @validator('size_kb', always=True)
    def set_size_kb(cls, value, values):
        """Calcula o tamanho do arquivo em KB se não fornecido"""
        if value is None:
            file_path = values.get('file_path')
            try:
                path = Path(file_path)
                if path.exists():
                    return round(path.stat().st_size / 1024, 2)
            except Exception:
                pass
        return value

    class Config:
        json_schema_extra = {
            "example": {
                "file_id": "550e8400-e29b-41d4-a716-446655440000",
                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                "resum_id": "123e4567-e89b-12d3-a456-426614174001",
                "original_name": "Curriculo_Joao_Silva.pdf",
                "file_path": "/caminho/para/arquivo.pdf",
                "file_type": "pdf",
                "created_at": "2023-10-01T12:00:00Z",
                "size_kb": 125.5
            }
        }
