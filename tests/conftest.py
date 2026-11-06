# coding: utf-8
"""Isola o banco de testes e fixa o diretório de trabalho.

``main.py`` carrega o CSV no import e inicializa o catálogo no banco. Para não
tocar no banco de desenvolvimento, apontamos ``CIFRAME_DB_PATH`` para um arquivo
temporário *antes* de importar ``main`` (o import acontece nos módulos de teste,
depois deste conftest).
"""
import os
import sys
import tempfile
from contextlib import closing
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# main.py abre 'data/top/dataset_final.csv' relativo ao cwd.
os.chdir(RAIZ)

_FD, _CAMINHO_DB = tempfile.mkstemp(prefix='ciframe-test-', suffix='.db')
os.close(_FD)
os.environ['CIFRAME_DB_PATH'] = _CAMINHO_DB


@pytest.fixture(autouse=True)
def catalogo_limpo():
    """Mantém só as 6 legadas antes de cada teste."""
    import db

    db.init_db()
    with closing(db.conectar()) as conn, conn:
        conn.execute('DELETE FROM sequencias WHERE legado_id IS NULL')
    yield


def pytest_sessionfinish(session, exitstatus):
    for sufixo in ('', '-wal', '-shm'):
        try:
            os.remove(_CAMINHO_DB + sufixo)
        except OSError:
            pass
