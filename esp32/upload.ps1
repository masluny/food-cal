# Compile and upload the firmware to the ESP32 display.
# Stops the tray service (it holds the COM port) and starts it again after the upload.
#   powershell -ExecutionPolicy Bypass -File esp32\upload.ps1 [-Port COM3]
param([string]$Port = "COM3")
$root = Split-Path $PSScriptRoot -Parent
$cli = "$env:LOCALAPPDATA\Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe"

Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*scan_service.py*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

& $cli compile --fqbn esp32:esp32:esp32 --output-dir "$root\esp32\build" "$root\esp32\food_cal_display"
if ($LASTEXITCODE -ne 0) { exit 1 }
# 921600 loses data on this board's CH340 — 512000 works
& $cli upload -p $Port --fqbn esp32:esp32:esp32:UploadSpeed=512000 --input-dir "$root\esp32\build" "$root\esp32\food_cal_display"
if ($LASTEXITCODE -ne 0) { exit 1 }

# start through Explorer, so the service does not belong to this console
$lnk = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\food-cal-scan.lnk"
if (Test-Path $lnk) { explorer.exe $lnk } else { Start-Process "$root\.venv\Scripts\pythonw.exe" -ArgumentList "`"$root\src\scan_service.py`"" -WorkingDirectory $root }
Write-Host "Uploaded. The tray service is running again."
