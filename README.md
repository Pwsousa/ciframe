# deciframe

Descubra as músicas que você já sabe tocar (e ainda não faz ideia). Busque por
título/artista, gênero, pelos acordes que você já manja, ou por sequências de
acordes famosas — o deciframe cruza isso com uma base de cifras e sugere
músicas parecidas.

Stack: backend Flask (Python) servindo uma API JSON + um frontend AngularJS
estático. As músicas e gêneros vêm de um CSV carregado em memória; o catálogo de
sequências de acordes (as 6 famosas + as cadastradas por visitantes) fica num
banco SQLite local.

## Rodando localmente

### Com Docker

```
docker build -t ciframe .
docker run -v ciframe-data:/app/instance -p 8080:8080 ciframe
```

O volume mantém as sequências cadastradas entre containers. Sem ele, os dados
vivem apenas na camada gravável do container (e somem se o container for
recriado).

Acesse [http://localhost:8080](http://localhost:8080).

### Com virtualenv

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Acesse [http://localhost:5000](http://localhost:5000).

O banco fica em `instance/deciframe.db` (ignorado pelo git). Para apontar para
outro arquivo — útil em testes — defina `CIFRAME_DB_PATH`.

## Testes

```
pip install -r requirements-dev.txt
pytest
```

Para cobertura:

```
pytest --cov=main --cov=db --cov=sequencias --cov=musica --cov-report=term-missing
```

---

Para convenções de contribuição, veja [CONTRIB.md](CONTRIB.md). Licença: [LICENSE](LICENSE).
