#! /bin/bash
LD_LIBRARY_PATH=$CONDA_PREFIX/lib pyinstaller --onefile --windowed --icon=gui_icon.ico install_simnibs.py
