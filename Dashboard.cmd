@echo off
pushd "%~dp0"
python "%~dp0tools\dashboard.py" --open %*
set "DASHBOARD_RESULT=%ERRORLEVEL%"
popd
exit /b %DASHBOARD_RESULT%
