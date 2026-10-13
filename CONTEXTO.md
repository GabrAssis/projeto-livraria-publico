# CONTEXTO.md · Memória viva do projeto

> **Leia este arquivo antes de qualquer tarefa.** Ele vence o SPEC e o PRD em caso de conflito. **Atualize ao final de cada etapa** (§1 e §5). O agente SQL também lê este arquivo inteiro.

## 1\. Estado do projeto

| etapa | status | observação |
| :---- | :---- | :---- |
| 1 · Scraping → bronze | ✅ aprovada (12/10) | Scraper rodou contra o banco: 1.000 livros (50 páginas) gravados. Bronze = 1.080 linhas / 1.000 UPCs (80 linhas da amostra via MCP, sem `descricao`, ficam por serem append-only). |
| 2 · Prata | ✅ aprovada (12/10) | `sql/01_prata.sql` aplicado. Base completa: 1.000 linhas = 1.000 UPCs, sem nulos, sem `Default`/`Add a comment` (219 → `Sem categoria`), 49 categorias. |
| 3 · Ouro | ✅ aprovada (12/10) | `sql/02_ouro.sql` aplicado (views `ouro.livros` e `ouro.categorias`). `sum(qtd_titulos)` = 1.000 = `count(*)` da prata; `faixa_preco` só com os 3 valores de M3. `ouro.categorias` inclui `Sem categoria` (219 títulos); o filtro de M4 fica por conta de quem consulta. |
| 4 · Agente SQL | ✅ aprovada (12/10) | `04_sql_agent.py` testado com `anthropic` / `claude-sonnet-5-5`. Com contexto: 4/4 perguntas do PRD corretas na 1ª tentativa, todas só em `prata`/`ouro` (Nonfiction R$ 231.287,47 · 75 · 1.000 · £14,80 / £30,06 / £49,91). Sem contexto (`--sem-contexto`): Q1 errada ("Sem categoria", em GBP, sem converter); Q3 correta. Guardrails validados: SELECT/WITH, 1 comando, sem bronze com contexto, read only, timeout 10 s, limit 50, 3 tentativas. |

&nbsp;

**Próximo passo:** projeto concluído. Extra: interface de chat em `app_streamlit.py` (`streamlit run app_streamlit.py`, porta 8501).

## 2\. Fonte de dados: books.toscrape.com

- Site público feito para treinar scraping. 50 páginas × 20 livros \= 1.000 livros.  
- Listagem: `https://books.toscrape.com/catalogue/page-{n}.html` → links em `article.product_pod h3 a`.  
- Detalhe do livro: título em `div.product_main h1`; preço em `div.product_main p.price_color`; avaliação na classe de `p.star-rating` (ex.: `star-rating Three`); tabela `table.table` com `UPC`, `Availability`, `Number of reviews`; categoria no 3º link de `ul.breadcrumb`.  
- **Encoding:** o site não declara charset. Com `requests`, o `£` costuma chegar como `Â£`. Na bronze isso fica como veio; R2 resolve na prata.  
- Campos do `payload` na bronze: `url`, `titulo`, `preco_raw`, `rating_raw`, `estoque_raw`, `upc`, `n_reviews_raw`, `categoria_raw`, `descricao`.

## 3\. Regras de negócio

**Bronze → prata**

- **R1 · Chave e duplicidade:** chave \= `upc`. Manter só a linha com o `_ingestao_em` mais recente.  
- **R2 · Preço:** extrair só o número de `preco_raw` → `preco_gbp numeric(10,2)`. Moeda \= libra (GBP).  
- **R3 · Avaliação:** `star-rating One..Five` → `rating` 1..5.  
- **R4 · Estoque:** de `In stock (22 available)` extrair `22` → `estoque_qtd int`. Sem número \= 0\.  
- **R5 · Reviews:** `n_reviews_raw` → `n_reviews int`.  
- **R6 · Categoria:** `Default` e `Add a comment` não são categorias → `Sem categoria`.  
- **R7 · Texto:** remover espaços nas pontas.

**Métricas (ouro)**

- **M1 · Valor em estoque** \= `preco_gbp × estoque_qtd`.  
- **M2 · Bem avaliado** \= `rating >= 4`.  
- **M3 · Faixa de preço:** `até £20` (\< 20\) · `£20–40` (20 a \< 40\) · `acima de £40` (≥ 40).  
- **M4 · Moeda das respostas:** GBP. Se pedirem reais, usar o câmbio de §5. Rankings de categoria **excluem** `Sem categoria`, salvo pedido explícito.

## 4\. Dicionário de dados

**prata.livros** (1 linha \= 1 livro): `upc` · `titulo` · `categoria` · `preco_gbp` · `rating` · `estoque_qtd` · `n_reviews` · `url` · `_ingestao_em`

**ouro.livros:** prata \+ `valor_estoque_gbp` (M1) · `faixa_preco` (M3) · `bem_avaliado` (M2, bool)

**ouro.categorias** (1 linha \= 1 categoria): `categoria` · `qtd_titulos` · `preco_medio_gbp` · `rating_medio` · `estoque_unidades` · `valor_estoque_gbp` · `pct_bem_avaliados`

## 5\. Decisões

| data | decisão | motivo | quem |
| :---- | :---- | :---- | :---- |
| 08/10 | Bronze append-only; dedup só na prata | preservar o que veio de cada execução | Eng. Dados |
| 08/10 | Prata e ouro como views | base pequena, sempre atualizada | Eng. Dados |
| 08/10 | Câmbio fixo **£1 \= R\$ 7,20** | relatório da diretoria em reais (valor fictício da aula) | Financeiro |
| 08/10 | Agente SQL só lê `prata` e `ouro` | bronze tem lixo e duplicidade | Eng. Dados |
| 12/10 | Banco = projeto Supabase dedicado à livraria | isolar a livraria de outros projetos | Eng. Dados |
| 12/10 | Amostra inicial da bronze carregada via MCP (80 linhas, sem `descricao`); depois carga completa pelo scraper | `DATABASE_URL` ainda indisponível na época; a prata deduplica por R1 | Claude |
| 12/10 | `DATABASE_URL` usa o pooler do Supabase, senha URL-encoded | senha tinha caracteres especiais (`@`) | Eng. Dados |
| 12/10 | `ouro.categorias` mantém `Sem categoria` como uma linha; `pct_bem_avaliados` em escala 0–100 (2 casas) | critério de aceite exige soma de títulos = total da prata; M4 manda excluir só nos rankings | Claude |
| 12/10 | Adicionado `streamlit` e `app_streamlit.py` (interface para perguntar e ver SQL, dados e resposta); `responder()` do agente passou a devolver um dict | pedido do usuário; reaproveita o agente sem duplicar lógica | Eng. Dados |
| 12/10 | Regra no agente: pergunta fora do contexto da livraria → responder que não sabe, orientar o tipo de pergunta aceito e **não gerar SQL** | evitar SQL e respostas sem relação com a base | Eng. Dados |
| 12/10 | Interface em chat com memória: `responder()` recebe `historico` (últimas 6 trocas); pergunta ambígua → agente oferece opções concretas (ex.: todos ou top 3) e o usuário responde em cima | permitir conversa de esclarecimento em vez de chute | Eng. Dados |
| 12/10 | Histórico do chat vive só na sessão do navegador (`st.session_state`); recarregar a página limpa | interface simples, sem persistência | Claude |

&nbsp;

## 6\. Pendências

- Guardar histórico de preço (SCD2)? → fora do escopo de hoje.