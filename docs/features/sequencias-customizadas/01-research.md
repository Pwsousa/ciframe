# Pesquisa — Sequências de Acordes Customizadas

Esta fase foi feita antes da implementação, com três fontes de evidência:

1. leitura do código e dos dados que já existiam;
2. um script de análise rodado contra o dataset real
   (`scripts/analyze_seq_matching.py`);
3. um snapshot dos resultados das 6 sequências originais, capturado **antes**
   de qualquer mudança (`scripts/snapshot_legacy_results.py`).

Nada aqui é suposição: os números abaixo saíram dessas execuções.

## 1. Algoritmo de matching

### Como as 6 sequências funcionam hoje

No `main.py` original (linhas 40–46) o catálogo é um dicionário fixo:

```python
sequencias = {'BmGDA': 0, 'CGAmF': 1, 'EmG': 2, 'CA7DmG7': 3, 'GmF': 4, 'CC7FFm': 5}
```

O índice 0–5 **não é calculado**. Ele vem da coluna `SEQ_FAMOSA` do
`data/top/dataset_final.csv` (índice 7), que já contém uma tag pré-computada por
música. A busca em `get_similares_por_sequencia` é literalmente
`str(id_seq) in musica.seqs_famosas`. Ou seja: hoje não existe algoritmo de
matching em tempo real — existe uma curadoria gravada no CSV.

Isso importa porque o critério de regressão do enunciado é "as 6 originais
continuam retornando os mesmos resultados". Qualquer algoritmo novo que
substitua a tag corre o risco de quebrar esse critério.

### Dados disponíveis para um matching em tempo real

`musica.py` expõe:

- `musica.cifra`: lista de acordes na ordem em que aparecem na cifra (já limpa
  por `limpa_cifra`, que remove tablaturas e separa acordes por espaço);
- `musica.acordes`: `list(set(cifra))` — conjunto, sem ordem e sem repetição;
- `musica.seqs_famosas`: a tag do CSV.

O dataset tem **67.585 músicas** carregadas. As cifras reais contêm grafias
variadas (`Dm4/7`, `Bb5-/D`, `A4(7/9)`, `G/B`, acidentes com `#` e `b`) e
também ruído de tablatura/marcadores. Qualquer matching precisa normalizar
antes de comparar.

### Algoritmos candidatos medidos contra a tag do CSV

O script `scripts/analyze_seq_matching.py` replica a leitura do `main.py`
(inclusive os `replace('NA', '')`, `[:-1]`, `split(',')`) e compara quatro
definições de "a sequência aparece na música" contra a tag `SEQ_FAMOSA`:

| Definição | TP | FP | FN | Precisão | Recall |
|---|---:|---:|---:|---:|---:|
| Conjunto (todos os acordes presentes, ordem ignorada) | 514 | 31.102 | 0 | 1,63% | 100% |
| Conjunto normalizado | 514 | 31.102 | 0 | 1,63% | 100% |
| Subsequência ordenada (pode pular acordes) | 514 | 28.127 | 0 | 1,79% | 100% |
| **Run contíguo (sem pular acordes, dedup)** | **514** | **5.980** | **0** | **7,91%** | **100%** |

Contagem real por sequência (tag do CSV):

| Índice | Acordes | Músicas |
|---|---|---:|
| 0 | Bm, G, D, A | 199 |
| 1 | C, G, Am, F | 296 |
| 2 | Em, G | 4 |
| 3 | C, A7, Dm, G7 | 5 |
| 4 | Gm, F | 7 |
| 5 | C, C7, F, Fm | 3 |

Total: **514 músicas**.

Leituras que fiz desses números:

- **Recall é 100% em todas as definições**: toda música marcada na tag contém
  todos os acordes da sequência em algum lugar da cifra. A tag é um
  subconjunto dos matches estruturais, nunca o contrário.
- **Precisão é baixíssima**: o conjunto simples gera 31 mil falsos positivos
  (uma música com `C`, `G`, `Am` e `F` espalhados em qualquer ordem entra). O
  run contíguo reduz o ruído em ~5x, mas ainda erra muito.
- **Nenhum algoritmo reproduz a tag exatamente.** O script imprime
  `exact=False` para todas as variantes (conjunto, conjunto normalizado,
  subsequência ordenada, run contíguo, e as versões com dedup). A tag foi
  curada, não gerada por uma regra estrutural.
- O run contíguo é o que mais se aproxima do "refrão" que um músico reconhece:
  `C → G → Am → F` só conta se os quatro aparecerem nessa ordem e em sequência.
  Por isso ele foi escolhido para sequências novas — mas **não** para as 6
  originais, que continuam usando a tag para preservar a regressão.

### Normalização necessária

A análise mostrou que comparar strings cruas perde matches reais:

- caixa (`am` vs `Am`);
- espaços em volta (`" Dm4/7 "`);
- acordes com acidente (`c#m` vs `C#m`);
- repetições consecutivas (`C, C, G` vs `C, G`).

A decisão de pesquisa foi: normalizar com `NFKC` + `strip`, validar o símbolo
com uma regex permissiva (o dataset usa sufixos como `4/7`, `(7/9)`, `/B`) e
comparar em `casefold`. Repetições consecutivas são colapsadas dos dois lados
antes do match. Repetição não consecutiva continua significando algo diferente
(`C, G, C` ≠ `C, G`).

## 2. Validação da hipótese

### Snapshot antes da mudança

`scripts/snapshot_legacy_results.py` foi rodado no código **original**, antes
de existir banco, e gravou `tests/fixtures/legacy_similar_ids.json` com a lista
completa de IDs de cada uma das 6 buscas (paginação de 100 em 100). Contagens
capturadas: **199, 296, 4, 5, 7, 3**.

