; Values and the extension registry entries are supplied by build.py.
[Setup]
AppId={{3C24D663-19B6-4987-88D3-D8045741D871}
AppName=ParrotIA
AppVersion={#AppVersion}
AppPublisher=Igor Bispo
AppPublisherURL=https://github.com/igorbispo99/ParrotIA
AppSupportURL=https://github.com/igorbispo99/ParrotIA/issues
DefaultDirName={localappdata}\Programs\ParrotIA
DefaultGroupName=ParrotIA
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
LicenseFile=..\..\LICENSE
SetupIconFile=..\..\src\parrotia\assets\parrotia.ico
UninstallDisplayIcon={app}\parrotia-gui.exe
WizardStyle=modern
DisableWelcomePage=no
#ifdef StableValidation
; Diagnostic build: execute at a fixed path instead of a randomized .tmp helper.
; The normal release below remains a single self-contained executable.
UseSetupLdr=no
OutputDir=..\..\dist\installer-check
OutputBaseFilename=ParrotIA-InstallerCheck
#else
OutputDir=..\..\dist\installer
OutputBaseFilename=ParrotIA-{#AppVersion}-windows-x64-setup
#endif
Compression=lzma2
SolidCompression=yes
ChangesAssociations=yes
CloseApplications=yes

[Messages]
WelcomeLabel2=Transcribe audio and video privately on your PC.%n%nSetup includes Python and all required libraries. No separate Python or FFmpeg installation is needed.%n%nModels download on first use and are cached for offline transcription.

[Tasks]
Name: desktopicon; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"
Name: explorer; Description: "Add &Transcribe on Parrot to audio/video right-click menus"; GroupDescription: "File Explorer:"

[Files]
Source: "..\..\dist\ParrotIA\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\ParrotIA"; Filename: "{app}\parrotia-gui.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\ParrotIA"; Filename: "{app}\parrotia-gui.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
#include RegistryFile

[Run]
Filename: "{app}\parrotia-gui.exe"; Description: "Open ParrotIA"; Flags: nowait postinstall skipifsilent
