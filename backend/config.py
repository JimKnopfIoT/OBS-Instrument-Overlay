"""Backend-Konfiguration für das OBS-Overlay.

Hier alle Geräte-Adressen, Ports und Polling-Raten an einer Stelle. Pendant zu
`overlay/config.js` auf der Frontend-Seite.

Nach dem Editieren das Backend (server.py) neu starten; die Datei wird beim
Modul-Import gelesen.
"""

# ---------- Lab-Geräte (LAN) ----------
DMM = ("192.168.10.45", 5025)      # Keithley DMM7510  (TCP/SCPI)
BB3 = ("192.168.10.78", 5025)      # Envox BB3 Ch1 + Ch2 (TCP/SCPI, gleiche Verbindung)
KEL = ("192.168.10.83", 18190)     # Korad KEL103       (UDP, lokaler Bind auf 18190 nötig)

# ---------- USB-Tester (BLE) ----------
# Im Overlay-Panel "USB" angezeigt — echter USB-Output hinter dem PD-Modul.
# Aktuell aktiv: Fnirsi C1. Bei Wechsel auf FNB-C2 nur die MAC tauschen
# (Protokoll ist identisch: FNB48-Familie inklusive C1/FNB-C2).
C1_MAC      = "98:DA:B0:02:34:5E"
C1_NOTIFY_U = "0000ffe4-0000-1000-8000-00805f9b34fb"
C1_WRITE_U  = "0000ffe9-0000-1000-8000-00805f9b34fb"

# ---------- Netzwerk-Server ----------
WS_HOST   = "0.0.0.0"
WS_PORT   = 7891
HTTP_HOST = "0.0.0.0"
HTTP_PORT = 7890

# ---------- Polling-Raten ----------
DMM_PERIOD       = 0.25   # 4 Hz
BB3_PERIOD       = 0.25   # 4 Hz (für beide BB3-Kanäle zusammen)
KEL_PERIOD       = 0.50   # 2 Hz (UDP-Latenz)
BROADCAST_PERIOD = 0.20   # 5 Hz an Frontend

# ---------- Reconnect-Backoff ----------
RECONNECT_BACKOFF    = 2.0
TCP_BUSY_BACKOFF     = 8.0   # länger, wenn das Gerät die alte TCP-Session noch hält
C1_RECONNECT_BACKOFF = 5.0