O fixture é a linha de base do teste de regressão. A suíte tem dois testes:

1. `test_busca_legada_continua_identica_ao_snapshot`: chama
   `/similares?sequencia=...` no código novo, pagina tudo e compara o
   **conjunto** de IDs com o fixture.
2. `test_snapshot_confere_com_a_tag_do_csv`: recalcula os IDs diretamente da
   tag `seqs_famosas` do CSV e compara com o fixture. Isso prova que o snapshot
   não foi capturado de uma base diferente.

A comparação é por conjunto, não por lista, porque a ordem entre gêneros não é
determinística: `main.py` monta `generos = list(set(generos))` e a coleção é
concatenada na ordem desse set. A ordem *dentro* de cada gênero é estável (por
popularidade), mas a ordem dos gêneros varia entre processos. Comparar listas
produziria falha falsa.

### Conclusão da validação

- É possível manter as 6 originais **exatamente** iguais apenas mantendo o
  caminho da tag `SEQ_FAMOSA`.
- É possível calcular sequências novas em tempo real com o run contíguo.
- Unificar os dois caminhos em um algoritmo só violaria o critério de regressão
  (nenhum algoritmo estrutural reproduz a curadoria).

## 3. Banco de dados

Restrições: container Docker único, local-only, sem serviço externo
(`docs/adr/0001-local-only-docker-deploy.md`), e o banco precisa sobreviver a
reinícios do container.

| Opção | Prós | Contras |
|---|---|---|
| **SQLite (`sqlite3` da stdlib)** | Zero dependência nova; arquivo único; transações e `UNIQUE`; WAL para leitura concorrente; cabe no container | Um escritor por vez; migrations manuais; backup é cópia de arquivo |
| Arquivo JSON / TinyDB | Trivial de ler; zero dependência | Sem `UNIQUE` real; risco de corrupção em escrita concorrente; dedup teria que ser feito em código |
| PostgreSQL / MySQL | Concorrência e recursos de SQL | Exige serviço/container extra; viola o "container único, sem serviços externos" |
| Redis | Rápido; TTL | Serviço extra; persistência é outro modelo; não é catálogo relacional |
| DuckDB | Analítico; arquivo único | Dependência extra; overkill para dezenas de linhas; foco OLAP |

### Detalhe de Docker que a pesquisa revelou

O `Dockerfile` atual não declara volume. Para persistir o arquivo do banco
entre **recriações** de container, é preciso um volume. O caminho óbvio seria
`/app/data`, mas `data/` é exatamente onde está o `dataset_final.csv`: montar
um volume em `/app/data` esconde o CSV e o app não sobe. Por isso o banco deve
ficar em outro diretório (`/app/instance`) e o volume deve apontar para ele.

Esse é um risco real e não teórico: o erro só aparece quando o container é
recriado, não no primeiro `docker run`.

## 4. Frontend existente

`static/assets/js/routes.js` mapeia `#/porsequencia` para
`templates/sequencia.html` + `SequenciaController`.

O controller original (em `HEAD`) tem **4 sequências hardcoded**:
`sequencia1` (Bm G D A), `sequencia2` (C G Am F), `sequencia3` (Gm F) e
`sequencia4` (C C7 F Fm). O backend tem **6**: faltam `Em G` e `C A7 Dm G7`.
É uma divergência pré-existente, não um bug introduzido pela tarefa, mas mostra
por que o catálogo precisa vir de uma fonte só.

O restante do controller:

- monta a query como `similares?sequencia=<acordes separados por vírgula>`;
- usa caminhos relativos (`api/...`), então a página funciona em qualquer host;
- filtra por gênero via `&generos=`;
- não tem estado de carregamento, erro de catálogo nem formulário de cadastro.

O template original só lista os cards e os resultados. Não há campo para
cadastrar sequência, nem distinção visual entre original e comunitária.

## Trade-offs identificados

### Matching

- **Conjunto**: simples e com recall 100%, mas 31 mil falsos positivos. Um
  usuário que digita `C G Am F` receberia músicas que têm esses acordes
  espalhados, não o refrão. Descartado para sequências novas.
- **Subsequência ordenada**: melhor que conjunto, mas ainda permite pular
  acordes no meio (`C ... G ... Am ... F`). 28 mil falsos positivos.
  Descartado.
- **Run contíguo**: mais próximo da noção musical de "essa progressão aparece
  aqui"; 5.980 falsos positivos, ~5x menos que o conjunto. Escolhido para
  sequências novas, com a ressalva de que ainda não é a tag curada.
- **Usar o mesmo algoritmo para as 6 originais**: quebraria a regressão.
  Descartado.

### Banco

- **SQLite**: escolhido. Cabe no container, sem serviço, com `UNIQUE` para
  dedup e transações. O custo é migrations manuais e um escritor por vez.
- **JSON/TinyDB**: mais simples, mas sem garantia de unicidade nem escrita
  atômica; o catálogo é aberto e anônimo, então concorrência não é hipotética.
  Descartado.
- **Postgres/MySQL/Redis**: exigem serviço extra. Descartado pelo ADR 0001.

### Frontend

- **Manter hardcoded e só adicionar um formulário**: não atende "reflete o
  catálogo real". Descartado.
- **Carregar o catálogo do backend e renderizar dinamicamente**: escolhido.
  Custo: precisa de estados de carregamento/erro e de recarregar após cadastro.
- **Enviar o ID da sequência na busca em vez dos acordes**: mais limpo, mas
  mudaria o contrato de `/similares` usado pelo frontend. Preferimos manter o
  parâmetro `sequencia` aceitando o formato atual (vírgulas) e também o formato
  antigo concatenado das 6 originais, sem quebrar links existentes.
