import pathlib
p = pathlib.Path(r"C:\Users\cathe\OneDrive\Desktop\varynx\tests\integration\test_api_routes.py")
src = p.read_text(encoding="utf-8")
src = src.replace("        client = _make_client()\n        body = {\n            \"agent_id\": \"ag-bcse-phase2\"",
                  "        client, _ = _fresh_client()\n        body = {\n            \"agent_id\": \"ag-bcse-phase2\"")
src = src.replace("        client = _make_client()\n        body = {\n            \"agent_id\": \"ag-bcse-empty-alts\"",
                  "        client, _ = _fresh_client()\n        body = {\n            \"agent_id\": \"ag-bcse-empty-alts\"")
p.write_text(src, encoding="utf-8")
print("fixed:", "_make_client" not in src)