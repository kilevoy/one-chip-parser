@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo === Установка PyInstaller (если не установлен) ===
python -m pip install --upgrade pyinstaller || goto :err

echo.
echo === Сборка one-chip-parser.exe ===
python -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name one-chip-parser ^
    --hidden-import=parser ^
    --collect-submodules bs4 ^
    --collect-submodules lxml ^
    --collect-submodules openpyxl ^
    app.py || goto :err

echo.
echo === Готово. Файл: dist\one-chip-parser.exe ===
explorer dist
exit /b 0

:err
echo.
echo !!! Ошибка сборки. Запустите этот .bat от имени обычного пользователя.
pause
exit /b 1
