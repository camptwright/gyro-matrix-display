import asyncio
from types import SimpleNamespace
from uuid import UUID
from bleak import BleakScanner, BleakClient

# --- BLE (Nordic UART) ---
NUS_SERVICE = UUID("6e400001-b5a3-f393-e0a9-e50e24dcca9e")
NUS_TX      = UUID("6e400003-b5a3-f393-e0a9-e50e24dcca9e")
DEVICE_HINTS = ["imu raw (ble uart)", "imu controller", "imu controller (ble uart)"]

# --- Gesture params ---
SAMPLE_HZ = 50.0
DT = 1.0 / SAMPLE_HZ
EMA_ALPHA1 = 0.25
EMA_ALPHA2 = 0.25

# start thresholds
YAW_RATE_START   = 120.0   # deg/s
YAW_ACC_START    = 900.0   # deg/s^2
PITCH_RATE_START = 120.0
PITCH_ACC_START  = 900.0
# completion thresholds
RATE_END = 25.0
GESTURE_MIN_MS = 60
GESTURE_MAX_MS = 450
COOLDOWN_MS    = 300

# axis mapping (flat board): gz = yaw (left/right), gx = pitch (up/down)
YAW_SIGN   = +1.0
PITCH_SIGN = +1.0

# ----- your matrix-display hooks (replace prints with real calls) -----
def next_game():        print("next game", flush=True)
def prev_game():        print("previous game", flush=True)
def next_sport():       print("next sport", flush=True)
def prev_sport():       print("previous sport", flush=True)
def audio_up():         print("audio up", flush=True)
def audio_down():       print("audio down", flush=True)
def brightness_up():    print("brightness up", flush=True)
def brightness_down():  print("brightness down", flush=True)

# ----- helpers -----
def ema(prev, x, a, have_prev): return (a*x + (1.0-a)*prev) if have_prev else x

class GFSM:
    NONE=0; YAW=1; PITCH=2
    def __init__(self):
        self.active=self.NONE
        self.dir=0            # -1 or +1
        self.tstart=0
        self.lastCompleteMs=0

def filter_dev(device, adv):
    name = (device.name or "").lower()
    by_name = any(h in name for h in DEVICE_HINTS)
    by_uuid = bool(adv and adv.service_uuids and str(NUS_SERVICE) in [s.lower() for s in adv.service_uuids])
    return by_name or by_uuid

