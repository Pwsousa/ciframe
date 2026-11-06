# coding: utf-8
"""Domínio das sequências de acordes: normalização, canonicalização e matching.

Este módulo é puro (só stdlib) para poder ser testado sem carregar o CSV nem
abrir o banco. A persistência fica em ``db.py``.
"""
import re
import unicodedata

# Separador usado na chave canônica gravada no banco. Acordes validados nunca
# contêm "|", então a chave é inequívoca.
SEPARADOR_CHAVE = '|'

# Separador usado na cifra preparada para matching. É um caractere de controle
# que não aparece em símbolos de acorde, o que garante limites de token exatos.
SEPARADOR_MATCHING = '\x1f'

# Símbolo de acorde: fundamental A-G (aceita minúscula na entrada), acidente
# opcional (#/b) e sufixo (m, 7, 9, 4/7, (7/9), /B, etc.). É permissivo de
# propósito: o dataset usa cifras como "Dm4/7", "Bb5-/D" e "A4(7/9)".
_ACORDE_RE = re.compile(r'^[A-Ga-g][#b]?[A-Za-z0-9()+\-/#°ºø.]*$')

MIN_ACORDES = 2
MAX_ACORDES = 12
MAX_ACORDES_BRUTOS = 64
MAX_TAMANHO_ACORDE = 20
MAX_TAMANHO_NOME = 80

# As 6 sequências que já existiam em main.py (linhas 40-45 no master).
# ``legado_id`` é o índice usado na coluna SEQ_FAMOSA do CSV.
LEGACY_SEQUENCES = [
    {'legado_id': 0, 'nome': 'Bm → G → D → A', 'acordes': ['Bm', 'G', 'D', 'A']},
    {'legado_id': 1, 'nome': 'C → G → Am → F', 'acordes': ['C', 'G', 'Am', 'F']},
    {'legado_id': 2, 'nome': 'Em → G', 'acordes': ['Em', 'G']},
    {'legado_id': 3, 'nome': 'C → A7 → Dm → G7', 'acordes': ['C', 'A7', 'Dm', 'G7']},
    {'legado_id': 4, 'nome': 'Gm → F', 'acordes': ['Gm', 'F']},
    {'legado_id': 5, 'nome': 'C → C7 → F → Fm', 'acordes': ['C', 'C7', 'F', 'Fm']},
]


def _chave_acorde(acorde):
    """Representação case-insensitive usada para comparar acordes."""
    return normalizar_acorde(acorde).casefold()


def _chave_concatenada(valor):
    """Chave do formato antigo (``CGAmF``), sem validar como acorde único."""
    if not isinstance(valor, str):
        return ''
    return unicodedata.normalize('NFKC', valor).strip().casefold()


def normalizar_acorde(acorde):
    """Valida e normaliza um acorde para exibição.

    - Rejeita valores que não são string, vazios ou fora do formato.
    - ``NFKC`` + ``strip``.
    - A fundamental recebe maiúscula (``am`` -> ``Am``); o resto é preservado
      (``c#m`` -> ``C#m``, ``bb9`` -> ``Bb9``, ``Dm4/7`` -> ``Dm4/7``).
    """
    if not isinstance(acorde, str):
        raise ValueError('acorde deve ser texto')
    limpo = unicodedata.normalize('NFKC', acorde).strip()
    if not limpo:
        raise ValueError('acorde vazio')
    if len(limpo) > MAX_TAMANHO_ACORDE or not _ACORDE_RE.match(limpo):
        raise ValueError('acorde inválido: %r' % acorde)
    return limpo[0].upper() + limpo[1:]


# Compatibilidade com o formato antigo ``/similares?sequencia=CGAmF``.
LEGACY_POR_CHAVE_CONCATENADA = {
    ''.join(_chave_acorde(a) for a in seq['acordes']): seq['legado_id']
    for seq in LEGACY_SEQUENCES
}


