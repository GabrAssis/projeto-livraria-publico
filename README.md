# Livraria Inteligente

Pipeline de dados e agente SQL em linguagem natural sobre o catálogo de [books.toscrape.com](https://books.toscrape.com).

```
books.toscrape.com → bronze.livros → prata.livros → ouro.livros / ouro.categorias → agente SQL
```

- **Bronze:** scraping cru, append-only (`01_scraper_bronze.py`).
- **Prata e ouro:** views em SQL puro (`sql/`), com regras R1–R7 e métricas M1–M4 documentadas em `CONTEXTO.md`.
- **Agente SQL:** `04_sql_agent.py` (CLI) e `app_streamlit.py` (chat). Só executa `SELECT`/`WITH`, em transação somente leitura, com timeout e limite de linhas.

## Como rodar

1. `pip install -r requirements.txt`
2. Copie `.env.exemplo` para `.env` e preencha com as **suas** credenciais (Postgres/Supabase e chave do provedor de LLM). O `.env` nunca é versionado.
3. `python aplicar_sql.py sql/00_bronze.sql` → `python 01_scraper_bronze.py --paginas 50` → `python aplicar_sql.py sql/01_prata.sql` → `python aplicar_sql.py sql/02_ouro.sql`
4. `python 04_sql_agent.py "Quantos livros únicos temos na base?"` ou `streamlit run app_streamlit.py`

> Este repositório publica apenas o código. Não há instância pública do app nem credenciais.
