import pathlib
BASE = pathlib.Path(r"C:\Users\cathe\OneDrive\Desktop\varynx")
aws = BASE / "varynx" / "aws"
aws.mkdir(parents=True, exist_ok=True)

# Write each file
def W(rel, txt):
    p = BASE / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, encoding="utf-8")
    print(f"Written: {rel} ({p.stat().st_size}b)")