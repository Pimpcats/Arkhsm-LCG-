@echo off
REM Start the Still Hour TTS relay (Windows, double-click). Same as the one-line
REM PowerShell command in docs/TTS_RELAY.md.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\tts_relay\start-relay.ps1"
pause
