#!/usr/bin/env bash
# Startet das Lab-Overlay-Backend im Hintergrund und danach OBS Studio.
# Beim Schließen von OBS wird das Backend automatisch wieder gestoppt.

set -u

BACKEND="$HOME/OBS/backend/server.py"
LOG="$HOME/OBS/backend.log"

# Falls noch eine alte Backend-Instanz läuft, vorher beenden
pkill -f "python3.*server\.py" 2>/dev/null
sleep 0.5

# Backend im Hintergrund starten, stdout/stderr ins Log
echo "→ Starte Backend ($BACKEND)"
python3 "$BACKEND" >"$LOG" 2>&1 &
BACKEND_PID=$!

# Beim Beenden des Scripts (z.B. nach OBS-Schließen) das Backend killen
cleanup() {
    echo
    echo "→ Stoppe Backend (PID $BACKEND_PID)"
    kill "$BACKEND_PID" 2>/dev/null
    wait "$BACKEND_PID" 2>/dev/null
}
trap cleanup EXIT INT TERM

# Kurz warten, damit das Backend die Ports öffnen kann
sleep 2

# Backend-Status quick-check
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "✗ Backend ist nicht gestartet — Log:"
    tail -20 "$LOG"
    exit 1
fi
echo "✓ Backend läuft (PID $BACKEND_PID), Log: $LOG"

# OBS starten (blockt, bis OBS geschlossen wird)
echo "→ Starte OBS Studio"
obs
