# coding: utf-8
"""Unitários de canonicalização/matching, API do catálogo e persistência."""
import json
import sqlite3
import urllib.parse

import pytest

import db
import main
import sequencias


def get_json(client, url):
    resposta = client.get(url)
    assert resposta.status_code == 200, url
    return json.loads(resposta.get_data(as_text=True))


def post_json(client, payload):
    return client.post('/api/sequencias', data=json.dumps(payload),
                       content_type='application/json')


def paginar(client, query):
    """Percorre todas as páginas de /similares e devolve a lista de IDs."""
    ids = []
    pagina = 1
    while True:
        dados = get_json(client, '/similares?%s&pagina=%d' % (query, pagina))
        ids.extend(m['id_unico_musica'] for m in dados)
        if len(dados) < main.TAM_PAGINA:
            return ids
        pagina += 1


@pytest.fixture
def client():
    return main.app.test_client()


# --------------------------------------------------------------------------
# Canonicalização
# --------------------------------------------------------------------------

def test_normalizar_acorde_ajusta_so_a_fundamental():
    assert sequencias.normalizar_acorde('am') == 'Am'
    assert sequencias.normalizar_acorde('c#m') == 'C#m'
    assert sequencias.normalizar_acorde('bb9') == 'Bb9'
    assert sequencias.normalizar_acorde('  Dm4/7 ') == 'Dm4/7'


@pytest.mark.parametrize('invalido', ['', '   ', 'H', 'C G', None, 3])
def test_normalizar_acorde_rejeita_invalidos(invalido):
    with pytest.raises(ValueError):
        sequencias.normalizar_acorde(invalido)


def test_canonicalizar_colapsa_repetidos_consecutivos():
    assert sequencias.canonicalizar_acordes(['C', 'C', 'G', 'G', 'Am']) == ['C', 'G', 'Am']
    assert sequencias.canonicalizar_acordes(['C', 'G', 'C']) == ['C', 'G', 'C']


def test_canonicalizar_valida_quantidade():
    with pytest.raises(ValueError):
        sequencias.canonicalizar_acordes(['C'])
    with pytest.raises(ValueError):
        sequencias.canonicalizar_acordes(['C%d' % i for i in range(13)])


def test_chave_ignora_caixa_e_espacos():
    assert sequencias.chave_sequencia(['C', 'G', 'Am']) == \
        sequencias.chave_sequencia(['c', 'g', 'am'])


def test_nome_padrao_usa_seta():
    assert sequencias.normalizar_nome(None, ['C', 'G', 'Am']) == 'C → G → Am'
    assert sequencias.normalizar_nome('  Meu   refrão ', ['C', 'G']) == 'Meu refrão'


def test_dividir_acordes_aceita_virgula_e_espaco():
    assert sequencias.dividir_acordes('C, G  Am,F') == ['C', 'G', 'Am', 'F']
    assert sequencias.dividir_acordes('') == []


def test_formato_concatenado_legado_e_resolvido():
    assert sequencias.legado_id_do_parametro('CGAmF') == 1
    assert sequencias.legado_id_do_parametro('cgamf') == 1
    assert sequencias.legado_id_do_parametro('C,G,Am,F') is None


# --------------------------------------------------------------------------
# Matching estrutural
# --------------------------------------------------------------------------

def test_matching_exige_run_contiguo_na_ordem():
    cifra = ['C', 'G', 'Am', 'F']
    assert sequencias.cifra_contem_sequencia(cifra, ['C', 'G'])
    assert sequencias.cifra_contem_sequencia(cifra, ['G', 'Am', 'F'])
    assert not sequencias.cifra_contem_sequencia(cifra, ['G', 'C'])
    assert not sequencias.cifra_contem_sequencia(cifra, ['C', 'Am'])


def test_matching_colapsa_repeticao_dos_dois_lados():
    assert sequencias.cifra_contem_sequencia(['C', 'C', 'G'], ['C', 'G'])
    assert sequencias.cifra_contem_sequencia(['C', 'G'], ['C', 'C', 'G'])


def test_matching_e_case_insensitive():
    assert sequencias.cifra_contem_sequencia(['c', 'g', 'am'], ['C', 'G'])
    assert sequencias.cifra_contem_sequencia(['C', 'G'], ['c', 'g'])


