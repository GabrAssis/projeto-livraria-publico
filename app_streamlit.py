import importlib.util
from decimal import Decimal
from pathlib import Path

import streamlit as st

PERGUNTAS_EXEMPLO = [
    "Qual categoria tem o maior valor em estoque, em reais?",
    "Quantos livros bem avaliados custam menos de £20?",
    "Quantos livros únicos temos na base?",
    "Qual o preço médio por faixa de preço?",
    "Quais são os livros melhor avaliados?",
]
TURNOS_DE_MEMORIA = 6


@st.cache_resource
def carregar_agente():
    caminho = Path(__file__).with_name("04_sql_agent.py")
    spec = importlib.util.spec_from_file_location("sql_agent", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def historico_para_llm(chat):
    mensagens = []
    for m in chat[-2 * TURNOS_DE_MEMORIA:]:
        if m["role"] == "assistant" and m.get("sql"):
            texto = f"{m['content']}\n\n[SQL executado: {m['sql']}]"
        else:
            texto = m["content"]
        mensagens.append({"role": m["role"], "content": texto})
    return mensagens


def perguntar(pergunta, sem_contexto, historico):
    agente = carregar_agente()
    with agente.conectar() as conn:
        system = agente.montar_system_prompt(conn, sem_contexto)
        return agente.responder(conn, system, pergunta, sem_contexto, historico)


def linhas_para_tabela(colunas, linhas):
    return [
        {c: float(v) if isinstance(v, Decimal) else v for c, v in zip(colunas, linha)}
        for linha in linhas
    ]


def mostrar_mensagem(m):
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m["role"] != "assistant":
            return
        for e in m.get("erros", []):
            with st.expander("Tentativa com erro"):
                st.code(e["sql"], language="sql")
                st.error(e["erro"])
        if m.get("sql"):
            with st.expander("SQL gerado e dados do banco", expanded=True):
                st.code(m["sql"], language="sql")
                if m["linhas"]:
                    st.dataframe(linhas_para_tabela(m["colunas"], m["linhas"]), width="stretch")
                else:
                    st.info("A consulta não retornou linhas.")


st.set_page_config(page_title="Livraria Inteligente", page_icon="📚")
st.title("📚 Livraria Inteligente")
st.caption("Converse em português. O agente gera o SQL, consulta o banco e pode pedir esclarecimentos.")

if "chat" not in st.session_state:
    st.session_state["chat"] = []
chat = st.session_state["chat"]

with st.sidebar:
    sem_contexto = st.checkbox(
        "Sem contexto (CONTEXTO.md)",
        help="Só instrução mínima + schema de todas as tabelas, inclusive a bronze.",
    )
    if st.button("🗑️ Nova conversa", width="stretch"):
        st.session_state["chat"] = []
        st.rerun()
    st.markdown("**Exemplos**")
    for exemplo in PERGUNTAS_EXEMPLO:
        if st.button(exemplo, width="stretch"):
            st.session_state["pendente"] = exemplo

for m in chat:
    mostrar_mensagem(m)

pergunta = st.chat_input("Pergunte algo sobre a livraria...") or st.session_state.pop("pendente", None)

if pergunta:
    historico = historico_para_llm(chat)
    mostrar_mensagem({"role": "user", "content": pergunta})
    with st.spinner("Consultando..."):
        try:
            r = perguntar(pergunta, sem_contexto, historico)
        except Exception as e:
            st.error(f"Falha ao consultar: {e}")
            st.stop()
    chat.append({"role": "user", "content": pergunta})
    resposta = {"role": "assistant", "content": r["resposta"], "sql": r["sql"],
                "colunas": r["colunas"], "linhas": r["linhas"], "erros": r["erros"]}
    chat.append(resposta)
    mostrar_mensagem(resposta)
