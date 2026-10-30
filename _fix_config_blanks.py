import pathlib, re
p = pathlib.Path(r"C:\Users\cathe\OneDrive\Desktop\varynx\varynx\config.py")
src = p.read_text(encoding="utf-8")

# Find the single newline between end of AWSConfig and class VarynxConfig
# Pattern: closing "    )\n" followed directly by "class VarynxConfig"
before = "    )\n\nclass VarynxConfig"
after  = "    )\n\n\nclass VarynxConfig"
if before in src and after not in src:
    src = src.replace(before, after, 1)
    p.write_text(src, encoding="utf-8")
    print("Fixed: added second blank line before VarynxConfig")
elif after in src:
    print("Already has 2 blank lines -- no change needed")
else:
    # Show what's actually around class VarynxConfig
    idx = src.index("class VarynxConfig")
    print("Context:", repr(src[idx-20:idx+20]))
    print("ERROR: pattern not found")