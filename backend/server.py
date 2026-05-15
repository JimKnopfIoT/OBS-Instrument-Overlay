#!/usr/bin/env python3
"""OBS Overlay Backend.

Pollt Lab-Instrumente parallel und broadcastet die Werte per WebSocket
an das HTML-Overlay (../overlay/overlay.html).

  DMM7510      192.168.10.45:5025   TCP/SCPI
  BB3 Ch1      192.168.10.78:5025   TCP/SCPI  → Display "bb3a"
  BB3 Ch2      192.168.10.78:5025   TCP/SCPI  → intern "bb3b_raw" (Telemetrie)
  KEL103       192.168.10.83:18190  UDP  (lokaler Bind auf 18190 nötig!)
  Fnirsi C1    BLE 98:DA:B0:02:34:5E         → Display "bb3b" (USB-Output)
"""
import asyncio
import http.server
import json
import logging
import os
import socket
import struct
import sys
import threading
import time
from functools import partial

import websockets

try:
    from bleak import BleakClient
    _have_bleak = True
except ImportError:
    _have_bleak = False

# Spammy WebSocket-Handshake-Tracebacks unterdrücken (Port-Scans, Health-Checks)
logging.getLogger("websockets.server").setLevel(logging.CRITICAL)
logging.getLogger("websockets.asyncio.server").setLevel(logging.CRITICAL)

# ---------- Konfiguration ----------
# Alle Geräte-Adressen, Ports, Polling-Raten leben in backend/config.py.
from config import (
    DMM, BB3, KEL,
    C1_MAC, C1_NOTIFY_U, C1_WRITE_U,
    WS_HOST, WS_PORT, HTTP_HOST, HTTP_PORT,
    DMM_PERIOD, BB3_PERIOD, KEL_PERIOD, BROADCAST_PERIOD,
    RECONNECT_BACKOFF, TCP_BUSY_BACKOFF, C1_RECONNECT_BACKOFF,
)

OVERLAY_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "overlay"))

# DMM7510 :SENS:FUNC? Antwort → (UI-Label, Einheit)
DMM_MODE_MAP = {
    "VOLT:DC":      ("V DC",   "V"),
    "VOLT:AC":      ("V AC",   "V"),
    "CURR:DC":      ("A DC",   "A"),
    "CURR:AC":      ("A AC",   "A"),
    "RES":          ("Ω 2W",   "Ω"),
    "FRES":         ("Ω 4W",   "Ω"),
    "CAP":          ("Cap",    "F"),
    "DIOD":         ("Diode",  "V"),
    "FREQ:VOLT":    ("Freq",   "Hz"),
    "PER:VOLT":     ("Period", "s"),
    "TEMP":         ("Temp",   "°C"),
    "VOLT:DC:RAT":  ("Ratio",  ""),
}

# Per-Funktion: passender Range-Query. Werte ohne sinnvolle Range (Diode, Freq,
# Period, Temp, Ratio) bleiben raus → Frontend fällt dann auf Wert-Magnitude zurück.
DMM_RANGE_CMD = {
    "VOLT:DC":  b":SENS:VOLT:DC:RANG?\n",
    "VOLT:AC":  b":SENS:VOLT:AC:RANG?\n",
    "CURR:DC":  b":SENS:CURR:DC:RANG?\n",
    "CURR:AC":  b":SENS:CURR:AC:RANG?\n",
    "RES":      b":SENS:RES:RANG?\n",
    "FRES":     b":SENS:FRES:RANG?\n",
    "CAP":      b":SENS:CAP:RANG?\n",
}

# ---------- Gemeinsamer State ----------
STATE = {
    "ts": 0,
    "devices": {
        "dmm":  {"ok": False, "mode": "—", "value": None, "unit": "", "range": None},
        "bb3a":     {"ok": False, "mode": "—", "voltage": None, "current": None, "output": None},
        "bb3b":     {"ok": False, "mode": "—", "voltage": None, "current": None, "output": None,
                     "dp": None, "dn": None, "protocol": "—"},
        "bb3b_raw": {"ok": False, "mode": "—", "voltage": None, "current": None, "output": None},
        "kel":      {"ok": False, "mode": "—", "voltage": None, "current": None, "output": None},
    },
}
CLIENTS: set = set()


def log(tag, msg):
    print(f"[{tag}] {msg}", file=sys.stderr, flush=True)


