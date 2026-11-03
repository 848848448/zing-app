import os, re, subprocess, time, xml.etree.ElementTree as ET

os.makedirs("qa-out", exist_ok=True)
PKG = "com.zingmusic.app"

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

def result(name, ok):
    print(("PASS " if ok else "FAIL ") + name, flush=True)
    with open("qa-out/results.txt", "a") as f:
        f.write(("PASS " if ok else "FAIL ") + name + "\n")

# Install the actual hook-free production APK from the latest public release
r = sh("adb install -r prod.apk")
result("install production APK", "Success" in r.stdout)
sh("adb shell monkey -p %s -c android.intent.category.LAUNCHER 1" % PKG)
time.sleep(20)
shot("prod-1-signin")
root = dump("prod-ui-1")
result("production sign-in page renders", bool(nodes_with(root, "Sign in", "Password", "Zing")))
result("native Check for updates control present", bool(nodes_with(root, "Check for updates")))
r = sh("adb shell dumpsys package %s | grep versionCode" % PKG)
print(r.stdout)
m = re.search(r"versionCode=(\d+)", r.stdout)
result("production versionCode recorded", bool(m))
