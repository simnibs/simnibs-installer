# SimNIBS Installer

Installer for SimNIBS

## Status

I've programmed a CI in Azure Pipelines to automatically build and test the installer.
You should also download the latest compiled version by clicking on "Artifacts", in the top right corner of the page

### Linux
[![Build Status](https://dev.azure.com/simnibs/simnibs-dev/_apis/build/status/Installer%20-%20Linux?branchName=master)](https://dev.azure.com/simnibs/simnibs-dev/_build/latest?definitionId=6&branchName=master)

### Windows
[![Build Status](https://dev.azure.com/simnibs/simnibs-dev/_apis/build/status/Installer%20-%20Windows?branchName=master)](https://dev.azure.com/simnibs/simnibs-dev/_build/latest?definitionId=7&branchName=master)



## Compiling Locally

I don't recommend compiling locally, as the builds in Azure already use old OS versions (CentOS6, Windows 2012) to maximize compatibility

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
conda activate simnibs_installer
pip install pyqt5
compile.cmd
```
The additional pip install call is needed because of a bug in conda/pyinstaller. It might be removed in the future.

The compiled binary can be found in the dist/ folder

## License

GPL V3
