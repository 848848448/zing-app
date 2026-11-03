import os, re, subprocess, sys, time, math, struct, wave, xml.etree.ElementTree as ET

os.makedirs("qa-out", exist_ok=True)
PKG = "com.zingmusic.app"

def sh(cmd, check=False):
    print("+", cmd, flush=True)
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, check=check)

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

def tap(node):
    m = re.findall(r"\d+", node.get("bounds"))
    x = (int(m[0]) + int(m[2])) // 2
    y = (int(m[1]) + int(m[3])) // 2
    sh("adb shell input tap %d %d" % (x, y))

FAILURES = []

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
            '<audio id="audio" src="/tone.wav" loop autoplay></audio>')
sr = 8000
with wave.open("qa-fixture/tone.wav", "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
    frames = b"".join(struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * i / sr)))
                      for i in range(sr * 30))
    w.writeframes(frames)
server = subprocess.Popen([sys.executable, "-m", "http.server", "8765",
                           "--directory", "qa-fixture"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(2)

sh("adb logcat -c")

# 1. install b1 + launch with the fixture URL (QA mode)
r = sh("adb install -r qa-b1.apk"); result("install b1", "Success" in r.stdout)
sh("adb shell pm grant %s android.permission.POST_NOTIFICATIONS" % PKG)
sh("adb shell appops set %s REQUEST_INSTALL_PACKAGES allow" % PKG)
sh("adb shell am start -n %s/.MainActivity --es qa_url http://10.0.2.2:8765/" % PKG)
time.sleep(20)
shot("qa-1-launched")
root = dump("ui-1")
result("update control present", bool(nodes_with(root, "Check for updates")))

def playback_times():
    out = sh("adb shell logcat -d -s ZingQA:I").stdout
    return [float(m.group(1)) for m in re.finditer(r'audio="true\|([0-9.]+)"', out)]

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
result("playback notification while backgrounded", "Zing" in notif)
result("playback advanced across backgrounding", bool(t2) and t2[-1] > last1)

# 4. production site renders its sign-in page (no credentials used)
sh("adb shell am force-stop %s" % PKG)
sh("adb shell am start -n %s/.MainActivity" % PKG)
time.sleep(15)
root = dump("ui-4")
shot("qa-4-prod-signin")
result("production site renders (sign-in page)", bool(nodes_with(root, "Sign in", "Password", "Zing")))

# 5. update round-trip b1 -> b2 via the in-app updater
sh("adb shell am force-stop %s" % PKG)
sh("adb shell monkey -p %s -c android.intent.category.LAUNCHER 1" % PKG)
time.sleep(15)
dlg = nodes_with(dump("ui-5"), "Update available")
result("update dialog shown for b2", bool(dlg))
upd = nodes_with(dump("ui-5b"), "Update")
upd = [n for n in upd if "check for updates" not in ((n.get("content-desc") or "").lower())]
if upd:
    tap(upd[0])
time.sleep(30)
root6 = dump("ui-6")
allow = nodes_with(root6, "Allow from this source")
if allow:
    tap(allow[0])
    time.sleep(3)
    sh("adb shell input keyevent KEYCODE_BACK")
    time.sleep(8)
    upd2 = nodes_with(dump("ui-6b"), "Update")
    upd2 = [n for n in upd2 if "check for updates" not in ((n.get("content-desc") or "").lower())]
    if upd2:
        tap(upd2[0])
    time.sleep(25)
    root6 = dump("ui-6c")
inst = nodes_with(root6, "Install")
if inst:
    tap(inst[0])
    time.sleep(20)
    done = nodes_with(dump("ui-7"), "Done", "Open")
    if done: tap(done[0])
r = sh("adb shell dumpsys package %s | grep versionCode" % PKG)
print(r.stdout)
result("b2 installed via in-app updater", "versionCode=2" in r.stdout)
shot("qa-5-updated")

server.terminate()
print(open("qa-out/results.txt").read(), flush=True)
sys.exit(1 if FAILURES else 0)
