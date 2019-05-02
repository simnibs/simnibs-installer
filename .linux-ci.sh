#! /bin/bash -e
DIRNAME="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd $DIRNAME
yum install -y mesa-libGL
conda update -y conda
conda env update -f environment.yml
source activate simnibs_installer
export FONTCONFIG_FILE=/etc/fonts/fonts.conf
export FONTCONFIG_PATH=/etc/fonts/
rm -rf dist/ build/
./compile.sh
dist/install_simnibs --pre-release -s
