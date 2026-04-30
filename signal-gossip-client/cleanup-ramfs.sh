#!/bin/bash

TARGET_DIR="./libsignal/target"
ANDROID_BUILD_DIR="./Signal-Android/app/build"
JNI_BUILD_DIR="./libsignal/java/android/build"

ALL_PATHS=("$TARGET_DIR" "$ANDROID_BUILD_DIR" "$JNI_BUILD_DIR")

case "$1" in
    clean)
        echo "Cleaning contents of RAM discs..."
        for path in "${ALL_PATHS[@]}"; do
            if mountpoint -q "$path"; then
                rm -rf "${path:?}"/*
                echo "$path cleared."
            else
                echo "$path  is not mounted. Skipping..."
            fi
        done
        ;;
    free)
        echo "Unmounting RAM disks... nevermind, not implemented."
        # sudo systemctl stop mnt-Dev-projects-code-libsignal-target.automount
        # sudo systemctl stop mnt-Dev-projects-code-Signal\\x20Android-app-build.automount
        # sudo systemctl stop mnt-Dev-projects-code-libsignal-java-android-build.automount
        
        # for path in "${ALL_PATHS[@]}"; do
        #     sudo umount -l "$path" 2>/dev/null
        # done
        # echo "RAM has been freed for new horrors."
        ;;
    status)
        echo "Current state of the build folders:"
        df -h | grep -E "target|build" || echo "Keine RAM-Disks aktiv."
        ;;
    *)
        echo "Usage: $0 {clean|free|status}"
        echo "  clean  - Deletes all build artifacts in RAM (keeps mounts)."
        echo "  free   - Unmounts everything and releases RAM."
        echo "  status - Shows current usage of storage."
        ;;
esac
