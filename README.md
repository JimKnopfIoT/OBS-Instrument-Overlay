# OBS-Instrument-Overlay
Instrument overlay for OBS-Studio

From time to time, I repair electronic stuff that end up on my workbench. For diagnostics and testing, I use various instruments and measurement tools. Most of my test gear supports LAN connectivity and SCPI/LXI, while some devices — like the FNIRSI C1 USB meter — use Bluetooth BLE.

For documentation, I usually take screenshots from the web interfaces of my test-gear. The downside is that, for a single test setup, I often need multiple screenshots from different instruments. Sometimes I also record the process using OBS Studio.
Recently, I watched a YouTube video by BordRev. He uses several diagnostic tools as well, but all of them share the same visual style and overlay design. I really liked that clean and unified look.

Since my programming knowledge is limited, I used Claude Code to help me create a solution using Python, WebSockets, HTML, and CSS. The system now runs on my Linux laptop and is tailored to my specific instrument setup. Claude also helped generate a configuration system for colors, layouts, and device-specific settings.
The setup consists of a backend service that starts first. OBS then connects to it through a local WebSocket-based HTML interface, which is used as a browser source inside OBS. So far, Claude successfully connected not only my LAN-based instruments (Keithley DMM7510, Envox Bench Box 3, and Korad KEL103), but also the FNIRSI C1 USB meter over BLE.
Adding SCPI-compatible devices is relatively easy. The well-known TestController application already includes configuration files for a wide range of instruments, which makes integrating additional hardware much simpler.

## View
<p align="center">
<img src="Bildschirmfoto vom 2026-05-14 20-56-48.jpg" width=420"> 
<img src="Bildschirmfoto vom 2026-05-15 18-46-12.jpg" width="420">
</p> 
