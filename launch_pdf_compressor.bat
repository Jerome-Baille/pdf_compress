@echo off
REM This batch file activates the virtual environment and launches the PDF Compressor application without showing the console window

REM Change to the directory containing the script
cd /d "%~dp0"

REM Activate the virtual environment and run the application with pythonw (no console window)
call venv\Scripts\activate.bat && start "" /b pythonw.exe pdf_compressor.py

REM Exit the batch file
exit
