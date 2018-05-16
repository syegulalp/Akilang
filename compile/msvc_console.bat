@SETLOCAL
call "C:\Program Files (x86)\Microsoft Visual Studio\2017\Community\VC\Auxiliary\Build\vcvarsall.bat" amd64
link.exe %1.obj -defaultlib:ucrt msvcrt.lib user32.lib kernel32.lib legacy_stdio_definitions.lib /SUBSYSTEM:CONSOLE /MACHINE:X64 /OUT:%1.exe /OPT:REF
EXIT /B %ERRORLEVEL%