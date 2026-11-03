package com.zingmusic.app;

import android.app.Activity;
import android.app.DownloadManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.URLUtil;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

public class MainActivity extends Activity {
    static final String SITE = "https://yidpluszingdownload.abdeveloping.workers.dev/";
    static final String HOST = "yidpluszingdownload.abdeveloping.workers.dev";
    private WebView web;
    private View customView;
    private WebChromeClient.CustomViewCallback customCallback;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private boolean playing = false;
    private boolean qaMode = false;
    private final BroadcastReceiver mediaReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context c, Intent i) {
            final String a = i == null ? null : i.getStringExtra("action");
            if (a == null || web == null) return;
            web.post(() -> web.evaluateJavascript(
                    "window.zingMediaAction&&window.zingMediaAction('" + a + "')", null));
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        web = new WebView(this);
        FrameLayout root = new FrameLayout(this);
        root.addView(web, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        setContentView(root);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, true);

        web.addJavascriptInterface(new Object() {
            @android.webkit.JavascriptInterface
            public void checkForUpdates() { Updater.check(MainActivity.this, true); }
            @android.webkit.JavascriptInterface
            public int getAppBuild() { return Updater.currentBuild(MainActivity.this); }
            @android.webkit.JavascriptInterface
            public String getAppVersion() { return Updater.currentVersion(MainActivity.this); }
            @android.webkit.JavascriptInterface
            public void updateNowPlaying(String title, String artist, String cover) {
                PlaybackService.updateNowPlaying(MainActivity.this, title, artist, cover);
            }
            @android.webkit.JavascriptInterface
            public void share(String title, String url) {
                MainActivity.this.runOnUiThread(() -> {
                    try {
                        String t = title == null ? "" : title;
                        String u = url == null ? "" : url;
                        Intent send = new Intent(Intent.ACTION_SEND);
                        send.setType("text/plain");
                        if (!t.isEmpty()) send.putExtra(Intent.EXTRA_SUBJECT, t);
                        send.putExtra(Intent.EXTRA_TEXT, u.isEmpty() ? t : (t + "\n" + u));
                        startActivity(Intent.createChooser(send, null));
                    } catch (Exception ignored) {}
                });
            }
        }, "ZingNative");

        {
            IntentFilter f = new IntentFilter(PlaybackService.MEDIA_ACTION);
            if (Build.VERSION.SDK_INT >= 33) registerReceiver(mediaReceiver, f, Context.RECEIVER_NOT_EXPORTED);
            else registerReceiver(mediaReceiver, f);
        }

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                Uri u = r.getUrl();
                if (u != null && HOST.equals(u.getHost())) return false;
                try { startActivity(new Intent(Intent.ACTION_VIEW, u)); } catch (Exception ignored) {}
                return true;
            }

            @Override
            public void onPageFinished(WebView v, String url) {
                // Trust boundary: only our own site (and, in QA builds, the
                // local fixture) may receive the navigator.share bridge shim.
                // A server-side redirect or a hostile page that ever loads
                // inside the WebView gets no bridge wiring.
                Uri page = url == null ? null : Uri.parse(url);
                String h = page == null ? null : page.getHost();
                boolean own = HOST.equals(h)
                        || (qaMode && h != null && (h.equals("10.0.2.2") || h.equals("localhost") || h.equals("127.0.0.1")));
                if (!own) return;
                // Give pages a real navigator.share backed by the Android share
                // sheet. Sites with their own fallback (copy link) are
                // untouched when this bridge is absent.
                v.evaluateJavascript(
                        "if(window.ZingNative&&ZingNative.share&&!navigator.share){"
                        + "navigator.share=function(d){d=d||{};"
                        + "ZingNative.share(String(d.title||document.title),String(d.url||location.href));"
                        + "return Promise.resolve();};}", null);
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onShowCustomView(View view, CustomViewCallback cb) {
                customView = view;
                customCallback = cb;
                ((FrameLayout) getWindow().getDecorView()).addView(view,
                        new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
                web.setVisibility(View.GONE);
            }
            @Override
            public void onHideCustomView() {
                if (customView != null) {
                    ((FrameLayout) getWindow().getDecorView()).removeView(customView);
                    customView = null;
                }
                if (customCallback != null) customCallback.onCustomViewHidden();
                web.setVisibility(View.VISIBLE);
            }
        });

        web.setDownloadListener((url, ua, contentDisposition, mime, len) -> {
            try {
                DownloadManager.Request req = new DownloadManager.Request(Uri.parse(url));
                String cookie = CookieManager.getInstance().getCookie(url);
                if (cookie != null) req.addRequestHeader("Cookie", cookie);
                req.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                req.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS,
                        URLUtil.guessFileName(url, contentDisposition, mime));
                ((DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE)).enqueue(req);
            } catch (Exception ignored) {}
        });

        String qa = QaFlags.QA_ENABLED ? getIntent().getStringExtra("qa_url") : null;
        if (qa != null && !qa.isEmpty()) {
            qaMode = true;
            WebView.setWebContentsDebuggingEnabled(true);
        }
        web.loadUrl(qaMode ? qa : SITE);

        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{android.Manifest.permission.POST_NOTIFICATIONS}, 1);
        }

        Updater.check(this, false);
        handler.postDelayed(audioPoller, 3000);
    }

    private final Runnable audioPoller = new Runnable() {
        @Override
        public void run() {
            try {
                web.evaluateJavascript(
                        "(function(){var a=document.querySelector('audio');return a?((!a.paused)+'|'+a.currentTime.toFixed(1)):'none';})()",
                        v -> {
                            boolean p = v != null && v.startsWith("\"true|");
                            if (qaMode) android.util.Log.i("ZingQA", "audio=" + v);
                            if (p != playing) {
                                playing = p;
                                if (p) PlaybackService.start(MainActivity.this);
                                else PlaybackService.pause(MainActivity.this);
                            }
                        });
            } catch (Exception ignored) {}
            handler.postDelayed(this, 3000);
        }
    };

    @Override
    public void onBackPressed() {
        if (customView != null) {
            WebView w = web;
            if (w != null) w.getWebChromeClient();
            if (customCallback != null) { customCallback.onCustomViewHidden(); }
            return;
        }
        if (web.canGoBack()) web.goBack(); else super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacks(audioPoller);
        try { unregisterReceiver(mediaReceiver); } catch (Exception ignored) {}
        PlaybackService.stop(this);
        if (web != null) web.destroy();
        super.onDestroy();
    }
}


