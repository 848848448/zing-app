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
            "<button onclick=\"document.getElementById('audio').play();if(window.ZingNative&&ZingNative.updateNowPlaying)ZingNative.updateNowPlaying('QA Fixture Song','QA Artist','http://10.0.2.2:8765/cover.jpg');\">Play fixture</button>"
            '<div id="appver">version: <span id="ver">?</span> build <span id="bld">?</span></div>'
            '<button id="ptest" onclick="var r=prompt(\'QA name?\',\'x\');console.log(\'QAPROMPT=\'+(r===null?\'null\':r))">Prompt test</button>'
            '<button id="ctest" onclick="console.log(\'QACONFIRM=\'+confirm(\'QA ok?\'))">Confirm test</button>'
            '<button id="bridgecheck" onclick="window.ZingNative && window.ZingNative.checkForUpdates()">Bridge update check</button>'
            '<audio id="audio" src="/tone.wav" controls></audio>'
            '<script>window.zingMediaAction=function(a){var el=document.getElementById("audio");if(!el)return;if(a==="toggle"){if(el.paused)el.play();else el.pause();}else if(a==="pause")el.pause();else if(a==="play")el.play();};try{if(window.ZingNative){document.getElementById("ver").textContent=ZingNative.getAppVersion();'
            'document.getElementById("bld").textContent=ZingNative.getAppBuild();}}catch(e){}</script>')
