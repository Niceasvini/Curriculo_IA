# Conexão com Supabase
import os
import re
from dotenv import load_dotenv
from supabase import create_client
from typing import List, Dict, Optional, Tuple
from LOGS.log_config import setup_logger

load_dotenv() # Carrega variáveis de ambiente do arquivo .env
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") # chave pública (anon)
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # chave secreta (service_role)

log = setup_logger(__name__, "database.log")

# Cliente público para operações comuns (login, signup)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Cliente admin para operações administrativas (list_users etc)
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

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
        
        if len(password) > 72:
            return False, "A senha deve ter no máximo 72 caracteres"
        
        return True, ""

    def sign_up(self, email: str, password: str) -> dict:
        """
        Cria um novo usuário - MÉTODO DIRETO SEM VERIFICAÇÃO PRÉVIA
        Deixa o Supabase decidir se o email já existe
        """
        
        try:
            log.info(f"🚀 TENTANDO CRIAR CONTA PARA: {email}")
            
            # 1️⃣ Validações locais
            email_valido, email_erro = self.validar_email(email)
            if not email_valido:
                raise ValueError(email_erro)

            senha_valida, senha_erro = self.validar_senha(password)
            if not senha_valida:
                raise ValueError(senha_erro)

            email = email.strip().lower()

            # 2️⃣ Envia requisição de criação ao Supabase
            existing_users = supabase_admin.auth.admin.list_users()
            print(existing_users)
            if any(u.email == email for u in existing_users):
                log.warning(f"❌ Email {email} JÁ EXISTE no Supabase.")
                raise ValueError("Este email já está registrado no sistema.")

            # Tenta sign up
            log.info(f"📤 Enviando requisição para Supabase...")
            response = supabase.auth.sign_up({"email": email, "password": password})
            log.info(f"📥 Response recebido do Supabase")
            
            # ✅ SUCESSO - CONTA CRIADA
            if response.user:
                log.info(f"🎉 CONTA CRIADA COM SUCESSO PARA: {email}")
                return {
                    "success": True,
                    "user": response.user,
                    "message": f"Conta criada com sucesso! Verifique seu email ({email}) para confirmar o cadastro."
                }
            
            else:
                error_msg = "Resposta inesperada do servidor"
                if hasattr(response, 'error') and response.error:
                    error_msg = str(response.error.message)

                log.error(f"❌ Resposta sem user: {error_msg}")
                raise ValueError(f"Erro ao criar conta: {error_msg}")
                
        except Exception as e:
            error_msg = str(e).lower()
            log.error(f"💥 ERRO AO CRIAR CONTA PARA {email}: {e}")
            if "user already registered" in error_msg or "email already registered" in error_msg:
                raise ValueError("Este email já está registrado no sistema.")
            
            else:
                raise ValueError(f"Erro ao criar conta: {str(e)}")

    def sign_in(self, email: str, password: str) -> dict:
        """Faz login"""
        try:
            log.info(f"🔑 TENTATIVA DE LOGIN PARA: {email}")
            
            # Validações básicas
            email_valido, email_erro = self.validar_email(email)
            if not email_valido:
                raise ValueError(email_erro)
            
            if not password:
                raise ValueError("Senha é obrigatória")
            
            email = email.strip().lower()
            
            response = supabase.auth.sign_in_with_password({
                "email": email, 
                "password": password
            })
            
            if response.user:
                log.info(f"✅ LOGIN REALIZADO COM SUCESSO PARA: {email}")
                return {
                    "success": True,
                    "user": response.user,
                    "message": "Login realizado com sucesso!"
                }
            else:
                log.warning(f"❌ Falha no login para {email}")
                raise ValueError("Email ou senha incorretos")
                
        except ValueError:
            raise
        except Exception as e:
            error_msg = str(e).lower()
            log.error(f"💥 Erro no login para {email}: {e}")
            
            if any(phrase in error_msg for phrase in [
                "invalid login credentials", 
                "invalid email or password",
                "wrong password",
                "incorrect password"
            ]):
                raise ValueError("Email ou senha incorretos")
            elif any(phrase in error_msg for phrase in [
                "email not confirmed",
                "email not verified"
            ]):
                raise ValueError("Email não confirmado. Verifique sua caixa de entrada e confirme seu cadastro")
            elif any(phrase in error_msg for phrase in [
                "too many requests",
                "rate limit"
            ]):
                raise ValueError("Muitas tentativas de login. Aguarde alguns minutos")
            else:
                raise ValueError("Erro no login. Tente novamente")

    def reset_password(self, email: str) -> dict:
        """
        🔄 NOVA FUNÇÃO: Reset de senha manual (para botão "Esqueci Senha")
        """
        try:
            log.info(f"🔄 SOLICITAÇÃO DE RESET DE SENHA PARA: {email}")
            
            # Validação básica
            email_valido, email_erro = self.validar_email(email)
            if not email_valido:
                raise ValueError(email_erro)
            
            email = email.strip().lower()
            
            # Enviar email de reset
            response = supabase.auth.reset_password_email(email)
            
            log.info(f"✅ EMAIL DE RESET ENVIADO PARA: {email}")
            return {
                "success": True,
                "message": f"Email de recuperação enviado para {email}. Verifique sua caixa de entrada."
            }
            
        except Exception as e:
            error_msg = str(e).lower()
            log.error(f"💥 Erro no reset de senha para {email}: {e}")
            
            if any(phrase in error_msg for phrase in [
                "rate limit",
                "too many requests",
                "48 seconds"
            ]):
                raise ValueError("Aguarde alguns minutos antes de solicitar outro reset de senha")
            elif any(phrase in error_msg for phrase in [
                "user not found",
                "email not found"
            ]):
                # Por segurança, não revelamos se o email existe ou não
                return {
                    "success": True,
                    "message": f"Se o email {email} estiver cadastrado, você receberá as instruções de recuperação."
                }
            else:
                raise ValueError("Erro ao enviar email de recuperação. Tente novamente")

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