# Desktop Release Runbook

This runbook defines the minimum safe release process for the Windows desktop app.

## Goals

- build a packaged EXE/installer
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

## 3. Optional Windows code signing

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

## 4. Run release preflight

```powershell
cd desktop
npm run release:check
```

This reports:

- whether `UPDATE_FEED_URL` is set
- whether Windows signing variables are set

## 5. Build

```powershell
cd desktop
npm run build:release
```

## 6. Validate artifacts

Expected outputs under:

- `desktop/dist/`

Validate:

- installer launches
- app activates against the target API URL
- chat works
- if `UPDATE_FEED_URL` is configured, update status no longer reports `not_configured`

## 7. Public distribution rule

Recommended minimum before broad external release:

- signed EXE
- real `UPDATE_FEED_URL`
- tested installer on a clean Windows machine
- tested activation and chat against staging or production
