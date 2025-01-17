#!/bin/bash

# Build script to create Mac App Bundle for pgmanage

# Exit when any command fails
set -e -e

APP_VERSION="$1"

# if version is not provided, we use last tag from repository
if [ -z "$APP_VERSION" ]
then
    # Fetch all tags from remote repository
    git fetch --all --tags

    # Get last tag version
    APP_VERSION=$(git describe --tags $(git rev-list --tags --max-count=1))
fi

APP_LONG_VERSION=pgmanage-$APP_VERSION
APP_NAME=PgManage

rm -rf release_$APP_VERSION tmp
mkdir release_$APP_VERSION tmp

# Prepare temporary directory
cp -R ../../pgmanage/ tmp
cd tmp/
rm -rf pgmanage.db pgmanage.log
touch pgmanage.db

# Install pyenv to manage specific python version
brew update && brew upgrade
brew install pyenv

# Install Python 3.8.10 and create virtual environment
env PYTHON_CONFIGURE_OPTS="--enable-shared" pyenv install 3.8.10 --skip-existing

pyenv local 3.8.10
PYTHON_EXE=$(pyenv which python)
$PYTHON_EXE -m venv venv
source venv/bin/activate

# Install all required libraries
pip3 install -r ../../../requirements.txt
pip3 install pyinstaller

# set up versions in custom_settins.py
sed -i '' "s/Dev/PgManage $APP_VERSION/" pgmanage/custom_settings.py
sed -i '' "s/dev/$APP_VERSION/" pgmanage/custom_settings.py

pyinstaller pgmanage-mac.spec

mkdir pgmanage-server && mv dist/pgmanage-server pgmanage-server

curl -LO https://dl.nwjs.io/v0.69.1/nwjs-v0.69.1-osx-x64.zip
unzip nwjs-v0.69.1-osx-x64.zip
mv nwjs-v0.69.1-osx-x64/nwjs.app $APP_LONG_VERSION.app

mkdir $APP_LONG_VERSION.app/Contents/Resources/app.nw
mv pgmanage-server $APP_LONG_VERSION.app/Contents/Resources/app.nw/

cp ../../app/* $APP_LONG_VERSION.app/Contents/Resources/app.nw/
sed -i '' "s/version_placeholder/v$APP_VERSION/" $APP_LONG_VERSION.app/Contents/Resources/app.nw/index.html

# Replace default icons with pgmanage icon
cp ../mac-icon.icns $APP_LONG_VERSION.app/Contents/Resources/app.icns
cp ../mac-icon.icns $APP_LONG_VERSION.app/Contents/Resources/document.icns

# Set up correct application name

plutil -replace CFBundleDisplayName -string "$APP_NAME" $APP_LONG_VERSION.app/Contents/Info.plist

plutil -replace CFBundleExecutable -string "$APP_NAME" $APP_LONG_VERSION.app/Contents/Info.plist

plutil -replace CFBundleShortVersionString -string $APP_VERSION $APP_LONG_VERSION.app/Contents/Info.plist

echo CFBundleDisplayName = \"$APP_NAME\" >> $APP_LONG_VERSION.app/Contents/Resources/el.lproj/InfoPlist.strings

# rename nwjs executable
mv $APP_LONG_VERSION.app/Contents/MacOS/nwjs $APP_LONG_VERSION.app/Contents/MacOS/$APP_NAME

mv $APP_LONG_VERSION.app ../release_$APP_VERSION/$APP_NAME.app

# Create dmg file

# Install dmgbuild command line tool
pip3 install dmgbuild

dmgbuild -s ../settings.py -D app=../release_$APP_VERSION/$APP_NAME.app "$APP_NAME" "$APP_LONG_VERSION"_mac_x64.dmg

mv "$APP_LONG_VERSION"_mac_x64.dmg ../release_$APP_VERSION/

# Remove tmp folder
cd ..

deactivate

rm -rf tmp
