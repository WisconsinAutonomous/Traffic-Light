import os, json, threading, time
from pathlib import Path
try:
    import RPi.GPIO as GPIO
    USING_GPIO = True
except Exception:
    USING_GPIO = False
    class MockGPIO:
        BOARD = BCM = OUT = IN = HIGH = 1; LOW = 0
        def setmode(self, *_): pass
        def setup(self, *_): pass
        def output(self, pin, val): print(f"[MOCK GPIO] pin {pin} -> {'HIGH' if val else 'LOW'}")
        def cleanup(self): pass
    GPIO = MockGPIO()

from flask import Flask, render_template, request, redirect, url_for, jsonify, flash

app = Flask(__name__)
app.secret_key = "traffic-secret"  # for flash messages

# -----------------------------
# GPIO / Lights configuration
# -----------------------------
BOARD_MODE = True
if BOARD_MODE:
    GPIO.setmode(GPIO.BOARD)
    PINS = {"RED": 11, "YELLOW": 13, "GREEN": 15}
else:
    GPIO.setmode(GPIO.BCM)
    PINS = {"RED": 17, "YELLOW": 27, "GREEN": 22}

for p in PINS.values():
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, GPIO.LOW)

# -----------------------------
# Persistence for presets
# -----------------------------
DATA_DIR = Path(__file__).parent
PRESETS_FILE = DATA_DIR / "presets.json"

