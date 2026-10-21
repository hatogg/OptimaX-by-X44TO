; OptimaX by X44TO — інсталятор (Inno Setup 6.3+ або 7.x)
; Збирається через build_installer.bat; версію та шлях до файлів програми підставляє скрипт збірки.

#ifndef MyAppVersion
  #define MyAppVersion "6.3.1"
#endif
#ifndef AppBuildDir
  #define AppBuildDir "..\dist\OptimaX"
#endif
#define MyAppName "OptimaX"
#define MyAppPublisher "X44TO"
#define MyAppExe "OptimaX.exe"
#define MyAppUserModelID "X44TO.OptimaX"

[Setup]
AppId={{8F3C2A61-4B7E-4D21-9C5A-0E6F1B2D7A44}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppCopyright=© {#MyAppPublisher}
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=OptimaX by X44TO Setup
VersionInfoProductName={#MyAppName}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
DisableReadyPage=no
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; будь-яка 64-бітна Windows 10 або 11; на збірках, старших за 1809, InitializeSetup попереджає (див. [Code])
MinVersion=10.0
OutputDir=..\Output
OutputBaseFilename=OptimaX-Setup-{#MyAppVersion}
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName=OptimaX by X44TO
WizardStyle=modern
WizardImageFile=wizard-100.bmp,wizard-150.bmp,wizard-200.bmp
WizardSmallImageFile=wizard-small-100.bmp,wizard-small-150.bmp,wizard-small-200.bmp
Compression=lzma2/ultra64
SolidCompression=yes
; поки OptimaX працює, інсталятор попросить його закрити (ці м'ютекси створює сама програма)
AppMutex=OptimaX_X44TO,Global\OptimaX_X44TO
CloseApplications=yes
RestartApplications=no
ShowLanguageDialog=yes
LanguageDetectionMethod=uilanguage
#ifdef UseSign
SignTool=std
SignedUninstaller=yes
#endif

[Languages]
Name: "uk"; MessagesFile: "compiler:Languages\Ukrainian.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
uk.AutoStart=Запускати OptimaX разом із Windows (згорнутим у трей)
ru.AutoStart=Запускать OptimaX вместе с Windows (свёрнутым в трей)
en.AutoStart=Start OptimaX with Windows (minimized to the tray)
uk.StartupGroup=Автозапуск:
ru.StartupGroup=Автозапуск:
en.StartupGroup=Startup:
uk.SettingAutoStart=Налаштування автозапуску…
ru.SettingAutoStart=Настройка автозапуска…
en.SettingAutoStart=Setting up startup…
uk.RevertAsk=Повернути всі зміни, які зробив OptimaX (оптимізації, служби, DNS тощо), до ваших початкових значень?%n%nЯкщо натиснути «Ні», оптимізації залишаться в системі.
ru.RevertAsk=Вернуть все изменения, сделанные OptimaX (оптимизации, службы, DNS и т. д.), к вашим исходным значениям?%n%nЕсли нажать «Нет», оптимизации останутся в системе.
en.RevertAsk=Roll back every change OptimaX made (tweaks, services, DNS, etc.) to your original values?%n%nIf you choose No, the optimizations stay in the system.
uk.DeleteDataAsk=Видалити також налаштування OptimaX, список ігор і журнал змін?
ru.DeleteDataAsk=Удалить также настройки OptimaX, список игр и журнал изменений?
en.DeleteDataAsk=Also delete OptimaX settings, the game list and the change journal?
uk.StartingDns=Запуск фільтра реклами…
ru.StartingDns=Запуск фильтра рекламы…
en.StartingDns=Starting the ad blocker…
uk.AppComment=Оптимізація Windows для ігор, ноутбуків і старих ПК
ru.AppComment=Оптимизация Windows для игр, ноутбуков и старых ПК
en.AppComment=Windows optimization for gaming, laptops and old PCs
uk.RescueName=OptimaX — аварійний відкат
ru.RescueName=OptimaX — аварийный откат
en.RescueName=OptimaX — Emergency rollback
uk.RescueComment=Повертає зміни OptimaX без запуску програми, також із безпечного режиму
ru.RescueComment=Возвращает изменения OptimaX без запуска программы, также из безопасного режима
en.RescueComment=Rolls back OptimaX changes without starting the program, also from Safe Mode
uk.OldWindows=У вас Windows 10 збірки %1, вона старша за версію 1809 (17763).%n%nOptimaX перевіряють на новіших версіях Windows: на цій програма може не запуститися, а частина оптимізацій буде недоступна.%n%nВсе одно встановити?
ru.OldWindows=У вас Windows 10 сборки %1, она старше версии 1809 (17763).%n%nOptimaX проверяют на более новых версиях Windows: на этой программа может не запуститься, а часть оптимизаций будет недоступна.%n%nВсё равно установить?
en.OldWindows=You have Windows 10 build %1, which is older than version 1809 (17763).%n%nOptimaX is tested on newer versions of Windows: on this one the program may not start, and some optimizations won't be available.%n%nInstall anyway?

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "{cm:AutoStart}"; GroupDescription: "{cm:StartupGroup}"; Flags: unchecked

[Files]
Source: "{#AppBuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; запускач аварійного відкату: сам сценарій OptimaX переписує після кожної зміни в %ProgramData%\OptimaX\rescue
Source: "OptimaX-Rescue.cmd"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Comment: "{cm:AppComment}"; AppUserModelID: "{#MyAppUserModelID}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Comment: "{cm:AppComment}"; AppUserModelID: "{#MyAppUserModelID}"; Tasks: desktopicon
Name: "{autoprograms}\{cm:RescueName}"; Filename: "{app}\OptimaX-Rescue.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExe}"; Comment: "{cm:RescueComment}"

[Registry]
; мова, вибрана в інсталяторі, стає мовою програми (поки її не змінять у налаштуваннях OptimaX)
Root: HKCU; Subkey: "Software\X44TO\OptimaX"; ValueType: string; ValueName: "Language"; ValueData: "{language}"; Flags: uninsdeletevalue uninsdeletekeyifempty
Root: HKCU; Subkey: "Software\X44TO"; Flags: uninsdeletekeyifempty

[Run]
; фільтр реклами (якщо був увімкнений) знову стартує з новою версією файлів
Filename: "{sys}\schtasks.exe"; Parameters: "/Run /TN ""OptimaX DNS"""; StatusMsg: "{cm:StartingDns}"; Flags: runhidden waituntilterminated; Check: DnsTaskWasRunning
Filename: "{app}\{#MyAppExe}"; Parameters: "--set-autostart"; Tasks: autostart; StatusMsg: "{cm:SettingAutoStart}"; Flags: runhidden waituntilterminated
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
; тихе оновлення з самої програми (/UPDATE=1): після встановлення запускаємо нову версію
Filename: "{app}\{#MyAppExe}"; Parameters: "--restarted"; Flags: nowait; Check: IsSilentUpdate

[Code]
var
  DnsTaskFound: Boolean;

function IsSilentUpdate: Boolean;
begin
  Result := WizardSilent and (ExpandConstant('{param:UPDATE|0}') = '1');
end;

function InitializeSetup: Boolean;
var
  I: Integer;
  Win: TWindowsVersion;
begin
  { старі збірки Windows 10 не блокуємо, а попереджаємо: інтерфейс (Qt 6) офіційно підтримує 1809+ }
  GetWindowsVersionEx(Win);
  if (Win.Major = 10) and (Win.Build < 17763) and (not WizardSilent) then
    if MsgBox(FmtMessage(CustomMessage('OldWindows'), [IntToStr(Win.Build)]), mbConfirmation,
              MB_YESNO or MB_DEFBUTTON2) <> IDYES then
    begin
      Result := False;
      Exit;
    end;
  { під час оновлення програма сама закривається — даємо їй до 10 секунд }
  if ExpandConstant('{param:UPDATE|0}') = '1' then
    for I := 1 to 40 do
    begin
      if not CheckForMutexes('OptimaX_X44TO') then
        Break;
      Sleep(250);
    end;
  Result := True;
end;

{ Фільтр реклами працює від імені SYSTEM з файлу OptimaX.exe — зупиняємо його, щоб файл можна було замінити.
  Поки його немає, Windows користується резервним DNS роутера, тож інтернет не зникає. }
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Result := '';
  DnsTaskFound := Exec(ExpandConstant('{sys}\schtasks.exe'), '/Query /TN "OptimaX DNS"', '', SW_HIDE,
    ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
  if DnsTaskFound then
  begin
    Exec(ExpandConstant('{sys}\schtasks.exe'), '/End /TN "OptimaX DNS"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(1500);
  end;
end;

function DnsTaskWasRunning: Boolean;
begin
  Result := DnsTaskFound;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
  Args: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    Args := '--uninstall';
    if (not UninstallSilent) and (MsgBox(CustomMessage('RevertAsk'), mbConfirmation, MB_YESNO) = IDYES) then
      Args := Args + ' --revert-all';
    { прибирає задачі планувальника, повертає режим гри та (за згодою) усі зміни }
    Exec(ExpandConstant('{app}\{#MyAppExe}'), Args, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
  if CurUninstallStep = usPostUninstall then
  begin
    if (not UninstallSilent) and
       (MsgBox(CustomMessage('DeleteDataAsk'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES) then
    begin
      DelTree(ExpandConstant('{userappdata}\OptimaX'), True, True, True);
      { списки й статистика фільтра реклами }
      DelTree(ExpandConstant('{commonappdata}\OptimaX'), True, True, True);
    end;
  end;
end;
