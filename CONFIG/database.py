# Conexão com Supabase
import os
import re
from dotenv import load_dotenv
from supabase import create_client
from typing import List, Dict, Optional, Tuple
from LOGS.log_config import setup_logger

load_dotenv() # Carrega variáveis de ambiente do arquivo .env
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

log = setup_logger(__name__, "database.log")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class AnalyseDataBase:

    def insert_job(self, job_data: Dict):
        supabase.table("jobs").insert(job_data).execute()

    def insert_resum(self, resum_data: Dict):
        supabase.table("resums").upsert(resum_data, on_conflict=["id"]).execute()

    def insert_analysis(self, analysis_data: Dict):
        supabase.table("analysis").upsert(analysis_data, on_conflict=["resum_id"]).execute()

    def insert_file(self, file_data: Dict):
        supabase.table("files").upsert(file_data, on_conflict=["file_path"]).execute()

    def find_file_by_name(self, file_name: str) -> List[Dict]:
        """
        Busca por arquivos que tenham um nome original específico.
        
        Args:
            file_name: O nome do arquivo a ser procurado.
        
        Returns:
            Uma lista de dicionários com os dados dos arquivos encontrados.
            Retorna uma lista vazia se nenhum arquivo for encontrado.
        """
        # A sintaxe correta é usar .select() para escolher as colunas
        # e .eq() para criar a condição "onde a coluna é igual a".
        response = supabase.table("files").select("*").eq("original_name", file_name).execute()
        return response.data
    
    def validar_email(self, email: str) -> Tuple[bool, str]:
        """Valida formato do email"""
        if not email or not email.strip():
            return False, "Email é obrigatório"
        
        email = email.strip().lower()
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if not re.match(pattern, email):
            return False, "Formato de email inválido"
        
        return True, ""

    def validar_senha(self, password: str) -> Tuple[bool, str]:
        """Valida força da senha"""
        if not password:
            return False, "Senha é obrigatória"
        
        if len(password) < 6:
            return False, "A senha deve ter pelo menos 6 caracteres"
        
        if len(password) > 72:  # Limite do Supabase
            return False, "A senha deve ter no máximo 72 caracteres"
        
        # Opcional: validações adicionais de força
        if password.isdigit():
            return False, "A senha não pode conter apenas números"
        
        if password.lower() == password and password.isalpha():
            return False, "A senha deve conter pelo menos um número ou caractere especial"
        
        return True, ""

    def verificar_email_existente(self, email: str) -> bool:
        """Verifica se email já existe no sistema"""
        try:
            email = email.strip().lower()
            
            # Método mais confiável: tentar fazer login com senha inválida
            # Se o email existir, retornará erro de senha incorreta
            # Se não existir, retornará erro de usuário não encontrado
            try:
                response = supabase.auth.sign_in_with_password({
                    "email": email, 
                    "password": "senha_temporaria_invalida_123456789"
                })
                # Se chegou aqui sem erro, algo está errado
                return True
            except Exception as e:
                error_msg = str(e).lower()
                
                # Se contém "invalid login credentials" ou "email not confirmed"
                # significa que o email existe mas a senha está errada
                if any(phrase in error_msg for phrase in [
                    "invalid login credentials", 
                    "email not confirmed",
                    "invalid email or password"
                ]):
                    log.info(f"Email {email} já existe no sistema")
                    return True
                
                # Se contém "user not found" ou similar, email não existe
                if any(phrase in error_msg for phrase in [
                    "user not found",
                    "no user found",
                    "user does not exist"
                ]):
                    log.info(f"Email {email} não existe no sistema")
                    return False
                
                # Para outros erros, assumimos que existe por segurança
                log.warning(f"Erro ambíguo ao verificar email {email}: {e}")
                return True
                
        except Exception as e:
            log.error(f"Erro ao verificar email {email}: {e}")
            # Em caso de erro, assumimos que existe por segurança
            return True

    def sign_up(self, email: str, password: str) -> dict:
        """Cria um novo usuário com validações melhoradas"""
        
        # Validações locais primeiro
        email_valido, email_erro = self.validar_email(email)
        if not email_valido:
            raise ValueError(email_erro)
        
        senha_valida, senha_erro = self.validar_senha(password)
        if not senha_valida:
            raise ValueError(senha_erro)
        
        email = email.strip().lower()
        
        # Verifica se email já existe
        if self.verificar_email_existente(email):
            raise ValueError("Este email já está cadastrado no sistema")
        
        try:
            log.info(f"Tentando criar conta para: {email}")
            
            response = supabase.auth.sign_up({
                "email": email, 
                "password": password
            })
            
            if response.user:
                log.info(f"Conta criada com sucesso para: {email}")
                return {
                    "success": True,
                    "user": response.user,
                    "message": f"Conta criada com sucesso! Verifique seu email ({email}) para confirmar o cadastro."
                }
            else:
                error_msg = "Erro desconhecido ao criar conta"
                if hasattr(response, 'error') and response.error:
                    error_msg = str(response.error.message)
                
                log.error(f"Falha ao criar conta para {email}: {error_msg}")
                raise ValueError(f"Erro ao criar conta: {error_msg}")
                
        except Exception as e:
            error_msg = str(e)
            log.error(f"Exceção ao criar conta para {email}: {error_msg}")
            
            # Traduzir erros comuns
            if "user already registered" in error_msg.lower():
                raise ValueError("Este email já está cadastrado no sistema")
            elif "invalid email" in error_msg.lower():
                raise ValueError("Email inválido")
            elif "password" in error_msg.lower() and "6" in error_msg:
                raise ValueError("A senha deve ter pelo menos 6 caracteres")
            elif "rate limit" in error_msg.lower():
                raise ValueError("Muitas tentativas. Aguarde alguns minutos e tente novamente")
            else:
                raise ValueError(f"Erro ao criar conta: {error_msg}")

    def sign_in(self, email: str, password: str) -> dict:
        """Faz login com validações melhoradas"""
        
        # Validações básicas
        email_valido, email_erro = self.validar_email(email)
        if not email_valido:
            raise ValueError(email_erro)
        
        if not password or len(password.strip()) == 0:
            raise ValueError("Senha é obrigatória")
        
        email = email.strip().lower()
        
        try:
            log.info(f"Tentativa de login para: {email}")
            
            response = supabase.auth.sign_in_with_password({
                "email": email, 
                "password": password
            })
            
            if response.user:
                log.info(f"Login realizado com sucesso para: {email}")
                return {
                    "success": True,
                    "user": response.user,
                    "message": "Login realizado com sucesso!"
                }
            else:
                error_msg = "Credenciais inválidas"
                if hasattr(response, 'error') and response.error:
                    error_msg = str(response.error.message)
                
                log.warning(f"Falha no login para {email}: {error_msg}")
                raise ValueError("Email ou senha incorretos")
                
        except Exception as e:
            error_msg = str(e).lower()
            log.error(f"Exceção no login para {email}: {e}")
            
            # Traduzir erros específicos
            if any(phrase in error_msg for phrase in [
                "invalid login credentials", 
                "invalid email or password",
                "email or password"
            ]):
                raise ValueError("Email ou senha incorretos")
            elif "email not confirmed" in error_msg:
                raise ValueError("Email não confirmado. Verifique sua caixa de entrada e confirme seu cadastro")
            elif "too many requests" in error_msg or "rate limit" in error_msg:
                raise ValueError("Muitas tentativas de login. Aguarde alguns minutos")
            elif "network" in error_msg or "connection" in error_msg:
                raise ValueError("Erro de conexão. Verifique sua internet")
            else:
                raise ValueError("Erro no login. Tente novamente")

    def sign_out(self):
        """Faz logout"""
        try:
            supabase.auth.sign_out()
            log.info("Logout realizado com sucesso")
        except Exception as e:
            log.error(f"Erro no logout: {e}")

    
    def get_user(self):
        """Retorna o usuário autenticado atual."""
        return supabase.auth.user()

    def get_job_by_name(self, name: str) -> Optional[Dict]:
        result = supabase.table("jobs").select("*").eq("name", name).execute()
        return result.data[0] if result.data else None
    
    def get_job_details(self, job_id: str) -> Optional[Dict]:
        """Retorna os detalhes completos de uma vaga específica pelo ID"""
        result = supabase.table("jobs").select("*").eq("id", job_id).execute()
        return result.data[0] if result.data else None

    def get_jobs(self) -> List[Dict]:
        result = supabase.table("jobs").select("*").execute()
        return result.data

    def get_resum_by_id(self, resum_id: str) -> Optional[Dict]:
        result = supabase.table("resums").select("*").eq("id", resum_id).execute()
        return result.data[0] if result.data else None

    def get_analysis_by_job_id(self, job_id: str) -> List[Dict]:
        result = supabase.table("analysis").select("*").eq("job_id", job_id).execute()
        return result.data

    def get_resums_by_job_id(self, job_id: str) -> List[Dict]:
        result = supabase.table("resums").select("*").eq("job_id", job_id).execute()
        return result.data

    def delete_job_data(self, job_id: str) -> Dict[str, int]:
        res1 = supabase.table("resums").delete().eq("job_id", job_id).execute()
        res2 = supabase.table("analysis").delete().eq("job_id", job_id).execute()
        res3 = supabase.table("files").delete().eq("job_id", job_id).execute()
        return {
            "resums": len(res1.data or []),
            "analysis": len(res2.data or []),
            "files": len(res3.data or [])
        }
    
    def delete_job_and_related_data(self, job_id: str) -> Dict[str, int]:
        """
        Exclui a vaga e todos os dados relacionados nas tabelas:
        - analysis (deve vir antes de resums por causa da FK)
        - resums
        - files
        - jobs
        """
        deleted_counts = {
            "analysis": 0,
            "resums": 0,
            "files": 0,
            "jobs": 0
        }

        try:
            # Deletar registros em analysis (depende de resum_id)
            res_analysis = supabase.table("analysis").delete().eq("job_id", job_id).execute()
            deleted_counts["analysis"] = len(res_analysis.data or [])

            # Deletar registros em files (também depende de resum_id)
            res_files = supabase.table("files").delete().eq("job_id", job_id).execute()
            deleted_counts["files"] = len(res_files.data or [])

            # Deletar registros em resums
            res_resums = supabase.table("resums").delete().eq("job_id", job_id).execute()
            deleted_counts["resums"] = len(res_resums.data or [])

            # Por fim, deletar a vaga em jobs
            res_jobs = supabase.table("jobs").delete().eq("id", job_id).execute()
            deleted_counts["jobs"] = len(res_jobs.data or [])

        except Exception as e:
            print(f"Erro ao deletar dados da vaga: {e}")

        return deleted_counts


    def update_job(self, job_id: str, updated_data: Dict) -> Optional[Dict]:
        """
        Atualiza uma vaga (job) com os dados fornecidos.
        """
        try:
            response = supabase.table("jobs").update(updated_data).eq("id", job_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Erro ao atualizar job {job_id}: {e}")
            return None

    def get_db_stats(self) -> Dict[str, int]:
        stats = {}
        for table in ["jobs", "resums", "analysis", "files"]:
            result = supabase.table(table).select("*", count="exact").execute()
            stats[table] = result.count or 0
        return stats

    def print_db_stats(self):
        stats = self.get_db_stats()
        print("\n=== DATABASE STATS ===")
        for table, count in stats.items():
            print(f"{table.capitalize()}: {count}")
        print("=====================\n")

    def close(self):
        pass  # Sem necessidade de fechar conexão com Supabase