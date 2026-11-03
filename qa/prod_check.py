import os, re, subprocess, sys, time, xml.etree.ElementTree as ET

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

# ============ Phase A: latest production APK, clean install ============
r = sh("adb install prod.apk")
result("install production APK", "Success" in r.stdout)
sh("adb shell input keyevent KEYCODE_WAKEUP")
sh("adb shell wm dismiss-keyguard")
r = sh("adb shell am start -W -n %s/.MainActivity" % PKG)
print(r.stdout, r.stderr, flush=True)
time.sleep(15)

root = dump("prod-ui-1")
shot("prod-1-first-launch")
allow = exact(root, "Allow")
result("first-install notification prompt shown", allow is not None)
if allow is not None:
    tap(allow)
    time.sleep(3)

sh("adb shell am force-stop %s" % PKG)
sh("adb shell am start -W -n %s/.MainActivity" % PKG)
time.sleep(12)
root = None
for attempt in range(8):
    root = dump("prod-ui-2")
    if nodes_with(root, "Sign in with your email"):
        break
    time.sleep(3)
shot("prod-2-signin")
result("production sign-in page renders", bool(nodes_with(root, "Sign in with your email")))

# The floating update FAB was removed in b8: no "Check for updates" overlay
# may be present on screen anymore.
result("floating update control removed", not nodes_with(root, "Check for updates"))

# Installed build IS the latest release: the auto-check must not offer an update.
result("no update dialog when up-to-date", not nodes_with(root, "Update available"))

r = sh("adb shell dumpsys package %s | grep versionCode" % PKG)
print(r.stdout)
m = re.search(r"versionCode=(\d+)", r.stdout)
result("production versionCode recorded", bool(m))
result("production versionCode exceeds 7", bool(m) and int(m.group(1)) > 7)
latest_vc = int(m.group(1)) if m else -1

# ============ Phase B: real update installation prev -> latest ============
sh("adb uninstall %s" % PKG)
r = sh("adb install prev.apk")
result("install previous release APK", "Success" in r.stdout)
sh("adb shell am start -W -n %s/.MainActivity" % PKG)
time.sleep(20)
root = None
for attempt in range(10):
    root = dump("prod-ui-upd")
    if nodes_with(root, "Update available"):
        break
    allow = exact(root, "Allow")
    if allow is not None:
        tap(allow)
    time.sleep(4)
shot("prod-4-update-dialog")
result("update dialog shown on previous build", bool(nodes_with(root, "Update available")))
# Note: this dialog is rendered by the PREVIOUS build's own updater code, so the
# b8 "What's new" display cannot appear here; it is verified in qa/run.py where
# the installed build carries the new updater.
upd = exact(root, "Update")
if upd is not None:
    tap(upd)
time.sleep(25)
root = dump("prod-ui-consent")
allowsrc = nodes_with(root, "Allow from this source")
if allowsrc:
    shot("prod-5-unknown-sources")
    tap(allowsrc[0])
    time.sleep(3)
    sh("adb shell input keyevent KEYCODE_BACK")
    time.sleep(6)
    # re-trigger the update flow via a fresh launch (auto-check); poll for the dialog
    sh("adb shell am force-stop %s" % PKG)
    sh("adb shell am start -W -n %s/.MainActivity" % PKG)
    time.sleep(8)
    upd2 = None
    for attempt in range(12):
        root = dump("prod-ui-redialog")
        upd2 = exact(root, "Update")
        if upd2 is not None:
            break
        allowx = exact(root, "Allow")
        if allowx is not None:
            tap(allowx)
        time.sleep(4)
    result("update dialog reshown after consent", upd2 is not None)
    if upd2 is not None:
        tap(upd2)
        time.sleep(20)
    root = dump("prod-ui-install")
inst = exact(root, "Update")
if inst is None:
    inst = exact(root, "Install")
if inst is not None:
    tap(inst)
    time.sleep(20)
    done = nodes_with(dump("prod-ui-done"), "Done", "Open")
    if done:
        tap(done[0])
r = sh("adb shell dumpsys package %s | grep versionCode" % PKG)
print(r.stdout)
result("latest installed via real in-app update", ("versionCode=%d" % latest_vc) in r.stdout)
shot("prod-6-updated")

sh("adb shell logcat -d > qa-out/full-logcat.txt")
print(open("qa-out/results.txt").read(), flush=True)
sys.exit(1 if FAILURES else 0)
