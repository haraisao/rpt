@echo off

setlocal EnableDelayedExpansion
set PKGS=local ros_base ros_desktop control plan navigation robot setup

if "%2" == "" (
    if "%TMP_DIR%" == "" (
        set TMP_DIR=ros4win_pkg
    )
) else (
    set TMP_DIR=%2
)

for %%a in (%PKGS%) do (
    echo == Download %%a  to %TMP_DIR% ==
    choice /C YNC /T 3 /D Y /m "Y:Download, N:Skip , C:Cancel downlaod all packages"
    if errorlevel 3 goto INST
    if errorlevel 2 ( 
        echo Skip download %%a
    ) else (
        %~dp0r4wpkg get_pkg %%a %TMP_DIR%
    )
)

:INST
if "%1" == "" (
    set INST_DRV=%~d0
) else (
    set INST_DRV=%1
)
echo == Install Ros4Win to %INST_DRV% ==
choice /T 3 /D Y
if errorlevel 2 goto END
%~dp0r4wpkg install %TMP_DIR% %INST_DRV%
echo == Fnish to install Ros4Win ===

:END
endlocal
echo on