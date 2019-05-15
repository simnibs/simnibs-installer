#! /bin/bash -e

pip install -r requirements.txt
./compile.sh
dist/install_simnibs -s --pre-release
mv dist/install_simnibs.app .
zip -r install_simnibs_macOS.zip install_simnibs.app