# ---------- DMM7510 ----------
async def dmm_poll():
    backoff = RECONNECT_BACKOFF
    while True:
        writer = None
        try:
            log("dmm", f"connect {DMM[0]}:{DMM[1]}")
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(*DMM), timeout=5.0
            )
            writer.write(b"*lang scpi;FORMat:ASCii:PRECision MAXimum\n")
            await writer.drain()
            await asyncio.sleep(0.2)
            log("dmm", "connected")
            backoff = RECONNECT_BACKOFF
            while True:
                writer.write(b":SENS:FUNC?\n")
                await writer.drain()
                func_raw = (await asyncio.wait_for(reader.readline(), 2.0)).decode().strip().strip('"')

                # Sanity-Check: Mode-Strings sind Wörter ("VOLT:DC", "DIOD", …),
                # niemals numerisch. Wenn func_raw mit Ziffer oder Vorzeichen
                # beginnt, ist die TCP-Antwortreihenfolge verrutscht. Buffer
                # leeren und nächste Runde sauber neu starten.
                if not func_raw or func_raw[0] in "0123456789+-.":
                    log("dmm", f"SCPI-Desync, verwerfe: {func_raw[:30]!r}")
                    try:
                        await asyncio.wait_for(reader.readline(), 0.3)
                    except asyncio.TimeoutError:
                        pass
                    await asyncio.sleep(0.3)
                    continue

                writer.write(b':READ? "defbuffer1",READ\n')
                await writer.drain()
                val_raw = (await asyncio.wait_for(reader.readline(), 2.0)).decode().strip()

                # Aktuelle Range nachfragen, sofern die Funktion eine kennt. Wird der
                # Wert ans Frontend gegeben, kann es die Anzeige-Einheit (mV/V/µV
                # bzw. mA/A …) und die Y-Skala an die Geräte-Range koppeln — so
                # springt nichts mehr beim Wertewechsel im selben Range.
                rng = None
                range_cmd = DMM_RANGE_CMD.get(func_raw)
                if range_cmd is not None:
                    writer.write(range_cmd)
                    await writer.drain()
                    range_raw = (await asyncio.wait_for(reader.readline(), 2.0)).decode().strip()
                    try:
                        rng = float(range_raw)
                    except (ValueError, TypeError):
                        rng = None

                label, unit = DMM_MODE_MAP.get(func_raw, (func_raw or "—", ""))
                try:
                    value = float(val_raw)
                except (ValueError, TypeError):
                    value = None
                STATE["devices"]["dmm"] = {
                    "ok": True, "mode": label, "value": value, "unit": unit, "range": rng
                }
                await asyncio.sleep(DMM_PERIOD)
        except (asyncio.TimeoutError, OSError, ConnectionError) as e:
            STATE["devices"]["dmm"]["ok"] = False
            # Bei "Connection refused/timeout" hält das Gerät meist noch die alte TCP-Session
            backoff = min(backoff * 1.5, TCP_BUSY_BACKOFF * 2) if "Connect call failed" in str(e) or isinstance(e, (asyncio.TimeoutError, ConnectionRefusedError)) else RECONNECT_BACKOFF
            log("dmm", f"error: {type(e).__name__}: {e} — retry in {backoff:.1f}s")
            if writer is not None:
                try:
                    writer.close(); await writer.wait_closed()
                except Exception:
                    pass
            await asyncio.sleep(backoff)
        except Exception as e:
            STATE["devices"]["dmm"]["ok"] = False
            log("dmm", f"unexpected: {type(e).__name__}: {e}")
            if writer is not None:
                try:
                    writer.close(); await writer.wait_closed()
                except Exception:
                    pass
            await asyncio.sleep(RECONNECT_BACKOFF)


