from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import unicodedata
from typing import Callable

import pandas as pd
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

URL_ZENDESK = (
    "https://atendimento.ultrafarma.com.br/auth/v3/signin"
    "?return_to=https%3A%2F%2Fultrafarma2803.zendesk.com"
    "%2Fagent%2Ffilters%2F28605876587419"
    "&role=agent"
)
URL_FRACTION = "https://www.jadlog.com.br/FractionWeb/login.jad"

ARQUIVO_LOGIN = Path("login.xlsx")
PASTA_RESULTADOS = Path("resultados")
COLUNAS_OBRIGATORIAS = {"Codigo", "Pedido", "Status", "Descricao"}

MAPEAMENTO_STATUS_ZENDESK = {
    "MUDOU-SE": "Mudou-se",
    "DESTINATARIO DESCONHECIDO": "Destinatário desconhecido",
    "FECHADO": "Local fechado",
    "NUMERO NAO LOCALIZADO": "Número não localizado",
    "AUSENTE": "Ausente",
    "AUSENTE 2": "Ausente",
    "AUSENTE 3": "Ausente",
    "ENDERECO NAO LOCALIZADO": "Endereço não localizado",
    "CEP ERRADO": "Cep não atendido",
    "RESTRICAO DE ACESSO / MOVIMENTACAO": "Área de risco",
    "ENDERECO EM ZONA RURAL": "Área rural",
    "RECUSADO": "Recusou-se a receber",
}

MAPEAMENTO_STATUS_ASSUNTO = {
    "MUDOU-SE": "MUDOU-SE",
    "DESTINATARIO DESCONHECIDO": "DESTINATÁRIO DESCONHECIDO",
    "FECHADO": "FECHADO",
    "NUMERO NAO LOCALIZADO": "NÚMERO NÃO LOCALIZADO",
    "AUSENTE": "AUSENTE",
    "AUSENTE 2": "AUSENTE 2",
    "AUSENTE 3": "AUSENTE 3",
    "ENDERECO NAO LOCALIZADO": "ENDEREÇO NÃO LOCALIZADO",
    "CEP ERRADO": "CEP ERRADO",
    "RESTRICAO DE ACESSO / MOVIMENTACAO": "RESTRIÇÃO DE ACESSO / MOVIMENTAÇÃO",
    "ENDERECO EM ZONA RURAL": "ENDEREÇO EM ZONA RURAL",
    "RECUSADO": "RECUSADO",
}

MAPEAMENTO_TEXTO_TICKET = {
    "MUDOU-SE": "MUDOU-SE",

    "DESTINATARIO DESCONHECIDO": "DESTINATÁRIO DESCONHECIDO",

    "FECHADO": "FECHADO",

    "NUMERO NAO LOCALIZADO": (
        'Prezados, remessa teve ocorrência de "NÚMERO NÃO LOCALIZADO", '
        'favor confirmar os dados de endereço de entrega, mais ponto de '
        'referência e telefone ativo para contato.'
    ),

    "AUSENTE": "AUSENTE",

    "AUSENTE 2": "AUSENTE 2",

    "AUSENTE 3": "AUSENTE 3",

    "ENDERECO NAO LOCALIZADO": "ENDEREÇO NÃO LOCALIZADO",

    "CEP ERRADO": "CEP ERRADO",

    "RESTRICAO DE ACESSO / MOVIMENTACAO": (
        "RESTRIÇÃO DE ACESSO / MOVIMENTAÇÃO"
    ),

    "ENDERECO EM ZONA RURAL": "ENDEREÇO EM ZONA RURAL",

    "RECUSADO": "RECUSADO",
}


def normalizar_texto(valor) -> str:
    if pd.isna(valor):
        return ""
    texto = unicodedata.normalize("NFKD", str(valor).strip())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).upper()


