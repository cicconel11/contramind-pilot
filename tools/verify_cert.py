import sys, base64, json, requests
from nacl.signing import VerifyKey

def b64url_dec(s: str) -> bytes:
    pad = '=' * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)

jws = sys.argv[1]
h,p,s = jws.split('.')
header = json.loads(b64url_dec(h))
payload = json.loads(b64url_dec(p))
keys = requests.get('http://localhost:8082/keys').json()['keys']
kid = header['kid']
key_b64 = keys[kid]
vk = VerifyKey(base64.b64decode(key_b64))
vk.verify((h+'.'+p).encode(), b64url_dec(s))
print('VALID', payload)
