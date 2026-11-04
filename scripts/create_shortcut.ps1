param([string]$DesktopDirectory = [Environment]::GetFolderPath('Desktop'))
$ErrorActionPreference = 'Stop'
$appRoot = Split-Path -Parent $PSScriptRoot
$pythonWindowed = Join-Path $appRoot '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonWindowed)) {
    throw 'Missing .venv\Scripts\pythonw.exe. Set up the source environment first.'
}
$shortcutFile = Join-Path $DesktopDirectory '谛听 FaceGuard.lnk'
$shortcutShell = New-Object -ComObject WScript.Shell
$shortcut = $shortcutShell.CreateShortcut($shortcutFile)
$shortcut.TargetPath = $pythonWindowed
$shortcut.Arguments = '"' + (Join-Path $appRoot 'run_app.pyw') + '"'
$shortcut.WorkingDirectory = $appRoot
$shortcut.IconLocation = (Join-Path $appRoot 'src\faceguard\ui\brand.ico') + ',0'
$shortcut.Description = '谛听 FaceGuard · 本机照片与视频检测'
$shortcut.Save()
[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($shortcut)
[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($shortcutShell)
Write-Output $shortcutFile
