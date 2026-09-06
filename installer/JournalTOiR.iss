; JournalTOiR installer
#define MyAppName "Журнал ТОиР"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "Андреев Константин Романович"
#define MyAppExeName "Journal_TOiR.exe"

[Setup]
AppId={{A9C6F5A2-6E8B-4E8B-84DA-5F9F0D71A701}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\JournalTOiR
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=output
OutputBaseFilename=JournalTOiR_Setup_1.1.0
SetupIconFile=..\resources\app_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
UsePreviousAppDir=yes
UsePreviousGroup=yes
AllowNoIcons=yes

[Files]
Source: "..\dist\Journal_TOiR\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Ярлыки:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
function CopyDirectoryTree(const SourceDir, DestDir: string): Boolean;
var
  FindRec: TFindRec;
  SourcePath, DestPath: string;
begin
  Result := True;
  if not DirExists(SourceDir) then
    exit;

  ForceDirectories(DestDir);
  if FindFirst(AddBackslash(SourceDir) + '*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') then
        begin
          SourcePath := AddBackslash(SourceDir) + FindRec.Name;
          DestPath := AddBackslash(DestDir) + FindRec.Name;
          if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
          begin
            if not CopyDirectoryTree(SourcePath, DestPath) then
              Result := False;
          end
          else if not FileCopy(SourcePath, DestPath, False) then
            Result := False;
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  PortableData, InstalledData: string;
begin
  if CurStep = ssPostInstall then
  begin
    PortableData := ExpandConstant('{src}\data');
    InstalledData := ExpandConstant('{app}\data');

    if DirExists(PortableData) and
       FileExists(AddBackslash(PortableData) + 'app_config.json') and
       not FileExists(AddBackslash(InstalledData) + 'app_config.json') then
    begin
      CopyDirectoryTree(PortableData, InstalledData);
    end;
  end;
end;
