import os, re, subprocess, sys, time, math, struct, wave, xml.etree.ElementTree as ET

os.makedirs("qa-out", exist_ok=True)
PKG = "com.zingmusic.app"
FAILURES = []

def sh(cmd):
    print("+", cmd, flush=True)
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def dump(name):
    sh("adb shell uiautomator dump /sdcard/ui.xml")
    sh("adb pull /sdcard/ui.xml qa-out/%s.xml" % name)
    try:
        return ET.parse("qa-out/%s.xml" % name).getroot()
    except Exception:
        return None

def shot(name):
    sh("adb shell screencap -p /sdcard/%s.png" % name)
    sh("adb pull /sdcard/%s.png qa-out/%s.png" % (name, name))

def nodes_with(root, *words):
    out = []
    if root is None:
        return out
    for n in root.iter("node"):
        t = ((n.get("text") or "") + " " + (n.get("content-desc") or "")).lower()
        if any(w.lower() in t for w in words):
            out.append(n)
    return out

def exact(root, word):
    if root is None:
        return None
    for n in root.iter("node"):
        if (n.get("text") or "").strip().lower() == word.lower():
            return n
    return None

def tap(node):
    m = re.findall(r"\d+", node.get("bounds"))
    x = (int(m[0]) + int(m[2])) // 2
    y = (int(m[1]) + int(m[3])) // 2
    sh("adb shell input tap %d %d" % (x, y))

def result(name, ok):
    print(("PASS " if ok else "FAIL ") + name, flush=True)
    if not ok:
        FAILURES.append(name)
    with open("qa-out/results.txt", "a") as f:
        f.write(("PASS " if ok else "FAIL ") + name + "\n")

# --- local audio fixture: a page with a looping tone, no site credentials ---
os.makedirs("qa-fixture", exist_ok=True)
with open("qa-fixture/index.html", "w") as f:
    f.write('<!doctype html><title>Zing QA fixture</title>'
            '<body style="background:#0a0a12;color:#fff">fixture'
            "<button onclick=\"document.getElementById('audio').play()\">Play fixture</button>"
            '<audio id="audio" src="/tone.wav" controls></audio>')
sr = 8000
with wave.open("qa-fixture/tone.wav", "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
    frames = b"".join(struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * i / sr)))
                      for i in range(sr * 300))
    w.writeframes(frames)
server = subprocess.Popen([sys.executable, "-m", "http.server", "8765",
                           "--directory", "qa-fixture"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(2)

sh("adb logcat -c")

# 1. install b1 + launch with the fixture URL (QA mode). Genuine first
#    install: no pregranted permissions; the notification prompt is answered
#    through the visible system dialog.
r = sh("adb install -r qa-b1.apk"); result("install b1", "Success" in r.stdout)
sh("adb shell am start -n %s/.MainActivity --es qa_url http://10.0.2.2:8765/" % PKG)
time.sleep(15)
shot("qa-1-launched")
root = dump("ui-1")
allow = exact(root, "Allow")
result("first-install notification prompt shown", allow is not None)
if allow is not None:
    tap(allow)
    time.sleep(3)
    root = dump("ui-1b")
later = exact(root, "Later")
if later is not None:
    tap(later)
    time.sleep(2)
    root = dump("ui-1c")
# Permission and update dialogs can arrive in either order.
allow2 = exact(root, "Allow")
if allow2 is not None:
    tap(allow2)
    time.sleep(2)
    root = dump("ui-1d")
shot("qa-1b-fixture-visible")
result("update control present", bool(nodes_with(root, "Check for updates")))

def playback_times():
    out = sh("adb shell logcat -d -s ZingQA:I").stdout
    open("qa-out/audio-log.txt", "w").write(out)
    return [float(m.group(1)) for m in re.finditer(r'audio="true\|([0-9.]+)"', out)]

play = exact(dump("ui-play"), "Play fixture")
result("fixture play control present", play is not None)
if play is not None:
    tap(play)

# 2. fixture audio plays and advances in the foreground
time.sleep(8)
t1 = playback_times()
result("fixture audio playing", len(t1) >= 1)
shot("qa-2-playing")

# 3. background the app: playback time must keep advancing, notification up
last1 = t1[-1] if t1 else -1
sh("adb shell input keyevent KEYCODE_HOME")
time.sleep(15)
t2 = playback_times()
shot("qa-3-backgrounded-home")
sh("adb shell dumpsys notification > qa-out/notif.txt")
notif = open("qa-out/notif.txt").read()
result("playback notification while backgrounded", "pkg=com.zingmusic.app" in notif and "channel=playback" in notif)
print("FOREGROUND_TIMES", t1, "BACKGROUND_TIMES", t2, flush=True)
result("playback advanced across backgrounding", bool(t1) and bool(t2) and t2[-1] > last1 + 5)
sh("adb shell logcat -d > qa-out/full-logcat.txt")

# 4. production site renders its sign-in page (no credentials used)
sh("adb shell am force-stop %s" % PKG)
sh("adb shell am start -n %s/.MainActivity" % PKG)
time.sleep(15)
root = dump("ui-4")
later4 = exact(root, "Later")
if later4 is not None:
    tap(later4)
for attempt in range(8):
    root = dump("ui-4-visible")
    if nodes_with(root, "Sign in with your email"):
        break
    time.sleep(3)
shot("qa-4-prod-signin")
result("production site renders (sign-in page)", bool(nodes_with(root, "Sign in with your email")))

# 5. update round-trip b1 -> b2 via the in-app updater, through the real UI:
#    dialog, download, genuine unknown-source consent in Settings, installer.
sh("adb shell am force-stop %s" % PKG)
sh("adb shell am start -W -n %s/.MainActivity" % PKG)
time.sleep(15)
root5 = dump("ui-5")
dlg = nodes_with(root5, "Update available")
result("update dialog shown for b2", bool(dlg))
shot("qa-5-update-dialog")
upd = exact(root5, "Update")
if upd is not None:
    tap(upd)
time.sleep(25)
root6 = dump("ui-6")
allowsrc = nodes_with(root6, "Allow from this source")
result("unknown-source consent screen shown", bool(allowsrc))
if allowsrc:
    shot("qa-6-unknown-sources")
    tap(allowsrc[0])
    time.sleep(3)
    sh("adb shell input keyevent KEYCODE_BACK")
    time.sleep(6)
    fab = nodes_with(dump("ui-6b"), "Check for updates")
    if fab:
        tap(fab[0])
        time.sleep(6)
    root6b = dump("ui-6c")
    upd2 = exact(root6b, "Update")
    if upd2 is not None:
        tap(upd2)
        time.sleep(20)
    root6 = dump("ui-6d")
inst = exact(root6, "Update")
if inst is None:
    inst = exact(root6, "Install")
if inst is not None:
    tap(inst)
    time.sleep(20)
    done = nodes_with(dump("ui-7"), "Done", "Open")
    if done: tap(done[0])
r = sh("adb shell dumpsys package %s | grep versionCode" % PKG)
print(r.stdout)
result("b2 installed via in-app updater", "versionCode=2" in r.stdout)
shot("qa-7-updated")

server.terminate()
print(open("qa-out/results.txt").read(), flush=True)
sys.exit(1 if FAILURES else 0)
