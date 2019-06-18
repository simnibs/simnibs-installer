# SimNIBS Installer

Installer for SimNIBS

## Build Status

| Linux   | Windows    | MacOS |
|---------|------------|-----|
| [![Build Status](https://dev.azure.com/simnibs/simnibs-installer/_apis/build/status/Installer%20-%20Linux?branchName=master)](https://dev.azure.com/simnibs/simnibs-installer/_build/latest?definitionId=13&branchName=master)| [![Build Status](https://dev.azure.com/simnibs/simnibs-installer/_apis/build/status/Installer%20-%20Windows?branchName=master)](https://dev.azure.com/simnibs/simnibs-installer/_build/latest?definitionId=12&branchName=master) | [![Build Status](https://dev.azure.com/simnibs/simnibs-installer/_apis/build/status/Installer%20-%20MacOS?branchName=master)](https://dev.azure.com/simnibs/simnibs-installer/_build/latest?definitionId=11&branchName=master) |

## Compiling Locally

I don't recommend compiling locally, as the builds in Azure already use old OS versions to maximize compatibility

SimNIBS installer is meant to be compiled to a binary using PyInstaller, and the binary shipped to the final user.
The installer depends on Python >= 3.6 PyQt5 and Requests.

### Linux/OSX

```bash
pip install -r requirements.txt
bash compile.sh
```

### Windows
```bash
pip install -r requirements.txt
compile.cmd
```

The compiled binary can be found in the dist/ folder

## License

GPL V3
