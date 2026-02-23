@echo off
echo ===========================================
echo Peakz Padel WhatsApp Bot Installer
echo ===========================================
echo.
echo Installing Python and Node.js dependencies...
powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1
echo.
echo ===========================================
echo Installation Complete! 
echo You can now use Start-PadelBot.bat to run the bot.
echo ===========================================
pause
