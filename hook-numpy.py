# hook-numpy.py
from PyInstaller.utils.hooks import get_package_paths
from PyInstaller.utils.hooks import collect_all

# Usa collect_all em numpy para tentar resolver o problema de importação
# E retorna as informações para o PyInstaller.
def hook(hook_api):
    packages = ['numpy', 'pandas', 'scipy', 'sklearn'] # Inclui pandas por precaução
    
    # Coleta todas as dependências de NumPy/Pandas que PyInstaller pode ter perdido
    for package in packages:
        try:
            datas, binaries, hiddenimports = collect_all(package)
            hook_api.add_datas(datas)
            hook_api.add_binaries(binaries)
            hook_api.add_imports(*hiddenimports)
        except Exception:
            pass
            
    # Forçar a importação do numpy no momento certo
    hook_api.add_runtime_import_module('numpy')
    return []