def test_matching_com_vazio_ou_sequencia_maior():
    assert not sequencias.cifra_contem_sequencia([], ['C', 'G'])
    assert not sequencias.cifra_contem_sequencia(['C', 'G'], [])
    assert not sequencias.cifra_contem_sequencia(['C'], ['C', 'G'])


def test_matching_ignora_tokens_invalidos_da_cifra():
    preparada = sequencias.preparar_cifra(['C', '[Intro]', 'G', '|', 'Am'])
    assert sequencias.cifra_contem_sequencia(preparada, ['C', 'G'])


# --------------------------------------------------------------------------
# GET /api/sequencias
# --------------------------------------------------------------------------

def test_get_sequencias_devolve_as_seis_legadas(client):
    dados = get_json(client, '/api/sequencias')
    assert [s['acordes'] for s in dados] == [
        ['Bm', 'G', 'D', 'A'],
        ['C', 'G', 'Am', 'F'],
        ['Em', 'G'],
        ['C', 'A7', 'Dm', 'G7'],
        ['Gm', 'F'],
        ['C', 'C7', 'F', 'Fm'],
    ]
    assert all(s['legado'] is True for s in dados)
    assert all(isinstance(s['id'], int) for s in dados)


# --------------------------------------------------------------------------
# POST /api/sequencias
# --------------------------------------------------------------------------

def test_post_valido_cadastra_e_aparece_no_catalogo(client):
    resposta = post_json(client, {'acordes': ['c', 'g', 'am']})
    assert resposta.status_code == 201
    criada = json.loads(resposta.get_data(as_text=True))
    assert criada['acordes'] == ['C', 'G', 'Am']
    assert criada['legado'] is False
    assert criada['nome'] == 'C → G → Am'

    catalogo = get_json(client, '/api/sequencias')
    assert len(catalogo) == 7
    assert catalogo[-1]['id'] == criada['id']


def test_post_aceita_nome_customizado(client):
    resposta = post_json(client, {'acordes': ['D', 'A', 'Bm'], 'nome': '  Meu   refrão '})
    assert resposta.status_code == 201
    assert json.loads(resposta.get_data(as_text=True))['nome'] == 'Meu refrão'


def test_post_colapsa_repetidos_consecutivos(client):
    resposta = post_json(client, {'acordes': ['C', 'C', 'G', 'G']})
    assert resposta.status_code == 201
    assert json.loads(resposta.get_data(as_text=True))['acordes'] == ['C', 'G']


def test_post_duplicado_devolve_409_com_a_existente(client):
    primeira = post_json(client, {'acordes': ['D', 'A', 'Bm']})
    assert primeira.status_code == 201
    existente = json.loads(primeira.get_data(as_text=True))

    segunda = post_json(client, {'acordes': ['d', 'a', 'bm']})
    assert segunda.status_code == 409
    corpo = json.loads(segunda.get_data(as_text=True))
    assert corpo['sequencia']['id'] == existente['id']

    assert len(get_json(client, '/api/sequencias')) == 7


def test_post_duplicado_de_legada_devolve_409(client):
    resposta = post_json(client, {'acordes': ['C', 'G', 'Am', 'F']})
    assert resposta.status_code == 409
    corpo = json.loads(resposta.get_data(as_text=True))
    assert corpo['sequencia']['legado'] is True


@pytest.mark.parametrize('payload', [
    {'acordes': []},
    {'acordes': ['C']},
    {'acordes': 'C,G'},
    {'acordes': ['C', 'H']},
    {'acordes': ['C', 'G'] * 7},
    {'acordes': ['C', 'G'], 'nome': 'x' * 81},
    {},
])
def test_post_invalido_devolve_400(client, payload):
    resposta = post_json(client, payload)
    assert resposta.status_code == 400
    assert 'erro' in json.loads(resposta.get_data(as_text=True))


def test_post_sem_json_devolve_400(client):
    resposta = client.post('/api/sequencias', data='nao e json',
                           content_type='application/json')
    assert resposta.status_code == 400


# --------------------------------------------------------------------------
# Busca por sequência
# --------------------------------------------------------------------------

def contar_matches(acordes):
    alvo = sequencias.preparar_sequencia(acordes)
    return sum(
        1 for musica in main.musicas.values()
        if alvo in musica.cifra_preparada
    )


