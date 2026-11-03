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

# Genuine first install of the hook-free production APK: no pregranted
# permissions, no appops bypass. Every prompt is answered through visible UI.
r = sh("adb install prod.apk")
result("install production APK", "Success" in r.stdout)
sh("adb shell monkey -p %s -c android.intent.category.LAUNCHER 1" % PKG)
time.sleep(15)

# 1. first-install notification permission prompt, tapped through the UI
root = dump("prod-ui-1")
shot("prod-1-first-launch")
allow = exact(root, "Allow")
result("first-install notification prompt shown", allow is not None)
if allow is not None:
    tap(allow)
    time.sleep(3)

# 2. production sign-in render + native update control
root = dump("prod-ui-2")
shot("prod-2-signin")
result("production sign-in page renders", bool(nodes_with(root, "Sign in", "Password", "Zing")))
fab = nodes_with(root, "Check for updates")
result("native Check for updates control present", bool(fab))

# 3. exercise the control with the production update source: installed build is
#    the latest release, so a manual check must answer up-to-date (or offer a
#    newer production release if one exists)
if fab:
    tap(fab[0])
    seen = False
    for i in range(6):
        time.sleep(2)
        r2 = dump("prod-ui-check-%d" % i)
        if nodes_with(r2, "up to date") or nodes_with(r2, "Update available"):
            seen = True
            break
    shot("prod-3-update-check")
    result("update control responds from production source", seen)

r = sh("adb shell dumpsys package %s | grep versionCode" % PKG)
print(r.stdout)
m = re.search(r"versionCode=(\d+)", r.stdout)
result("production versionCode recorded", bool(m))
print(open("qa-out/results.txt").read(), flush=True)
sys.exit(1 if FAILURES else 0)
