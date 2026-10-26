# Android native dependency

`pydantic-core 2.46.5` is built from the official PyPI sdist, not a desktop wheel or an unverified Termux wheel.

- Official sdist SHA256: `10416c15b8839ecc4ef4d0885da76da6fd0f67333a0eb8aff6d93c4b8f2910fc`
- Runtime: Chaquopy Python 3.12.15, Android API24, ARM64 and x86_64.
- NDK r26d (`26.3.11579264`); Rust stable; maturin1.15.0.
- Linked Python library comes from `com.chaquo.python:target:3.12.15-0`.
- `scripts/build_android_core.sh` rebuilds both wheels once the documented tools/source/runtime files are installed.
- Wheels are local build artifacts and ignored by Git. Pydantic-core's MIT license is included in each wheel.
