import argparse
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

import psycopg
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from psycopg.types.json import Jsonb

BASE = "https://books.toscrape.com/catalogue/"
LISTAGEM = BASE + "page-{n}.html"
HEADERS = {"User-Agent": "projeto-livraria-aula/1.0 (estudo de engenharia de dados)"}
PARALELISMO = 8

DDL = """
create schema if not exists bronze;
create table if not exists bronze.livros (
    id           bigserial primary key,
    fonte_url    text,
    payload      jsonb,
    _execucao_id text,
    _ingestao_em timestamptz default now()
);
"""


def baixar(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.content, "html.parser")


def links_da_pagina(n):
    soup = baixar(LISTAGEM.format(n=n))
    return [urljoin(LISTAGEM.format(n=n), a["href"])
            for a in soup.select("article.product_pod h3 a")]


def texto(el):
    return el.get_text() if el else None


def raspar_livro(url):
    soup = baixar(url)
    # r.content como bytes: o texto sai cru, com o £ possivelmente como Â£
    tabela = {th.get_text(): td.get_text()
              for th in soup.select("table.table th")
              for td in [th.find_next_sibling("td")]}
    estrelas = soup.select_one("p.star-rating")
    crumbs = soup.select("ul.breadcrumb li a")
    descricao = soup.select_one("#product_description ~ p")
    return {
        "url": url,
        "titulo": texto(soup.select_one("div.product_main h1")),
        "preco_raw": texto(soup.select_one("div.product_main p.price_color")),
        "rating_raw": " ".join(estrelas["class"]) if estrelas else None,
        "estoque_raw": tabela.get("Availability"),
        "upc": tabela.get("UPC"),
        "n_reviews_raw": tabela.get("Number of reviews"),
        "categoria_raw": crumbs[2].get_text() if len(crumbs) >= 3 else None,
        "descricao": texto(descricao),
    }


def gravar(payloads, execucao_id):
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute(DDL)
        with conn.cursor() as cur:
            cur.executemany(
                "insert into bronze.livros (fonte_url, payload, _execucao_id) values (%s, %s, %s)",
                [(p["url"], Jsonb(p), execucao_id) for p in payloads],
            )


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--paginas", type=int, default=1, help="páginas de listagem (20 livros cada)")
    args = ap.parse_args()
    if not os.getenv("DATABASE_URL"):
        sys.exit("DATABASE_URL não definida no .env")

    with ThreadPoolExecutor(PARALELISMO) as ex:
        links = [l for pag in ex.map(links_da_pagina, range(1, args.paginas + 1)) for l in pag]
        print(f"{len(links)} livros encontrados")
        payloads = list(ex.map(raspar_livro, links))

    execucao_id = uuid.uuid4().hex
    gravar(payloads, execucao_id)
    print(f"{len(payloads)} linhas gravadas em bronze.livros (execucao {execucao_id})")


if __name__ == "__main__":
    main()