def canonicalizar_acordes(acordes):
    """Valida uma sequência e devolve a forma canônica.

    Repetições consecutivas são colapsadas (``C,C,G,G,Am`` -> ``C,G,Am``).
    A ordem é preservada e repetições não consecutivas continuam valendo
    (``C,G,C`` é diferente de ``C,G``).
    """
    if not isinstance(acordes, (list, tuple)):
        raise ValueError('acordes deve ser uma lista')
    if len(acordes) > MAX_ACORDES_BRUTOS:
        raise ValueError('informe no máximo %d acordes' % MAX_ACORDES_BRUTOS)

    canonicos = []
    for acorde in acordes:
        normalizado = normalizar_acorde(acorde)
        if not canonicos or canonicos[-1].casefold() != normalizado.casefold():
            canonicos.append(normalizado)

    if len(canonicos) < MIN_ACORDES:
        raise ValueError('informe pelo menos %d acordes' % MIN_ACORDES)
    if len(canonicos) > MAX_ACORDES:
        raise ValueError('informe no máximo %d acordes' % MAX_ACORDES)
    return canonicos


def chave_sequencia(acordes):
    """Chave canônica estável, case-insensitive, usada para deduplicar."""
    return SEPARADOR_CHAVE.join(_chave_acorde(a) for a in acordes)


def normalizar_nome(nome, acordes):
    """Valida o rótulo opcional; se vazio, deriva dos acordes."""
    if nome is None:
        nome = ''
    if not isinstance(nome, str):
        raise ValueError('nome deve ser texto')
    nome = ' '.join(nome.split())
    if len(nome) > MAX_TAMANHO_NOME:
        raise ValueError('nome deve ter no máximo %d caracteres' % MAX_TAMANHO_NOME)
    if not nome:
        nome = ' → '.join(acordes)
    return nome


def dividir_acordes(texto):
    """Divide o parâmetro ``sequencia`` por vírgula e/ou espaço."""
    if not texto:
        return []
    return [parte for parte in re.split(r'[\s,]+', texto.strip()) if parte]


def legado_id_do_parametro(valor):
    """Resolve o formato antigo concatenado (``CGAmF``) para um ``legado_id``."""
    return LEGACY_POR_CHAVE_CONCATENADA.get(_chave_concatenada(valor))


def preparar_cifra(cifra):
    """Prepara a cifra de uma música para matching em tempo real.

    Normaliza cada acorde, descarta tokens inválidos (ruído de tablatura) e
    colapsa repetições consecutivas. Devolve uma string delimitada por
    ``SEPARADOR_MATCHING``, o que permite testar a ocorrência de uma sequência
    contígua com um simples ``in``.
    """
    tokens = []
    for acorde in cifra or []:
        try:
            token = _chave_acorde(acorde)
        except ValueError:
            continue
        if not tokens or tokens[-1] != token:
            tokens.append(token)
    if not tokens:
        return ''
    return SEPARADOR_MATCHING + SEPARADOR_MATCHING.join(tokens) + SEPARADOR_MATCHING


def preparar_sequencia(acordes):
    """Prepara uma sequência canônica para o teste de run contíguo."""
    tokens = []
    for acorde in acordes or []:
        try:
            token = _chave_acorde(acorde)
        except ValueError:
            return ''
        if not tokens or tokens[-1] != token:
            tokens.append(token)
    if not tokens:
        return ''
    return SEPARADOR_MATCHING + SEPARADOR_MATCHING.join(tokens) + SEPARADOR_MATCHING


def cifra_contem_sequencia(cifra, acordes):
    """True se a sequência aparece como run contíguo na cifra.

    Aceita tanto a cifra bruta (lista de acordes) quanto o resultado de
    ``preparar_cifra``; o mesmo vale para a sequência. Ordem importa e um
    acorde intermediário quebra o match.
    """
    alvo = acordes if isinstance(acordes, str) else preparar_sequencia(acordes)
    if not alvo:
        return False
    preparada = cifra if isinstance(cifra, str) else preparar_cifra(cifra)
    return alvo in preparada
