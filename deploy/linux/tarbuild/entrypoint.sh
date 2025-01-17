#!/bin/bash

# Checking environment
echo "REPO=$REPO"
echo "BRANCH=$BRANCH"
echo "VERSION=$VERSION"

# Cloning repo
git clone $REPO --depth 1 -b $BRANCH pgmanage

# Installing dependencies
cd pgmanage/
pip3 install -r requirements.txt

# if version is not provided, we use last tag from repository
if [ -z "$VERSION" ]
then
    # Fetching all tags from remote repository
    git fetch --all --tags

    # Getting last tag version
    export VERSION=$(git describe --tags $(git rev-list --tags --max-count=1))
fi

# Building server
cd pgmanage/

# setting up versions in custom_settins.py
sed -i "s/Dev/PgManage $VERSION/" pgmanage/custom_settings.py
sed -i "s/dev/$VERSION/" pgmanage/custom_settings.py

rm -f pgmanage.db pgmanage.log
touch pgmanage.db
pyinstaller pgmanage-lin.spec
mv dist/pgmanage-server $HOME
rm -rf build dist
cd $HOME
# temporarily disabled, we do not distribute the server-only version yet
# mkdir pgmanage-server_$VERSION
# cp pgmanage-server pgmanage-server_$VERSION/
# tar -czvf pgmanage-server_$VERSION-linux-x64.tar.gz pgmanage-server_$VERSION/
# mv pgmanage-server_$VERSION-linux-x64.tar.gz /tmp/

# Building app
cd /tmp
curl -C - -LO https://dl.nwjs.io/v0.69.1/nwjs-v0.69.1-linux-x64.tar.gz
# get appimagetool v13
curl -C - -LO https://github.com/AppImage/AppImageKit/releases/download/13/appimagetool-x86_64.AppImage && chmod +x /tmp/appimagetool-x86_64.AppImage
cd -
tar -xzvf /tmp/nwjs-v0.69.1-linux-x64.tar.gz
mv nwjs-v0.69.1-linux-x64 pgmanage-app_$VERSION
cd pgmanage-app_$VERSION
rm ./lib/libEGL.so
rm ./lib/libGLESv2.so
rm ./lib/libvulkan.so.1
rm ./lib/libvk_swiftshader.so
rm ./lib/*.json

mkdir pgmanage-server
cp $HOME/pgmanage-server ./pgmanage-server/
# copy index.html .desktop and pgmanage_icon.png to the output dir
cp $HOME/pgmanage/deploy/app/* .
# adjust the version
sed -i "s/version_placeholder/v$VERSION/" index.html
sed -i "s/X-AppImage-Version=dev/X-AppImage-Version=$VERSION/" pgmanage.desktop
# rename nwjs runtime as pgmanage-app
mv nw pgmanage-app && ln -s ./pgmanage-app AppRun
cd $HOME
/tmp/appimagetool-x86_64.AppImage --appimage-extract-and-run pgmanage-app_$VERSION/ pgmanage-app_$VERSION.AppImage
# tar -czvf pgmanage-app_$VERSION-linux-x64.tar.gz pgmanage-app_$VERSION/
# mv pgmanage-app_$VERSION-linux-x64.tar.gz /tmp/
mv pgmanage-app_$VERSION.AppImage /tmp
