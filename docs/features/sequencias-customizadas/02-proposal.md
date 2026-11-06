# Proposta — Sequências de Acordes Customizadas

A proposta parte da pesquisa: as 6 originais são curadoria em CSV, não
resultado de algoritmo; o run contíguo é o algoritmo estrutural com melhor
precisão; SQLite é o banco embarcado que cabe no container único; e o frontend
precisa de uma fonte única de catálogo.

## Abordagem escolhida

### Algoritmo de matching

Uma sequência cadastrada é uma **lista ordenada de acordes**. Ela "aparece" em
uma música quando ocorre como **run contíguo** na cifra da música, depois de
normalizada dos dois lados.

Definição operacional:

1. **Normalização do acorde**: `NFKC`, `strip`, validação por regex
   `^[A-Ga-g][#b]?[A-Za-z0-9()+\-/#°ºø.]*$`, fundamental em maiúscula. O resto
   do símbolo é preservado (`c#m` → `C#m`, `Dm4/7` continua `Dm4/7`).
2. **Canonicalização da sequência**: normaliza cada acorde e colapsa
   repetições **consecutivas** (`C, C, G, G, Am` → `C, G, Am`). A ordem é
   preservada; repetição não consecutiva continua válida (`C, G, C` ≠ `C, G`).
3. **Preparação da cifra**: normaliza cada acorde, descarta tokens que não são
   acorde (ruído de tablatura/marcadores) e colapsa repetições consecutivas.
   O resultado é uma string delimitada por um separador de controle (`\x1f`),
   o que permite testar o run com um `in` exato, sem casar `C` dentro de `C#m`.
4. **Match**: a sequência canônica delimitada precisa ser substring da cifra
   preparada. Isso exige ordem e contiguidade: `C, G` casa em `C G Am F`, mas
   `G, C` e `C, Am` não casam.

**Exceção deliberada — as 6 originais.** Elas continuam casando pela tag
`SEQ_FAMOSA` do CSV (`legado_id` 0–5), porque a pesquisa mostrou que nenhum
algoritmo estrutural reproduz a curadoria e o enunciado exige resultados
idênticos. O banco guarda `legado_id` para identificar esse caminho. Sequências
novas têm `legado_id = NULL` e usam o run contíguo.

Consequência assumida: as duas famílias têm semânticas diferentes. É o preço
explícito de preservar a regressão sem congelar o catálogo novo.

### Banco de dados

**SQLite via `sqlite3` da stdlib.** Motivos:

- zero dependência nova e zero serviço externo, compatível com o container
  único do ADR 0001;
- arquivo único, transações e `UNIQUE`, que resolvem dedup de forma atômica;
- `WAL` + `busy_timeout` para leitura concorrente razoável no uso real
  (catálogo pequeno, escritas raras);
- conexões curtas por operação, sem pool nem estado global.

Arquivo: `instance/deciframe.db` (relativo à raiz do projeto), com override por
`CIFRAME_DB_PATH`. Fica **fora** de `data/` de propósito: um volume em
`/app/data` esconderia o `dataset_final.csv`.

Persistência entre recriações de container: `VOLUME ["/app/instance"]` no
`Dockerfile` e `docker run -v ciframe-data:/app/instance`.

### Esquema de dados (alto nível)

Uma tabela `sequencias`:

| Campo | Tipo | Papel |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | identidade pública |
| `nome` | TEXT NOT NULL | rótulo; se vazio, derivado dos acordes (`C → G → Am`) |
| `acordes` | TEXT NOT NULL | lista JSON na ordem canônica |
| `chave` | TEXT NOT NULL UNIQUE | dedup canônica (`c\|g\|am`), case-insensitive e sensível à ordem |
| `legado_id` | INTEGER UNIQUE NULL | 0–5 para as originais; `NULL` para comunitárias |
| `criada_em` | TEXT NOT NULL | ISO-8601 UTC |

O seed das 6 originais é **idempotente**: consulta a `chave` antes de inserir.
Um `INSERT OR IGNORE` violaria o `UNIQUE` e ainda consumiria um id do
`AUTOINCREMENT` a cada inicialização — por isso a checagem explícita.

### API

Todos os endpoints continuam devolvendo `json.dumps(...)` como string (não
`jsonify`), preservando o contrato legado. O CORS `*` também é mantido.

**`GET /api/sequencias`** → `200`

```json
[
  {"id": 1, "nome": "Bm → G → D → A", "acordes": ["Bm","G","D","A"], "legado": true,  "criada_em": "..."},
  {"id": 7, "nome": "Riff de Wonderwall", "acordes": ["D","A","Bm","G"], "legado": false, "criada_em": "..."}
]
```

