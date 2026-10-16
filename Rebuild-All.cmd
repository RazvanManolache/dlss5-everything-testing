@echo off
pushd "%~dp0"
python "%~dp0tools\build.py" %*
set "BUILD_RESULT=%ERRORLEVEL%"
popd
exit /b %BUILD_RESULT%
