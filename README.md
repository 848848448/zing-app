# Zing app

Android app for Zing Music.

- Fullscreen native wrapper around the live Zing site, with background audio
  playback (foreground media service while music plays).
- In-app updates: the app checks this repository's latest release on start and
  offers to download and install it. Ship an update by pushing to `main` -
  CI builds, signs and publishes a new release.
- Signing key lives only in encrypted secrets (`KEYSTORE_B64`,
  `KEYSTORE_PASSWORD`); a recovery bundle is kept in the owner's secure vault.

Build locally: `BUILD_NO=1 ./build.sh` (unsigned) then `sign.sh` with
`KEYSTORE`/`KEYSTORE_PASSWORD` set.
