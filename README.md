# 📚 Livraria Inteligente

Um projeto de **engenharia de dados** que:

1. **coleta** os dados de ~1.000 livros de um site de treino (books.toscrape.com);
2. **organiza** esses dados em um banco de dados, em 3 camadas (bronze → prata → ouro);
3. deixa você **perguntar em português** ("qual categoria tem mais valor em estoque?") e uma IA escreve o SQL, consulta o banco e responde.

Não precisa saber programar para seguir este guia: basta copiar e colar os comandos, na ordem.

---

## O que você vai precisar (tudo tem opção gratuita)

| item | para quê | onde conseguir |
|---|---|---|
| **Python 3.11 ou mais novo** | rodar o projeto | https://www.python.org/downloads/ (no Windows, marque *"Add Python to PATH"*) |
| **Conta no Supabase** | banco de dados (PostgreSQL) na nuvem | https://supabase.com (plano gratuito basta) |
| **Chave de API de uma IA** | o agente que escreve o SQL | Anthropic (https://console.anthropic.com) **ou** OpenAI (https://platform.openai.com). Uso pago, mas cada pergunta custa centavos. |
| **Git** (opcional) | baixar o projeto | https://git-scm.com, ou use o botão verde *Code → Download ZIP* no GitHub |

---

## Como funciona (em 30 segundos)

```
site de livros ──► BRONZE ──► PRATA ──► OURO ──► Agente de IA ──► resposta
 (scraping)      (dado cru)  (limpo)  (métricas)   (escreve SQL)
```

- **Bronze:** guarda os textos exatamente como vieram do site (preço `£51.77`, nota `star-rating Three`...). Nunca é alterada.
- **Prata:** limpa tudo (preço vira número, nota vira 1 a 5, remove duplicados...).
- **Ouro:** calcula o que interessa ao negócio (valor em estoque, faixa de preço, "bem avaliado"...).
- **Agente:** lê as regras do projeto (`CONTEXTO.md`) e consulta **somente** prata e ouro.

---

## Passo a passo

### 1. Baixe o projeto

```bash
git clone <URL-DESTE-REPOSITORIO>
cd <pasta-do-projeto>
```

(Ou baixe o ZIP, extraia e abra um terminal dentro da pasta.)

### 2. Instale as dependências

```bash
pip install -r requirements.txt
```

### 3. Crie o banco no Supabase

1. Entre em https://supabase.com → **New project**. Escolha um nome e **anote a senha do banco** que você definir.
2. Quando o projeto terminar de subir, clique em **Connect** (botão no topo) e copie a **Connection string** do tipo **Session pooler** (formato `postgresql://postgres.xxxx:[YOUR-PASSWORD]@aws-...pooler.supabase.com:5432/postgres`).
3. Troque `[YOUR-PASSWORD]` pela sua senha, **sem os colchetes**.

> ⚠️ Se a senha tiver caracteres especiais (`@`, `!`, `#`, `/`...), a conexão falha. Codifique a senha assim e use o resultado no lugar dela:
> ```bash
> python -c "from urllib.parse import quote; print(quote('SUA_SENHA', safe=''))"
> ```

### 4. Crie o arquivo `.env`

O arquivo `.env.exemplo` é só um **modelo** (não tem credenciais reais). Copie-o para `.env` (`cp .env.exemplo .env`; no Windows, `copy .env.exemplo .env`) ou crie um arquivo chamado exatamente `.env` (com o ponto, sem `.txt`) com este conteúdo, trocando pelos seus valores:

```
DATABASE_URL=postgresql://postgres.xxxx:SUA_SENHA@aws-...pooler.supabase.com:5432/postgres
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-5-5
ANTHROPIC_API_KEY=sua-chave-aqui
```

Se preferir OpenAI, use `LLM_PROVIDER=openai`, o nome de um modelo da OpenAI em `LLM_MODEL` e `OPENAI_API_KEY=sua-chave`.

> 🔒 O `.env` guarda suas senhas. Ele já está no `.gitignore`: **nunca** envie esse arquivo para o GitHub nem o compartilhe.

### 5. Crie as tabelas e carregue os dados

Rode estes 4 comandos, **um por vez e nesta ordem**:

```bash
python aplicar_sql.py sql/00_bronze.sql       # cria os schemas e a tabela bronze
python 01_scraper_bronze.py --paginas 50      # coleta os 1.000 livros (leva ~1 a 2 min)
python aplicar_sql.py sql/01_prata.sql        # cria a camada prata
python aplicar_sql.py sql/02_ouro.sql         # cria a camada ouro
```

Para testar rápido, use `--paginas 2` (40 livros).

Conferir se deu certo:

```bash
python aplicar_sql.py --query "select count(*) as livros from prata.livros"
```

Deve mostrar `1000` (ou `40`, se usou `--paginas 2`).

### 6. Pergunte!

**Opção A: no terminal**

```bash
python 04_sql_agent.py "Quantos livros únicos temos na base?"
```

Sem a pergunta entre aspas, ele abre um modo de conversa.

**Opção B: em uma página web (chat)**

```bash
streamlit run app_streamlit.py
```

Abra http://localhost:8501 no navegador. Você conversa com o agente, vê o **SQL gerado** e a **tabela que veio do banco**. Se a pergunta for ambígua (ex.: "livros melhor avaliados"), ele pergunta o que você quer (todos? top 3?) e você responde em cima.

**Perguntas para experimentar**

- Qual categoria tem o maior valor em estoque, em reais?
- Quantos livros bem avaliados custam menos de £20?
- Quantos livros únicos temos na base?
- Qual o preço médio por faixa de preço?

---

## Se algo der errado

| sintoma | causa provável | solução |
|---|---|---|
| `failed to resolve host ...` | senha com caractere especial sem codificar | codifique a senha (passo 3) |
| `DATABASE_URL não definida` | `.env` fora da pasta ou com nome errado | confira que o arquivo se chama `.env` e está na raiz |
| erro de conexão / timeout | usou a conexão direta (IPv6) | use a string **Session pooler** |
| `Defina LLM_PROVIDER ... e LLM_MODEL` | faltam variáveis de IA no `.env` | complete o passo 4 |
| `401` / erro de autenticação da IA | chave inválida ou sem crédito | confira a chave e o saldo no painel do provedor |
| `pip` ou `python` não encontrado | Python fora do PATH | reinstale marcando *Add Python to PATH*; em alguns sistemas use `python3` e `pip3` |
| tabela `prata.livros` não existe | passo 5 fora de ordem | rode de novo os 4 comandos, na ordem |

Rodar o scraper de novo é seguro: a bronze só **acrescenta** linhas e a prata remove os duplicados.

---

## O que tem em cada arquivo

| arquivo | função |
|---|---|
| `01_scraper_bronze.py` | coleta os livros e grava na bronze |
| `aplicar_sql.py` | executa um `.sql` (ou uma consulta) no banco |
| `sql/00_bronze.sql` | cria os schemas e a tabela bronze |
| `sql/01_prata.sql` | limpeza (regras R1 a R7) |
| `sql/02_ouro.sql` | métricas de negócio (M1 a M4) |
| `04_sql_agent.py` | agente de IA em linha de comando |
| `app_streamlit.py` | chat web do agente |
| `CONTEXTO.md` | regras de negócio e dicionário de dados (o agente lê este arquivo) |
| `PRD.md` / `SPEC.md` | o que o produto deve fazer / como foi construído, etapa por etapa |
| `AGENTS.md` | regras de trabalho para agentes de código |

---

## Segurança e custos

- O agente só executa `SELECT`, em transação **somente leitura**, com limite de 10 s e 50 linhas, e não consulta a bronze.
- Cada pergunta faz 2 chamadas à IA e **gera custo na sua conta**. Defina um limite de gasto no painel do provedor.
- Não publique o app com a sua chave: qualquer visitante gastaria o seu crédito. Este repositório publica **apenas o código**, sem credenciais.
- Os dados vêm de um site feito para treino de scraping; os preços e estoques são fictícios.

## Tecnologias

Python · requests · BeautifulSoup · PostgreSQL (Supabase) · psycopg · Anthropic / OpenAI · Streamlit
