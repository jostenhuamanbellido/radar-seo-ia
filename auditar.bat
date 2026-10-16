@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Primero ejecuta iniciar.bat una vez para instalar todo.
  pause
  exit /b 1
)
if "%~1"=="" (
  set /p URL=Pega la URL a auditar: 
  call ".venv\Scripts\python.exe" cli.py "%%URL%%"
) else (
  ".venv\Scripts\python.exe" cli.py %*
)
pause
