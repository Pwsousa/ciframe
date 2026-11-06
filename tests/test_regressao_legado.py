# coding: utf-8
"""Regressão das 6 sequências originais contra o snapshot tirado antes da mudança.

A ordem entre gêneros não é determinística (``list(set(generos))`` em main.py),
então comparamos **conjuntos** de IDs, nunca a ordem.
"""
import json
import urllib.parse
from pathlib import Path

import pytest

import main

FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'legacy_similar_ids.json'


@pytest.fixture(scope='module')
def snapshot():
    with FIXTURE.open(encoding='utf-8') as arquivo:
        return json.load(arquivo)


def paginar(client, acordes):
    ids = []
    pagina = 1
    while True:
        resposta = client.get('/similares?sequencia=%s&pagina=%d' % (
            urllib.parse.quote(','.join(acordes)), pagina))
        assert resposta.status_code == 200
        dados = json.loads(resposta.get_data(as_text=True))
        ids.extend(m['id_unico_musica'] for m in dados)
        if len(dados) < main.TAM_PAGINA:
            return ids
        pagina += 1


@pytest.mark.parametrize('legado_id', ['0', '1', '2', '3', '4', '5'])
def test_busca_legada_continua_identica_ao_snapshot(snapshot, legado_id):
    esperado = snapshot[legado_id]
    obtido = paginar(main.app.test_client(), esperado['chords'])

    assert len(obtido) == esperado['count']
    assert set(obtido) == set(esperado['ids'])


@pytest.mark.parametrize('legado_id', ['0', '1', '2', '3', '4', '5'])
def test_snapshot_confere_com_a_tag_do_csv(snapshot, legado_id):
    """Prova que o snapshot não foi capturado de uma base diferente."""
    esperado = set(snapshot[legado_id]['ids'])
    vivos = {
        musica.id_unico_musica
        for musica in main.musicas.values()
        if legado_id in musica.seqs_famosas
    }
    assert vivos == esperado
