# Plano — Sequências de Acordes Customizadas

> Roteiro executável da implementação. As decisões abaixo são as que
> sobreviveram à pesquisa e à implementação; desvios estão registrados na
> seção "Mudanças de plano durante a execução".

## Contexto

- O catálogo das 6 sequências vivia hardcoded no backend (`main.py`, linhas
  40–46) e 4 delas viviam hardcoded no frontend
  (`static/assets/js/controllers/sequencia.js`).
- `GET /similares?sequencia=...` só reconhecia as 6, via tag pré-computada
  `SEQ_FAMOSA` do CSV.
- Músicas e gêneros continuam vindo do CSV em memória; só o catálogo de
  sequências ganha persistência.
- Deploy: Docker único, local-only (`docs/adr/0001-local-only-docker-deploy.md`).

## Requisitos

### Funcionais

- Qualquer visitante cadastra uma sequência (lista ordenada de acordes), sem
  login.
- Qualquer sequência do catálogo (6 originais + novas) busca músicas, com
  resultados idênticos aos de hoje para as 6 originais.
- O catálogo persiste em banco e sobrevive a reinícios/recriações do container.
- `#/porsequencia` reflete o catálogo real do backend e permite cadastrar.

### Fixos (não são decisão)

- Músicas/gêneros continuam no CSV em memória.
- Docker único, local-only.
- Regressão exata das 6 originais.
- Endpoints continuam retornando `json.dumps(...)`, não `jsonify`.

### Decisões minhas

- Algoritmo de matching, banco, schema, API, validação e detalhes de frontend.

## Decisões de design

### Matching

- **Originais (`legado_id` 0–5)**: caminho da tag `SEQ_FAMOSA`, idêntico ao
  código anterior. É o único jeito de garantir regressão exata.
- **Comunitárias (`legado_id = NULL`)**: run contíguo na cifra normalizada.
  Ordem importa; acorde intermediário quebra o match; repetições consecutivas
  são colapsadas dos dois lados; comparação é case-insensitive.
- **Normalização**: `NFKC` + `strip`, regex permissiva de símbolo de acorde,
  fundamental em maiúscula, `casefold` para comparar.
- **Cifra preparada**: calculada uma vez por música na carga do CSV
  (`Musica.cifra_preparada`), para o match ser um `in` sobre string delimitada
  por `\x1f` em vez de varrer listas por request.

### Banco

- SQLite (`sqlite3`, stdlib), arquivo `instance/deciframe.db`.
- Override por `CIFRAME_DB_PATH` (usado pelos testes).
- `PRAGMA journal_mode=WAL` e `busy_timeout=5000`; conexão curta por operação.
- `VOLUME ["/app/instance"]` no Dockerfile. **Não** usar `/app/data`: o volume
  esconderia o `dataset_final.csv`.

### Schema

`sequencias(id, nome, acordes, chave, legado_id, criada_em)`:

- `chave TEXT NOT NULL UNIQUE`: dedup canônica (`c|g|am`), sensível à ordem e
  insensível a caixa.
- `legado_id INTEGER UNIQUE NULL`: 0–5 para as originais; `NULL` para novas.
- `acordes TEXT` em JSON, na ordem canônica.
- Seed idempotente por consulta à `chave` (não `INSERT OR IGNORE`, que
  consumiria ids do AUTOINCREMENT).

### API

- `GET /api/sequencias` → lista pública (`id`, `nome`, `acordes`, `legado`,
  `criada_em`).
- `POST /api/sequencias` → `201` criada; `400` inválida; `409` duplicada com a
  existente no corpo.
- `GET /similares?sequencia=...` → aceita vírgula/espaço e o formato
  concatenado antigo; desconhecida → `[]`; paginação e filtro de gênero
  inalterados; formato de card legado.
- Respostas sempre `json.dumps(...)`; CORS `*` inalterado.

### Validação

- `acordes` precisa ser lista com 2–12 acordes canônicos (máx. 64 brutos).
- Cada acorde: string, até 20 caracteres, regex permissiva.
- `nome` opcional, até 80 caracteres; vazio → `' → '.join(acordes)`.
- Duplicada → `409`, não sobrescreve nem cria outra linha.

### Frontend

