@echo off
pip install -r requirements.txt
call compile.cmd
dist\install_simnibs.exe -s --pre-release
move dist\install_simnibs.exe dist\install_simnibs_windows.exe
echo %errorlevel%
type %LOCALAPPDATA%\SimNIBS\simnibs_install_log.txt
