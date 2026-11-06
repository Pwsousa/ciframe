# coding: utf-8
"""Persistência do catálogo de sequências em SQLite.

Só o catálogo de sequências vive aqui. As músicas e os gêneros continuam vindo
de ``data/top/dataset_final.csv`` e são carregados em memória por ``main.py``.
"""
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

import sequencias

DB_ENV = 'CIFRAME_DB_PATH'
DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'instance', 'deciframe.db')

_SCHEMA = '''
CREATE TABLE IF NOT EXISTS sequencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    acordes TEXT NOT NULL,
    chave TEXT NOT NULL UNIQUE,
    legado_id INTEGER UNIQUE,
    criada_em TEXT NOT NULL
);
'''


class SequenciaDuplicada(Exception):
    """Levantada quando a chave canônica já existe no catálogo."""

    def __init__(self, existente):
        super(SequenciaDuplicada, self).__init__('sequência já cadastrada')
        self.existente = existente


def caminho_db():
    return os.environ.get(DB_ENV) or DEFAULT_DB_PATH


def conectar():
    """Abre uma conexão curta, criando o diretório do banco se necessário."""
    caminho = caminho_db()
    diretorio = os.path.dirname(os.path.abspath(caminho))
    if diretorio:
        os.makedirs(diretorio, exist_ok=True)
    conn = sqlite3.connect(caminho, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=5000')
    return conn


def _agora_iso():
    agora = datetime.now(timezone.utc).replace(microsecond=0)
    return agora.isoformat().replace('+00:00', 'Z')


def _row_para_interno(row):
    if row is None:
        return None
    return {
        'id': row['id'],
        'nome': row['nome'],
        'acordes': json.loads(row['acordes']),
        'chave': row['chave'],
        'legado_id': row['legado_id'],
        'criada_em': row['criada_em'],
    }


def publica(sequencia):
    """Formato público (sem detalhes internos de persistência)."""
    return {
        'id': sequencia['id'],
        'nome': sequencia['nome'],
        'acordes': sequencia['acordes'],
        'legado': sequencia['legado_id'] is not None,
        'criada_em': sequencia['criada_em'],
    }


def _semear(conn):
    """Insere as 6 legadas de forma idempotente.

    Consulta a chave antes de inserir: um ``INSERT OR IGNORE`` violaria o UNIQUE
    e ainda assim consumiria um id do AUTOINCREMENT a cada inicialização.
    """
    for seq in sequencias.LEGACY_SEQUENCES:
        chave = sequencias.chave_sequencia(seq['acordes'])
        if conn.execute(
                'SELECT 1 FROM sequencias WHERE chave = ?', (chave,)).fetchone():
            continue
        conn.execute(
            'INSERT INTO sequencias '
            '(nome, acordes, chave, legado_id, criada_em) VALUES (?, ?, ?, ?, ?)',
            (seq['nome'],
             json.dumps(seq['acordes'], ensure_ascii=False),
             chave,
             seq['legado_id'],
             _agora_iso()))


def init_db():
    """Cria o schema e semeia as 6 sequências originais."""
    with closing(conectar()) as conn, conn:
        conn.executescript(_SCHEMA)
        _semear(conn)


def listar_sequencias():
    """Retorna o catálogo público, na ordem de criação."""
    with closing(conectar()) as conn:
        rows = conn.execute('SELECT * FROM sequencias ORDER BY id').fetchall()
    return [publica(_row_para_interno(row)) for row in rows]


def buscar_por_chave(chave):
    """Retorna a sequência interna com a chave canônica, ou ``None``."""
    with closing(conectar()) as conn:
        row = conn.execute(
            'SELECT * FROM sequencias WHERE chave = ?', (chave,)).fetchone()
    return _row_para_interno(row)


def buscar_por_legado(legado_id):
    """Retorna a sequência interna de uma das 6 originais, ou ``None``."""
    with closing(conectar()) as conn:
        row = conn.execute(
            'SELECT * FROM sequencias WHERE legado_id = ?', (legado_id,)).fetchone()
    return _row_para_interno(row)


def cadastrar_sequencia(nome, acordes):
    """Valida, canonicaliza e cadastra uma sequência nova.

    Levanta ``ValueError`` para entrada inválida e ``SequenciaDuplicada`` quando
    a chave já existe (inclusive para uma das 6 originais).
    """
    canonicos = sequencias.canonicalizar_acordes(acordes)
    nome_final = sequencias.normalizar_nome(nome, canonicos)
    chave = sequencias.chave_sequencia(canonicos)

    existente = buscar_por_chave(chave)
    if existente is not None:
        raise SequenciaDuplicada(existente)

    try:
        with closing(conectar()) as conn, conn:
            conn.execute(
                'INSERT INTO sequencias '
                '(nome, acordes, chave, legado_id, criada_em) VALUES (?, ?, ?, NULL, ?)',
                (nome_final,
                 json.dumps(canonicos, ensure_ascii=False),
                 chave,
                 _agora_iso()))
    except sqlite3.IntegrityError:
        # Corrida entre dois cadastros iguais: o UNIQUE resolve.
        existente = buscar_por_chave(chave)
        if existente is not None:
            raise SequenciaDuplicada(existente)
        raise

    return buscar_por_chave(chave)
