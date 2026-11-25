@echo off
setlocal
cd /d "%~dp0"
set "APP_ENV=%~dp0.lightmap-venv"
set "APP_PYTHON=%APP_ENV%\Scripts\python.exe"
set "APP_PYTHONW=%APP_ENV%\Scripts\pythonw.exe"

if exist "%APP_PYTHONW%" if exist "%APP_PYTHON%" goto check_dependencies

:prepare_environment
echo Preparing LightMap for this computer...
for %%V in (314 313 312) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
        "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" -m venv "%APP_ENV%"
        if not errorlevel 1 goto install_dependencies
    )
)
for %%V in (3.14 3.13 3.12) do (
    py -%%V -m venv "%APP_ENV%" 2>nul
    if not errorlevel 1 goto install_dependencies
)
python -c "import sys; assert (3, 12) <= sys.version_info[:2] <= (3, 14)" 2>nul
if errorlevel 1 goto missing_python
python -m venv "%APP_ENV%"
if errorlevel 1 goto setup_failed
goto install_dependencies

:check_dependencies
"%APP_PYTHON%" -B -c "import sys" >nul 2>&1
if errorlevel 1 goto prepare_environment
"%APP_PYTHON%" -B -c "import PIL.Image, pyaudiowpatch" >nul 2>&1
if not errorlevel 1 goto launch

:install_dependencies
"%APP_PYTHON%" -m pip install -r "%~dp0src\requirements.txt"
if errorlevel 1 goto setup_failed

:launch
start "" /D "%~dp0src" "%APP_PYTHONW%" -B -m lightmap <nul >nul 2>&1
exit /b %errorlevel%

:missing_python
echo Install 64-bit Python 3.12, 3.13 or 3.14 with Tcl/Tk, then double-click LightMap.cmd again.
pause
exit /b 1

:setup_failed
echo LightMap setup failed. Check the message above and try again.
pause
exit /b 1
