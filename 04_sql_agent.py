import argparse
import os
import re
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

MAX_TENTATIVAS = 3
LIMITE_LINHAS = 50
TIMEOUT_MS = 10_000
PALAVRAS_PROIBIDAS = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|call|do|vacuum|merge)\b", re.I
)

INSTRUCOES_COM_CONTEXTO = """Você é um analista de dados da livraria. Responda perguntas de negócio em português consultando o banco PostgreSQL.
Regras:
- Use somente as tabelas dos schemas prata e ouro. Nunca use o schema bronze.
- Gere UM único SELECT (ou WITH ... SELECT) por vez, dentro de um bloco ```sql.
- Siga as regras de negócio, métricas (M1 a M4) e decisões do CONTEXTO abaixo.
- Se a pergunta for ambígua, peça esclarecimento em vez de chutar (responda sem bloco sql). Ofereça opções concretas (ex.: "todos ou só o top 3?").
- Você conversa em turnos: use as mensagens anteriores para entender respostas curtas como "top 3" ou "só os de Poetry".
- Se alguém perguntar algo fora do contexto da livraria, responda que não sabe, direcione o tipo de pergunta que você pode responder e não gere SQL.
"""

INSTRUCOES_SEM_CONTEXTO = """Você responde perguntas em português consultando um banco PostgreSQL.
Gere UM único SELECT dentro de um bloco ```sql."""

INSTRUCOES_RESPOSTA = (
    "Com base na pergunta, no SQL executado e no resultado, responda em português, de forma curta e direta. "
    "Use os números exatamente como vieram. Informe a moeda quando for valor monetário."
)


def conectar():
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL não definida no .env")
    return psycopg.connect(url)


def ler_schema(conn, schemas):
    linhas = conn.execute(
        """select table_schema, table_name, column_name, data_type
           from information_schema.columns
           where table_schema = any(%s)
           order by table_schema, table_name, ordinal_position""",
        (list(schemas),),
    ).fetchall()
    tabelas = {}
    for schema, tabela, coluna, tipo in linhas:
        tabelas.setdefault(f"{schema}.{tabela}", []).append(f"{coluna} {tipo}")
    return "\n".join(f"{t}({', '.join(cols)})" for t, cols in tabelas.items())


def montar_system_prompt(conn, sem_contexto):
    if sem_contexto:
        schema = ler_schema(conn, ["bronze", "prata", "ouro"])
        return f"{INSTRUCOES_SEM_CONTEXTO}\n\n# Schema\n{schema}"
    contexto = Path(__file__).with_name("CONTEXTO.md").read_text(encoding="utf-8")
    schema = ler_schema(conn, ["prata", "ouro"])
    return f"{INSTRUCOES_COM_CONTEXTO}\n# CONTEXTO.md\n{contexto}\n\n# Schema real (information_schema)\n{schema}"


def chamar_llm(system, mensagens):
    provedor = os.getenv("LLM_PROVIDER", "").lower()
    modelo = os.getenv("LLM_MODEL")
    if provedor not in ("openai", "anthropic") or not modelo:
        sys.exit("Defina LLM_PROVIDER (openai|anthropic) e LLM_MODEL no .env")
    if provedor == "anthropic":
        import anthropic
        r = anthropic.Anthropic().messages.create(
            model=modelo, max_tokens=1500, system=system, messages=mensagens
        )
        return "".join(b.text for b in r.content if b.type == "text")
    from openai import OpenAI
    r = OpenAI().chat.completions.create(
        model=modelo, messages=[{"role": "system", "content": system}, *mensagens]
    )
    return r.choices[0].message.content


def extrair_sql(texto):
    m = re.search(r"```sql\s*(.*?)```", texto, re.S | re.I)
    return m.group(1).strip().rstrip(";").strip() if m else None


def validar_sql(sql, sem_contexto):
    if not re.match(r"^\s*(select|with)\b", sql, re.I):
        raise ValueError("Só são permitidos SELECT/WITH.")
    if ";" in sql:
        raise ValueError("Envie um único comando, sem ';' no meio.")
    if PALAVRAS_PROIBIDAS.search(sql):
        raise ValueError("Comando de escrita/DDL não é permitido.")
    if not sem_contexto and re.search(r"\bbronze\b", sql, re.I):
        raise ValueError("O schema bronze não pode ser consultado; use prata ou ouro.")


def executar_sql(conn, sql):
    with conn.transaction():
        conn.execute("set transaction read only")
        conn.execute(f"set local statement_timeout = {TIMEOUT_MS}")
        cur = conn.execute(f"select * from (\n{sql}\n) as _q limit {LIMITE_LINHAS}")
        colunas = [c.name for c in cur.description]
        return colunas, cur.fetchall()


def formatar_resultado(colunas, linhas):
    if not linhas:
        return "(sem linhas)"
    return "\n".join([" | ".join(colunas), *(" | ".join(str(v) for v in l) for l in linhas)])


def conversa_anterior(historico):
    if not historico:
        return ""
    trechos = [f"{'Usuário' if m['role'] == 'user' else 'Assistente'}: {m['content']}" for m in historico[-6:]]
    return "Conversa até aqui:\n" + "\n".join(trechos) + "\n\n"


def responder(conn, system, pergunta, sem_contexto, historico=None):
    mensagens = [*(historico or []), {"role": "user", "content": pergunta}]
    saida = {"resposta": None, "sql": None, "colunas": [], "linhas": [], "erros": []}
    for _ in range(MAX_TENTATIVAS):
        texto = chamar_llm(system, mensagens)
        sql = extrair_sql(texto)
        if sql is None:
            saida["resposta"] = texto
            return saida
        saida["sql"] = sql
        try:
            validar_sql(sql, sem_contexto)
            colunas, linhas = executar_sql(conn, sql)
        except Exception as e:
            erro = str(e).strip()
            saida["erros"].append({"sql": sql, "erro": erro})
            mensagens += [
                {"role": "assistant", "content": texto},
                {"role": "user", "content": f"Erro ao executar: {erro}\nCorrija e gere um novo SQL."},
            ]
            continue
        saida["colunas"], saida["linhas"] = colunas, linhas
        resultado = formatar_resultado(colunas, linhas)
        saida["resposta"] = chamar_llm(
            INSTRUCOES_RESPOSTA,
            [{"role": "user", "content": f"{conversa_anterior(historico)}Pergunta: {pergunta}\n\nSQL:\n{sql}\n\nResultado:\n{resultado}"}],
        )
        return saida
    saida["sql"] = None
    saida["resposta"] = f"Não consegui gerar um SQL válido em {MAX_TENTATIVAS} tentativas."
    return saida


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pergunta", nargs="?", help="pergunta única; sem ela abre o modo interativo")
    ap.add_argument("--sem-contexto", action="store_true",
                    help="só instrução mínima + schema de todas as tabelas (comparação em aula)")
    args = ap.parse_args()

    with conectar() as conn:
        system = montar_system_prompt(conn, args.sem_contexto)
        perguntas = [args.pergunta] if args.pergunta else iter(lambda: input("\nPergunta (vazio sai): ").strip(), "")
        for pergunta in perguntas:
            r = responder(conn, system, pergunta, args.sem_contexto)
            for e in r["erros"]:
                print(f"\n[SQL com erro]\n{e['sql']}\n[erro] {e['erro']}")
            if r["sql"]:
                print(f"\n[SQL]\n{r['sql']}")
                print(f"\n[Resultado]\n{formatar_resultado(r['colunas'], r['linhas'])}")
            print(f"\n[Resposta]\n{r['resposta']}")


if __name__ == "__main__":
    main()
