# Android Foundation

## Scope

This repository now contains an initial Android project under `android/` with:

- Kotlin + Jetpack Compose app module
- Hilt dependency injection
- Navigation shell for auth, dashboard, and future feature routes
- Retrofit and OkHttp networking skeleton
- Room cache skeleton for lessons, vocabulary, and progress snapshots
- DataStore-backed bearer-token session persistence that respects the keep-signed-in choice
- Environment-specific build flavors for `dev`, `staging`, and `prod`

## Project Layout

```text
android/
├── app/
│   ├── build.gradle.kts
│   ├── schemas/
│   └── src/main/
│       ├── AndroidManifest.xml
│       ├── java/com/ahsansuny/languagecoach/
│       │   ├── core/
│       │   ├── data/
│       │   ├── di/
│       │   └── ui/
│       └── res/
├── gradle/
│   ├── libs.versions.toml
│   └── wrapper/
├── build.gradle.kts
├── gradle.properties
├── gradlew
├── gradlew.bat
└── settings.gradle.kts
```

## Environment Configuration

Base URLs are flavor-specific and can be overridden through `android/local.properties`, Gradle properties, or environment variables.

Supported keys:

- `LANGUAGE_COACH_DEV_BASE_URL`
- `LANGUAGE_COACH_STAGING_BASE_URL`
- `LANGUAGE_COACH_PROD_BASE_URL`

Default values:

- `dev`: `http://10.0.2.2:5000/`
- `staging`: `https://language.ahsansuny.com/`
- `prod`: `https://language.ahsansuny.com/`

Example `android/local.properties` snippet:

```properties
sdk.dir=C\:\\Users\\YOU\\AppData\\Local\\Android\\Sdk
LANGUAGE_COACH_DEV_BASE_URL=http://10.0.2.2:5000/
LANGUAGE_COACH_STAGING_BASE_URL=https://staging.example.com/
LANGUAGE_COACH_PROD_BASE_URL=https://api.example.com/
```

## Contract Fit

The Android foundation is aligned to the approved contract in `C:\Users\YOU TECH BD\OneDrive - ICIQ\CODEX App\Language_Coach_api_contract\docs\android_mvp_api_contract.md`.

The service layer now assumes:

- bearer-token auth through `POST /api/v1/auth/session`
- authenticated reads and writes through `Authorization: Bearer <token>`
- lesson, vocabulary, and progress repositories wired to the approved `/api/v1/languages/...` and `/api/v1/progress` routes
- local lesson caching keyed by both language and lesson id so French and Spanish lesson ids can coexist safely

Future agents can flesh out feature screens against those approved contracts without restructuring the app shell.

## Expected Toolchain

- JDK 17
- Android SDK with platform 34 and build-tools
- Gradle wrapper included in `android/`

Typical build command:

```bash
cd android
./gradlew :app:assembleDevDebug
```
