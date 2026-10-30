import importlib
for pkg in ["numpy","scipy","boto3","cryptography","hypothesis"]:
    try:
        m=importlib.import_module(pkg); print(pkg+": "+getattr(m,"__version__","?"))
    except ImportError:
        print(pkg+": NOT")