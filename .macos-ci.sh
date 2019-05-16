#! /bin/bash -e

pip install -r requirements.txt
./compile.sh
#dist/install_simnibs -s --pre-release
mv dist/* .
#zip -r install_simnibs_macOS.zip install_simnibs.app
# for now, because we dont have a certificate, i will ship the executable instead of the app
zip -r install_simnibs_macOS.zip install_simnibs