def valor_para_texto(valor) -> str:
    if pd.isna(valor):
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def validar_dataframe(df: pd.DataFrame) -> None:
    faltantes = COLUNAS_OBRIGATORIAS - set(df.columns)
    if faltantes:
        raise ValueError(
            "A planilha precisa conter Codigo, Pedido, Status e Descricao. "
            f"Ausentes: {sorted(faltantes)}"
        )


def carregar_login(aba: str) -> tuple[str, str]:
    if not ARQUIVO_LOGIN.exists():
        raise FileNotFoundError("login.xlsx não encontrado.")
    df = pd.read_excel(ARQUIVO_LOGIN, sheet_name=aba)
    if "USER" not in df.columns or "PASSWORD" not in df.columns:
        raise ValueError(f"A aba {aba} precisa conter USER e PASSWORD.")
    if df.empty:
        raise ValueError(f"A aba {aba} está vazia.")
    usuario = valor_para_texto(df.loc[0, "USER"])
    senha = valor_para_texto(df.loc[0, "PASSWORD"])
    if not usuario or not senha:
        raise ValueError(f"USER/PASSWORD vazio na aba {aba}.")
    return usuario, senha


def preparar_dataframe(df_entrada: pd.DataFrame) -> pd.DataFrame:
    validar_dataframe(df_entrada)
    df = df_entrada.copy()
    df["Fila_Ticket"] = ""
    df["Ticket_Criado"] = ""
    df["Observacao_Fraction"] = ""
    df["Erro_Automacao"] = ""

    for i, linha in df.iterrows():
        status = normalizar_texto(linha["Status"])
        descricao = normalizar_texto(linha["Descricao"])

        if status != "CUSTODIA":
            df.at[i, "Fila_Ticket"] = "NAO - STATUS DIFERENTE DE CUSTODIA"
            df.at[i, "Ticket_Criado"] = "NAO"
            df.at[i, "Observacao_Fraction"] = "NAO EXECUTADO"
        elif descricao not in MAPEAMENTO_STATUS_ZENDESK:
            df.at[i, "Fila_Ticket"] = "NAO - DESCRICAO FORA DA FILA"
            df.at[i, "Ticket_Criado"] = "NAO"
            df.at[i, "Observacao_Fraction"] = "NAO EXECUTADO"
        else:
            df.at[i, "Fila_Ticket"] = "SIM"

    return df


def login_zendesk(page: Page, usuario: str, senha: str, solicitar_token, log) -> None:
    log("Abrindo Zendesk...")
    page.goto(URL_ZENDESK, wait_until="domcontentloaded", timeout=120_000)
    page.get_by_test_id("email-input").fill(usuario)
    page.get_by_test_id("password-input").fill(senha)
    page.get_by_test_id("submit-button").click()

    campo_token = page.get_by_test_id("mfa-challenge-input")
    campo_token.wait_for(state="visible", timeout=60_000)
    token = solicitar_token().strip()
    if not token:
        raise ValueError("Token MFA não informado.")
    campo_token.fill(token)
    page.get_by_test_id("mfa-challenge-submit").click()

    page.locator('[data-test-id="header-toolbar-search-button"]').wait_for(
        state="visible", timeout=120_000
    )
    log("Login no Zendesk concluído.")


def pesquisar_ticket(page: Page, pedido: str) -> bool:
    """
    Fluxo mapeado:
    - abre a pesquisa;
    - usa o campo mapeado;
    - digita o Pedido;
    - se aparecer search-dialog-matches-item, considera que já existe ticket;
    - fecha a pesquisa e segue.
    """
    page.locator(
        '[data-test-id="header-toolbar-search-button"]'
    ).click()

    page.wait_for_timeout(700)

    container_pesquisa = page.locator(
        ".StyledTextInput-sc-1r6733h-0.StyledTextFauxInput-sc-yqw7j9-0"
    ).last

    container_pesquisa.wait_for(
        state="visible",
        timeout=30_000,
    )

    campo_pesquisa = container_pesquisa.locator("input").first

    campo_pesquisa.wait_for(
        state="visible",
        timeout=30_000,
    )

    campo_pesquisa.click()
    campo_pesquisa.fill(pedido)

    resultado = page.locator(
        '[data-test-id="search-dialog-matches-item"]'
    )

    try:
        resultado.first.wait_for(
            state="visible",
            timeout=8_000,
        )
        encontrado = True
    except PlaywrightTimeoutError:
        encontrado = False
    finally:
        page.keyboard.press("Escape")
        page.wait_for_timeout(700)

    return encontrado


