create schema if not exists bronze;
create schema if not exists prata;
create schema if not exists ouro;

create table if not exists bronze.livros (
    id           bigserial primary key,
    fonte_url    text,
    payload      jsonb,
    _execucao_id text,
    _ingestao_em timestamptz default now()
);
