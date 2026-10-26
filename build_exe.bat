@echo off
chcp 65001 >nul
cd /d "%~dp0"

python -m pip install -r requirements.txt
python -m pip install "pyinstaller>=6"

python -m PyInstaller --noconfirm --clean --windowed --name Kuromi ^
  --icon "character\assets\kuromi.ico" ^
  --add-data "character\assets;character\assets" ^
  --collect-all langchain_core ^
  --collect-all langchain_openai ^
  --collect-all openai ^
  --collect-all tiktoken ^
  main.py

echo.
echo Build finished. The app folder is: dist\Kuromi\
echo Run dist\Kuromi\Kuromi.exe, then pack that folder with Inno Setup if you want an installer.
pause
