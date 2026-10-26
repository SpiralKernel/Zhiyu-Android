#!/usr/bin/env bash
# Build from the official, SHA256-pinned pydantic-core source. Never use a desktop .so on Android.
set -euo pipefail
TASK_REPO=$(cd "$(dirname "$0")/.." && pwd)
TASK_TOOLS=${AI_TEACHER_ANDROID_TOOLS:-${XDG_DATA_HOME:-$HOME/.local/share}/AI-teacher-android}
TASK_NDK="$TASK_TOOLS/sdk/ndk/26.3.11579264/toolchains/llvm/prebuilt/linux-x86_64/bin"
export RUSTUP_HOME="$TASK_TOOLS/rustup" CARGO_HOME="$TASK_TOOLS/cargo"
export PATH="$TASK_TOOLS/cargo/bin:$TASK_TOOLS/build/venv/bin:$PATH"
for TASK_ABI in arm64-v8a x86_64; do
    if [[ "$TASK_ABI" == arm64-v8a ]]; then TASK_TARGET=aarch64-linux-android;TASK_ENV=AARCH64_LINUX_ANDROID; else TASK_TARGET=x86_64-linux-android;TASK_ENV=X86_64_LINUX_ANDROID;fi
    TASK_CONFIG="$TASK_TOOLS/build/config/$TASK_ABI.txt"
    cat > "$TASK_CONFIG" <<EOF
implementation=CPython
version=3.12
shared=true
abi3=false
lib_name=python3.12
lib_dir=$TASK_TOOLS/build/python-$TASK_ABI/jniLibs/$TASK_ABI
pointer_width=64
EOF
    export PYO3_CONFIG_FILE="$TASK_CONFIG"
    export "CARGO_TARGET_${TASK_ENV}_LINKER=$TASK_NDK/${TASK_TARGET}24-clang"
    (cd "$TASK_TOOLS/build/pydantic_core-2.46.5" && maturin build --release --target "$TASK_TARGET" --interpreter "$TASK_REPO/.venv/bin/python" --auditwheel skip --out "$TASK_REPO/android/wheels")
done

"$TASK_REPO/.venv/bin/python" "$TASK_REPO/scripts/normalize_android_wheels.py"
