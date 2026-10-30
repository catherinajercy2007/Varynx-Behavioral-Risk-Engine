import pathlib
BASE = pathlib.Path(r"C:\Users\cathe\OneDrive\Desktop\varynx")
(BASE/"varynx/aws").mkdir(parents=True, exist_ok=True)
print("AWS dir created at:", BASE/"varynx/aws")