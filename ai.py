import re
import os
import logging
from typing import Dict, Optional,Tuple
from openai import OpenAI
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('deepseek_analysis.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Carrega variáveis de ambiente
load_dotenv()

def round_to_nearest_half(num: float) -> float:
    return round(num * 2) / 2

class DeepSeekClient:
    def __init__(self, model_id: str = "deepseek-chat"):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("API Key do DeepSeek não encontrada.")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com",
            timeout=httpx.Timeout(60.0, read=120.0),
            max_retries=5
        )
        self.model_id = model_id

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(), retry=retry_if_exception_type(httpx.TimeoutException))
    def generate_response(self, prompt: str, temperature: float = 0.5, max_tokens: int = 5000) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Erro na API DeepSeek: {e}")
            raise

    def resume_cv(self, cv_text: str) -> str:
        prompt = f"""
        Você é um analista de currículos. Extraia informações do seguinte currículo em formato Markdown.
        
        ## Nome Completo
        [nome]

        ## Experiência Relevante
        - [Cargo] @ [Empresa] ([Ano-Início] - [Ano-Fim])
        - ...

        ## Habilidades Técnicas
        - Python, SQL, Power BI, etc.

        ## Formação Acadêmica
        - Bacharelado em [Curso] @ [Instituição]

        ## Idiomas
        - Inglês (Avançado), Espanhol (Intermediário)

        ### Conteúdo:
        {cv_text[:5000]}
        """
        result = self.generate_response(prompt, temperature=0.3, max_tokens=5000)
        return result or "Currículo não pôde ser resumido."

    def generate_score(self, cv_text: str, job_description: Dict) -> float:
        prompt = f"""
        Você é um avaliador especialista que dará uma nota de 0 a 10 para o seguinte currículo em relação à vaga '{job_description.get("name")}'.
        Considere experiência, habilidades, educação e adequação ao cargo.
        Retorne somente um número decimal, múltiplo de 0.5, sem texto adicional.
        Se precisar arredondar, arredonde para o múltiplo de 0.5 mais próximo.

        Currículo:
        {cv_text[:5000]}
        """

        response = self.generate_response(prompt, temperature=0.2, max_tokens=50)
        print("Resposta da IA:", response)
        match = re.search(r"(\d{1,2}(?:\.\d)?)", response)
        if match:
            raw_score = float(match.group(1))
            rounded_score = round_to_nearest_half(raw_score)
            return min(max(rounded_score, 0), 10)
        # Se falhar, retorna None para indicar erro (ou pode deixar 5.0 se preferir)
        return None

    def generate_opinion(self, cv_text: str, job_description: Dict) -> str:
        prompt = f"""
        Avalie o currículo abaixo com base na vaga: {job_description.get("name")}

        1. Alinhamento Técnico (tecnologias e experiência)
        2. Gaps técnicos
        3. Recomendação final: Sim / Parcial / Não

        Currículo:
        {cv_text[:5000]}
        """
        result = self.generate_response(prompt, temperature=0.5, max_tokens=5000)
        return result or "Análise indisponível."

    def analyze_cv(self, cv_text: str, job_description: Dict) -> Tuple[str, str, float]:
        prompt = f"""
        Você é um analista de currículos. Analise o currículo abaixo para a vaga '{job_description.get("name")}'.
        
        Retorne:
        - Um resumo estruturado do currículo em Markdown.
        - Uma opinião crítica com base na vaga (alinhamento técnico, gaps e recomendação).
        - Uma nota final de 0 a 10 (com uma casa decimal), baseada no alinhamento com a vaga.

        Use o seguinte formato:

        ### RESUMO
        (Resumo estruturado em Markdown)

        ### OPINIÃO
        1. Alinhamento Técnico: ...
        2. Gaps Técnicos: ...
        3. Recomendação Final: Sim / Parcial / Não

        ### SCORE
        (Apenas o número com uma casa decimal)

        Currículo:
        {cv_text[:5000]}
        """

        result = self.generate_response(prompt, temperature=0.4, max_tokens=5000)

        if not result:
            return "Resumo indisponível.", "Opinião indisponível.", 5.0

    
        resumo = re.search(r"### RESUMO\s*(.*?)\s*(?=### OPINIÃO|### SCORE|$)", result, re.DOTALL)
        opiniao = re.search(r"### OPINIÃO\s*(.*?)\s*(?=### SCORE|$)", result, re.DOTALL)
        score = re.search(r"### SCORE\s*([\d]{1,2}(?:\.\d)?)", result)

        resumo_text = resumo.group(1).strip() if resumo else "Resumo não encontrado."
        opiniao_text = opiniao.group(1).strip() if opiniao else "Opinião não encontrada."
        score_value = float(score.group(1)) if score else 5.0

        return resumo_text, opiniao_text, min(max(score_value, 0), 10)

    def _count_keywords(self, text: str, keywords: list) -> int:
        """Conta ocorrências de keywords no texto"""
        text_lower = text.lower()
        return sum(1 for kw in keywords if kw.lower() in text_lower)

    def _validate_extraction(self, md_text: str) -> Dict[str, bool]:
        """Valida se todas seções foram extraídas"""
        sections = {
            'Nome': r"## Nome Completo\n(.+)",
            'Experiência': r"## Experiência Relevante\n([\s\S]+?)(?=##|$)",
            'Habilidades': r"## Habilidades Técnicas\n([\s\S]+?)(?=##|$)",
            'Formação': r"## Formação Acadêmica\n([\s\S]+?)(?=##|$)"
        }
        return {
            section: bool(re.search(pattern, md_text, re.IGNORECASE))
            for section, pattern in sections.items()
        }

if __name__ == "__main__":
    # Exemplo de uso com dados de teste
    try:
        client = DeepSeekClient()
        
        test_cv = """
        Nome: Ana Oliveira
        Formação: Ciência da Computação - UFMG (2020)
        Certificações: Google Data Analytics, Microsoft DA-100
        Experiência:
        - Analista de Dados na Empresa Y (2021-presente)
          * Construção de dashboards em Power BI
          * Desenvolvimento de pipelines ETL em Python
        Habilidades: Python avançado, SQL, Power BI, Inglês intermediário
        """
        
        test_job = {
            "name": "Analista de Dados Pleno",
            "requirements": "Experiência com Python, SQL e Power BI, conhecimento em ETL"
        }
        
        print("=== RESUMO ESTRUTURADO ===")
        print(client.resume_cv(test_cv))
        
        print("\n=== SCORE ===")
        score = client.generate_score(test_cv, test_job)
        print(f"Score: {score:.1f}/10")
        
        print("\n=== ANÁLISE ===")
        print(client.generate_opinion(test_cv, test_job))
        
    except Exception as e:
        logger.critical(f"Erro no teste: {str(e)}")