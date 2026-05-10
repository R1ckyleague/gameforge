; ============================================================
; Inno Setup script — Animated Wallpaper
; Genera: output\AnimatedWallpaper_Setup_v1.0.0.exe
; ============================================================

#define AppName      "Animated Wallpaper"
#define AppVersion   "1.0.0"
#define AppPublisher "GameForge"
#define AppExe       "AnimatedWallpaper.exe"
#define AppURL       "https://github.com/R1ckyleague/gameforge"

[Setup]
AppId={{F3A84C21-7B5E-4D92-A1CF-8E3B29047D50}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} v{#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}

; Instalación en Archivos de programa
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes

; Permite que usuarios sin admin puedan instalarlo en su carpeta
PrivilegesRequiredOverridesAllowed=dialog

; Salida del instalador
OutputDir=output
OutputBaseFilename=AnimatedWallpaper_Setup_v{#AppVersion}
SetupIconFile=icon.ico

; Compresión máxima
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Apariencia
WizardStyle=modern
WizardResizable=no
ShowLanguageDialog=no

; Desinstalador
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
; Acceso directo en el escritorio (marcado por defecto)
Name: "desktopicon"; \
  Description: "Crear acceso directo en el Escritorio"; \
  GroupDescription: "Accesos directos:"; \
  Flags: checkedonce

; Inicio con Windows (desmarcado por defecto)
Name: "autostart"; \
  Description: "Iniciar con Windows"; \
  GroupDescription: "Inicio automático:"; \
  Flags: unchecked

[Files]
; Todos los archivos compilados por PyInstaller
Source: "dist\AnimatedWallpaper\*"; \
  DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Menú Inicio
Name: "{group}\{#AppName}";           Filename: "{app}\{#AppExe}"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"

; Escritorio (solo si el usuario marcó la opción)
Name: "{commondesktop}\{#AppName}"; \
  Filename: "{app}\{#AppExe}"; \
  Tasks: desktopicon

[Registry]
; Inicio automático con Windows (solo si el usuario lo marcó)
Root: HKCU; \
  Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; \
  ValueName: "AnimatedWallpaper"; \
  ValueData: """{app}\{#AppExe}"""; \
  Flags: uninsdeletevalue; \
  Tasks: autostart

[Run]
; Ofrecer lanzar la app al terminar la instalación
Filename: "{app}\{#AppExe}"; \
  Description: "Iniciar {#AppName} ahora"; \
  Flags: nowait postinstall skipifsilent

[UninstallRun]
; Cerrar la app si está corriendo antes de desinstalar
Filename: "taskkill.exe"; \
  Parameters: "/f /im {#AppExe}"; \
  Flags: runhidden waituntilterminated; \
  RunOnceId: "KillApp"

[Code]
// Comprueba si la app está corriendo al desinstalar y avisa al usuario
function InitializeUninstall(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
end;