- Carregar catálogo de `GET api/sequencias`; remover hardcode.
- Badges `original`/`comunidade`; cores distintas.
- Formulário com nome opcional + acordes, preview ao digitar.
- Estados de carregamento, erro de catálogo, catálogo vazio, erro/sucesso de
  cadastro, busca em andamento e busca vazia.
- Após `201`, recarregar catálogo e buscar a criada; após `409`, buscar a
  existente.
- Manter layout e busca atuais.

## Plano de implementação

Passos na ordem em que foram executados:

1. [x] Capturar a linha de base antes de tocar no código:
   `scripts/snapshot_legacy_results.py` → `tests/fixtures/legacy_similar_ids.json`
   (199/296/4/5/7/3 = 514 músicas).
2. [x] Medir algoritmos candidatos contra a tag do CSV:
   `scripts/analyze_seq_matching.py` (conjunto, subsequência, run contíguo;
   precisão/recall e checagem de igualdade exata).
3. [x] Criar `sequencias.py` (puro): normalização, canonicalização, chave,
   parsing do parâmetro, preparação de cifra e `cifra_contem_sequencia`.
4. [x] Criar `db.py`: conexão, schema, seed idempotente, listagem, busca por
   chave/legado, cadastro com dedup e `SequenciaDuplicada`.
5. [x] Ajustar `musica.py` para pré-computar `cifra_preparada` na carga.
6. [x] Ajustar `main.py`:
   - inicializar o banco após carregar o CSV;
   - `GET`/`POST /api/sequencias`;
   - resolver `?sequencia=` para catálogo (vírgula/espaço e concatenado);
   - manter tag para `legado_id` e run contíguo para novas;
   - preservar `json.dumps` e o formato de card.
7. [x] Reescrever `sequencia.js`: catálogo dinâmico, badges, formulário,
   preview, estados, cadastro e busca automática.
8. [x] Reescrever `sequencia.html` e completar `app.css` para os novos
   elementos, mantendo o layout existente.
9. [x] Docker: `VOLUME ["/app/instance"]`; ignorar `instance/` no git e no
   docker build; documentar `-v ciframe-data:/app/instance`.
10. [x] Testes: `tests/conftest.py` (DB temporário), unitários de domínio, API,
    persistência e regressão das 6.
11. [x] Rodar suíte + cobertura e corrigir o que falhou.
12. [x] Smoke test manual no browser: catálogo, busca original, cadastro,
    busca automática, badge, persistência após reload.
13. [x] Documentação: preencher 01–04, ADR 0002, README/AGENTS, GIF de demo.

### Arquivos afetados

| Arquivo | Mudança |
|---|---|
| `main.py` | Rotas `/api/sequencias`, resolução de `?sequencia=`, tag para legado, run contíguo para novas, `json.dumps` preservado |
| `db.py` (novo) | SQLite, schema, seed, listagem, busca, cadastro, dedup |
| `sequencias.py` (novo) | Normalização, canonicalização, chave, parsing, matching |
| `musica.py` | `cifra_preparada` pré-computada |
| `static/assets/js/controllers/sequencia.js` | Catálogo dinâmico, formulário, preview, estados, pós-cadastro |
| `static/templates/sequencia.html` | Formulário, estados, badges, lista dinâmica |
| `static/assets/css/app.css` | Estilos de catálogo, formulário, preview, estados |
| `Dockerfile` | `VOLUME ["/app/instance"]` |
| `.gitignore` / `.dockerignore` | Ignorar `instance/` e artefatos de teste |
| `requirements-dev.txt` (novo) | `pytest`, `pytest-cov` |
| `tests/` (novo) | `conftest.py`, unitários/API, regressão, fixture |
| `scripts/analyze_seq_matching.py` (novo) | Evidência da pesquisa |
| `scripts/snapshot_legacy_results.py` (novo) | Linha de base da regressão |
| `README.md` / `AGENTS.md` | Banco, volume, testes, gotchas |
| `docs/adr/0002-persist-custom-sequences.md` | ADR da persistência |
| `docs/features/sequencias-customizadas/01..04` | Fases do RePPIT |
| `docs/features/sequencias-customizadas/demo-sequencias.gif` | Demo no browser |

### Mudanças de plano durante a execução

Registradas porque o enunciado pede que o plano não fique desatualizado:

1. **Caminho do banco**: o plano inicial era `data/sequencias.db`. A pesquisa
   de Docker mostrou que um volume em `/app/data` esconderia o
   `dataset_final.csv`. Mudou para `instance/deciframe.db` e
   `VOLUME ["/app/instance"]`.