def preencher_assunto(page: Page, pedido: str, descricao: str) -> None:
    desc = normalizar_texto(descricao)
    assunto = f"{MAPEAMENTO_STATUS_ASSUNTO[desc]} | {pedido}"
    campo = page.locator('[data-test-id="omni-header-subject"]')
    campo.wait_for(state="visible", timeout=30_000)
    tag = campo.evaluate("(el) => el.tagName.toLowerCase()")
    if tag in ("input", "textarea"):
        campo.fill(assunto)
    else:
        real = campo.locator("input, textarea").first
        real.wait_for(state="visible", timeout=30_000)
        real.fill(assunto)


def preencher_solicitante(page: Page) -> None:
    container = page.locator('[data-test-id="ticket-system-field-requester-select"]')
    container.wait_for(state="visible", timeout=30_000)
    container.click()
    campo = container.locator("input").first
    campo.wait_for(state="visible", timeout=30_000)
    campo.fill("jadlog")
    page.wait_for_timeout(600)
    page.get_by_text("Jadlog atendimento4@evelog.", exact=False).click()


def preencher_ticket(page: Page, pedido: str, status_planilha: str, descricao: str, log) -> None:
    desc = normalizar_texto(descricao)

    page.locator('[data-test-id="header-toolbar-add-menu-button"]').click()
    page.wait_for_timeout(400)
    page.locator('[data-test-id="header-toolbar-add-menu-new-ticket"]').click()

    page.locator('[data-test-id="ticket-system-field-requester-select"]').wait_for(
        state="visible", timeout=60_000
    )

    preencher_assunto(page, pedido, descricao)
    preencher_solicitante(page)

    page.locator(
        '[data-test-id="ticket-form-field-dropdown-field-29872094462107"] '
        '[data-test-id="ticket-form-field-dropdown-button"]'
    ).click()
    page.get_by_role("option", name="Transportadoras", exact=True).click()

    page.locator(
        '[data-test-id="ticket-form-field-dropdown-field-29900641482651"] '
        '[data-test-id="ticket-form-field-dropdown-button"]'
    ).click()
    page.get_by_role("option", name="Insucesso na entrega", exact=True).click()

    page.locator(
        '[data-test-id="ticket-form-field-dropdown-field-29873874671003"] '
        '[data-test-id="ticket-form-field-dropdown-button"]'
    ).click()
    page.get_by_role(
        "option", name=MAPEAMENTO_STATUS_ZENDESK[desc], exact=True
    ).click()

    page.locator(
        '[data-test-id="ticket-form-field-multiline-field-29873683570203"] '
        '[data-test-id="ticket-fields-multiline-field"]'
    ).fill(pedido)

    # Por enquanto, o comentário recebe a Descricao, com a mesma escrita
    # corrigida usada no assunto. Ex.: NUMERO NAO LOCALIZADO ->
    # NÚMERO NÃO LOCALIZADO. Depois este trecho pode ser substituído por um
    # mapeamento de textos específicos para cada descrição.

    texto_ticket = MAPEAMENTO_TEXTO_TICKET[desc]

    editor = page.locator(
        '[data-test-id="omnicomposer-rich-text-ckeditor"]'
    )

    editor.wait_for(
        state="visible",
        timeout=30_000,
    )

    editor.click()
    editor.fill(texto_ticket)

    # Cria o ticket de verdade.
    botao_criar = page.locator(
        '[data-test-id="submit_button-button"]'
    )
    botao_criar.wait_for(
        state="visible",
        timeout=30_000,
    )
    botao_criar.click()

    # Dá tempo para o Zendesk concluir a criação antes de fechar a aba.
    page.wait_for_timeout(2_000)

    log(f"Pedido {pedido}: ticket criado.")