async def main():
    print("Scanning...")
    dev = await BleakScanner.find_device_by_filter(filter_dev, timeout=12.0)
    if not dev:
        print("Device not found."); return

    print(f"Connecting to: {dev.name} [{dev.address}]")
    client = BleakClient(dev)
    await client.connect()
    if not client.is_connected:
        print("Failed to connect."); return
    print("Connected. Subscribing...")

    # ---- mutable state container (Option A) ----
    st = SimpleNamespace(
        # filtering state
        r1x=0.0, r1y=0.0, r1z=0.0,
        r2x=0.0, r2y=0.0, r2z=0.0,
        prev_r2x=0.0, prev_r2y=0.0, prev_r2z=0.0,
        have_prev=False,
        # mode from button (ESP32 sends MODE lines): 'sports'|'audio'|'brightness'
        mode="sports",
        # gesture FSM
        fsm=GFSM()
    )

    # announce starting state for your logs/UI
    print("BUTTON: mode=sports")  # shown in PC terminal at start

    # ---- FSM utilities ----
    def reset_fsm():
        st.fsm.active = GFSM.NONE
        st.fsm.dir = 0
        st.fsm.tstart = 0

    def try_arm(yawRate,yawAcc,pitchRate,pitchAcc, tms):
        if tms - st.fsm.lastCompleteMs < COOLDOWN_MS:
            return
        yawTrig = (abs(yawRate)>=YAW_RATE_START) and (abs(yawAcc)>=YAW_ACC_START)
        pitTrig = (abs(pitchRate)>=PITCH_RATE_START) and (abs(pitchAcc)>=PITCH_ACC_START)
        if not yawTrig and not pitTrig:
            return
        if yawTrig and (not pitTrig or abs(yawAcc) >= abs(pitchAcc)):
            st.fsm.active = GFSM.YAW
            st.fsm.dir = 1 if yawAcc>0 else -1   # + = right, - = left
        else:
            st.fsm.active = GFSM.PITCH
            st.fsm.dir = 1 if pitchAcc>0 else -1 # + = up,    - = down
        st.fsm.tstart = tms

    def update_active(yawRate,yawAcc,pitchRate,pitchAcc, tms):
        if st.fsm.active==GFSM.NONE:
            return
        dur = tms - st.fsm.tstart
        if dur > GESTURE_MAX_MS:
            reset_fsm(); return

        if st.fsm.active==GFSM.YAW:
            if abs(yawRate) < RATE_END and dur >= GESTURE_MIN_MS and st.mode == "sports":
                # left/right are always previous/next game
                (prev_game() if st.fsm.dir>0 else next_game())
                st.fsm.lastCompleteMs = tms
                reset_fsm()
        else:
            if abs(pitchRate) < RATE_END and dur >= GESTURE_MIN_MS:
                # up/down depend on mode
                if st.mode == "audio":
                    (audio_up() if st.fsm.dir>0 else audio_down())
                elif st.mode == "brightness":
                    (brightness_up() if st.fsm.dir>0 else brightness_down())
                else:  # sports
                    (next_sport() if st.fsm.dir>0 else prev_sport())
                st.fsm.lastCompleteMs = tms
                reset_fsm()

    # ---- BLE notification handler ----
    def on_notify(_, data: bytearray):
        try:
            line = data.decode("utf-8").strip()
        except:
            return

        # button press from ESP32 arrives as MODE,<mode>
        if line.startswith("MODE,"):
            m = line.split(",",1)[1].strip().lower()
            if m in ("sports","audio","brightness"):
                st.mode = m
                print(f"BUTTON: mode={st.mode}")  # show the press in PC terminal
            return

        # RAW,<ms>,<gx>,<gy>,<gz>,<ax>,<ay>,<az>,<btn>,<mode>
        if not line.startswith("RAW,"):
            return
        parts = line.split(",")
        if len(parts) < 10:
            return

        try:
            ms = int(parts[1])
            gx = float(parts[2]); gy = float(parts[3]); gz = float(parts[4])
        except:
            return

        # filter: two-stage EMA on gyro (deg/s)
        st.r1x = ema(st.r1x, gx, EMA_ALPHA1, st.have_prev)
        st.r1y = ema(st.r1y, gy, EMA_ALPHA1, st.have_prev)
        st.r1z = ema(st.r1z, gz, EMA_ALPHA1, st.have_prev)

        st.r2x = ema(st.r2x, st.r1x, EMA_ALPHA2, st.have_prev)
        st.r2y = ema(st.r2y, st.r1y, EMA_ALPHA2, st.have_prev)
        st.r2z = ema(st.r2z, st.r1z, EMA_ALPHA2, st.have_prev)

        if st.have_prev:
            ax_dps2 = (st.r2x - st.prev_r2x) / DT
            ay_dps2 = (st.r2y - st.prev_r2y) / DT
            az_dps2 = (st.r2z - st.prev_r2z) / DT
        else:
            ax_dps2 = ay_dps2 = az_dps2 = 0.0
            st.have_prev = True

        st.prev_r2x, st.prev_r2y, st.prev_r2z = st.r2x, st.r2y, st.r2z

        # axis pick + sign flips
        yawRate   = YAW_SIGN   * st.r2z
        yawAcc    = YAW_SIGN   * az_dps2
        pitchRate = PITCH_SIGN * st.r2x
        pitchAcc  = PITCH_SIGN * ax_dps2

        # FSM
        if st.fsm.active==GFSM.NONE:
            try_arm(yawRate,yawAcc,pitchRate,pitchAcc, ms)
        else:
            update_active(yawRate,yawAcc,pitchRate,pitchAcc, ms)

    await client.start_notify(str(NUS_TX), on_notify)
    print("Listening... Ctrl+C to quit.")
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        if client.is_connected:
            await client.disconnect()
        print("Disconnected.")

if __name__ == "__main__":
    asyncio.run(main())