import base64
# 256x256 gradient jpeg: exercises the artwork path with real, recognizable art
open("qa-fixture/cover.jpg", "wb").write(base64.b64decode(
    "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o53Z24q9xRuVLlpzv6jnf1nbir3FG5UuWni31HO7O3JXuKTdyv53nU07oe57xRuLDtip4xXnUz3uXeOD2ffrwd53gAAAAAAAAAAAAAD14/KvO94P0p+jljrpiveObxqfOvbNy0qnf1NzXeJ9xUd5zqdy3ctCd0eLfEO4qty51K5buWnO6Kd/WfuKvcUrlu5ak7op3Z24q9xSuW7lpzujndnbir3FK5buWnO/qOd/WduKvcUrlu5ac7o53Z24q9xSuVLlpzujndnbir3FG5UuWnO6Od2duKvcUblS5ac7o53Z24q9xRuVLlpzv6indnbir3FG5UuWpO6Kd/WduKvcUrlu5ak7+o53Z24q9xSuW7lpzujnf1nbir3FK5buWnO/qKd2duKrcUrlu5ak7op39Z+4q9xSuW7lqTuindnbiq3FK5buWnO6Od2fuKrcUrlS5ac7o53Z+4qtxRuVLlpzv6jndn7iq3FG5UuWnO6Od2fuKrcUblS5ac7+o539Z+4qtxRuVLlpzujndn7iq3FKxu5aWac0kndn6n3ircU2rla4TujdtxZd47vOd804vWsd44PQ8gAAAAAD14/Ko/SgAAAAAAD7nfePj53POvrly67Tu4uW4urFy3xbO6TNO5Sbiq1jnUrlu5aU7op3Z+4q9xSuW7lqTuinf1nbir3FK5buWnO/qOd2duKvcUrlu5ac7o539Z24q9xSuVLlpzujndnbir3FG5UuWnO/qOd/WduKvcUblS5ac7o53Z24q9xRuVLlpzv6jndnbir3FG5UuWnO6Od2duKvcUrlu5ac7op3Z24q9xSuW7lqTv6indnbir3FK5buWpO6Od2duKvcUrlu5ac7+op3Z24q9xSuW7lqTuindnbir3FK5buWpO6Kd2duKvcUrlu5ac7o539Z24q9xSuVLlpzujndnbir3FG5UuWnO/qOd/WduKvcUblS5ac7o53Z24q9xRuVLlpzujnf1nbir3FK5buWnO6Od2duKvcUrlu5aeLI53Z24q9xS43ctDmudSzug7nvFO4sO3KtzxbnUrpuXxwdDnedc33vO8evH5VH6TAAAAAAAAAAAAAAHLHXvFe8eHnU+demblpTO6bne8cNxd/n1O5bsaE7+o8W7xFuKrUudSuW7lpzuinf1n7ir3FK5UuWpO6Kd2duKvcUblS5ac7o53Z24qtxRuVLlpzv6jndn7ir3FG5UuWnO6Od/WduKvcUblS5ac7o53Z24qtxRuVLlpzv6jndn7ir3FK5buWnO/qOd2duKrcUrlu5ac7op39Z+4qtxSuW7lqTv6inf1n7iq3FK5buWpO6Od2fuKrcUrlu5ac7op39Z+4qtxSuW7lqTuindn7iq3FK5buWpO6Kd2fuKrcUrlS5ak7+op3Z+4qtxRuVLlpzujndn7iq3FG5UuWnO/qOd/WfuKrcUblS5ac7o53Z+4qtxSuW7lpzujnf1n7iq3FK5buWnO6Od2fuKrcUrlu5ac7o53Z+4qtxepH5qH6BAAAAAAAAAAAAAAAAAAAAAfea7x8fO8519cuXXXFvjk57l9dGLltZO/qTO+5S7ip7nnUrlu5aU7op3Qbir3FK5UuWpO6Kd2duKvcUblS5ac7+o53Z24q9xRuVLlpzujnf1nbir3FG5UuWnO/qOd2duKvcUrlu5ac7o53Z24q9xSuW7lpzv6jnf1nbir3FK5buWnO6Od2duKvcUrlu5ac7+o53Z24q9xSuW7lpzuindnbir3FK5buWpO6Kd2duKvcUrlu5ak7+o53Z24q9xSuVLlpzuindnbir3FG5UuWpO6Kd2duKvcUblS5ak7op39Z24q9xRuVLlpzujndnbir3FG5UuWnO6Od/WduKvcUrlu5ac7o53Z24q9xeiH8DH9rAAAAAAAAAAAAAAAAAAAAAAAAAAAADg9Zp3Ly86xzr0zctKJ3T/fjjuLsnct2L53R4r3iPcVWp86lcqXLTnf1FO7P3FVuKNypctOd0c7+s/cVW4o3Kly053Rzuz9xVbilct3LTnf1HO7P3FVuKVy3ctOd0c7s/cVW4pXLdy053Rzv6z9xVbilct3LTndHO7P3FVuKVy3ctOd/Uc7s/cVW4pXLdy053RTv6z9xVbilct3LUndFO7PpFVuKVypctSd0U7s/cVW4o3Kly1J3RTuz9xVbijcqXLUnf1FO7P3FVuKNypctSd0U7+s/cVW4v/9k="))
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
# The auto update dialog and the permission prompt can race the fixture
# checks; dismiss modals first. Cold boots can stall the first WebView
# load, so wait generously and relaunch the activity once if stuck.
fixture_ready = False
for attempt in range(15):
    root = dump("ui-fixture")
    if nodes_with(root, "Update available"):
        laterx = exact(root, "Later")
        if laterx is not None:
            tap(laterx)
            time.sleep(2)
            continue
    allowx = exact(root, "Allow")
    if allowx is not None:
        tap(allowx)
        time.sleep(2)
        continue
    if exact(root, "Bridge update check") is not None:
        fixture_ready = True
        break
    if attempt == 7:
        sh("adb shell am force-stop %s" % PKG)
        sh("adb shell am start -n %s/.MainActivity --es qa_url http://10.0.2.2:8765/" % PKG)
        time.sleep(10)
    time.sleep(2)
if not fixture_ready:
    print("FIXTURE-NEVER-READY, visible nodes:")
    for n in root.iter("node"):
        t = (n.get("text") or "") or (n.get("content-desc") or "")
        if t:
            print("  NODE:", t[:120])
shot("qa-1b-fixture-visible")

# 1c. JS dialogs: does the installed WebView host show prompt()/confirm() and return values?
def chromium_log():
    return sh("adb shell logcat -d -s chromium:I").stdout
for label, btn, tag, okword in (("prompt", "Prompt test", "QAPROMPT=", "OK"), ("confirm", "Confirm test", "QACONFIRM=", "OK")):
    root = dump("ui-" + label)
    node = exact(root, btn)
    if node is None:
        result("%s test button present" % label, False)
        continue
    sh("adb logcat -c")
    tap(node)
    time.sleep(3)
    droot = dump("ui-" + label + "-dialog")
    shot("qa-1c-" + label + "-dialog")
    ok_node = exact(droot, okword)
    shown = ok_node is not None
    result("%s dialog is shown by the app WebView" % label, shown)
    if ok_node is not None:
        tap(ok_node)
        time.sleep(2)
    out = chromium_log()
    open("qa-out/chromium-" + label + ".txt", "w").write(out)
    m = re.search(tag + r"(\S+)", out)
    print("DIALOG", label, "shown=", shown, "result=", m.group(1) if m else None, flush=True)
    result("%s returns a usable value after OK" % label, bool(m) and m.group(1) not in ("null", "false"))