def fechar_ticket_atual(page: Page, log: Callable[[str], None]) -> None:
    """
    Fecha a aba interna do ticket depois da criação.

    Na versão final, se o Zendesk ainda pedir confirmação para sair sem salvar,
    a automação NÃO confirma o descarte e gera erro, para evitar perder um ticket
    cuja criação talvez não tenha terminado corretamente.
    """
    botao_fechar = page.locator(
        '[data-test-id="close-button"]'
    ).last

    botao_fechar.wait_for(
        state="visible",
        timeout=30_000,
    )

    botao_fechar.click()
    page.wait_for_timeout(700)

    confirmar_sem_salvar = page.locator(
        '[data-test-id="ticket-close-confirm-modal-confirm-btn"]'
    )

    if confirmar_sem_salvar.count() > 0 and confirmar_sem_salvar.first.is_visible():
        raise RuntimeError(
            "O Zendesk pediu confirmação para sair sem salvar após a criação. "
            "A automação não confirmou o descarte por segurança."
        )

    log("Aba do ticket fechada.")



def login_fraction(page: Page, usuario: str, senha: str, log) -> None:
    log("Abrindo FractionWeb...")
    page.goto(URL_FRACTION, wait_until="domcontentloaded", timeout=120_000)
    page.get_by_role("textbox", name="Usuário").fill(usuario)
    page.get_by_role("textbox", name="Senha").fill(senha)
    page.get_by_role("button", name="Login").click()
    page.get_by_role("link", name="Consultas").wait_for(
        state="visible", timeout=120_000
    )
    log("Login no Fraction concluído.")


def preencher_observacao_fraction(page: Page, codigo: str, log) -> None:
    page.get_by_role("link", name="Consultas").click()
    page.wait_for_timeout(400)
    page.get_by_role("link", name="Pesquisar").click()
    page.wait_for_timeout(500)
    page.locator('[id="frmPesquisa:cte"]').fill(codigo)
    page.get_by_role("button", name="Processar").click()

    botao_obs = page.get_by_role("button", name="Incluir Observação")
    botao_obs.wait_for(state="visible", timeout=120_000)
    botao_obs.click()

    campo = page.locator('[id="form_add_obs:descObsv"]')
    campo.wait_for(state="visible", timeout=30_000)
    campo.fill("REMETENTE ACIONADO.")

    botao_salvar = page.get_by_role(
        "button",
        name="Salvar",
    )

    botao_salvar.wait_for(
        state="visible",
        timeout=30_000,
    )

    botao_salvar.click()
    page.wait_for_timeout(1_000)

    log(
        f"Código {codigo}: observação REMETENTE ACIONADO. salva."
    )


def salvar_resultado(df: pd.DataFrame) -> Path:
    PASTA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    nome = "tickets_zendesk_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".xlsx"
    caminho = PASTA_RESULTADOS / nome
    df.to_excel(caminho, index=False)
    return caminho


