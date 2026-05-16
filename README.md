# OBS-Instrument-Overlay
Instrument overlay for OBS-Studio

From time to time i repair some electronic stuff that find their way to my bench. I use different devices for examination the DUT. Most of my test gear has LAN connection and supports SCPI/LXI, some other devices support BT BLE like the Fnirsi C1. For documentation i usually use the web frontent of my devies to make screenshots with the readings. The downside is, for the same situation, i have to take several screenshots from different devices. Sometimes i record it using OBS. Recently i watched a video on YT from the guy called BordRev. He uses different tools for diagnosing but all of them using the same look. Very cool. 

Because of a lack of programming knowledge, i let claude code do its magic in phyton/websocket/html/css programming to get it to work on my linux laptop with my special device setup in the same look. I let claude create a config file for setting color and device specific stuff.

There is a backend that has to be started first, then OBS starts and connects to it via websocket. It is a local html site that you can use in OBS. Claude managed not only to connect to my LAN devices (DMM7510, Envox Bench Box 3, Korad KEL103) but also to a Fnirsi C1 USB-Meter using BT BLE connection. 

It's easy to add devices that are using SCPI commands. The well known TestController-App has a folder containing settings for a wide range of devices.

View
<p align="center">
<img src="Bildschirmfoto vom 2026-05-14 20-56-48.jpg" width=420"> 
<img src="Bildschirmfoto vom 2026-05-15 18-46-12.jpg" width="420">
</p> 
