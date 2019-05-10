#! /bin/bash
pyinstaller --onefile --windowed --icon=gui_icon.ico --add-data="gui_icon.ico:." install_simnibs.py
