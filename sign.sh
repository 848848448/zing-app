#!/bin/bash
# Signs the unsigned build. Needs: KEYSTORE, KEYSTORE_PASSWORD, KEY_ALIAS (default "zing").
set -e
SDK=${ANDROID_HOME:-$HOME/android-sdk}
BT=$SDK/build-tools/34.0.0
APP=$(cd "$(dirname "$0")" && pwd)
BUILD_NO=${BUILD_NO:-1}
VERSION_NAME=${VERSION_NAME:-1.0-b$BUILD_NO}
KEY_ALIAS=${KEY_ALIAS:-zing}
cd "$APP"
$BT/apksigner sign \
  --ks "$KEYSTORE" --ks-pass "pass:$KEYSTORE_PASSWORD" --key-pass "pass:$KEYSTORE_PASSWORD" \
  --ks-key-alias "$KEY_ALIAS" \
  --out "Zing-$VERSION_NAME.apk" "build/Zing-$VERSION_NAME-unsigned.apk"
$BT/apksigner verify --print-certs "Zing-$VERSION_NAME.apk" | head -3
echo "SIGNED Zing-$VERSION_NAME.apk"
