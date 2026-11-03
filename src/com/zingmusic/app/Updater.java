package com.zingmusic.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.ProgressDialog;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

public class Updater {
    private static final String REPO = "848848448/zing-app";

    static int currentBuild(Context c) {
        try {
            PackageInfo p = c.getPackageManager().getPackageInfo(c.getPackageName(), 0);
            if (Build.VERSION.SDK_INT >= 28) return (int) p.getLongVersionCode();
            return p.versionCode;
        } catch (Exception e) { return 0; }
    }

    static String currentVersion(Context c) {
        try {
            PackageInfo p = c.getPackageManager().getPackageInfo(c.getPackageName(), 0);
            return p.versionName == null ? "" : p.versionName;
        } catch (Exception e) { return ""; }
    }

    static void check(final Activity a, final boolean manual) {
        new Thread(() -> {
            try {
                // QA builds also see prereleases (temporary update-test fixtures);
                // release builds only ever see the production latest release.
                String api = QaFlags.QA_ENABLED
                        ? "https://api.github.com/repos/" + REPO + "/releases/tags/v1.0-b2"
                        : "https://api.github.com/repos/" + REPO + "/releases/latest";
                HttpURLConnection c = (HttpURLConnection) new URL(api).openConnection();
                c.setRequestProperty("Accept", "application/vnd.github+json");
                c.setRequestProperty("User-Agent", "zing-app-updater");
                c.setConnectTimeout(10000);
                c.setReadTimeout(15000);
                if (c.getResponseCode() != 200) {
                    if (manual) toast(a, "Could not check for updates");
                    return;
                }
                String body = readAll(c.getInputStream()).trim();
                JSONObject j = body.startsWith("[") ? new JSONArray(body).getJSONObject(0) : new JSONObject(body);
                String tag = j.optString("tag_name", "");
                int dash = tag.lastIndexOf("-b");
                if (dash < 0) { if (manual) toast(a, "Could not check for updates"); return; }
                final int build = Integer.parseInt(tag.substring(dash + 2).trim());
                String apkUrl = null;
                JSONArray assets = j.optJSONArray("assets");
                if (assets != null) {
                    for (int k = 0; k < assets.length(); k++) {
                        JSONObject as = assets.getJSONObject(k);
                        if (as.optString("name", "").endsWith(".apk")) {
                            apkUrl = as.getString("browser_download_url");
                            break;
                        }
                    }
                }
                if (apkUrl == null || build <= currentBuild(a)) {
                    if (manual) toast(a, "Zing is up to date");
                    return;
                }
                final String url = apkUrl;
                final String label = tag;
                a.runOnUiThread(() -> {
                    if (a.isFinishing()) return;
                    new AlertDialog.Builder(a)
                            .setTitle("Update available")
                            .setMessage("A new Zing update is ready (" + label + ").\n\nInstall it now?")
                            .setPositiveButton("Update", (d, w) -> download(a, url))
                            .setNegativeButton("Later", null)
                            .show();
                });
            } catch (Exception e) {
                if (manual) toast(a, "Could not check for updates");
            }
        }).start();
    }

    private static void download(final Activity a, final String url) {
        final ProgressDialog pd = new ProgressDialog(a);
        pd.setTitle("Downloading update");
        pd.setProgressStyle(ProgressDialog.STYLE_HORIZONTAL);
        pd.setMax(100);
        pd.setCancelable(false);
        pd.setCanceledOnTouchOutside(false);
        pd.show();
        new Thread(() -> {
            try {
                HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
                c.setRequestProperty("User-Agent", "zing-app-updater");
                c.setConnectTimeout(10000);
                c.setReadTimeout(30000);
                int total = c.getContentLength();
                File f = new File(a.getCacheDir(), ApkProvider.APK_NAME);
                try (InputStream in = c.getInputStream(); FileOutputStream out = new FileOutputStream(f)) {
                    byte[] buf = new byte[65536];
                    int n;
                    long sofar = 0;
                    while ((n = in.read(buf)) >= 0) {
                        out.write(buf, 0, n);
                        sofar += n;
                        if (total > 0) {
                            final int p = (int) (sofar * 100 / total);
                            a.runOnUiThread(() -> pd.setProgress(p));
                        }
                    }
                }
                a.runOnUiThread(() -> { pd.dismiss(); install(a, f); });
            } catch (Exception e) {
                a.runOnUiThread(() -> { pd.dismiss(); toast(a, "Download failed - try again"); });
            }
        }).start();
    }

    private static void install(Activity a, File f) {
        if (Build.VERSION.SDK_INT >= 26 && !a.getPackageManager().canRequestPackageInstalls()) {
            try {
                a.startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                        Uri.parse("package:" + a.getPackageName())));
            } catch (Exception ignored) {}
            toast(a, "Allow Zing to install apps, then press Update again");
            return;
        }
        Uri uri = Uri.parse("content://" + a.getPackageName() + ".apkprovider/" + ApkProvider.APK_NAME);
        Intent i = new Intent(Intent.ACTION_VIEW);
        i.setDataAndType(uri, "application/vnd.android.package-archive");
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            a.startActivity(i);
        } catch (Exception e) {
            toast(a, "Could not start the installer");
        }
    }

    private static void toast(final Activity a, final String msg) {
        a.runOnUiThread(() -> Toast.makeText(a, msg, Toast.LENGTH_LONG).show());
    }

    private static String readAll(InputStream in) throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        int n;
        while ((n = in.read(buf)) >= 0) out.write(buf, 0, n);
        in.close();
        return out.toString("UTF-8");
    }
}
