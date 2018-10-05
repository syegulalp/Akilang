@SETLOCAL
pushd .\
set DISTUTILS_USE_SDK=1
call "C:\Program Files (x86)\Microsoft Visual Studio\2017\Community\VC\Auxiliary\Build\vcvarsall.bat" amd64
popd
nuitka3 aki.py --python-flag=no_site --follow-imports --output-dir=__build -j 7
rem --windows-disable-console
