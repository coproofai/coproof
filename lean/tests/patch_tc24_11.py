path = '/app/tests/tcd24_lean_performance/test_tcd24_lean_performance.py'
content = open(path).read()
old = '        args=["theorem hello : True := trivial"],\n    )\n    response = async_result.get'
new = '        args=["theorem hello : True := trivial"],\n        queue="lean_queue",\n    )\n    response = async_result.get'
assert old in content, 'ERROR: pattern not found in file'
open(path, 'w').write(content.replace(old, new))
print('patched OK')
