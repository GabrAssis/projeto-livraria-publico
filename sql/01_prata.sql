create schema if not exists prata;

create or replace view prata.livros as
with dedup as (
    select
        b.*,
        row_number() over (
            partition by btrim(b.payload->>'upc')              -- R1
            order by b._ingestao_em desc, b.id desc            -- R1
        ) as rn
    from bronze.livros b
)
select
    btrim(payload->>'upc')                                                     as upc,              -- R7
    btrim(payload->>'titulo')                                                  as titulo,           -- R7
    case when btrim(payload->>'categoria_raw') in ('Default', 'Add a comment') -- R6
         then 'Sem categoria'                                                  -- R6
         else btrim(payload->>'categoria_raw')                                 -- R7
    end                                                                        as categoria,
    regexp_replace(payload->>'preco_raw', '[^0-9.]', '', 'g')::numeric(10,2)  as preco_gbp,        -- R2
    case btrim(split_part(payload->>'rating_raw', ' ', 2))                     -- R3
         when 'One'   then 1                                                   -- R3
         when 'Two'   then 2                                                   -- R3
         when 'Three' then 3                                                   -- R3
         when 'Four'  then 4                                                   -- R3
         when 'Five'  then 5                                                   -- R3
    end                                                                        as rating,
    coalesce(substring(payload->>'estoque_raw' from '\((\d+) available\)')::int, 0) as estoque_qtd, -- R4
    nullif(btrim(payload->>'n_reviews_raw'), '')::int                          as n_reviews,        -- R5
    btrim(coalesce(payload->>'url', fonte_url))                                as url,              -- R7
    _ingestao_em
from dedup
where rn = 1;                                                                  -- R1
