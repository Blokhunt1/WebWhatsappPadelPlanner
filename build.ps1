Write-Host "Setting up Padel Bot environment..."
if (!(Test-Path -Path "venv")) {
    python -m venv venv
}
.\venv\Scripts\Activate.ps1
pip install -r src\requirements.txt
playwright install
cd src
npm install
cd ..
Write-Host "Setup complete!"

$batContent = "@echo off`ncd src`nnode bot.js`npause"
Set-Content -Path "Start-PadelBot.bat" -Value $batContent
Write-Host "Created Start-PadelBot.bat! You can now double click it to run the bot."