**`POST /api/sequencias`** — corpo JSON `{"nome": "opcional", "acordes": ["D","A","Bm","G"]}`

- `201` com a sequência criada (mesmo formato do GET);
- `400` com `{"erro": "..."}` para corpo inválido, acordes vazios, menos de 2
  ou mais de 12 acordes, acorde fora do formato, nome com mais de 80 caracteres;
- `409` com `{"erro": "sequência já cadastrada", "sequencia": {...}}` quando a
  chave canônica já existe (inclusive uma das 6 originais). O corpo devolve a
  existente para o frontend poder buscá-la em vez de só mostrar erro.

**`GET /similares?sequencia=...`** — aceita:

- formato do frontend: `C,G,Am,F` (vírgulas e/ou espaços);
- formato antigo concatenado das 6 originais: `CGAmF`;
- `&generos=Rock,Samba` e `&pagina=N` como hoje.

Sequência fora do catálogo → `[]` (mesmo contrato de "não encontrada" que o
frontend já trata). Resultado mantém o formato legado dos cards
(`id_unico_musica`, `nome_artista`, `nome_musica`, `popularidade`, `acordes`,
`genero`, `url`), sem `diferenca`/`intersecao`.

### Frontend

`#/porsequencia` passa a ter uma fonte única: `GET /api/sequencias`.

- **Catálogo dinâmico**: remove as 4 sequências hardcoded e renderiza o que o
  backend devolver, com badge `original` (legado) ou `comunidade`.
- **Cadastro**: botão `+` abre um formulário com nome opcional e sequência de
  acordes. Preview dos acordes é atualizado enquanto digita (sem esperar o
  backend). Submit faz `POST /api/sequencias`.
- **Estados**: `carregando catálogo`, erro de catálogo com botão "tentar de
  novo", catálogo vazio, erro de cadastro, sucesso, busca em andamento, busca
  sem resultados.
- **Fluxo pós-cadastro**: recarrega o catálogo, encontra a sequência criada e
  dispara a busca automaticamente. Em `409`, mostra "já cadastrada" e busca a
  existente.
- **Busca**: continua enviando `similares?sequencia=<acordes por vírgula>` e
  respeita o filtro de gênero. Nada de hardcode.

## Alternativas consideradas e descartadas

1. **Um único algoritmo estrutural para todas as sequências.** Seria mais
   simples conceitualmente, mas a pesquisa mostrou que nenhum algoritmo
   reproduz a tag curada; adotá-lo quebraria o critério de regressão
   obrigatório. Descartado.
2. **Matching por conjunto de acordes.** Recall 100%, mas 31.102 falsos
   positivos (precisão 1,63%). Inútil na prática. Descartado.
3. **Arquivo JSON em vez de SQLite.** Sem `UNIQUE` atômico e sujeito a
   corrupção em escrita concorrente, num catálogo aberto e anônimo.
   Descartado.
4. **PostgreSQL/MySQL/Redis.** Exigiriam serviço extra e violariam o container
   único local-only. Descartado.
5. **Buscar por ID da sequência em vez dos acordes.** Mais limpo, mas mudaria
   o contrato de `/similares` já usado pelo frontend e por links existentes.
   Preferimos aceitar os dois formatos sem quebrar nada.

## Escopo explícito

**Dentro do escopo:**

- persistência do catálogo de sequências em SQLite, com seed idempotente das 6
  originais;
- `GET`/`POST /api/sequencias` e adaptação de `GET /similares?sequencia=`;
- matching estrutural por run contíguo para sequências comunitárias;
- preservação exata das 6 originais via `SEQ_FAMOSA`;
- frontend dinâmico com cadastro, preview, estados e busca automática;
- volume Docker para `/app/instance`;
- testes unitários, de API, de persistência e de regressão.

**Fora do escopo (e por quê):**

- moderação/autenticação do catálogo: o enunciado exige cadastro anônimo;
- edição/remoção de sequências: não foi pedido, e remoção exigiria decidir o
  que fazer com links antigos;
- migração de músicas/gêneros para o banco: o enunciado fixa CSV em memória;
- paginação/ordenação nova do catálogo: o volume é pequeno e a ordem de criação
  é suficiente;
- busca por ID e mudança de contrato dos endpoints: evitar regressão de API;
- migrações versionadas de schema: o schema é criado com
  `CREATE TABLE IF NOT EXISTS`; uma evolução futura precisará de migração
  explícita.
