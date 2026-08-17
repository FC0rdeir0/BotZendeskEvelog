@echo off
setlocal

cd /d "%~dp0"

title Automacao Zendesk + Fraction

echo ==========================================
echo     AUTOMACAO ZENDESK + FRACTION
echo ==========================================
echo.

rem ==================================================
rem 1. Verifica o Python
rem ==================================================

where python >nul 2>&1

if errorlevel 1 (
    echo ERRO: Python nao foi encontrado.
    echo.
    echo Instale o Python e marque a opcao:
    echo Add Python to PATH
    echo.
    pause
    exit /b 1
)

rem ==================================================
rem 2. Verifica Git e atualiza o projeto
rem ==================================================

where git >nul 2>&1

if errorlevel 1 (
    echo AVISO: Git nao foi encontrado.
    echo O aplicativo sera iniciado sem verificar atualizacoes.
    echo.
    goto AMBIENTE
)

if not exist ".git" (
    echo AVISO: Esta pasta nao e um repositorio Git.
    echo O aplicativo sera iniciado sem verificar atualizacoes.
    echo.
    goto AMBIENTE
)

echo ==========================================
echo Verificando atualizacoes no Git...
echo ==========================================
echo.

git pull --ff-only

if errorlevel 1 (
    echo.
    echo AVISO: Nao foi possivel atualizar o projeto.
    echo.
    echo Possiveis motivos:
    echo - existem alteracoes locais;
    echo - computador sem internet;
    echo - acesso ao repositorio expirou;
    echo - branch local diferente da remota.
    echo.
    echo O aplicativo sera iniciado com a versao atual.
    echo.
) else (
    echo.
    echo Projeto atualizado com sucesso.
    echo.
)

:AMBIENTE

rem ==================================================
rem 3. Cria ambiente virtual
rem ==================================================

if not exist ".venv\Scripts\python.exe" (
    echo ==========================================
    echo Criando ambiente virtual...
    echo ==========================================
    echo.

    python -m venv .venv

    if errorlevel 1 (
        echo.
        echo ERRO: Nao foi possivel criar o ambiente virtual.
        pause
        exit /b 1
    )

    echo Ambiente virtual criado.
    echo.
)

set "PYTHON=.venv\Scripts\python.exe"

rem ==================================================
rem 4. Verifica requirements.txt
rem ==================================================

if not exist "requirements.txt" (
    echo ERRO: requirements.txt nao foi encontrado.
    echo.
    pause
    exit /b 1
)

rem ==================================================
rem 5. Atualiza pip
rem ==================================================

echo ==========================================
echo Atualizando pip...
echo ==========================================
echo.

"%PYTHON%" -m pip install --upgrade pip --quiet

if errorlevel 1 (
    echo.
    echo ERRO: Nao foi possivel atualizar o pip.
    pause
    exit /b 1
)

rem ==================================================
rem 6. Instala/atualiza dependencias
rem ==================================================

echo ==========================================
echo Verificando dependencias...
echo ==========================================
echo.

"%PYTHON%" -m pip install -r requirements.txt --quiet

if errorlevel 1 (
    echo.
    echo ERRO: Nao foi possivel instalar as dependencias.
    pause
    exit /b 1
)

echo Dependencias verificadas.
echo.

rem ==================================================
rem 7. Instala/verifica Chromium do Playwright
rem ==================================================

echo ==========================================
echo Verificando Chromium do Playwright...
echo ==========================================
echo.

"%PYTHON%" -m playwright install chromium

if errorlevel 1 (
    echo.
    echo ERRO: Nao foi possivel instalar o Chromium do Playwright.
    pause
    exit /b 1
)

echo Chromium verificado.
echo.

rem ==================================================
rem 8. Cria pasta de resultados
rem ==================================================

if not exist "resultados" (
    mkdir resultados
)

rem ==================================================
rem 9. Verifica arquivos obrigatorios
rem ==================================================

if not exist "app.py" (
    echo ERRO: app.py nao foi encontrado.
    pause
    exit /b 1
)

if not exist "automacao.py" (
    echo ERRO: automacao.py nao foi encontrado.
    pause
    exit /b 1
)

if not exist "login.xlsx" (
    echo ERRO: login.xlsx nao foi encontrado.
    echo.
    echo O arquivo precisa possuir as abas:
    echo ZENDESK
    echo FRACTION
    echo.
    pause
    exit /b 1
)

rem ==================================================
rem 10. Inicia Streamlit
rem ==================================================

echo ==========================================
echo Iniciando o aplicativo...
echo ==========================================
echo.
echo Para encerrar, pressione Ctrl+C.
echo.

"%PYTHON%" -m streamlit run app.py

echo.
echo Aplicativo encerrado.
echo.

pause

endlocal