# -*- mode: python ; coding: utf-8 -*-
#
# CORREÇÃO PARA INCLUSÃO DE DEPENDÊNCIAS DO PySide6 E PLOTLY
# O problema de IndexError do PyInstaller está sendo contornado aqui.
#

# Importa a função de coleta de dependências
from PyInstaller.utils.hooks import collect_all

# Coleta recursivamente todas as dependências necessárias para o PySide6 e Plotly
# A saída 'datas' agora inclui todos esses arquivos para empacotamento
pyside6_data = collect_all('PySide6')[0]
plotly_data = collect_all('plotly')[0]

# Combina todas as dependências coletadas
block_cipher = None
datas = pyside6_data + plotly_data


a = Analysis(
    ['terminal_desktop.py'],
    pathex=[],
    binaries=[],
    datas=datas,  # ADICIONADO: Inclui dados coletados do PySide6/Plotly
    hiddenimports=['PySide6.QtWebEngineWidgets'],  # FORÇA A INCLUSÃO DO MÓDULO DE GRÁFICOS
    hookspath=[],
    hooksconfig={},
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
    # CORREÇÃO: console=False para evitar a janela preta do terminal
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Opcional: Adicionar ícone aqui, ex: icon='icon.ico'
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