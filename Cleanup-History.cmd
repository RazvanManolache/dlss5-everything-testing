@echo off
pushd "%~dp0"
powershell -NoProfile -File "%~dp0Cleanup-History.ps1" %*
set "CLEANUP_RESULT=%ERRORLEVEL%"
popd
exit /b %CLEANUP_RESULT%