def load_presets():
    if PRESETS_FILE.exists():
        try:
            with open(PRESETS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_presets(presets):
    with open(PRESETS_FILE, "w", encoding="utf-8") as f:
        json.dump(presets, f, indent=2)

presets = load_presets()
# Provide a few defaults if file empty
if not presets:
    presets = {
        "Default": {"red": 5.0, "yellow": 3.0, "green": 5.0, "flash": 0.5},
        "School": {"red": 30.0, "yellow": 15.0, "green": 30.0, "flash": 0.5},
        "City": {"red": 25.0, "yellow": 3.0, "green": 25.0, "flash": 0.5}
    }
    save_presets(presets)

# -----------------------------
# State
# -----------------------------
state_lock = threading.Lock()
state = {
    "running": False,
    "mode": "STOP",             # STOP | SEQUENCE | HOLD_* | FLASH_*
    "durations": dict(presets.get("Default", {"red":5.0,"yellow":3.0,"green":5.0,"flash":0.5})),
    "active_preset": "Default"
}

# threads
sequence_thread = None
flash_threads = {c: None for c in ("RED", "YELLOW", "GREEN")}
flash_flags = {c: threading.Event() for c in ("RED", "YELLOW", "GREEN")}

# -----------------------------
# Helpers
# -----------------------------
def all_off():
    for pin in PINS.values():
        GPIO.output(pin, GPIO.LOW)

def set_only(color):
    for k, pin in PINS.items():
        GPIO.output(pin, GPIO.HIGH if k == color else GPIO.LOW)

def _sequence_should_continue():
    """Return True only while we really want the sequence running."""
    with state_lock:
        return state["running"] and state["mode"] == "SEQUENCE"

def _sleep_interruptible(total):
    """
    Sleep for up to `total` seconds, but wake early if sequence is stopped
    or mode changes away from SEQUENCE. Returns False if we should abort.
    """
    end = time.time() + total
    while True:
        if not _sequence_should_continue():
            return False
        remaining = end - time.time()
        if remaining <= 0:
            return True
        time.sleep(min(0.1, remaining))

# -----------------------------
# Threads
# -----------------------------
def sequence_worker():
    """
    Traffic-light sequence:
      RED -> GREEN -> YELLOW -> repeat
    Can be interrupted quickly by Hold/Stop/Flash actions.
    """
    while _sequence_should_continue():
        # copy durations under lock
        with state_lock:
            d = dict(state["durations"])

        # RED phase
        set_only("RED")
        if not _sleep_interruptible(d["red"]):
            break

        # GREEN phase
        set_only("GREEN")
        if not _sleep_interruptible(d["green"]):
            break

        # YELLOW phase
        set_only("YELLOW")
        if not _sleep_interruptible(d["yellow"]):
            break
    # IMPORTANT: do NOT call all_off() here.
    # Stop / Hold / Flash handlers manage the LEDs explicitly.

def start_sequence():
    global sequence_thread
    stop_all_flashes()
    with state_lock:
        state["mode"] = "SEQUENCE"
        state["running"] = True
    sequence_thread = threading.Thread(target=sequence_worker, daemon=True)
    sequence_thread.start()

def stop_sequence():
    with state_lock:
        state["running"] = False
        state["mode"] = "STOP"
    all_off()

def flash_worker(color):
    pin = PINS[color]
    e = flash_flags[color]
    while True:
        with state_lock:
            if e.is_set() or state["mode"] != f"FLASH_{color}":
                break
            interval = state["durations"]["flash"]
        GPIO.output(pin, GPIO.HIGH)
        time.sleep(interval)
        GPIO.output(pin, GPIO.LOW)
        time.sleep(interval)
    GPIO.output(pin, GPIO.LOW)

def start_flash(color):
    stop_sequence()
    stop_all_flashes()
    with state_lock:
        state["mode"] = f"FLASH_{color}"
    flash_flags[color].clear()
    t = threading.Thread(target=flash_worker, args=(color,), daemon=True)
    flash_threads[color] = t
    t.start()

def stop_flash(color):
    flash_flags[color].set()
    t = flash_threads.get(color)
    if t and t.is_alive():
        t.join(timeout=0.05)
    GPIO.output(PINS[color], GPIO.LOW)

def stop_all_flashes():
    for c in ("RED", "YELLOW", "GREEN"):
        stop_flash(c)

def hold_color(color):
    # Stop any running sequences or flashes, then solidly drive one color.
    stop_sequence()
    stop_all_flashes()
    with state_lock:
        state["mode"] = f"HOLD_{color}"
    set_only(color)

def _maybe_float(x):
    try:
        return max(0.1, float(x))
    except Exception:
        return None

# -----------------------------
# Routes
# -----------------------------
@app.route("/", methods=["GET"])
def home():
    with state_lock:
        s = dict(state)
        s["durations"] = dict(state["durations"])
    return render_template("index.html", state=s, pins=PINS, presets=sorted(presets.keys()))

@app.route("/control", methods=["POST"])
def control():
    action = request.form.get("action")
    # Optional timing updates
    red = _maybe_float(request.form.get("red"))
    yellow = _maybe_float(request.form.get("yellow"))
    green = _maybe_float(request.form.get("green"))
    flash_int = _maybe_float(request.form.get("flash"))
    with state_lock:
        if red is not None: state["durations"]["red"] = red
        if yellow is not None: state["durations"]["yellow"] = yellow
        if green is not None: state["durations"]["green"] = green
        if flash_int is not None: state["durations"]["flash"] = flash_int

    if action == "START_SEQUENCE":
        start_sequence()
    elif action == "STOP":
        stop_sequence()
    elif action in ("HOLD_RED","HOLD_YELLOW","HOLD_GREEN"):
        hold_color(action.split("_")[1])
    elif action in ("FLASH_RED","FLASH_YELLOW","FLASH_GREEN"):
        start_flash(action.split("_")[1])
    return redirect(url_for("home"))

@app.route("/preset/save", methods=["POST"])
def preset_save():
    name = (request.form.get("preset_name") or "").strip()
    if not name:
        flash("Preset name is required.", "error")
        return redirect(url_for("home"))
    with state_lock:
        presets[name] = dict(state["durations"])
        state["active_preset"] = name
    save_presets(presets)
    flash(f"Saved preset '{name}'.", "ok")
    return redirect(url_for("home"))

@app.route("/preset/apply", methods=["POST"])
def preset_apply():
    name = request.form.get("preset_select")
    if not name or name not in presets:
        flash("Choose a valid preset to apply.", "error")
        return redirect(url_for("home"))
    with state_lock:
        state["durations"] = dict(presets[name])
        state["active_preset"] = name
    flash(f"Applied preset '{name}'.", "ok")
    return redirect(url_for("home"))

@app.route("/preset/delete", methods=["POST"])
def preset_delete():
    name = request.form.get("preset_select")
    if not name or name not in presets:
        flash("Choose a valid preset to delete.", "error")
        return redirect(url_for("home"))
    if len(presets) <= 1:
        flash("Cannot delete the last remaining preset.", "error")
        return redirect(url_for("home"))
    with state_lock:
        was_active = (state["active_preset"] == name)
    del presets[name]
    save_presets(presets)
    if was_active:
        fallback = "Default" if "Default" in presets else sorted(presets.keys())[0]
        with state_lock:
            state["durations"] = dict(presets[fallback])
            state["active_preset"] = fallback
    flash(f"Deleted preset '{name}'.", "ok")
    return redirect(url_for("home"))

@app.route("/api/state")
def api_state():
    with state_lock:
        s = dict(state)
        s["durations"] = dict(state["durations"])
    return jsonify(s)

@app.route("/shutdown", methods=["POST"])
def shutdown():
    stop_sequence()
    stop_all_flashes()
    GPIO.cleanup()
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