2. **Caminho da API**: o plano inicial era `/sequencias`. O frontend usa
   caminhos relativos e já chamava `api/sequencias`; mantivemos
   `/api/sequencias` para não introduzir um segundo padrão.
3. **Algoritmo**: o plano inicial era matching por subconjunto de acordes. A
   análise mostrou 31.102 falsos positivos (precisão 1,63%). Trocamos por run
   contíguo (precisão 7,91%) para as novas, mantendo a tag para as 6.
4. **Fallback**: o plano previa "usar a tag só se a regressão falhar". A
   pesquisa mostrou que **sempre** falha (nenhum algoritmo é exato), então a
   tag deixou de ser fallback e virou o caminho oficial das 6.
5. **Validação**: duplicados passaram de "a decidir" para `409` com a
   sequência existente, porque o catálogo é aberto e repetição é ruído.
6. **Módulos**: o plano previa tudo em `main.py`. Separar `sequencias.py`
   (puro) e `db.py` (persistência) permitiu testar domínio sem CSV/banco e
   deixou `main.py` com as rotas.
7. **Nome da env var**: `CIFRAME_DB_PATH` (nome do projeto), não
   `DECIFRAME_DB_PATH`.
8. **Seed**: `INSERT OR IGNORE` foi trocado por checagem explícita da `chave`,
   porque o `OR IGNORE` consumia ids do AUTOINCREMENT a cada boot.

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Regressão nas 6 originais | Snapshot antes da mudança + teste por conjunto de IDs + segundo teste que recalcula da tag |
| Falsos positivos do run contíguo | Documentado; é o melhor algoritmo medido; as originais não dependem dele |
| Duplicata concorrente | `chave UNIQUE` + tratamento de `IntegrityError` → `409` |
| Perda de dados ao recriar container | `VOLUME /app/instance` + documentação do `-v` |
| Volume esconder o CSV | Banco fora de `/app/data`; documentado em README/AGENTS |
| Frontend e backend divergirem | Catálogo só vem de `/api/sequencias`; nenhum hardcode |
| Ordem de gêneros não determinística | Teste compara conjuntos, não listas |
| CSV lido com encoding errado no Windows | `open(..., encoding='utf-8')` |
| SQL injection | Placeholders `?` em todas as queries; validação antes de gravar |

## Testes (influencia a mudança)

- Regressão obrigatória das 6: mesmos conjuntos de IDs do snapshot.
- Unitários: normalização, canonicalização, chave, parsing, run contíguo,
  colapso de repetição, case-insensitive, tokens inválidos.
- API: GET com 6, POST válido, nome, colapso, duplicata 409 (inclusive legada),
  400 para payloads inválidos, busca nova, busca desconhecida, formato
  concatenado, filtro de gênero, formato de card, paginação.
- Persistência: cadastro visível em nova conexão; `init_db` idempotente.
- Manual: fluxo completo no browser + GIF.

## Observabilidade (não se aplica)

- O projeto não tem métricas/logs estruturados/tracing; a mudança não introduz
  nenhum. Erros de validação voltam no corpo JSON.

## Rollout (não se aplica)

- Deploy local-only via Docker único; sem staging/produção separados. Rollout é
  rebuild + recriar o container com o volume.

## Segurança

- Cadastro anônimo por requisito; não há autenticação a implementar.
- Entrada pública validada no backend antes de gravar.
- SQL sempre com placeholders `?`, nunca concatenação.
- Limites de tamanho (acorde 20, nome 80, 2–12 acordes) reduzem abuso trivial.
- CORS `*` mantido (comportamento atual).
- Não há secrets no código; o caminho do banco é configurável por env.

## Definição de pronto

- [x] Cadastro anônimo funciona.
- [x] Busca por sequência nova funciona e retorna músicas.
- [x] As 6 originais continuam idênticas (regressão documentada).
- [x] Catálogo persiste (arquivo SQLite + volume documentado).
- [x] `#/porsequencia` exibe o catálogo do backend e permite cadastrar.
- [x] Suíte automatizada passa com cobertura documentada.
- [x] Demo no browser gravada em GIF.
- [x] Fases 01–04 e ADR 0002 preenchidos.

## Prazo / Timeline

- Não informado no enunciado. Execução em sessão única, com pesquisa e
  snapshot antes da implementação.
