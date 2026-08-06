@echo off
setlocal
chcp 65001 >nul

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

if not "%~1"=="" (
  set "WORD_FILE=%~1"
) else (
  set "WORD_FILE=%PROJECT_DIR%private-source\Automation_book4Aug2026.docx"
)

if not defined WORD_FILE goto :missing_word
if not exist "%WORD_FILE%" goto :missing_word

where py >nul 2>&1
if %errorlevel%==0 (
  set "PYTHON_CMD=py -3"
) else (
  where python >nul 2>&1
  if errorlevel 1 goto :missing_python
  set "PYTHON_CMD=python"
)

where pandoc >nul 2>&1
if errorlevel 1 goto :missing_pandoc

where soffice >nul 2>&1
if errorlevel 1 (
  if exist "%ProgramFiles%\LibreOffice\program\soffice.exe" (
    set "PATH=%ProgramFiles%\LibreOffice\program;%PATH%"
  ) else if exist "%ProgramFiles(x86)%\LibreOffice\program\soffice.exe" (
    set "PATH=%ProgramFiles(x86)%\LibreOffice\program;%PATH%"
  ) else (
    goto :missing_libreoffice
  )
)

echo.
echo Installing or checking Python packages...
%PYTHON_CMD% -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo.
echo Building the website from:
echo %WORD_FILE%
%PYTHON_CMD% scripts\build-from-word-semantic.py "%WORD_FILE%" --out docs
if errorlevel 1 goto :failed

echo.
echo Validating the generated public website...
%PYTHON_CMD% scripts\validate-book.py --docs docs
if errorlevel 1 goto :failed

echo.
echo ============================================================
echo BUILD AND VALIDATION SUCCEEDED
echo Check every changed question and solution before publishing.
echo ============================================================
start "" "%PROJECT_DIR%docs\index.html"
pause
exit /b 0

:missing_word
echo.
echo ERROR: The Word file was not found.
echo Expected: private-source\Automation_book4Aug2026.docx
echo Or drag another DOCX file onto BUILD_SITE_WINDOWS.bat.
goto :failed_end

:missing_python
echo.
echo ERROR: Python 3 is not installed or is not available in PATH.
goto :failed_end

:missing_pandoc
echo.
echo ERROR: Pandoc is not installed or is not available in PATH.
goto :failed_end

:missing_libreoffice
echo.
echo ERROR: LibreOffice was not found.
echo Install LibreOffice and restart Windows before trying again.
goto :failed_end

:failed
echo.
echo ERROR: BUILD OR VALIDATION FAILED.
echo Do not publish. Copy the complete error message for technical support.

:failed_end
pause
exit /b 1
