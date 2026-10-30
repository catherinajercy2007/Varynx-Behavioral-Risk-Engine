import sys; sys.path.insert(0,'.')
try:
    exec(open('write_aws.py').read())
except Exception as e:
    import traceback; traceback.print_exc()