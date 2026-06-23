#!/usr/bin/env bash
# Start the Android emulator for this project.
set -euo pipefail

export ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
export PATH="$PATH:$ANDROID_HOME/emulator:$ANDROID_HOME/platform-tools"

AVD_NAME="${1:-Medium_Phone_API_36.0}"

if ! command -v emulator >/dev/null; then
  echo "emulator not found. Install Android Studio → SDK Manager → Android Emulator."
  exit 1
fi

echo "Available AVDs:"
emulator -list-avds

if ! emulator -list-avds | grep -qx "$AVD_NAME"; then
  echo ""
  echo "AVD '$AVD_NAME' not found."
  echo "Create one in Android Studio: Device Manager → Create Device"
  echo "Or pass another name: ./scripts/start_emulator.sh <AvdName>"
  exit 1
fi

if adb devices | grep -q "emulator-.*device"; then
  echo "Emulator already running:"
  adb devices
  exit 0
fi

echo "Starting $AVD_NAME ..."
emulator -avd "$AVD_NAME" -no-snapshot-load &
adb wait-for-device
echo "Waiting for Android to finish booting ..."
until [ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; do
  sleep 2
done
echo "Ready:"
adb devices
