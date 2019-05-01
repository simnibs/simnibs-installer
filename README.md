# SimNIBS Installer

Installer for SimNIBS

## Compiling

SimNIBS installer is meant to be compiled to a binary using PyInstaller, and the binary shipped to the final user.
The installer also depends on PyQt5 and Requests.
To install the requirements and compile the SimNIBS installer using conda, please use

### Linux/OSX

```bash
conda env create -f environment.yml
conda activate simnibs_installer
bash compile.sh
```

### Windows
```bash
conda env create -f environment.yml
pip install pyqt5
conda activate simnibs_installer
bash compile.cmd
```
The additional pip install call is needed because of a bug in conda/pyinstaller. It might be removed in the future.

The compiled binary can be found in the dist/ folder

## License

GPL V3
