PRODUCT = "Aki"
VERSION = '0.0.2019.03.30'
COPYRIGHT = "2019"

CONFIG_INI_DEFAULTS = '''[paths]
source_dir=examples
output_dir=output
dump_dir=.
editor=notepad.exe

[aux]
lib_dir=lib
basiclib=basiclib.aki
compiler_dir=compile

[nt_compiler]
path = "C:\\Program Files (x86)\\Microsoft Visual Studio\\2017\\Community\\VC\\Auxiliary\\Build\\vcvarsall.bat"
'''

ABOUT = f'''{PRODUCT} v.{VERSION}
© {COPYRIGHT} Serdar Yegulalp

Based on code created by:
- Frédéric Guérin (https://github.com/frederickjeanguerin/pykaleidoscope)
- Eli Bendersky (https://github.com/eliben/pykaleidoscope)'''

WELCOME = f"{PRODUCT} v.{VERSION}"