# Relatório de testes — Sequências de Acordes Customizadas

## Resultado geral

- **52 testes, 52 passando** (`pytest -q`).
- **Cobertura total: 86%** (374 statements, 53 não cobertos).
- Regressão das 6 originais: **passa**, com os mesmos conjuntos de IDs
  capturados antes da mudança (199 / 296 / 4 / 5 / 7 / 3 = 514 músicas).
- Fluxo completo no browser: **verificado manualmente** (catálogo, busca
  original, cadastro, preview, busca automática, badge, persistência após
  reload).

## Cobertura

| Arquivo | Statements | Não cobertos | Cobertura |
|---|---:|---:|---:|
| `db.py` | 72 | 5 | 93% |
| `main.py` | 193 | 42 | 78% |
| `musica.py` | 18 | 1 | 94% |
| `sequencias.py` | 91 | 5 | 95% |
| **Total** | **374** | **53** | **86%** |

### O que cada grupo de testes verifica

**Domínio (`tests/test_sequencias.py` — canonicalização e matching)**

- `normalizar_acorde` ajusta só a fundamental (`am`→`Am`, `c#m`→`C#m`,
  `bb9`→`Bb9`) e preserva sufixos (`Dm4/7`).
- Rejeita vazio, espaços, `H`, acorde com espaço, `None` e número.
- `canonicalizar_acordes` colapsa repetição consecutiva, mas preserva
  repetição não consecutiva (`C,G,C` ≠ `C,G`).
- Valida mínimo de 2 e máximo de 12 acordes.
- `chave_sequencia` ignora caixa e espaços.
- Nome padrão usa `→`; nome explícito tem espaços normalizados.
- `dividir_acordes` aceita vírgula e/ou espaço.
- Formato concatenado antigo (`CGAmF`) resolve para o `legado_id` correto.
- Matching exige run contíguo e ordem; quebra com acorde intermediário.
- Colapsa repetição dos dois lados, é case-insensitive, lida com vazio e com
  sequência maior que a cifra.
- Ignora tokens inválidos da cifra (ex.: `[Intro]`, `|`).

**API do catálogo (`tests/test_sequencias.py`)**

- `GET /api/sequencias` devolve as 6 legadas na ordem e com `legado=true`.
- `POST` válido cria, aparece no catálogo e deriva o nome.
- `POST` aceita nome customizado e normaliza espaços.
- `POST` colapsa repetidos consecutivos.
- Duplicata devolve `409` com a sequência existente, inclusive quando a
  duplicata é uma das 6 originais.
- `400` para: lista vazia, 1 acorde, acordes como string, acorde inválido,
  mais de 12 acordes, nome > 80, payload vazio e corpo não-JSON.

**Busca por sequência (`tests/test_sequencias.py`)**

- Uma sequência nova (achada dinamicamente no dataset) retorna exatamente o
  conjunto calculado pelo matching estrutural.
- Sequência desconhecida devolve `[]`.
- Formato concatenado e formato por vírgula devolvem o mesmo conjunto.
- Filtro de gênero funciona.
- Resultado tem formato de card legado (sem `diferenca`/`intersecao`).
- Paginação de 1 em 1 não repete IDs entre páginas.

**Persistência (`tests/test_sequencias.py`)**

- Cadastro feito pela API é visível em uma conexão SQLite nova, com `nome`,
  `acordes` JSON e `legado_id = NULL`.
- `init_db()` chamado duas vezes não duplica as 6 nem muda seus IDs.

**Regressão (`tests/test_regressao_legado.py`)**

- Para cada uma das 6: pagina `/similares?sequencia=...` e compara o conjunto
  de IDs com `tests/fixtures/legacy_similar_ids.json`.
- Para cada uma das 6: recalcula os IDs direto da tag `seqs_famosas` do CSV e
  compara com o fixture, provando que o snapshot veio da mesma base.

## Teste de regressão obrigatório

As 6 sequências originais precisam continuar retornando os mesmos resultados
de antes da migração para o banco.

**Como foi verificado**

1. Antes de qualquer mudança, `scripts/snapshot_legacy_results.py` foi rodado
   no código original e gravou `tests/fixtures/legacy_similar_ids.json` com a
   lista completa de IDs, paginando de 100 em 100.
2. Contagens do snapshot: `199, 296, 4, 5, 7, 3` (total 514).
3. Depois da implementação, `tests/test_regressao_legado.py` repete as buscas
   no código novo e compara **conjuntos** de IDs.
4. Um segundo teste recalcula os IDs da tag `SEQ_FAMOSA` no CSV carregado e
   compara com o fixture.

**Por que conjuntos e não listas**

`main.py` monta `generos = list(set(generos))`; a ordem dos gêneros na coleção
varia entre processos. A ordem dentro de cada gênero é estável (popularidade),
mas a ordem entre gêneros não é. Comparar listas produziria falha falsa. O
conjunto de IDs é o contrato que importa para o usuário.

**Resultado**

Todos os 6 casos passam, com contagem e conjunto idênticos ao snapshot.
Nenhuma música foi adicionada ou removida das buscas originais.

## Como rodar

```bash
# instalar dependências de teste
pip install -r requirements-dev.txt

# suíte completa
pytest -q

# suíte + cobertura
pytest -q --cov=main --cov=db --cov=sequencias --cov=musica \
  --cov-report=term-missing
```

No Windows com o virtualenv do projeto:

```bash
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m pytest -q --cov=main --cov=db --cov=sequencias \
  --cov=musica --cov-report=term-missing
```

`tests/conftest.py` aponta `CIFRAME_DB_PATH` para um arquivo temporário antes
de importar `main`, então a suíte nunca toca `instance/deciframe.db`.

## O que ficou de fora

- **Build/execução Docker**: o Docker Desktop não estava rodando no ambiente
  (`npipe:////./pipe/dockerDesktopLinuxEngine` indisponível). O `Dockerfile` e
  o volume foram revisados, mas o `docker build`/`docker run` não foi
  executado. A persistência foi provada no nível de SQLite (nova conexão +
  reload do browser), não no nível de recriação de container.
- **Vídeo nativo**: `ffmpeg` não está instalado, então o agente de browser não
  conseguiu gravar `.webm`. O demo foi composto como GIF a partir de
  screenshots reais do fluxo (com legendas), usando Pillow.
- **Testes de frontend automatizados**: o projeto não tem runner JS. A
  verificação do frontend foi manual, com asserções no DOM via browser
  automatizado (contagem de cards, badges, texto de sucesso, preview,
  persistência após reload). Não há teste de regressão visual de CSS.
- **Concorrência real**: o caminho de `IntegrityError` (dois cadastros iguais
  simultâneos) está implementado e tem `UNIQUE` no banco, mas não foi
  exercitado com threads/processos concorrentes.
- **Carga/performance**: não há benchmark de `/similares` com o catálogo cheio.
  O matching novo é um `in` sobre string pré-computada, e o catálogo tem
  dezenas de linhas; não foi tratado como risco.
- **Migrations**: o schema usa `CREATE TABLE IF NOT EXISTS`. Evolução futura de
  colunas exigirá migração explícita, que não existe hoje.
- **Navegadores além do Chrome**: o fluxo foi verificado apenas no Chrome
  headless usado pelo agente.
- **Acessibilidade automatizada**: não foi rodado axe-core nem auditoria WCAG
  formal nesta entrega.
