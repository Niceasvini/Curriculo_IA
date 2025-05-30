from supabase import create_client
from typing import List, Dict, Optional

SUPABASE_URL = "https://bndkpowgvagtlxwmthma.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJuZGtwb3dndmFndGx4d210aG1hIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDg1NjQ3NDYsImV4cCI6MjA2NDE0MDc0Nn0.uXCaQurTXcszNIpL6mY50L4GcIl089TXRSCG7Vg9avE"

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

    def get_job_by_name(self, name: str) -> Optional[Dict]:
        result = supabase.table("jobs").select("*").eq("name", name).execute()
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