# ---------- BB3 ----------
async def bb3_poll():
    backoff = RECONNECT_BACKOFF
    while True:
        writer = None
        try:
            log("bb3", f"connect {BB3[0]}:{BB3[1]}")
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(*BB3), timeout=5.0
            )
            log("bb3", "connected")
            backoff = RECONNECT_BACKOFF
            while True:
                # CH1 → "bb3a" wird im Overlay angezeigt.
                # CH2 → "bb3b_raw" ist interne Telemetrie; das angezeigte "bb3b"-Panel
                # wird vom Fnirsi C1 (BLE) befüllt (= echter USB-Output hinter PD-Modul).
                for key, ch in (("bb3a", "CH1"), ("bb3b_raw", "CH2")):
                    writer.write(f"MEAS:VOLT? {ch}\n".encode())
                    await writer.drain()
                    v = float((await asyncio.wait_for(reader.readline(), 2.0)).decode().strip())

                    writer.write(f"MEAS:CURR? {ch}\n".encode())
                    await writer.drain()
                    a = float((await asyncio.wait_for(reader.readline(), 2.0)).decode().strip())

                    writer.write(f"OUTP:MODE? {ch}\n".encode())
                    await writer.drain()
                    mode = (await asyncio.wait_for(reader.readline(), 2.0)).decode().strip().strip('"')

                    writer.write(f"OUTP? {ch}\n".encode())
                    await writer.drain()
                    outp_raw = (await asyncio.wait_for(reader.readline(), 2.0)).decode().strip()
                    output_on = outp_raw == "1"

                    STATE["devices"][key] = {
                        "ok": True, "mode": mode, "voltage": v, "current": a, "output": output_on
                    }
                await asyncio.sleep(BB3_PERIOD)
        except (asyncio.TimeoutError, OSError, ConnectionError) as e:
            STATE["devices"]["bb3a"]["ok"] = False
            STATE["devices"]["bb3b_raw"]["ok"] = False
            backoff = min(backoff * 1.5, TCP_BUSY_BACKOFF * 2) if "Connect call failed" in str(e) or isinstance(e, (asyncio.TimeoutError, ConnectionRefusedError)) else RECONNECT_BACKOFF
            log("bb3", f"error: {type(e).__name__}: {e} — retry in {backoff:.1f}s")
            if writer is not None:
                try:
                    writer.close(); await writer.wait_closed()
                except Exception:
                    pass
            await asyncio.sleep(backoff)
        except Exception as e:
            STATE["devices"]["bb3a"]["ok"] = False
            STATE["devices"]["bb3b_raw"]["ok"] = False
            log("bb3", f"unexpected: {type(e).__name__}: {e}")
            if writer is not None:
                try:
                    writer.close(); await writer.wait_closed()
                except Exception:
                    pass
            await asyncio.sleep(RECONNECT_BACKOFF)


# ---------- Fnirsi C1 USB-Tester (BLE) ----------
# Protokoll von blakelton/FNIRSI-FNB-Web-Server (Android-App-Reverse-Engineering).
# Init: Notifications enablen → GET_INFO (0x81) → GET_STATUS (0x85) → START (0x82).
# Notifications enthalten verkettete Sub-Pakete [0xAA][CMD][LEN][DATA...][CRC8].
# Hauptdaten in CMD=0x04: V/I/P als int32-LE × 1/10000.
C1_CMD_GET_INFO   = 0x81
C1_CMD_START      = 0x82
C1_CMD_STOP       = 0x84
C1_CMD_GET_STATUS = 0x85


def _crc16_xmodem(data):
    crc = 0
    for byte in data:
        for bit in range(8):
            x = ((byte >> (7 - bit)) & 1) == 1
            m = ((crc >> 15) & 1) == 1
            crc = (crc << 1) & 0xFFFF
            if x ^ m:
                crc ^= 0x1021
    return crc & 0xFFFF


def _c1_build_cmd(cmd, payload=b""):
    pkt = bytes([0xAA, cmd, len(payload)]) + bytes(payload)
    return pkt + bytes([_crc16_xmodem(pkt) & 0xFF])


def _c1_protocol(voltage, dp, dn):
    """Heuristische Protokoll-Erkennung aus V und D+/D-.
    Apple-Toleranzen weiter gefasst als in blakelton/FNIRSI-FNB-Web-Server
    (das C1-Display erkennt Apple 2.4A auch bei D+/D- ≈ 2.45 V, also unterhalb
    der dort dokumentierten 2.5–2.9-V-Range).
    """
    if voltage is None or dp is None or dn is None:
        return "—"
    # USB-PD nach Bus-Spannung (Apple/QC haben 5 V)
    if 8.5  <= voltage <=  9.5:    return "PD 9V"
    if 11.5 <= voltage <= 12.5:    return "PD 12V"
    if 14.5 <= voltage <= 15.5:    return "PD 15V"
    if 19.5 <= voltage <= 20.5:    return "PD 20V"
    # Apple 2.4A: D+ ≈ D- ≈ 2.7 V (Toleranz weiter: 2.3–3.0)
    if 2.3 <= dp <= 3.0 and 2.3 <= dn <= 3.0:
        return "Apple 2.4A"
    # Apple 2.1A: einer ≈ 2.7 V, der andere ≈ 2.0 V
    if (2.3 <= dp <= 3.0 and 1.7 <= dn <= 2.2) or (1.7 <= dp <= 2.2 and 2.3 <= dn <= 3.0):
        return "Apple 2.1A"
    # Apple 1A: D+ ≈ D- ≈ 2.0 V
    if 1.7 <= dp <= 2.2 and 1.7 <= dn <= 2.2:
        return "Apple 1A"
    # Qualcomm QuickCharge 2.0 (5/9/12 V via D+/D--Spannungsmuster)
    if 0.25 <= dp <= 0.45 and 0.25 <= dn <= 0.45:   return "QC 5V"
    if 0.50 <= dp <= 0.70 and 0.25 <= dn <= 0.45:   return "QC 9V"
    if 0.50 <= dp <= 0.70 and 0.50 <= dn <= 0.70:   return "QC 12V"
    # DCP — D+ ≈ D- kurzgeschlossen (~2 V)
    if abs(dp - dn) < 0.15 and 1.4 <= dp <= 2.3:    return "DCP"
    # Fallback: Standard Downstream Port 5 V
    if 4.5 <= voltage <= 5.5:                       return "SDP 5V"
    return "—"


