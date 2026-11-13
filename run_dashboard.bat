@echo off
setlocal enabledelayedexpansion

rem =========================================================
rem run_dashboard.bat
rem Instala dependencias (na primeira vez) e roda o dashboard
rem de Faturamento de Pedidos localmente, no navegador.
rem =========================================================

cd /d %~dp0

echo ============================================================
echo   Dashboard de Faturamento de Pedidos - Protheus
echo ============================================================
echo.

rem --- localizar o Python ---
set PY_CMD=
where python >nul 2>nul
if not errorlevel 1 (
    set PY_CMD=python
) else (
    where py >nul 2>nul
    if not errorlevel 1 (
        set PY_CMD=py
    )
)

if "%PY_CMD%"=="" (
    echo [ERRO] Python nao foi encontrado no PATH.
    echo Instale o Python 3.10 ou superior ^(https://www.python.org/downloads/^)
    echo marcando a opcao "Add python.exe to PATH" durante a instalacao.
    pause
    exit /b 1
)

rem --- criar ambiente virtual, se necessario ---
if not exist "venv\Scripts\activate.bat" (
    echo [1/4] Criando ambiente virtual Python em .\venv ...
    %PY_CMD% -m venv venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar o ambiente virtual.
        pause
        exit /b 1
    )
) else (
    echo [1/4] Ambiente virtual ja existe.
)

call "venv\Scripts\activate.bat"

rem --- instalar dependencias, se necessario ---
if not exist "venv\.deps_ok" (
    echo [2/4] Instalando dependencias ^(streamlit, pandas, plotly, pyodbc...^)
    python -m pip install --upgrade pip >nul
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERRO] Falha ao instalar as dependencias. Verifique sua conexao
        echo com a internet ou rode manualmente: pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo ok> "venv\.deps_ok"
) else (
    echo [2/4] Dependencias ja instaladas.
)

rem --- criar .env a partir do exemplo, se necessario ---
if not exist ".env" (
    echo [3/4] Criando .env a partir de .env.example ^(modo demo ligado^)...
    copy ".env.example" ".env" >nul
    echo        Edite o arquivo .env para conectar no Protheus real quando quiser.
) else (
    echo [3/4] Arquivo .env encontrado.
)

echo [4/4] Iniciando o dashboard... o navegador vai abrir automaticamente.
echo        Para encerrar, feche esta janela ou pressione Ctrl+C.
echo.
streamlit run app.py

pause
