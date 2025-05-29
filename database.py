from tinydb import TinyDB, Query
from typing import List, Dict, Optional, Union
from pathlib import Path
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AnalyseDataBase:
    def __init__(self, db_path: Union[str, Path] = 'db.json'):
        if isinstance(db_path, str):
            db_path = Path(db_path)
        self._db_path = db_path.absolute()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = TinyDB(self._db_path)
        self._setup_tables()

    def _setup_tables(self):
        self.jobs = self._db.table('jobs')
        self.resums = self._db.table('resums')
        self.analysis = self._db.table('analysis')
        self.files = self._db.table('files')
        logger.info(f"Banco de dados inicializado em {self._db_path}")

    def insert_job(self, job_data: Dict):
        if not isinstance(job_data, dict):
            raise TypeError("job_data deve ser um dicionário")
        self.jobs.insert(job_data)

    def insert_resum(self, resum_data: Union[Dict, object]):
        if not isinstance(resum_data, dict):
            resum_data = resum_data.__dict__
        if self.resums.contains(Query().id == resum_data['id']):
            logger.warning(f"Resumo já existe: {resum_data['id']}")
            return
        self.resums.insert(resum_data)

    def insert_analysis(self, analysis_data: Union[Dict, object]):
        if not isinstance(analysis_data, dict):
            analysis_data = analysis_data.__dict__
        if self.analysis.contains(Query().resum_id == analysis_data['resum_id']):
            logger.warning(f"Análise já existe: {analysis_data['resum_id']}")
            return
        self.analysis.insert(analysis_data)

    def insert_file(self, file_data: Union[Dict, object]):
        if not isinstance(file_data, dict):
            file_data = file_data.__dict__
        if self.files.contains(Query().file_path == file_data['file_path']):
            logger.warning(f"Arquivo já registrado: {file_data['file_path']}")
            return
        self.files.insert(file_data)

    def get_job_by_name(self, name: str) -> Optional[Dict]:
        Job = Query()
        results = self.jobs.search(Job.name == name)
        return results[0] if results else None
    
    def get_jobs(self) -> Optional[Dict]:
        Job = Query()
        results = self.jobs.all()
        return results if results else None

    def get_resum_by_id(self, resum_id: str) -> Optional[Dict]:
        Resum = Query()
        results = self.resums.search(Resum.id == resum_id)
        if not results:
            return None
        resum = results[0]

        # # Agora buscamos a análise associada
        # Analysis = Query()
        # analysis_results = self.analysis.search(Analysis.resum_id == resum_id)
        # if analysis_results:
        #     resum['opinion'] = analysis_results[0].get('opinion')

        return resum


    def get_analysis_by_job_id(self, job_id: str) -> List[Dict]:
        Analysis = Query()
        return self.analysis.search(Analysis.job_id == job_id)

    def get_resums_by_job_id(self, job_id: str) -> List[Dict]:
        Resum = Query()
        return self.resums.search(Resum.job_id == job_id)

    def delete_job_data(self, job_id: str) -> Dict[str, int]:
        counts = {
            'resums': len(self.resums.remove(Query().job_id == job_id)),
            'analysis': len(self.analysis.remove(Query().job_id == job_id)),
            'files': len(self.files.remove(Query().job_id == job_id))
        }
        return counts

    def get_db_stats(self) -> Dict[str, int]:
        return {
            'jobs': len(self.jobs),
            'resums': len(self.resums),
            'analysis': len(self.analysis),
            'files': len(self.files)
        }

    def print_db_stats(self):
        stats = self.get_db_stats()
        print("\n=== DATABASE STATS ===")
        for table, count in stats.items():
            print(f"{table.capitalize()}: {count}")
        print("=====================\n")

    def close(self):
        self._db.close()
        logger.info("Conexão com o banco de dados fechada")
