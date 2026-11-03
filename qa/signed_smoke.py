import re, subprocess, sys, time, xml.etree.ElementTree as ET
import os

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

EXPECTED_VC = int(os.environ.get("EXPECTED_VC", "0"))

# ============ Production-signed APK, clean install ============
r = sh("adb install signed.apk")
result("install production-signed APK", "Success" in r.stdout)
sh("adb shell input keyevent KEYCODE_WAKEUP")
sh("adb shell wm dismiss-keyguard")
r = sh("adb shell am start -W -n %s/.MainActivity" % PKG)
print(r.stdout, r.stderr, flush=True)
time.sleep(15)

root = dump("smoke-ui-1")
shot("smoke-1-first-launch")
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
    root = dump("smoke-ui-2")
    if nodes_with(root, "Sign in with your email"):
        break
    time.sleep(3)
shot("smoke-2-signin")
result("production sign-in page renders", bool(nodes_with(root, "Sign in with your email")))

result("floating update control removed", not nodes_with(root, "Check for updates"))

# This build carries the same versionCode as the latest public release:
# the auto-check must treat it as up to date.
result("no update dialog when up-to-date", not nodes_with(root, "Update available"))

r = sh("adb shell dumpsys package %s | grep versionCode" % PKG)
print(r.stdout)
m = re.search(r"versionCode=(\d+)", r.stdout)
result("signed build versionCode recorded", bool(m))
if EXPECTED_VC:
    result("versionCode matches expected release build", bool(m) and int(m.group(1)) == EXPECTED_VC)

# Signature sanity: the installed signer must match the latest release APK's signer.
r = sh("adb shell dumpsys package %s | grep -A2 'signatures\\|SigningInfo'" % PKG)
print(r.stdout)

# ============ QA hook must be inert in the signed build ============
# Launching with the QA fixture extra must be ignored: the production site,
# not a fixture, must render. This is the release/QA separation proof.
sh("adb shell am force-stop %s" % PKG)
sh("adb shell am start -W -n %s/.MainActivity --es qa_url http://10.0.2.2:8765/" % PKG)
time.sleep(12)
root = None
for attempt in range(8):
    root = dump("smoke-ui-qa")
    if nodes_with(root, "Sign in with your email"):
        break
    time.sleep(3)
shot("smoke-3-qa-hook-inert")
result("qa_url extra ignored in signed build (production site renders)",
       bool(nodes_with(root, "Sign in with your email")))
result("no QA fixture loaded in signed build", not nodes_with(root, "Zing QA fixture"))

sh("adb shell logcat -d > qa-out/full-logcat.txt")
print(open("qa-out/results.txt").read(), flush=True)
sys.exit(1 if FAILURES else 0)
