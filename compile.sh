#! /bin/bash
pyinstaller --onefile --windowed --icon=gui_icon.icns --add-data="gui_icon.ico:." install_simnibs.py
