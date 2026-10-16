@echo off
chcp 65001 >nul
title Radar SEO IA
cd /d "%~dp0"

where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")

if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno virtual de Python...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo.
    echo No se encontro Python. Instalalo desde https://www.python.org/downloads/
    echo y marca la casilla "Add python.exe to PATH". Luego vuelve a abrir este archivo.
    pause
    exit /b 1
  )
)

if not exist ".venv\instalado.txt" (
  echo Instalando dependencias, solo la primera vez...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Error instalando dependencias.
    pause
    exit /b 1
  )
  echo ok> ".venv\instalado.txt"
)

if not exist ".env" copy ".env.example" ".env" >nul

".venv\Scripts\python.exe" app.py
pause
