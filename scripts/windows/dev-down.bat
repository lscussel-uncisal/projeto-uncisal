@echo off
REM Derruba o servidor de desenvolvimento Django que estiver rodando na porta 8000.
REM Uso: clique duplo neste arquivo, ou rode "scripts\windows\dev-down.bat" num terminal.

setlocal enabledelayedexpansion

set "PORT=8000"
set "FOUND=0"

for /f "tokens=5" %%P in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":%PORT% "') do (
    set "PID=%%P"
    set "FOUND=1"
)

if "!FOUND!"=="0" (
    echo Nenhum servidor rodando na porta %PORT% — nada a fazer.
    exit /b 0
)

echo Encerrando processo na porta %PORT% ^(PID !PID!^)...
taskkill /PID !PID! /F
if errorlevel 1 (
    echo [ERRO] Nao foi possivel encerrar o processo. Pode precisar rodar como Administrador.
    exit /b 1
)

echo Servidor de desenvolvimento encerrado.
endlocal
