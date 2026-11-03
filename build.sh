#!/bin/bash
# Unsigned build. Signing happens only with an approved key (see sign.sh).
set -e
export JAVA_HOME=${JAVA_HOME:-$HOME/jdk17}
export PATH=$JAVA_HOME/bin:$PATH
SDK=${ANDROID_HOME:-$HOME/android-sdk}
BT=$SDK/build-tools/34.0.0
APP=$(cd "$(dirname "$0")" && pwd)
BUILD_NO=${BUILD_NO:-1}
VERSION_NAME=${VERSION_NAME:-1.0-b$BUILD_NO}
cd "$APP"
rm -rf build
mkdir -p build/classes build/gen build/dex

# QA gate: only qa.yml sets QA_MODE=1; release builds keep the fixture hook off.
if [ "$QA_MODE" = "1" ]; then
  sed -i 's/QA_ENABLED = false/QA_ENABLED = true/' src/com/zingmusic/app/QaFlags.java
  # QA-only: the local audio fixture is plain HTTP on the runner loopback.
  # Release builds (build.yml) keep usesCleartextTraffic=false.
  sed -i 's/android:usesCleartextTraffic="false"/android:usesCleartextTraffic="true"/' AndroidManifest.xml
else
  sed -i 's/QA_ENABLED = true/QA_ENABLED = false/' src/com/zingmusic/app/QaFlags.java
  sed -i 's/android:usesCleartextTraffic="true"/android:usesCleartextTraffic="false"/' AndroidManifest.xml
fi

$BT/aapt2 compile --dir res -o build/res.zip
$BT/aapt2 link -o build/zing-unsigned.apk \
  -I $SDK/platforms/android-34/android.jar \
  --manifest AndroidManifest.xml \
  --java build/gen \
  --min-sdk-version 26 --target-sdk-version 34 \
  --version-code $BUILD_NO --version-name "$VERSION_NAME" \
  build/res.zip

find src build/gen -name '*.java' > build/sources.txt
javac --release 11 -classpath $SDK/platforms/android-34/android.jar -d build/classes @build/sources.txt

$BT/d8 --release --min-api 26 --classpath $SDK/platforms/android-34/android.jar \
  --output build/dex $(find build/classes -name '*.class')

cp build/zing-unsigned.apk build/zing-dex.apk
cd build/dex && zip -q ../zing-dex.apk classes.dex && cd "$APP"
$BT/zipalign -f -p 4 build/zing-dex.apk "build/Zing-$VERSION_NAME-unsigned.apk"
echo "BUILT build/Zing-$VERSION_NAME-unsigned.apk"
