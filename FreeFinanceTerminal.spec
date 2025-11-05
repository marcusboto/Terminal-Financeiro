# -*- mode: python ; coding: utf-8 -*-
#
# CORREÇÃO FINAL PARA API INTERNA DO PYINSTALLER
#

# Importa a função de coleta de dependências
from PyInstaller.utils.hooks import collect_all

# Coleta recursivamente todas as dependências necessárias para o PySide6 e Plotly
block_cipher = None

# Coleta 1: PySide6 e Plotly (Módulos de Interface)
pyside6_data, pyside6_binaries, pyside6_hiddenimports = collect_all('PySide6')
plotly_data, plotly_binaries, plotly_hiddenimports = collect_all('plotly')

# Coleta 2: Binários para pacotes científicos (NumPy e Pandas)
# Usamos collect_all que é mais robusto para incluir binários C++ como o numpy
numpy_data, numpy_binaries, numpy_hiddenimports = collect_all('numpy')
pandas_data, pandas_binaries, pandas_hiddenimports = collect_all('pandas')


a = Analysis(
    ['terminal_desktop.py'],
    pathex=[],
    # Combina todos os binários
    binaries=pyside6_binaries + plotly_binaries + numpy_binaries + pandas_binaries,
    # Combina todos os arquivos de dados (recursos, etc.)
    datas=pyside6_data + plotly_data + numpy_data + pandas_data, 
    # Força a importação dos módulos escondidos
    hiddenimports=pyside6_hiddenimports + plotly_hiddenimports + numpy_hiddenimports + pandas_hiddenimports + ['PySide6.QtWebEngineWidgets'], 
    hookspath=[],
    hookscofig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FreeFinanceTerminal',  # Nome do Executável Final
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False, # Modo Janela
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FreeFinanceTerminal',
)