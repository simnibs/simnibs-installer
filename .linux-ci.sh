#! /bin/bash -e

#####################
# This script builds and tests the installer
# It is meant to be run with the centos:7 docker image
# Run with docker run -v `pwd`:/simnibs-installer centos:7 simnibs-installer/.linux-ci.sh
#####################
DIRNAME="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd $DIRNAME
yum update -y
yum install -y mesa-libGL yum-utils fontconfig freetype freetype-devel fontconfig-devel libXrender libxkbcommon-x11
yum groupinstall -y development
yum install -y https://centos7.iuscommunity.org/ius-release.rpm
yum install -y python36u python36u-pip python36u-devel
pip3.6 install -r requirements.txt
rm -rf dist/ build/ install_simnibs/
./compile.sh
dist/install_simnibs --pre-release -s
cp README.txt LICENSE.txt dist
mv dist/ install_simnibs
tar -cvzf install_simnibs_linux.tar.gz install_simnibs