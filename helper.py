import re
import os
import json
import uuid
import logging
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path
import fitz
from colorama import Fore, Style, init
from datetime import datetime

# Inicializa colorama
init()

# Configuração de logging
logging.basicConfig(level=logging.INFO,encoding='utf-8')
logger = logging.getLogger(__name__)

class PDFHelper:

    @staticmethod
    def read_pdf(file_path: str) -> str:
        try:
            text = []
            with fitz.open(file_path) as pdf:
                for page in pdf:
                    text.append(page.get_text())
            return "\n".join(text).strip()
        except Exception as e:
            logger.error(f"Erro ao ler PDF {file_path}: {str(e)}")
            raise

    @staticmethod
    def extract_name(content: str = "", fallback: str = "", file_path: str = "") -> str:
        """
        Extrai o nome baseado no nome do arquivo, ignorando o conteúdo do PDF.
        """
        if file_path:
            filename = os.path.basename(file_path)  # ex: CurrículoALFREDOQUIRINO.pdf
            name_part = os.path.splitext(filename)[0]  # remove extensão -> CurrículoALFREDOQUIRINO
        
            # Remove prefixos comuns, como "Currículo", "curriculo", etc.
            name_part = re.sub(r"(?i)^curr[ií]culo[_\- ]*", "", name_part)
        
            # Insere espaços antes de letras maiúsculas (exceto a primeira letra)
            name_with_spaces = re.sub(r"(?<!^)([A-Z])", r" \1", name_part).strip()
        
            if name_with_spaces:
                return name_with_spaces

        # fallback genérico
        return fallback or "Nome não identificado"


    @staticmethod
    def extract_email(content: str) -> str:
        match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", content)
        return match.group(0) if match else ""

    @staticmethod
    def extract_education(content: str) -> List[Dict[str, str]]:
        pattern = r"""
            (?P<degree>Bacharelado|Licenciatura|Mestrado|Doutorado|MBA|Especializa\u00e7\u00e3o|Gradua\u00e7\u00e3o|T\u00e9cnico)\s+(?:em\s+)?
            (?P<course>[^\n,]+?)\s*
            (?:na\s+|no\s+|@\s+)?
            (?P<institution>[^\n,]+?)\s*
            (?:,\s*|\s+)?
            (?P<period>\d{4}\s*[-\u2013]\s*\d{4}|\d{4}\s*[-\u2013]\s*at\u00e9\s+o\s+presente|\d{4})
            (?:,\s*|\s+)?
            (?P<status>Completo|Incompleto|Em\s+andamento|Conclu\u00eddo)?
        """
        try:
            matches = re.finditer(pattern, content, re.VERBOSE | re.IGNORECASE)
            return [match.groupdict() for match in matches]
        except Exception as e:
            logger.error(f"Erro ao extrair educação: {e}")
            return []

    @staticmethod
    def extract_skills(content: str) -> List[str]:
        section = re.search(r"(?i)(?:habilidades|skills|compet\u00eancias)\s*[:\-\n]*(.*?)\n{2,}", content, re.DOTALL)
        if section:
            skills = re.split(r"[\n,;\-]+", section.group(1))
            return [s.strip() for s in skills if s.strip()]
        return []

    @staticmethod
    def extract_languages(content: str) -> List[Dict[str, str]]:
        pattern = r"""
            (?P<language>Ingl\u00eas|Espanhol|Franc\u00eas|Alem\u00e3o|Italiano|Portugu\u00eas|Chin\u00eas|Japon\u00eas|Russo)\s*
            (?:\(|-\s*)?
            (?P<proficiency>B\u00e1sico|Intermedi\u00e1rio|Avan\u00e7ado|Fluente|Nativo)
            (?:\))?
        """
        try:
            matches = re.finditer(pattern, content, re.VERBOSE | re.IGNORECASE)
            return [match.groupdict() for match in matches]
        except Exception as e:
            logger.error(f"Erro ao extrair idiomas: {e}")
            return []

    @staticmethod
    def extract_experience(content: str) -> List[Dict[str, Any]]:
        try:
            pattern = r"(?P<position>[^@\n]+?)\s*@\s*(?P<company>[^\n,]+)[\s,]*(?P<period>\d{4}\s*-\s*\d{4}|presente)"
            matches = re.finditer(pattern, content, re.IGNORECASE)
            return [match.groupdict() for match in matches]
        except Exception as e:
            logger.error(f"Erro ao extrair experiência: {e}")
            return []

    @staticmethod
    def extract_data_analysis(resum_md: str, job_id: str, resum_id: str, score: float) -> Dict[str, Any]:
        """
        Extrai dados estruturados de um currículo em markdown com análise detalhada.
        
        Args:
            resum_md: Texto do currículo em markdown
            job_id: ID da vaga relacionada
            resum_id: ID do resumo do currículo
            score: Pontuação do currículo
            
        Returns:
            Dicionário com os dados extraídos para criar uma Analysis
            
        Raises:
            ValueError: Se campos obrigatórios estiverem faltando
        """
        try:
            content = resum_md  # Assume que já é texto puro
            
            # Extrai todas as informações
            education = PDFHelper.extract_education(content)
            skills = PDFHelper.extract_skills(content)
            languages = PDFHelper.extract_languages(content)
            experience = PDFHelper.extract_experience(content)
            
            # Extrai nome (obrigatório)
            name_match = re.search(r"(?i)(?:nome|name)\s*:\s*([^\n]+)", content)
            if not name_match:
                name_match = re.search(r"^([^\n]+)$", content)  # Primeira linha como fallback
            name = name_match.group(1).strip() if name_match else "Candidato não identificado"
            
            # Constrói o objeto de análise
            analysis_data = {
                "id": str(uuid.uuid4()),
                "job_id": job_id,
                "resum_id": resum_id,
                "name": name,
                "score": score,
                "education": education,
                "skills": skills,
                "languages": languages,
                "experience": experience,
                "details": json.dumps({
                    "extracted_data": {
                        "education": education,
                        "skills": skills,
                        "languages": languages,
                        "experience": experience
                    },
                    "analysis_date": datetime.now().isoformat()
                })
            }
            
            return analysis_data
            
        except Exception as e:
            logger.error(f"Erro ao extrair dados para análise: {str(e)}")
            raise ValueError(f"Falha ao processar currículo: {str(e)}")

    @staticmethod
    def get_pdf_paths(dir_name: str = 'curriculos') -> List[str]:
        """
        Obtém lista de arquivos PDF em um diretório.
        
        Args:
            dir_name: Nome do diretório (default: 'curriculos')
            
        Returns:
            Lista de caminhos absolutos para arquivos PDF
            
        Raises:
            FileNotFoundError: Se o diretório não existir
        """
        base_dir = Path(__file__).parent
        target_dir = base_dir / dir_name
        
        # Cria diretório se não existir
        target_dir.mkdir(exist_ok=True, parents=True)
        
        pdf_files = sorted([
            str(file.absolute())
            for file in target_dir.glob('*.pdf')
            if file.is_file()
        ])
        
        if not pdf_files:
            logger.warning(f"Nenhum PDF encontrado em {target_dir}")
            
        return pdf_files

    @staticmethod
    def print_score_details(analysis_data: dict):
        """Exibe detalhes formatados da análise do currículo"""
        print("\n" + "="*60)
        print(f"{Fore.YELLOW}DETALHAMENTO DA ANÁLISE DO CANDIDATO{Style.RESET_ALL}".center(60))
        print("="*60)
        
        print(f"\n{Fore.CYAN}CANDIDATO:{Style.RESET_ALL} {analysis_data.get('name', 'N/A')}")
        print(f"{Fore.GREEN}SCORE FINAL:{Style.RESET_ALL} {analysis_data.get('score', 0):.1f}/10")
        
        print(f"\n{Fore.BLUE}FORMAÇÃO ACADÊMICA:{Style.RESET_ALL}")
        for edu in analysis_data.get('education', []):
            print(f"- {edu.get('degree', '')} em {edu.get('course', '')} @ {edu.get('institution', '')} ({edu.get('period', '')})")
        
        print(f"\n{Fore.BLUE}HABILIDADES:{Style.RESET_ALL}")
        for category, skills in analysis_data.get('skills', {}).items():
            print(f"- {category.capitalize()}: {', '.join(skills)}")
        
        print(f"\n{Fore.BLUE}IDIOMAS:{Style.RESET_ALL}")
        for lang in analysis_data.get('languages', []):
            print(f"- {lang.get('language', '')} ({lang.get('proficiency', '')})")
        
        print(f"\n{Fore.BLUE}EXPERIÊNCIA PROFISSIONAL:{Style.RESET_ALL}")
        for exp in analysis_data.get('experience', []):
            print(f"- {exp.get('position', '')} @ {exp.get('company', '')} ({exp.get('period', '')})")
        
        print(f"\n{Fore.MAGENTA}FATORES DE PONTUAÇÃO:{Style.RESET_ALL}")
        factors = {
            'Experiência Profissional': 0.35,
            'Habilidades Técnicas': 0.30,
            'Formação Acadêmica': 0.20,
            'Idiomas': 0.15
        }
        for factor, weight in factors.items():
            print(f"{factor}: {weight*100}% do score")

    @staticmethod
    def get_detailed_analysis(content: str) -> dict:
        """
        Extrai informações detalhadas para análise de match com a vaga
        usando as novas funções de extração.
        
        Returns:
            {
                'education': [],
                'skills': {},
                'experience': [],
                'languages': [],
                'missing_sections': []
            }
        """
        analysis = {
            'education': PDFHelper.extract_education(content),
            'skills': PDFHelper.extract_skills(content),
            'experience': PDFHelper.extract_experience(content),
            'languages': PDFHelper.extract_languages(content),
            'missing_sections': []
        }
        
        # Verifica seções faltantes
        sections = {
            'education': 'Formação Acadêmica',
            'experience': 'Experiência Profissional',
            'languages': 'Idiomas'
        }
        
        for key, section in sections.items():
            if not analysis[key]:
                analysis['missing_sections'].append(section)
        
        return analysis

    @staticmethod
    def match_requirements(candidate_data: dict, job_requirements: dict) -> dict:
        """
        Compara as qualificações do candidato com os requisitos da vaga.
        
        Args:
            candidate_data: Dados extraídos do candidato
            job_requirements: Requisitos da vaga no formato:
                {
                    'education': [],
                    'skills': [],
                    'languages': []
                }
                
        Returns:
            {
                'matched': [],
                'partial': [],
                'missing': [],
                'score_impact': float
            }
        """
        result = {
            'matched': [],
            'partial': [],
            'missing': [],
            'score_impact': 0.0
        }
        
        # Função auxiliar para normalizar texto
        def normalize(text):
            return re.sub(r'[^a-z0-9]', '', text.lower())
        
        # Verifica educação
        candidate_edu = [normalize(edu.get('degree', '') + edu.get('course', '')) 
                        for edu in candidate_data.get('education', [])]
        
        for req in job_requirements.get('education', []):
            req_norm = normalize(req)
            if any(req_norm in edu for edu in candidate_edu):
                result['matched'].append(f"Formação: {req}")
            else:
                result['missing'].append(f"Formação: {req}")
                result['score_impact'] -= 0.2  # Penaliza 20% por formação faltante
        
        # Verifica habilidades
        candidate_skills = []
        for category in candidate_data.get('skills', {}).values():
            candidate_skills.extend(normalize(skill) for skill in category)
        
        for req in job_requirements.get('skills', []):
            req_norm = normalize(req)
            if req_norm in candidate_skills:
                result['matched'].append(f"Habilidade: {req}")
            else:
                # Verifica correspondência parcial
                partial_match = any(req_norm in skill or skill in req_norm 
                                  for skill in candidate_skills)
                if partial_match:
                    result['partial'].append(f"Habilidade: {req} (parcial)")
                    result['score_impact'] -= 0.05  # Penaliza 5% por correspondência parcial
                else:
                    result['missing'].append(f"Habilidade: {req}")
                    result['score_impact'] -= 0.1  # Penaliza 10% por habilidade faltante
        
        # Verifica idiomas
        candidate_langs = [normalize(lang.get('language', '')) 
                          for lang in candidate_data.get('languages', [])]
        
        for req in job_requirements.get('languages', []):
            req_norm = normalize(req)
            if req_norm in candidate_langs:
                result['matched'].append(f"Idioma: {req}")
            else:
                result['missing'].append(f"Idioma: {req}")
                result['score_impact'] -= 0.15  # Penaliza 15% por idioma faltante
        
        return result