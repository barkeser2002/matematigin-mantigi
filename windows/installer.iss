; Matematiğin Mantığı — Windows kurulum programı (Inno Setup 6).
; DOSYA UTF-8 BOM'LU KAYDEDİLMELİ: Inno BOM yoksa ANSI okur, 'ğ' bozulur.
; Derleme:  iscc /DAppVersion=<yapı numarası> windows\installer.iss   (windows\build_win.ps1 bunu kendisi yapar)
; Girdi: dist\Matematigin Mantigi\  (PyInstaller çıktısı)   Çıktı: kurulum\Matematigin-Mantigi-Kurulum.exe
;
; Kullanıcı bazında kurulum: yönetici izni istemez, bu yüzden uygulamanın kendi güncellemesi
; (/VERYSILENT /SUPPRESSMSGBOXES /NORESTART) sessizce çalışabilir. Kurulum bitince uygulama yeniden açılır
; (sessiz kurulumda da; aşağıdaki [Run] satırı skipifsilent taşımaz).
;
; Kullanıcı verisi (Belgeler\Matematiğin Mantığı: sorular, kayıtlar, oturumlar; ayarlar) {app} DIŞINDADIR ve
; kaldırmada SİLİNMEZ. [UninstallDelete] bilerek yok.
; Otomatik başlatma kurulum programına eklenmez: uygulama ayarlarıyla yönetilir.

#ifndef AppVersion
  #define AppVersion "0"
#endif

#define AppName "Matematiğin Mantığı"
#define ExeName "Matematigin Mantigi.exe"

[Setup]
; Sabit kimlik: sürümler arasında aynı kalmalı (güncelleme aynı kurulumun üzerine yazar). Değiştirme.
AppId={{4EB89412-26D7-41F2-AF5A-D2CE9B36942D}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} (Yapı {#AppVersion})
AppPublisher=Barış Keser
AppPublisherURL=https://github.com/barkeser2002/matematigin-mantigi
AppSupportURL=https://github.com/barkeser2002/matematigin-mantigi/issues
AppUpdatesURL=https://github.com/barkeser2002/matematigin-mantigi/releases
VersionInfoVersion=0.0.0.{#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} kurulum programı
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\Matematigin Mantigi
DisableProgramGroupPage=yes
DisableDirPage=auto
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#ExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
OutputDir=..\kurulum
OutputBaseFilename=Matematigin-Mantigi-Kurulum

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; Eski sürümün kütüphaneleri yenileriyle karışmasın (PyInstaller çıktısı tek klasördür). Kullanıcı verisi burada değil.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\Matematigin Mantigi\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#ExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#ExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall
