@echo off
title DevPocket
cd /d "%~dp0"

set SHORTCUT_NAME=DevPocket.lnk
set DESKTOP_PATH=%USERPROFILE%\Desktop\%SHORTCUT_NAME%

if not exist "%DESKTOP_PATH%" (
    set SCRIPT="%TEMP%\CreateDevPocketShortcut.vbs"
    set ICON_PATH=%~dp0app_icon.ico
    set TARGET_EXE=%~dp0pythonw.exe
    set APP_PY=%~dp0DevPocket.py

    if not exist "%TARGET_EXE%" set TARGET_EXE=pythonw.exe

    echo Set oWS = CreateObject("WScript.Shell") > %SCRIPT%
    echo sLinkFile = oWS.SpecialFolders("Desktop") ^& "\DevPocket.lnk" >> %SCRIPT%
    echo Set oLink = oWS.CreateShortcut(sLinkFile) >> %SCRIPT%
    echo oLink.TargetPath = "%TARGET_EXE%" >> %SCRIPT%
    echo oLink.Arguments = """%APP_PY%""" >> %SCRIPT%
    echo oLink.WorkingDirectory = "%~dp0" >> %SCRIPT%
    echo oLink.IconLocation = "%ICON_PATH%" >> %SCRIPT%
    echo oLink.Description = "DevPocket - Developer Notes & Kanban Management" >> %SCRIPT%
    echo oLink.Save >> %SCRIPT%

    cscript //nologo %SCRIPT% >nul 2>&1
    del %SCRIPT% >nul 2>&1
)

python DevPocket.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================================
    echo An error occurred while starting DevPocket (Code: %ERRORLEVEL%)
    echo Please check error_log.txt or the message above.
    echo ========================================================
    echo.
    pause
)
