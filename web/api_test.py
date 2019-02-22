from os.path import exists
from os import unlink

from requests import Session
from base64 import b64encode

URL = "http://127.0.0.1:10000"
TOKEN_PATH="/tmp/k"

s = Session()
if not exists(TOKEN_PATH):
    login_resp = s.post(f"{URL}/api/login", json={"username": "1@3", "password": "33333333"}).json()
    token = login_resp["token"]
    with open(TOKEN_PATH,"w") as f:
        f.write(token)
else:
    with open(TOKEN_PATH) as f:
        token = f.read()
s.headers["X-Token"] = token
print(token)
resp=s.post(f"{URL}/api/messages", json={"date": "2017"}).json()
print(resp)
if resp["status"]==4:
    unlink(TOKEN_PATH)
    exit()
resp=s.post(f"{URL}/api/dates").json()
print(resp)
exit(0)
print(s.post(f"{URL}/api/submit",json={"data":b64encode(open("/tmp/logs.txt","rb").read()).decode("utf-8")}))