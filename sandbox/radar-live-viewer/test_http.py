"""Check local health/auth rejection without starting radar acquisition."""
import json
import urllib.error
import urllib.request

base='http://127.0.0.1:8766'
state=json.load(urllib.request.urlopen(base+'/api/health',timeout=3))
assert state['service']=='TrueRehab local radar diagnostic'
print('HEALTH',state['mode'])
requests=[urllib.request.Request(base+'/api/start',method='POST'),
          urllib.request.Request(base+'/api/health',headers={'Host':'untrusted.invalid'})]
for request in requests:
    try:
        urllib.request.urlopen(request,timeout=3)
        raise AssertionError('Unauthorized request succeeded')
    except urllib.error.HTTPError as error:
        assert error.code==403
        print('SECURITY_CHECK',error.code)
