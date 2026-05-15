// ============================================================
//  Overlay-Konfiguration
//
//  Hier alles, was am Aussehen geändert werden kann.
//  Nach dem Speichern in OBS die Browser-Source aktualisieren
//  (Rechtsklick → Eigenschaften → "Cache der aktuellen Seite
//  aktualisieren" → OK).
// ============================================================

window.OVERLAY_CONFIG = {

  // ---------- Schrift ----------
  fonts: {
    // Mehrere Fonts mit Komma — der erste verfügbare wird genutzt.
    // OBS-Browser-Source nutzt System-Fonts.
    family: '"Roboto Mono", "Consolas", "Menlo", "Courier New", monospace',

    valueSize:      "30px",  // große Mess-Zahlen (Volt/Ampere)
    modeSize:       "30px",  // CV/CC links bei BB3 (Stack) — gleich wie Werte
    modeSingleSize: "30px",  // DMM-/KEL-Modus (einzeln) — gleich wie Werte
    labelSize:      "30px",  // Geräte-Bezeichnung unten — gleich wie Werte
    unitSize:       "0.85em", // Einheit ("V","A") relativ zum Wert

    valueWeight:    700,     // 100..900 — fett für Werte
    modeWeight:     700,
    labelWeight:    700,
    labelLetter:    "1px",   // Zeichenabstand bei Label
  },

  // ---------- Farben ----------
  colors: {
    background:      "rgba(26, 26, 26, 0.85)",  // Hauptbalken — 15% transparent
    graphBackground: "rgba(0, 0, 0, 0.2)",     // Graph-Boxen — 60% transparent
    graphBorder:     "#2a2a2a",   // dünner Rahmen um die Graphen
    graphGrid:       "rgba(255,255,255,0.08)",

    voltage: "#00d3ff",   // V-Werte und V-Linie — helles Türkis (gegen blauen Hintergrund)
    current: "#e4b700",   // A-Werte und A-Linie (gedecktes Gold-Gelb)
    mode:    "#64ff00",   // Mode-Label (helles Grün)
    label:   "#00d3ff",   // Geräte-Name — gleiches Türkis wie V-Werte
    subtext: "#6a7a7c",   // DMM-Zweitzeile ("—")

    offlineLabel: "#cc6666",  // Geräte-Name wird rot bei Ausfall
  },

  // ---------- Graphen ----------
  graph: {
    height:         "65px",  // Höhe der Mini-Graph-Boxen
    lineWidth:      2,       // Strichstärke der Verläufe
    millisPerPixel: 50,      // Scroll-Geschwindigkeit (kleiner = schneller; pro Gerät überschreibbar)
  },

  // Pro Gerät anpassbar:
  //   minValue / maxValue: feste Y-Skala (V). Weglassen für Auto-Skalierung.
  //   millisPerPixel:      Zeit pro Pixel (überschreibt graph.millisPerPixel).
  charts: {
    dmm:  { minValue: 0, maxValue: 12, millisPerPixel: 165 },  // 30 s @ 182 px; Y-Skala wird live aus Mode/Range gesetzt
    bb3a: { minValue: 0, maxValue: 20, millisPerPixel: 119 },  // 0–20 V, 30 s @ 252 px
    bb3b: { minValue: 0, maxValue:  6, millisPerPixel: 119 },  // 0–6 V, 30 s @ 252 px
    kel:  { millisPerPixel: 1190 },  // 5 min (= 300 s) @ 252 px
  },

  // ---------- Layout ----------
  layout: {
    panelGap:     "6px",       // Abstand zwischen den 4 Panels
    panelPadX:    "6px",       // horizontales Padding innerhalb Panel
    modeColWidth:  "136px",    // feste Breite Spalte 1 (Mode-Label)
    valueColWidth: "177px",    // feste Breite Spalte 2 (Wert + Einheit)
    columnGap:     "14px",     // Abstand mode↔value (col 1↔2)
    minWidth:      "1980px",   // Mindestbreite des Balkens
    borderRadius:  "4px",      // Eck-Rundung
  },

  // ---------- Backend ----------
  backend: {
    // ws-URL überschreiben (Default: gleicher Host wie HTML, Port 7891).
    // Beispiel für Remote: "ws://192.168.10.6:7891"
    wsUrl: null,
  },

};