result("floating update control removed", not nodes_with(root, "Check for updates"))
result("bridge version shown in page", bool(nodes_with(root, "version:", "build")))
bridge = exact(root, "Bridge update check")
result("bridge update button present", bridge is not None)
if bridge is not None:
    tap(bridge)
    time.sleep(8)
    rootd = dump("ui-bridge-dlg")
    shot("qa-1c-bridge-dialog")
    result("bridge triggers native update dialog", bool(nodes_with(rootd, "Update available")))
    result("update dialog shows What's new notes", bool(nodes_with(rootd, "What's new")))
    laterd = exact(rootd, "Later")
    if laterd is not None:
        tap(laterd)
        time.sleep(2)

def last_audio_state():
    out = sh("adb shell logcat -d -s ZingQA:I").stdout
    m = re.findall(r'audio="(true|false)\|', out)
    return m[-1] if m else "none"

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
print("NOTIF-DUMP-BEGIN"); print(notif[:4000]); print("NOTIF-DUMP-END", flush=True)
# title asserted from the expanded shade below (dumpsys redacts values)
result("notification has media actions", "Pause" in notif or "Play" in notif)
# Bring the app back to the foreground so the media receiver can drive the page,
# then tap the REAL notification Pause action and confirm playback pauses.
sh("adb shell am start -n %s/.MainActivity --es qa_url http://10.0.2.2:8765/" % PKG)
time.sleep(6)
sh("adb shell cmd statusbar expand-notifications")
time.sleep(4)
shade = dump("notif-shade")
shot("qa-3b-notification")
result("notification shows now-playing title", bool(nodes_with(shade, "QA Fixture Song")))
def exact_node(root, word):
    # exact match on text OR content-desc; Element truthiness is unusable (childless node == falsy)
    if root is None:
        return None
    for n in root.iter("node"):
        t = (n.get("text") or "").strip().lower()
        d = (n.get("content-desc") or "").strip().lower()
        if t == word.lower() or d == word.lower():
            return n
    return None

pausebtn = exact_node(shade, "Pause")
result("notification Pause action tappable", pausebtn is not None)

def audio_states():
    out = sh("adb shell logcat -d -s ZingQA:I").stdout
    return re.findall(r'audio="(true|false)\|', out)

def wait_audio_state(want, seen, tries=6):
    # wait for a NEW ZingQA line (beyond the pre-tap count) reporting the wanted state
    st = audio_states()
    for _ in range(tries):
        if len(st) > seen and st[-1] == want:
            return st
        time.sleep(4)
        st = audio_states()
    return st

try:
    if pausebtn is not None:
        pre = len(audio_states())
        tap(pausebtn)
        time.sleep(3)
        sh("adb shell cmd statusbar collapse")
        st = wait_audio_state("false", pre)
        print("AUDIO-LOG-AFTER-PAUSE-BEGIN")
        print(sh("adb shell logcat -d -s ZingQA:I").stdout[-1200:])
        print("AUDIO-LOG-AFTER-PAUSE-END", flush=True)
        paused_ok = len(st) > pre and st[-1] == "false"
        result("notification Pause actually pauses audio", paused_ok)
        sh("adb shell cmd statusbar expand-notifications")
        time.sleep(4)
        shade2 = dump("notif-shade-2")
        playbtn = exact_node(shade2, "Play")
        result("notification flips to Play when paused", playbtn is not None)
        if not paused_ok or playbtn is None:
            result("notification Play resumes audio", False)
        else:
            pre2 = len(audio_states())
            tap(playbtn)
            time.sleep(3)
            sh("adb shell cmd statusbar collapse")
            st2 = wait_audio_state("true", pre2)
            print("AUDIO-LOG-AFTER-PLAY-BEGIN")
            print(sh("adb shell logcat -d -s ZingQA:I").stdout[-1200:])
            print("AUDIO-LOG-AFTER-PLAY-END", flush=True)
            result("notification Play resumes audio", len(st2) > pre2 and st2[-1] == "true")
finally:
    sh("adb shell cmd statusbar collapse")
    time.sleep(2)
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
    sh("adb shell am force-stop %s" % PKG)
    sh("adb shell am start -W -n %s/.MainActivity" % PKG)
    time.sleep(15)
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

