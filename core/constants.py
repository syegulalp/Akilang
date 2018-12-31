PRODUCT = "Aki"
VERSION = '0.0.2018.12.31'
COPYRIGHT = "2018"

CONFIG_INI_DEFAULTS = '''[paths]
lib_dir=lib
basiclib=basiclib.aki
source_dir=src
compiler_dir=compile
output_dir=output
dump_dir=.
editor=notepad.exe

[nt_compiler]
path = "C:\\Program Files (x86)\\Microsoft Visual Studio\\2017\\Community\\VC\\Auxiliary\\Build\\vcvarsall.bat"
'''

ABOUT = f'''
{PRODUCT} v.{VERSION}
© {COPYRIGHT} Serdar Yegulalp

Based on code created by:
- Frédéric Guérin (https://github.com/frederickjeanguerin/pykaleidoscope)
- Eli Bendersky (https://github.com/eliben/pykaleidoscope)
'''
