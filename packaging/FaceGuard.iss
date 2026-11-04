#ifndef AppVersion
  #error AppVersion is required
#endif
#ifndef PayloadDir
  #error PayloadDir is required
#endif
#ifndef ReleaseDir
  #error ReleaseDir is required
#endif

[Setup]
AppId={{6D67E7E4-A631-488E-94CC-0B3B32A1FB79}
AppName=谛听 FaceGuard
AppVersion={#AppVersion}
AppPublisher=pocket996
AppPublisherURL=https://github.com/pocket996/faceguard
AppSupportURL=https://github.com/pocket996/faceguard/issues
DefaultDirName={localappdata}\Programs\FaceGuard
DefaultGroupName=谛听 FaceGuard
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0
OutputDir={#ReleaseDir}
OutputBaseFilename=FaceGuard-v{#AppVersion}-windows-x64-cpu-setup
SetupIconFile={#PayloadDir}\_internal\faceguard\ui\brand.ico
UninstallDisplayIcon={app}\FaceGuard.exe
LicenseFile={#PayloadDir}\CODE_LICENSE.txt
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
Uninstallable=yes
DisableProgramGroupPage=yes

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\谛听 FaceGuard\谛听 FaceGuard"; Filename: "{app}\FaceGuard.exe"; WorkingDir: "{app}"; AppUserModelID: "FaceGuard.Diting"
Name: "{userdesktop}\谛听 FaceGuard"; Filename: "{app}\FaceGuard.exe"; WorkingDir: "{app}"; Tasks: desktopicon; AppUserModelID: "FaceGuard.Diting"

[Run]
Filename: "{app}\FaceGuard.exe"; Description: "启动谛听 FaceGuard"; Flags: nowait postinstall skipifsilent
