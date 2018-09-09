# -*- mode: python -*-

block_cipher = None

workpath = '_build'
DISTPATH = '_dist'

a = Analysis(['aki.py'],
             pathex=['D:\\Genji\\Documents\\Current\\Video games\\aki'],
             binaries=[],
             datas=[
             ('lib', ''),
             ('src', ''),
             ('tests', ''),
             ],
             hiddenimports=['core.*','core.stdlib',
             'core.stdlib.nt'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[
                 'bz2','hashlib','lzma','socket','ssl', 'pyexpat','select'
             ],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='aki',
          debug=False,
          strip=False,
          upx=True,
          console=True )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='aki')
