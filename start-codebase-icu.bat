@echo off
setlocal

rem Resolve paths relative to this .bat file's own location, so it works
rem no matter what directory it is launched from.
set "ROOT_DIR=%~dp0"
set "BACKEND_DIR=%ROOT_DIR%codebase-icu"
set "FRONTEND_DIR=%ROOT_DIR%codebase-icu\frontend"

echo Starting Codebase ICU backend (FastAPI)...
start "Codebase ICU - Backend" cmd /k "cd /d %BACKEND_DIR% && call .venv\Scripts\activate.bat && uvicorn backend.main:app --reload"

echo Starting Codebase ICU frontend (Vite)...
start "Codebase ICU - Frontend" cmd /k "cd /d %FRONTEND_DIR% && npm run dev"

echo.
echo Codebase ICU is starting in two separate windows.
echo   Backend:  http://127.0.0.1:8000
echo   Frontend: http://localhost:5173
echo.
echo Close those windows to stop the servers.
echo.
pause

endlocal
