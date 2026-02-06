# Code Folder

This acts as a monorepo for the following projects:

- [Signal-Android @ v7.66.5](https://github.com/signalapp/Signal-Android/releases/tag/v7.66.5)
- [key-transparency-server @ 20250808.2.0](https://github.com/signalapp/key-transparency-server/releases/tag/20250808.2.0)
- [libsignal @ 0.86.8](https://github.com/signalapp/libsignal/releases/tag/v0.86.8)

## How the sourcecodes have been obtained

- pulled them from the according GitHub repository
- fetched the tags, pulled the current (stable) version
- removed the .git folder

## Requirements

- Android Studio
- JDK 17
- Rust (...)
- Docker
- At least 32GB of RAM, recommended: 64GB RAM

Highly recommended: 

- creating a RAM-based filesystem for the binaries under `libsignal/target`, `Signal-Android/app/build`, `libsignal/java/android/build`


## How to setup the project

1. Install needed dependencies
2. Open Signal-Android with Android Studio
3. Create a `local.properties` file in `libsignal/java` containing the path to the Android SDK
4. ...
