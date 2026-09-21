@echo off
REM Sobe o servidor de desenvolvimento Django localmente no Windows.
REM Uso: clique duplo neste arquivo, ou rode "scripts\windows\dev-up.bat" num terminal
REM a partir da raiz do repositorio.

setlocal
cd /d "%~dp0..\.."

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Virtualenv nao encontrada em ".venv".
    echo Crie e instale as dependencias primeiro:
    echo     python -m venv .venv
    echo     .venv\Scripts\pip install -r requirements-dev.txt
    exit /b 1
)

echo Aplicando migracoes pendentes...
".venv\Scripts\python.exe" src\manage.py migrate --noinput
if errorlevel 1 (
    echo [ERRO] Falha ao aplicar migracoes. Corrija o erro acima antes de continuar.
    exit /b 1
)

echo.
echo Iniciando servidor de desenvolvimento em http://localhost:8000
echo (abre numa janela separada — feche aquela janela, ou rode dev-down.bat, para parar)
echo.
start "Central de Chamados - servidor de desenvolvimento" cmd /k "cd /d "%cd%" && .venv\Scripts\python.exe src\manage.py runserver 0.0.0.0:8000"

endlocal
