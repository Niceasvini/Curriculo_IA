# config/log_config.py
import os
import sys
import logging
from pathlib import Path
import tempfile
import re

class AsciiOnlyFilter(logging.Filter):
    def filter(self, record):
        record.msg = re.sub(r'[^\x00-\x7F]+', '', record.getMessage())
        record.args = ()
        return True

def setup_logger(name: str, log_file: str) -> logging.Logger:
    # Garante que a pasta logs exista
    log_dir = Path(__file__).resolve().parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_path = log_dir / log_file

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Evita adicionar handlers duplicados
    if logger.hasHandlers():
        return logger

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    file_handler = logging.FileHandler(log_path, mode='a', encoding='utf-8')
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(AsciiOnlyFilter())

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger