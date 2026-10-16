@echo off
pushd "%~dp0"
python "%~dp0tools\run_all.py" %*
set "RUN_RESULT=%ERRORLEVEL%"
popd
exit /b %RUN_RESULT%
