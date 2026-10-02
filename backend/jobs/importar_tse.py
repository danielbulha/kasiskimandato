"""Importa os eleitos do Portal de Dados Abertos do TSE. Rode uma vez por eleição (ex.: no Shell do Render).

Uso: python jobs/importar_tse.py 2018 2022 2024
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("KASISKI_JOB", "1")

from app import create_app  # noqa: E402
from services import tse  # noqa: E402

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        for ano in (sys.argv[1:] or ["2018", "2022", "2024"]):
            print(f"{ano}: importando…", flush=True)
            print(f"{ano}: {tse.importar(int(ano))} eleitos gravados", flush=True)
