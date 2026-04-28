@echo off
REM Nuitka build script — produces a standalone Windows folder containing the .exe.
REM Output:  build\main.dist\RadiologyDictation.exe  (plus its DLLs / data)
REM
REM First run can take 10-20 minutes; Nuitka may auto-download MinGW64 the first
REM time it sees --assume-yes-for-downloads. Subsequent rebuilds are faster.

setlocal

set PYTHON=.venv\Scripts\python.exe

if not exist "%PYTHON%" (
    echo [build_exe] Could not find %PYTHON%
    echo            Activate or create the .venv first:  python -m venv .venv ^&^& .venv\Scripts\pip install -e ".[dev,build]"
    exit /b 1
)

%PYTHON% -m nuitka ^
    --standalone ^
    --enable-plugin=pyqt6 ^
    --windows-console-mode=disable ^
    --assume-yes-for-downloads ^
    --include-package=src ^
    --include-package=faster_whisper ^
    --include-package=ctranslate2 ^
    --include-package=sounddevice ^
    --include-package=hid ^
    --include-package=pydicom ^
    --include-package=pynetdicom ^
    --nofollow-import-to=torch ^
    --nofollow-import-to=torchaudio ^
    --nofollow-import-to=transformers ^
    --nofollow-import-to=funasr ^
    --nofollow-import-to=src.ai.sensevoice_stt_client ^
    --nofollow-import-to=src.ai.medasr_stt_client ^
    --nofollow-import-to=pytest ^
    --nofollow-import-to=pynetdicom.tests ^
    --nofollow-import-to=pydicom.tests ^
    --include-package-data=faster_whisper ^
    --include-package-data=ctranslate2 ^
    --include-package-data=pydicom ^
    --include-package-data=pynetdicom ^
    --include-data-dir=.venv\Lib\site-packages\_sounddevice_data=_sounddevice_data ^
    --product-name="Radiology Dictation" ^
    --product-version=0.1.0 ^
    --file-version=0.1.0 ^
    --company-name="Matthew Harwood, MD" ^
    --file-description="Local AI dictation platform" ^
    --output-dir=build ^
    --output-filename=RadiologyDictation.exe ^
    --remove-output ^
    --jobs=4 ^
    src\main.py

if errorlevel 1 (
    echo [build_exe] Build failed.
    exit /b 1
)

echo.
echo [build_exe] Done. Run:  build\main.dist\RadiologyDictation.exe
endlocal