def _c1_parse_notification(data, state):
    """Walke konkatenierte Sub-Pakete und aktualisiere `state` in-place.

    CMD=0x04 → V/I/P (int32 LE × 1/10000)
    CMD=0x06 → D- (uint16 LE), D+ (uint16 LE), beide × 1/1000
    """
    i = 0
    while i < len(data):
        if data[i] != 0xAA or i + 2 >= len(data):
            i += 1
            continue
        cmd = data[i + 1]
        length = data[i + 2]
        if i + 3 + length > len(data):
            break
        body = data[i + 3 : i + 3 + length]
        if cmd == 0x04 and len(body) >= 12:
            v, c, _p = struct.unpack_from("<iii", body, 0)
            state["voltage"] = v / 10000.0
            state["current"] = c / 10000.0
        elif cmd == 0x06 and len(body) >= 4:
            dn, dp = struct.unpack_from("<HH", body, 0)
            state["dn"] = dn / 1000.0
            state["dp"] = dp / 1000.0
        # Protokoll neu raten — D+/D- ändert sich i.d.R. nur bei Re-Negotiation,
        # aber so ist der State immer konsistent
        state["protocol"] = _c1_protocol(state.get("voltage"), state.get("dp"), state.get("dn"))
        i += 3 + length + 1


async def _c1_force_disconnect():
    """Stale BLE-Session via bluetoothctl auflösen — der C1 hält seinen
    vorherigen Connect-State sonst hartnäckig fest, und ein frischer
    BleakClient.connect() läuft dann in UNLIKELY_ERROR oder Timeout."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "bluetoothctl", "disconnect", C1_MAC,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=3.0)
    except Exception:
        pass


async def c1_poll():
    if not _have_bleak:
        log("c1", "bleak fehlt — Poller deaktiviert. `pip install bleak`")
        return
    backoff = C1_RECONNECT_BACKOFF
    while True:
        client = None
        try:
            await _c1_force_disconnect()  # alte Session aufräumen
            await asyncio.sleep(0.5)
            log("c1", f"connect {C1_MAC}")
            client = BleakClient(C1_MAC, timeout=15.0)
            await client.connect()
            log("c1", "connected")
            backoff = C1_RECONNECT_BACKOFF
            state = STATE["devices"]["bb3b"]

            def cb(_, data):
                _c1_parse_notification(bytes(data), state)
                state["ok"] = True
                state["mode"] = "USB"
                state["output"] = True

            await client.start_notify(C1_NOTIFY_U, cb)
            await asyncio.sleep(0.5)
            await client.write_gatt_char(C1_WRITE_U, _c1_build_cmd(C1_CMD_GET_INFO))
            await asyncio.sleep(1.0)
            await client.write_gatt_char(C1_WRITE_U, _c1_build_cmd(C1_CMD_GET_STATUS))
            await asyncio.sleep(0.3)
            await client.write_gatt_char(C1_WRITE_U, _c1_build_cmd(C1_CMD_START))

            while client.is_connected:
                await asyncio.sleep(1.0)
            log("c1", "disconnected")
        except Exception as e:
            STATE["devices"]["bb3b"]["ok"] = False
            log("c1", f"error: {type(e).__name__}: {e} — retry in {backoff:.1f}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.5, 30.0)
        finally:
            # Sauber abmelden — STOP + disconnect — sodass der C1 nicht in
            # einer Zombie-Session zurückbleibt.
            if client is not None and client.is_connected:
                try:
                    await client.write_gatt_char(C1_WRITE_U, _c1_build_cmd(C1_CMD_STOP))
                    await asyncio.sleep(0.1)
                except Exception:
                    pass
                try:
                    await client.disconnect()
                except Exception:
                    pass


# ---------- KEL103 (UDP, sync im Executor) ----------
def _kel_query(cmd, timeout=0.8, retries=2):
    """Frischer Socket mit lokalem Bind auf 18190. Bis zu (1+retries) Versuche."""
    last_err = None
    for _ in range(1 + retries):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("0.0.0.0", KEL[1]))
        s.settimeout(timeout)
        try:
            s.sendto((cmd + "\n").encode(), KEL)
            data, _ = s.recvfrom(4096)
            return data.decode(errors="replace").strip()
        except socket.timeout as e:
            last_err = e
        finally:
            s.close()
    raise last_err if last_err else TimeoutError(f"KEL query failed: {cmd}")


def _kel_parse_num(s: str) -> float:
    """'5.000V' → 5.0, '-1.23e-04A' → -1.23e-04"""
    i = 0
    while i < len(s) and (s[i].isdigit() or s[i] in ".-+eE"):
        i += 1
    return float(s[:i]) if i else 0.0


def _kel_read_all() -> dict:
    v = _kel_parse_num(_kel_query(":MEAS:VOLT?"))
    a = _kel_parse_num(_kel_query(":MEAS:CURR?"))
    mode = _kel_query(":FUNC?")
    onoff = _kel_query(":INP?")
    return {"ok": True, "mode": mode, "voltage": v, "current": a, "output": onoff}


async def kel_poll():
    loop = asyncio.get_event_loop()
    while True:
        try:
            data = await loop.run_in_executor(None, _kel_read_all)
            STATE["devices"]["kel"] = data
        except Exception as e:
            STATE["devices"]["kel"]["ok"] = False
            log("kel", f"error: {type(e).__name__}: {e}")
            await asyncio.sleep(RECONNECT_BACKOFF)
            continue
        await asyncio.sleep(KEL_PERIOD)


# ---------- WebSocket ----------
async def ws_handler(ws):
    CLIENTS.add(ws)
    log("ws", f"client connected ({len(CLIENTS)} total)")
    try:
        await ws.send(json.dumps(STATE))
        async for _ in ws:
            pass
    finally:
        CLIENTS.discard(ws)
        log("ws", f"client disconnected ({len(CLIENTS)} left)")


async def broadcaster():
    while True:
        await asyncio.sleep(BROADCAST_PERIOD)
        if not CLIENTS:
            continue
        STATE["ts"] = int(time.time() * 1000)
        msg = json.dumps(STATE)
        await asyncio.gather(
            *(ws.send(msg) for ws in list(CLIENTS)),
            return_exceptions=True,
        )


class QuietHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """Statischer File-Server mit gedrosseltem Logging, no-cache und HTML-Cache-Buster."""

    def log_message(self, format, *args):
        # OBS pollt häufig — Output sonst geflutet
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        super().end_headers()

    def do_GET(self):
        # overlay.html bekommt bei jedem Request einen frischen ?v=TIMESTAMP
        # in die Script/CSS-URLs gespritzt — damit kann OBS-CEF nicht mehr cachen.
        clean_path = self.path.split("?")[0]
        if clean_path in ("/overlay.html", "/"):
            html_path = os.path.join(OVERLAY_DIR, "overlay.html")
            try:
                with open(html_path, "rb") as f:
                    content = f.read()
                version = str(int(time.time() * 1000)).encode()
                content = content.replace(b"{{VERSION}}", version)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            except Exception as e:
                log("http", f"overlay.html error: {e}")
        super().do_GET()


def start_http_server():
    handler = partial(QuietHTTPHandler, directory=OVERLAY_DIR)
    httpd = http.server.ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), handler)
    log("http", f"serving {OVERLAY_DIR} on http://{HTTP_HOST}:{HTTP_PORT}")
    httpd.serve_forever()


async def main():
    threading.Thread(target=start_http_server, daemon=True).start()
    log("ws", f"serving on ws://{WS_HOST}:{WS_PORT}")
    async with websockets.serve(ws_handler, WS_HOST, WS_PORT):
        await asyncio.gather(
            dmm_poll(),
            bb3_poll(),
            kel_poll(),
            c1_poll(),
            broadcaster(),
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("main", "shutdown")
