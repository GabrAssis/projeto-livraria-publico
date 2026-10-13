import argparse
import os
import sys

import psycopg
from dotenv import load_dotenv


def conectar():
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL não definida no .env")
    return psycopg.connect(url, autocommit=True)


def aplicar_arquivo(caminho):
    with open(caminho, encoding="utf-8") as f:
        sql = f.read()
    with conectar() as conn:
        conn.execute(sql)
    print(f"aplicado: {caminho}")


def imprimir_consulta(sql):
    with conectar() as conn:
        cur = conn.execute(sql)
        if cur.description is None:
            print("ok")
            return
        print(" | ".join(c.name for c in cur.description))
        for linha in cur.fetchall():
            print(" | ".join(str(v) for v in linha))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("arquivo", nargs="?", help="arquivo .sql a executar")
    p.add_argument("--query", help="consulta a executar e imprimir")
    args = p.parse_args()
    if args.query:
        imprimir_consulta(args.query)
    elif args.arquivo:
        aplicar_arquivo(args.arquivo)
    else:
        p.error("informe um arquivo .sql ou --query")


if __name__ == "__main__":
    main()
