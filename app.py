from pathlib import Path
import queue
import threading
import pandas as pd
import streamlit as st
from automacao import executar_automacao, validar_dataframe

st.set_page_config(layout="wide")
st.title("Bot Zendesk Evelog")

for chave, valor in {
    "thread": None,
    "estado": None,
    "token_queue": None,
    "df": None,
}.items():
    if chave not in st.session_state:
        st.session_state[chave] = valor

col_1, _ = st.columns([1, 2])

with col_1:

    arquivo = st.file_uploader("Importe a planilha", type=["xlsx", "xls"])

if arquivo is not None:
    try:
        df = pd.read_excel(arquivo)
        validar_dataframe(df)
        st.session_state.df = df

        col_2, _ = st.columns([1, 2])

        with col_2:
            st.success(f"Planilha carregada com {len(df)} linha(s).")
            
        st.dataframe(df, use_container_width=True, height=300)
    except Exception as erro:
        st.session_state.df = None
        st.error(str(erro))


def worker(df, estado, token_queue):
    def log(msg):
        estado["logs"].append(msg)

    def token():
        estado["fase"] = "AGUARDANDO_MFA"
        return token_queue.get()

    def progresso(site, atual, total):
        estado["fase"] = site
        estado["atual"] = atual
        estado["total"] = total

    try:
        resultado, caminho = executar_automacao(df, token, log, progresso)
        estado["resultado"] = resultado
        estado["caminho"] = str(caminho)
        estado["fase"] = "CONCLUIDO"
    except Exception as erro:
        estado["erro"] = f"{type(erro).__name__}: {erro}"
        estado["fase"] = "ERRO"

thread = st.session_state.thread
rodando = thread is not None and thread.is_alive()

if st.button(
    "Iniciar automação",
    type="primary",
    disabled=st.session_state.df is None or rodando,
):
    estado = {
        "fase": "INICIANDO",
        "logs": [],
        "atual": 0,
        "total": 0,
        "resultado": None,
        "caminho": None,
        "erro": None,
    }
    token_queue = queue.Queue()
    thread = threading.Thread(
        target=worker,
        args=(st.session_state.df.copy(), estado, token_queue),
        daemon=True,
    )
    st.session_state.estado = estado
    st.session_state.token_queue = token_queue
    st.session_state.thread = thread
    thread.start()
    st.rerun()


@st.fragment(run_every=1)
def painel():
    estado = st.session_state.estado
    if not estado:
        return

    st.divider()
    fase = estado["fase"]
    st.subheader(f"Execução - {fase}")

    if estado["total"]:
        st.progress(
            estado["atual"] / estado["total"],
            text=f'{estado["atual"]} de {estado["total"]}',
        )

    col_3, _ = st.columns([1, 2])
                
    with col_3:

        if fase == "AGUARDANDO_MFA":
            with st.form("mfa"):
                token = st.text_input("Token MFA", type="password")
                enviar = st.form_submit_button("Enviar token")
            if enviar and token.strip():
                st.session_state.token_queue.put(token.strip())
                st.success("Token enviado.")

    if estado["logs"]:
        with st.expander("Log da automação", expanded=False):
            st.text_area(
                "Log",
                "\n".join(estado["logs"][-100:]),
                height=320,
                disabled=True,
                label_visibility="collapsed",
            )

    if fase == "ERRO":
        st.error(estado["erro"])

    if fase == "CONCLUIDO":

        col_4, _ = st.columns([1, 2])
                            
        with col_4:
            st.success("Automação concluída.")

painel()
