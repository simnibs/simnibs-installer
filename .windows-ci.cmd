@echo off
start /wait bitsadmin.exe /transfer JOB https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe %cd%\Miniconda3.exe
call Miniconda3.exe /InstallationType=JustMe /RegisterPython=0 /S /D=%cd%\MINICONDA
call %cd%\MINICONDA\Scripts\activate
call conda env create -f environment.yml
call conda activate simnibs_installer
pip install pyqt5
python install_simnibs.py -s --pre-release
call compile.cmd
dist\install_simnibs.exe -h -s
echo %errorlevel%
type %LOCALAPPDATA%\SimNIBS\simnibs_install_log.txt