def sequencia_nova_com_resultados(minimo=1, maximo=50, tamanho=6):
    """Acha uma sequência estrutural (fora do legado) com poucos resultados."""
    legadas = {sequencias.chave_sequencia(seq['acordes'])
               for seq in sequencias.LEGACY_SEQUENCES}
    for musica in main.musicas.values():
        cifra = musica.cifra
        if len(cifra) < tamanho:
            continue
        try:
            candidata = sequencias.canonicalizar_acordes(cifra[:tamanho])
        except ValueError:
            continue
        if sequencias.chave_sequencia(candidata) in legadas:
            continue
        if minimo <= contar_matches(candidata) <= maximo:
            return candidata
    pytest.fail('nenhuma sequência candidata encontrada')


def test_busca_por_sequencia_nova_bate_com_o_matching_estrutural(client):
    acordes = sequencia_nova_com_resultados()
    criada = post_json(client, {'acordes': acordes})
    assert criada.status_code == 201

    esperado = {
        m.id_unico_musica for m in main.musicas.values()
        if sequencias.cifra_contem_sequencia(m.cifra_preparada, acordes)
    }
    obtido = set(paginar(client, 'sequencia=' + urllib.parse.quote(','.join(acordes))))
    assert esperado
    assert obtido == esperado


def test_busca_por_sequencia_desconhecida_devolve_lista_vazia(client):
    assert get_json(client, '/similares?sequencia=C,Xyz') == []
    assert get_json(client, '/similares?sequencia=QQQ') == []


def test_busca_legada_aceita_formato_concatenado(client):
    por_virgula = set(paginar(client, 'sequencia=C,G,Am,F'))
    concatenada = set(paginar(client, 'sequencia=CGAmF'))
    assert por_virgula
    assert concatenada == por_virgula


def test_filtro_por_genero_na_busca_por_sequencia(client):
    dados = get_json(client, '/similares?sequencia=C,G,Am,F&generos=Rock')
    assert dados
    assert {m['genero'] for m in dados} == {'Rock'}


def test_resultado_de_sequencia_tem_formato_legado(client):
    dados = get_json(client, '/similares?sequencia=C,G,Am,F')
    assert dados
    assert 'diferenca' not in dados[0]
    assert 'intersecao' not in dados[0]
    for campo in ('id_unico_musica', 'nome_artista', 'nome_musica',
                  'popularidade', 'acordes', 'genero', 'url'):
        assert campo in dados[0]


def test_paginacao_da_busca_por_sequencia(client, monkeypatch):
    monkeypatch.setattr(main, 'TAM_PAGINA', 1)
    acordes = ['C', 'G']
    legadas = {sequencias.chave_sequencia(seq['acordes'])
               for seq in sequencias.LEGACY_SEQUENCES}
    assert sequencias.chave_sequencia(acordes) not in legadas
    assert contar_matches(acordes) >= 2

    assert post_json(client, {'acordes': acordes}).status_code == 201
    query = 'sequencia=' + urllib.parse.quote(','.join(acordes))

    pagina1 = get_json(client, '/similares?%s&pagina=1' % query)
    pagina2 = get_json(client, '/similares?%s&pagina=2' % query)
    assert len(pagina1) == 1
    assert pagina2
    assert {m['id_unico_musica'] for m in pagina1}.isdisjoint(
        {m['id_unico_musica'] for m in pagina2})


# --------------------------------------------------------------------------
# Persistência
# --------------------------------------------------------------------------

def test_cadastro_sobrevive_a_nova_conexao(client):
    criada = json.loads(post_json(client, {'acordes': ['E', 'B', 'C#m']}).get_data(as_text=True))

    # nova conexão, como faria outro worker/processo
    conn = sqlite3.connect(db.caminho_db())
    try:
        linha = conn.execute(
            'SELECT nome, acordes, legado_id FROM sequencias WHERE id = ?',
            (criada['id'],)).fetchone()
    finally:
        conn.close()

    assert linha is not None
    assert linha[0] == 'E → B → C#m'
    assert json.loads(linha[1]) == ['E', 'B', 'C#m']
    assert linha[2] is None


def test_init_db_e_idempotente(client):
    antes = get_json(client, '/api/sequencias')
    db.init_db()
    db.init_db()
    depois = get_json(client, '/api/sequencias')
    assert len(depois) == 6
    assert [s['id'] for s in depois] == [s['id'] for s in antes]
