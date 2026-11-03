package com.zingmusic.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.media.MediaMetadata;
import android.media.session.MediaSession;
import android.media.session.PlaybackState;
import android.os.Build;
import android.os.IBinder;

import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

public class PlaybackService extends Service {
    private static final String CHANNEL = "playback";
    private static final String STOP = "com.zingmusic.app.STOP";
    private static final String ACT_PREV = "com.zingmusic.app.PREV";
    private static final String ACT_TOGGLE = "com.zingmusic.app.TOGGLE";
    private static final String ACT_NEXT = "com.zingmusic.app.NEXT";
    static final String MEDIA_ACTION = "com.zingmusic.app.MEDIA_ACTION";

    private static String sTitle = "Zing";
    private static String sArtist = "";
    private static String sCover = "";
    private static boolean sPlaying = false;
    private static Bitmap sArt = null;
    private static String sArtFor = "";
    private static boolean sStarted = false;
    private MediaSession ms;

    public static void start(Context c) {
        sPlaying = true;
        Intent i = new Intent(c, PlaybackService.class);
        if (Build.VERSION.SDK_INT >= 26) c.startForegroundService(i); else c.startService(i);
    }

    public static void pause(Context c) {
        sPlaying = false;
        if (sStarted) {
            try { c.startService(new Intent(c, PlaybackService.class).setAction("refresh")); } catch (Exception ignored) {}
        }
    }

    public static void stop(Context c) {
        sPlaying = false;
        try { c.startService(new Intent(c, PlaybackService.class).setAction(STOP)); } catch (Exception ignored) {}
    }

    public static void updateNowPlaying(Context c, String title, String artist, String cover) {
        if (title != null && title.length() > 0) sTitle = title;
        sArtist = artist == null ? "" : artist;
        sCover = cover == null ? "" : cover;
        sPlaying = true;
        Intent i = new Intent(c, PlaybackService.class).setAction("meta");
        try {
            if (Build.VERSION.SDK_INT >= 26) c.startForegroundService(i); else c.startService(i);
        } catch (Exception ignored) {}
    }

    private PendingIntent act(String a, int req) {
        return PendingIntent.getService(this, req, new Intent(this, PlaybackService.class).setAction(a),
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }

    private void notifyAction(String a) {
        Intent i = new Intent(MEDIA_ACTION);
        i.setPackage(getPackageName());
        i.putExtra("action", a);
        sendBroadcast(i);
    }

    private void ensureSession() {
        if (ms != null) return;
        ms = new MediaSession(this, "zing");
        ms.setFlags(MediaSession.FLAG_HANDLES_TRANSPORT_CONTROLS | MediaSession.FLAG_HANDLES_MEDIA_BUTTONS);
        ms.setCallback(new MediaSession.Callback() {
            @Override public void onPlay() { notifyAction("toggle"); }
            @Override public void onPause() { notifyAction("toggle"); }
            @Override public void onSkipToNext() { notifyAction("next"); }
            @Override public void onSkipToPrevious() { notifyAction("prev"); }
        });
        ms.setActive(true);
    }

    private void loadArt() {
        if (sCover.equals(sArtFor)) return;
        final String url = sCover;
        sArtFor = url;
        sArt = null;
        if (url.length() == 0) return;
        new Thread(() -> {
            try {
                HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
                c.setConnectTimeout(8000);
                c.setReadTimeout(8000);
                InputStream in = c.getInputStream();
                Bitmap raw = BitmapFactory.decodeStream(in);
                in.close();
                if (raw != null) {
                    int w = raw.getWidth(), h = raw.getHeight(), m = Math.max(w, h);
                    sArt = m > 256 ? Bitmap.createScaledBitmap(raw, w * 256 / m, h * 256 / m, true) : raw;
                    if (sStarted) refresh();
                }
            } catch (Exception ignored) {}
        }).start();
    }

    private void refresh() {
        ensureSession();
        loadArt();
        ms.setMetadata(new MediaMetadata.Builder()
                .putString(MediaMetadata.METADATA_KEY_TITLE, sTitle)
                .putString(MediaMetadata.METADATA_KEY_ARTIST, sArtist)
                .putBitmap(MediaMetadata.METADATA_KEY_ALBUM_ART, sArt)
                .build());
        long acts = PlaybackState.ACTION_PLAY | PlaybackState.ACTION_PAUSE
                | PlaybackState.ACTION_SKIP_TO_NEXT | PlaybackState.ACTION_SKIP_TO_PREVIOUS
                | PlaybackState.ACTION_PLAY_PAUSE;
        ms.setPlaybackState(new PlaybackState.Builder()
                .setActions(acts)
                .setState(sPlaying ? PlaybackState.STATE_PLAYING : PlaybackState.STATE_PAUSED, 0, 1f)
                .build());

        NotificationManager nm = getSystemService(NotificationManager.class);
        if (Build.VERSION.SDK_INT >= 26) {
            nm.createNotificationChannel(new NotificationChannel(CHANNEL, "Playback", NotificationManager.IMPORTANCE_LOW));
        }
        PendingIntent pi = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(this, CHANNEL) : new Notification.Builder(this);
        b.setContentTitle(sTitle)
                .setContentText(sArtist.length() > 0 ? sArtist : "Zing")
                .setSmallIcon(R.drawable.ic_note)
                .setContentIntent(pi)
                .setOngoing(sPlaying)
                .setVisibility(Notification.VISIBILITY_PUBLIC);
        if (sArt != null) b.setLargeIcon(sArt);
        b.addAction(new Notification.Action.Builder(
                android.R.drawable.ic_media_previous, "Previous", act(ACT_PREV, 1)).build());
        b.addAction(new Notification.Action.Builder(
                sPlaying ? android.R.drawable.ic_media_pause : android.R.drawable.ic_media_play,
                sPlaying ? "Pause" : "Play", act(ACT_TOGGLE, 2)).build());
        b.addAction(new Notification.Action.Builder(
                android.R.drawable.ic_media_next, "Next", act(ACT_NEXT, 3)).build());
        if (Build.VERSION.SDK_INT >= 21) {
            b.setStyle(new Notification.MediaStyle().setMediaSession(ms.getSessionToken())
                    .setShowActionsInCompactView(0, 1, 2));
        }
        Notification n = b.build();
        if (!sStarted) {
            if (Build.VERSION.SDK_INT >= 29) {
                startForeground(1, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK);
            } else {
                startForeground(1, n);
            }
            sStarted = true;
        } else {
            nm.notify(1, n);
        }
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String a = intent == null ? null : intent.getAction();
        if (STOP.equals(a)) {
            sStarted = false;
            stopForeground(true);
            stopSelf();
            return START_NOT_STICKY;
        }
        if (ACT_PREV.equals(a)) { notifyAction("prev"); return START_STICKY; }
        if (ACT_TOGGLE.equals(a)) { notifyAction("toggle"); return START_STICKY; }
        if (ACT_NEXT.equals(a)) { notifyAction("next"); return START_STICKY; }
        refresh();
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        sStarted = false;
        if (ms != null) { ms.release(); ms = null; }
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) { return null; }
}
