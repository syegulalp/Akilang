PRODUCT = "Aki"
VERSION = "0.0.2018.05.18"
COPYRIGHT = "2018"

compilers = {
    'nt':'msvc_console.bat'
}

def _compiler_path():
    import os
    return compilers[os.name]

compiler_path = _compiler_path()