def executar_automacao(
    df_entrada: pd.DataFrame,
    solicitar_token: Callable[[], str],
    log: Callable[[str], None],
    atualizar_progresso: Callable[[str, int, int], None] | None = None,
) -> tuple[pd.DataFrame, Path]:
    """
    Ordem:
      1) Processa TODA a fila Zendesk.
      2) Fecha Zendesk.
      3) Abre Fraction e inicia a fila de observações.

    Filtro da fila de tickets:
      Status = CUSTODIA E Descricao presente no mapeamento.

    Versão final:
      - Cria os tickets no Zendesk.
      - Fecha a aba de cada ticket após a criação.
      - Depois de concluir toda a fila do Zendesk, abre o Fraction.
      - No Fraction inclui e salva REMETENTE ACIONADO. para cada ticket criado.
    """
    df = preparar_dataframe(df_entrada)
    uz, sz = carregar_login("ZENDESK")
    uf, sf = carregar_login("FRACTION")

    fila = df.index[df["Fila_Ticket"] == "SIM"].tolist()
    log(f"{len(fila)} pedido(s) entraram na fila de tickets.")

    # Somente tickets realmente criados entram na fila do Fraction.
    fila_fraction: list[int] = []

    with sync_playwright() as p:
        # -------- FASE 1: ZENDESK --------
        log("===== FASE 1: ZENDESK =====")
        bz = p.chromium.launch(headless=True, slow_mo=500, args=["--start-maximized"])
        cz = bz.new_context(no_viewport=True)
        pz = cz.new_page()

        try:
            login_zendesk(pz, uz, sz, solicitar_token, log)
            total = len(fila)

            for pos, i in enumerate(fila, start=1):
                if atualizar_progresso:
                    atualizar_progresso("ZENDESK", pos, total)

                linha = df.loc[i]
                pedido = valor_para_texto(linha["Pedido"])
                codigo = valor_para_texto(linha["Codigo"])
                status = valor_para_texto(linha["Status"])
                descricao = valor_para_texto(linha["Descricao"])

                try:
                    if not pedido:
                        raise ValueError("Pedido vazio.")
                    if not codigo:
                        raise ValueError("Codigo vazio.")

                    log(f"[Zendesk {pos}/{total}] Pedido {pedido} | {descricao}")

                    if pesquisar_ticket(pz, pedido):
                        df.at[i, "Ticket_Criado"] = "NAO - TICKET JA EXISTE"
                        df.at[i, "Observacao_Fraction"] = "NAO EXECUTADO"
                        continue

                    preencher_ticket(
                        pz,
                        pedido,
                        status,
                        descricao,
                        log,
                    )

                    # Fecha a aba depois da criação, antes de pesquisar o próximo.
                    fechar_ticket_atual(
                        pz,
                        log,
                    )

                    df.at[i, "Ticket_Criado"] = "SIM"
                    fila_fraction.append(i)

                except Exception as erro:
                    df.at[i, "Ticket_Criado"] = "NAO - ERRO"
                    df.at[i, "Observacao_Fraction"] = "NAO EXECUTADO"
                    df.at[i, "Erro_Automacao"] = f"{type(erro).__name__}: {erro}"
                    log(f"Erro no pedido {pedido}: {erro}")

        finally:
            cz.close()
            bz.close()

        # -------- FASE 2: FRACTION --------
        log("===== FASE 2: FRACTION =====")
        if fila_fraction:
            bf = p.chromium.launch(headless=True, slow_mo=500, args=["--start-maximized"])
            cf = bf.new_context(no_viewport=True)
            pf = cf.new_page()

            try:
                login_fraction(pf, uf, sf, log)
                total = len(fila_fraction)

                for pos, i in enumerate(fila_fraction, start=1):
                    if atualizar_progresso:
                        atualizar_progresso("FRACTION", pos, total)

                    codigo = valor_para_texto(df.loc[i, "Codigo"])
                    log(f"[Fraction {pos}/{total}] Código {codigo}")

                    try:
                        preencher_observacao_fraction(
                            pf,
                            codigo,
                            log,
                        )

                        df.at[i, "Observacao_Fraction"] = "SIM"

                        log(
                            "Observação salva. Seguindo para o próximo código."
                        )

                        pf.wait_for_timeout(500)
                    except Exception as erro:
                        df.at[i, "Observacao_Fraction"] = "NAO - ERRO"
                        df.at[i, "Erro_Automacao"] = (
                            (df.at[i, "Erro_Automacao"] + " | " if df.at[i, "Erro_Automacao"] else "")
                            + f"Fraction: {type(erro).__name__}: {erro}"
                        )
                        log(f"Erro no Fraction código {codigo}: {erro}")

            finally:
                cf.close()
                bf.close()

    caminho = salvar_resultado(df)
    log(f"Resultado salvo em {caminho}")
    return df, caminho
