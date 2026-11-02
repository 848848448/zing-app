package com.zingmusic.app;

import android.app.Activity;
import android.app.DownloadManager;
import android.content.Context;
import android.content.Intent;
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
import android.widget.ImageView;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.MotionEvent;

public class MainActivity extends Activity {
    static final String SITE = "https://yidpluszingdownload.abdeveloping.workers.dev/";
    static final String HOST = "yidpluszingdownload.abdeveloping.workers.dev";
    private WebView web;
    private View customView;
    private WebChromeClient.CustomViewCallback customCallback;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private boolean playing = false;
    private ImageView updateFab;
    private boolean qaMode = false;
    private final Runnable fabFader = this::fadeFab;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        web = new WebView(this);
        FrameLayout root = new FrameLayout(this);
        root.addView(web, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        updateFab = buildUpdateFab();
        root.addView(updateFab);
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
        }, "ZingNative");

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                Uri u = r.getUrl();
                if (u != null && HOST.equals(u.getHost())) return false;
                try { startActivity(new Intent(Intent.ACTION_VIEW, u)); } catch (Exception ignored) {}
                return true;
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
        handler.postDelayed(fabFader, 5000);
    }

    private ImageView buildUpdateFab() {
        float d = getResources().getDisplayMetrics().density;
        ImageView fab = new ImageView(this);
        fab.setImageResource(R.drawable.ic_refresh);
        GradientDrawable circle = new GradientDrawable();
        circle.setShape(GradientDrawable.OVAL);
        circle.setColors(new int[]{0xFF7C5CFF, 0xFFFF4D8D});
        circle.setOrientation(GradientDrawable.Orientation.TL_BR);
        fab.setBackground(circle);
        int pad = (int) (12 * d);
        fab.setPadding(pad, pad, pad, pad);
        int size = (int) (52 * d);
        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(size, size, Gravity.END | Gravity.BOTTOM);
        lp.rightMargin = (int) (16 * d);
        lp.bottomMargin = (int) (150 * d);
        fab.setLayoutParams(lp);
        fab.setElevation(8 * d);
        fab.setContentDescription("Check for updates");
        fab.setOnClickListener(v -> {
            fab.animate().alpha(1f).setDuration(150).start();
            Updater.check(this, true);
        });
        return fab;
    }

    private void fadeFab() {
        if (updateFab != null) updateFab.animate().alpha(0.35f).setDuration(600).start();
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
                                else PlaybackService.stop(MainActivity.this);
                            }
                        });
            } catch (Exception ignored) {}
            handler.postDelayed(this, 3000);
        }
    };

    @Override
    public boolean dispatchTouchEvent(MotionEvent ev) {
        if (ev.getAction() == MotionEvent.ACTION_DOWN && updateFab != null && updateFab.getAlpha() < 0.9f) {
            updateFab.animate().alpha(0.85f).setDuration(200).start();
        }
        if (ev.getAction() == MotionEvent.ACTION_DOWN) {
            handler.removeCallbacks(fabFader);
            handler.postDelayed(fabFader, 5000);
        }
        return super.dispatchTouchEvent(ev);
    }

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
        PlaybackService.stop(this);
        if (web != null) web.destroy();
        super.onDestroy();
    }
}
