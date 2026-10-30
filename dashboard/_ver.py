import json, os
base = r'C:\Users\cathe\OneDrive\Desktop\varynx\dashboard\node_modules'
for pkg in ['next','react','react-dom','eslint','eslint-config-next','typescript','tailwindcss','postcss','autoprefixer']:
    try:
        p = os.path.join(base, pkg, 'package.json')
        with open(p, encoding='utf-8') as f:
            d = json.load(f)
        v = d.get('version', '?')
        print(pkg + ': ' + v)
    except Exception as e:
        print(pkg + ': MISSING (' + type(e).__name__ + ')')