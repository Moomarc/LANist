@echo off
setlocal
cd /d "%~dp0.."

set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" set "CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if not exist "%CSC%" (
  echo csc.exe not found. Install .NET Framework 4.
  exit /b 1
)

if exist release rmdir /s /q release
if exist release (
  echo Cannot clear release. Close any running LANist window and retry.
  exit /b 1
)
mkdir release
if errorlevel 1 exit /b 1
"%CSC%" /nologo /target:winexe /codepage:65001 /win32icon:lanist\assets\icon.ico /out:release\LANist.exe /r:System.Windows.Forms.dll tools\launcher.cs
if errorlevel 1 exit /b 1

robocopy lanist release\lanist /E /XD __pycache__ /NFL /NDL /NJH /NJS >nul
if errorlevel 8 (
  echo Copy failed. Check that LANist is closed and retry.
  exit /b 1
)
copy /y README.md release\ >nul
if errorlevel 1 exit /b 1
copy /y LICENSE release\ >nul
if errorlevel 1 exit /b 1
copy /y THIRD_PARTY.md release\ >nul
if errorlevel 1 exit /b 1
echo Built release\LANist.exe
