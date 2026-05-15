(() => {
  // ---- Konfig aus config.js laden + auf CSS-Variablen mappen ----
  const C = (window.OVERLAY_CONFIG || {});
  const F = C.fonts || {};
  const COL = C.colors || {};
  const G = C.graph || {};
  const L = C.layout || {};

  function setVar(name, value) {
    if (value !== undefined && value !== null) {
      document.documentElement.style.setProperty(name, value);
    }
  }
  setVar("--bg",                COL.background);
  setVar("--bg-screen",         COL.graphBackground);
  setVar("--col-screen-border", COL.graphBorder);
  setVar("--col-v",             COL.voltage);
  setVar("--col-a",             COL.current);
  setVar("--col-mode",          COL.mode);
  setVar("--col-label",         COL.label);
  setVar("--col-sub",           COL.subtext);
  setVar("--col-offline",       COL.offlineLabel);
  setVar("--font-family",       F.family);
  setVar("--fs-value",          F.valueSize);
  setVar("--fs-mode",           F.modeSize);
  setVar("--fs-mode-single",    F.modeSingleSize);
  setVar("--fs-label",          F.labelSize);
  setVar("--fs-unit",           F.unitSize);
  setVar("--fw-value",          F.valueWeight);
  setVar("--fw-mode",           F.modeWeight);
  setVar("--fw-label",          F.labelWeight);
  setVar("--letter-label",      F.labelLetter);
  setVar("--graph-height",      G.height);
  setVar("--panel-gap",         L.panelGap);
  setVar("--panel-pad-x",       L.panelPadX);
  setVar("--mode-col-width",    L.modeColWidth);
  setVar("--value-col-width",   L.valueColWidth);
  setVar("--col-gap",           L.columnGap);
  setVar("--min-width",         L.minWidth);
  setVar("--border-radius",     L.borderRadius);

  const COL_V = COL.voltage         || "#33ccdd";
  const COL_A = COL.current         || "#d8c640";
  const COL_GRID = COL.graphGrid    || "rgba(255,255,255,0.08)";
  const COL_GRAPH_BG = COL.graphBackground || "#000";
  const LINE_WIDTH = G.lineWidth ?? 2;
  const MS_PER_PIXEL = G.millisPerPixel ?? 50;
  const CHART_SCALE = C.charts || {};

  // WS-URL: config.backend.wsUrl > ?ws=… > automatik
  const WS_URL = (() => {
    if (C.backend && C.backend.wsUrl) return C.backend.wsUrl;
    const override = new URLSearchParams(location.search).get("ws");
    if (override) return override;
    if (location.protocol === "file:") return "ws://127.0.0.1:7891";
    const host = location.hostname || "127.0.0.1";
    return `ws://${host}:7891`;
  })();

  // DMM-Format: immer 7 Nachkommastellen, Einheit wird an die aktuelle GERÄTE-Range
  // gekoppelt (sofern der Backend sie liefert), nicht an den aktuellen Messwert.
  // Dadurch wechselt die Anzeige nicht mehr zwischen mV/V oder µA/mA/A, wenn sich
  // nur der Messwert ändert — sie folgt strikt der DMM-Range.
  // Range fehlt (Diode, Freq, Period, Temp, Ratio): Fallback auf wert-basierte Auto-Skala.
  //   V → mV → µV    A → mA → µA    Ω → kΩ → MΩ    F → pF → nF → µF    Hz → kHz → MHz
  // Diode-Mode → Einheit immer "V" (so wie auf dem DMM-Display).
  // Gibt {num, unit} zurück (zwei DOM-Knoten).
  function fmtDmm(value, baseUnit, mode, range) {
    // Kein Wert / Overrange (Messleitung offen, Keithley liefert ±9.91E+37) →
    // num und sign leer, aber die Einheit (V/Ω/A/…) bleibt sichtbar an ihrer
    // festen Position. Vermeidet ein „springendes" V beim Antasten/Abheben.
    if (value === null || value === undefined || !isFinite(value) || Math.abs(value) > 1e30) {
      return { sign: "", num: "", unit: baseUnit || "" };
    }
    const abs = Math.abs(value);
    let scaled = value;
    let unit   = baseUnit || "";
    let fixedDecimals = null;             // null = nach 8-Digit-Regel rechnen

    // Diode immer in V mit 2 Stellen vor und 7 nach dem Komma (z.B. "01.1195763 V")
    if (mode === "Diode") {
      let s = Math.abs(value).toFixed(7);
      const dotIdx = s.indexOf(".");
      if (dotIdx < 2) s = "0".repeat(2 - dotIdx) + s;
      return { sign: value < 0 ? "-" : "", num: s, unit: "V" };
    }

    // Range-basierte Skala bevorzugen — sonst wert-basiert (alt).
    const r = (range !== null && range !== undefined && isFinite(range)) ? Math.abs(range) : null;

    if (baseUnit === "V" || baseUnit === "A") {
      let prefix;
      if (r !== null) {
        // Range ≤ 100µ → µ-Anzeige, ≤ 100m → m-Anzeige, sonst Basis.
        // Toleranz × 1.05, damit z.B. exakt 1.0 V Range nicht ins m-Fach rutscht.
        if (r <= 1.05e-4)       prefix = "µ";
        else if (r <= 1.05e-1)  prefix = "m";
        else                    prefix = "";
      } else {
        if (abs > 0 && abs < 1.2e-4)    prefix = "µ";
        else if (abs > 0 && abs < 1.2)  prefix = "m";
        else                            prefix = "";
      }
      if (prefix === "µ")      { scaled = value * 1e6; unit = "µ" + baseUnit; }
      else if (prefix === "m") { scaled = value * 1e3; unit = "m" + baseUnit; }
    } else if (baseUnit === "Ω") {
      let prefix;
      if (r !== null) {
        if (r >= 1.05e6)        prefix = "M";
        else if (r >= 1.05e3)   prefix = "k";
        else                    prefix = "";
      } else {
        if (abs >= 1.2e6)       prefix = "M";
        else if (abs >= 1.2e3)  prefix = "k";
        else                    prefix = "";
      }
      if (prefix === "M")      { scaled = value / 1e6; unit = "MΩ"; }
      else if (prefix === "k") { scaled = value / 1e3; unit = "kΩ"; }
    } else if (baseUnit === "F") {
      let prefix;
      if (r !== null) {
        if (r >= 1.05e-4)       prefix = "m";
        else if (r >= 1.05e-7)  prefix = "µ";
        else                    prefix = "n";
      } else {
        if (abs >= 1.2e-4)      prefix = "m";
        else if (abs >= 1.2e-7) prefix = "µ";
        else                    prefix = "n";
      }
      if (prefix === "m")      { scaled = value * 1e3; unit = "mF"; }
      else if (prefix === "µ") { scaled = value * 1e6; unit = "µF"; }
      else                     { scaled = value * 1e9; unit = "nF"; }
    } else if (baseUnit === "Hz") {
      if (abs >= 1.2e6)                { scaled = value / 1e6; unit = "MHz"; }
      else if (abs >= 1.2e3)           { scaled = value / 1e3; unit = "kHz"; }
      fixedDecimals = 3;
    } else if (baseUnit === "s") {
      if (abs > 0 && abs < 1e-6)       { scaled = value * 1e9; unit = "ns"; }
      else if (abs > 0 && abs < 1e-3)  { scaled = value * 1e6; unit = "µs"; }
      else if (abs > 0 && abs < 1)     { scaled = value * 1e3; unit = "ms"; }
      fixedDecimals = 3;
    } else if (baseUnit === "°C") {
      fixedDecimals = 3;
    } else if (mode === "Ratio") {
      fixedDecimals = 3;
    }

    // 8-Digit-Regel: Gesamtanzeige (int + dec) maximal 8 Ziffern.
    let decimals;
    if (fixedDecimals !== null) {
      decimals = fixedDecimals;
    } else {
      const absScaled = Math.abs(scaled);
      if (absScaled === 0 || !isFinite(absScaled)) {
        decimals = 7;
      } else {
        const intDigits = Math.max(1, Math.floor(Math.log10(absScaled)) + 1);
        decimals = Math.max(0, 8 - intDigits);
      }
    }
    // Vorzeichen in eigenes Feld separieren — Ziffernblock wandert nicht, wenn
    // sich nur das Vorzeichen ändert.
    return {
      sign: scaled < 0 ? "-" : "",
      num: Math.abs(scaled).toFixed(decimals),
      unit: unit,
    };
  }
  function fmt3(v) {
    if (v === null || v === undefined || !isFinite(v)) return "—";
    return v.toFixed(3);
  }

  // ----- Charts -----
  const charts = {};

  function buildChart(canvas, lines, scale) {
    const opts = {
      millisPerPixel: (scale && scale.millisPerPixel) || MS_PER_PIXEL,
      interpolation: "linear",
      grid: {
        fillStyle: COL_GRAPH_BG,
        strokeStyle: COL_GRID,
        verticalSections: 0,
        millisPerLine: 0,
        borderVisible: false,
      },
      labels: { disabled: true },
      responsive: false,
    };
    if (scale && typeof scale.maxValue === "number") {
      opts.minValue = scale.minValue ?? 0;
      opts.maxValue = scale.maxValue;
    } else {
      opts.minValueScale = 1.08;
      opts.maxValueScale = 1.08;
    }
    const chart = new SmoothieChart(opts);
    const series = lines.map(c => {
      const ts = new TimeSeries();
      chart.addTimeSeries(ts, { strokeStyle: c, lineWidth: LINE_WIDTH });
      return ts;
    });
    chart.streamTo(canvas, 250);
    return { chart, series };
  }

  function sizeCanvas(canvas) {
    const r = canvas.getBoundingClientRect();
    canvas.width  = Math.max(40, Math.floor(r.width));
    canvas.height = Math.max(20, Math.floor(r.height));
  }

  function initCharts() {
    let c = document.getElementById("dmm-g");
    sizeCanvas(c);
    charts.dmm = buildChart(c, [COL_V], CHART_SCALE.dmm);
    for (const id of ["bb3a", "bb3b", "kel"]) {
      const cv = document.getElementById(id + "-g");
      sizeCanvas(cv);
      charts[id] = buildChart(cv, [COL_V, COL_A], CHART_SCALE[id]);
    }
  }

  // ----- Render der State-Updates -----
  function setOk(panelId, ok) {
    const el = document.querySelector(`.panel[data-id="${panelId}"]`);
    if (!el) return;
    el.classList.toggle("offline", !ok);
  }

  // Y-Maximum für DMM-Graph: Diode = 12, sonst 120 % der DMM-Range (vom Gerät gelesen).
  // Fallback bei fehlender Range: nächste 10er-Dekade ≥ |Wert| × 1.2.
  function dmmYMax(value, mode, range) {
    if (mode === "Diode") return 12;
    if (range !== null && range !== undefined && isFinite(range) && Math.abs(range) > 0) {
      return Math.abs(range) * 1.2;
    }
    if (value === null || value === undefined || !isFinite(value)) return 1.2;
    const abs = Math.abs(value);
    if (abs < 1e-12) return 1.2;
    const decade = Math.pow(10, Math.ceil(Math.log10(abs)));
    return decade * 1.2;
  }

  // Hält jede gesehene DMM-Range für mindestens 32 s (Graph-Traversierung = 30 s
  // bei 165 ms/px × 182 px). Wechselt der DMM auf eine kleinere Range, bleibt das
  // Y-Max so lange auf der alten (größeren), bis deren Spur sicher rausgescrollt
  // ist. Beim Mode-Wechsel wird der Verlauf gelöscht (Range-Werte sind nicht
  // mode-übergreifend vergleichbar — 10 in V ist nicht 10 in Ω).
  const RANGE_HOLD_MS = 32000;
  const dmmRangeHistory = new Map();   // range → letzter Zeitpunkt gesehen
  let   dmmHistoryMode  = null;

  function dmmEffectiveRange(currentRange, currentMode) {
    const now = Date.now();
    if (dmmHistoryMode !== currentMode) {
      dmmRangeHistory.clear();
      dmmHistoryMode = currentMode;
    }
    if (currentRange !== null && currentRange !== undefined && isFinite(currentRange)) {
      dmmRangeHistory.set(currentRange, now);
    }
    for (const [r, ts] of dmmRangeHistory) {
      if (now - ts > RANGE_HOLD_MS) dmmRangeHistory.delete(r);
    }
    if (dmmRangeHistory.size === 0) return currentRange;
    return Math.max(...dmmRangeHistory.keys());
  }

  function renderDmm(s) {
    setOk("dmm", s.ok);
    document.getElementById("dmm-mode").textContent = s.mode || "—";
    const fmt = fmtDmm(s.value, s.unit || "", s.mode, s.range);
    document.getElementById("dmm-sign").textContent = fmt.sign;
    document.getElementById("dmm-val").textContent = fmt.num;
    document.getElementById("dmm-unit").textContent = fmt.unit;

    // Diode-Mode + |Wert| < 0.05 V → "Shorted" in rot in der mittleren Zeile
    const isShorted = s.mode === "Diode"
                   && s.value !== null && isFinite(s.value)
                   && Math.abs(s.value) < 0.05;
    const dmmPanel = document.querySelector('.panel[data-id="dmm"]');
    if (dmmPanel) dmmPanel.classList.toggle("shorted", isShorted);
    document.getElementById("dmm-sub").textContent = isShorted ? "Shorted" : "—";

    if (s.ok && s.value !== null && isFinite(s.value)) {
      charts.dmm.series[0].append(Date.now(), s.value);
      // Y-Skala an die DMM-Range koppeln, aber mit 32 s Halte-Zeit: schrumpft die
      // Range (z.B. nach Probe abnehmen), bleibt das Y-Max so lange auf der alten,
      // bis die historische Spur aus dem Graph rausgescrollt ist.
      const effRange = dmmEffectiveRange(s.range, s.mode);
      charts.dmm.chart.options.minValue = 0;
      charts.dmm.chart.options.maxValue = dmmYMax(s.value, s.mode, effRange);
    }
  }

  function renderTwoLine(id, s, modeIsSingle) {
    setOk(id, s.ok);
    if (modeIsSingle) {
      const modeEl = document.getElementById(id + "-mode");
      if (modeEl) modeEl.textContent = s.mode || "—";
    }
    // Output OFF (BB3 OUTP? == 0) → "OFF" statt Werte, Einheiten/Mode dimmen,
    // keine neuen Samples in den Graph (verbliebener Trace scrollt natürlich raus).
    const isOff = s.output === false;
    const panel = document.querySelector(`.panel[data-id="${id}"]`);
    if (panel) panel.classList.toggle("output-off", isOff);

    document.getElementById(id + "-v").textContent = isOff ? "OFF" : fmt3(s.voltage);
    document.getElementById(id + "-a").textContent = isOff ? "OFF" : fmt3(s.current);

    // USB-Panel (Fnirsi C1): D+/D- als kleine Aux-Anzeige rechts neben V/A,
    // Protokoll-Tag hinter "USB" im Label. Andere Panels haben diese Elemente nicht.
    const dpEl = document.getElementById(id + "-dp");
    const dnEl = document.getElementById(id + "-dn");
    const extraEl = document.getElementById(id + "-extra");
    if (dpEl && dnEl) {
      if (s.ok && isFinite(s.dp) && isFinite(s.dn)) {
        dpEl.textContent = `(D+ ${s.dp.toFixed(2)} V)`;
        dnEl.textContent = `(D− ${s.dn.toFixed(2)} V)`;
      } else {
        dpEl.textContent = "";
        dnEl.textContent = "";
      }
    }
    if (extraEl) {
      extraEl.textContent = (s.ok && s.protocol && s.protocol !== "—") ? s.protocol : "";
    }

    if (!isOff && s.ok && isFinite(s.voltage)) charts[id].series[0].append(Date.now(), s.voltage);
    if (!isOff && s.ok && isFinite(s.current)) charts[id].series[1].append(Date.now(), s.current);
  }

  function applyState(state) {
    const d = state.devices || {};
    if (d.dmm)  renderDmm(d.dmm);
    if (d.bb3a) renderTwoLine("bb3a", d.bb3a, false);
    if (d.bb3b) renderTwoLine("bb3b", d.bb3b, false);
    if (d.kel)  renderTwoLine("kel",  d.kel,  true);
  }

  // ----- WebSocket-Anbindung -----
  let ws = null;
  let reconnectTimer = null;

  function connect() {
    if (ws) try { ws.close(); } catch (e) {}
    ws = new WebSocket(WS_URL);
    ws.onopen = () => {
      console.log("[overlay] WS connected", WS_URL);
      document.body.classList.remove("disconnected");
    };
    ws.onmessage = (ev) => {
      try {
        const state = JSON.parse(ev.data);
        applyState(state);
      } catch (e) {
        console.error("[overlay] bad message", e);
      }
    };
    ws.onclose = () => {
      console.log("[overlay] WS closed, reconnect in 2 s");
      document.body.classList.add("disconnected");
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(connect, 2000);
    };
    ws.onerror = () => {
      try { ws.close(); } catch (e) {}
    };
  }

  window.addEventListener("DOMContentLoaded", () => {
    initCharts();
    window.addEventListener("resize", () => {
      for (const id of ["dmm", "bb3a", "bb3b", "kel"]) {
        sizeCanvas(document.getElementById(id + "-g"));
      }
    });
    connect();
  });
})();
