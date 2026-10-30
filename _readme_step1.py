import pathlib
p = pathlib.Path(r'C:\Users\cathe\OneDrive\Desktop\varynx\README.md')
src = p.read_text(encoding='utf-8')
print('read ok:', len(src))