# Desktop Release Runbook

This runbook defines the minimum safe release process for the desktop app on Windows and macOS.

## Goals

- build a packaged installer for Windows or macOS
- optionally enable auto-update through a generic feed
- strongly prefer signed binaries before public distribution

## 1. Configure desktop API URL

Edit:

- `desktop/desktop-config.json`

Set:

```json
{
  "apiUrl": "https://your-domain.example/api"
}
```

## 2. Optional auto-update feed

Set:

```powershell
$env:UPDATE_FEED_URL="https://downloads.your-domain.example/desktop"
```

If `UPDATE_FEED_URL` is not set:

- the desktop app still builds
- update status will show unconfigured
- auto-update will not work

## 3. Optional code signing

### Windows

Preferred environment variables:

```powershell
$env:CSC_LINK="file:///C:/path/to/certificate.pfx"
$env:CSC_KEY_PASSWORD="your-password"
```

Alternative Windows-specific names also work:

```powershell
$env:WIN_CSC_LINK="file:///C:/path/to/certificate.pfx"
$env:WIN_CSC_KEY_PASSWORD="your-password"
```

If signing vars are missing:

- the app can still be built
- the EXE will be unsigned
- SmartScreen trust will be worse

### macOS

Recommended environment variables for signing:

```powershell
$env:CSC_LINK="file:///Users/you/certs/macos-signing.p12"
$env:CSC_KEY_PASSWORD="your-password"
```

Recommended environment variables for notarization:

```powershell
$env:APPLE_API_KEY="/Users/you/private_keys/AuthKey_ABC123XYZ.p8"
$env:APPLE_API_KEY_ID="ABC123XYZ"
$env:APPLE_API_ISSUER="00000000-0000-0000-0000-000000000000"
```

Alternative certificate discovery also works:

```powershell
$env:CSC_NAME="Developer ID Application: Example Company (TEAMID1234)"
```

If macOS signing/notarization vars are missing:

- the app can still be built
- the `.app` or `.dmg` will be unsigned or not notarized
- Gatekeeper warnings will be worse on end-user machines

## 4. Run release preflight

```powershell
cd desktop
npm run release:check
```

For a macOS release target, set the platform explicitly before the check:

```powershell
$env:DESKTOP_RELEASE_PLATFORM="mac"
npm run release:check
```

This reports:

- whether `UPDATE_FEED_URL` is set
- whether platform-appropriate signing variables are set

## 5. Build

```powershell
cd desktop
npm run build:release
```

For macOS:

```powershell
cd desktop
npm run build:release:mac
```

The repository also includes `.github/workflows/desktop-macos-release.yml`.
Run it manually with the public API URL, or push a `v*` tag after configuring
the `DESKTOP_API_URL` repository variable. Tagged builds attach the universal
DMG and ZIP to the GitHub release. Configure
`NEXT_PUBLIC_DESKTOP_MAC_DOWNLOAD_URL` while building the admin image to point
the employee-page download button at that published DMG.

Note:

- `dmg` creation should be executed on a macOS build machine
- the config builds `universal` mac artifacts so one package supports Apple Silicon and Intel

## 6. Validate artifacts

Expected outputs under:

- `desktop/dist/`

Validate:

- installer launches
- app activates against the target API URL
- chat works
- if `UPDATE_FEED_URL` is configured, update status no longer reports `not_configured`
- on macOS, reopening the dock icon after all windows are closed opens a fresh window

## 7. Public distribution rule

Recommended minimum before broad external release:

- signed installer or app bundle
- real `UPDATE_FEED_URL`
- tested installer on a clean Windows or macOS machine matching the release target
- tested activation and chat against staging or production
