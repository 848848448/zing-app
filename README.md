# Zing app

Android app for Zing Music.

- Fullscreen native wrapper around the live Zing site, with background audio
  playback (foreground media service while music plays).
- In-app updates: the app checks this repository's latest release on start and
  offers to download and install it. Ship an APK update by committing app changes to `main`, then opening
  Actions -> build -> Run workflow -> main -> Run workflow. That deliberate
  release builds, signs and publishes v1.0-bN with a higher Android versionCode.
  Commits alone do not publish. Keep the existing signing key for every update.
  The app reads the latest full release, never temporary QA prereleases.
- On Android, users tap Update, allow Zing to install apps when Android asks,
  return to Zing and tap its update control again, then confirm Update in the
  Android installer. Android does not allow a normal app to silently install.
- Live website content changes appear in the wrapper separately; they are not
  APK updates. The workflow above publishes app-code updates.
- Signing key lives only in encrypted secrets (`KEYSTORE_B64`,
  `KEYSTORE_PASSWORD`); a recovery bundle is kept in the owner's secure vault.

Build locally: `BUILD_NO=1 ./build.sh` (unsigned) then `sign.sh` with
`KEYSTORE`/`KEYSTORE_PASSWORD` set.
