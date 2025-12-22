from kiteconnect import KiteConnect

API_KEY = "mw10aq5zzfouogfs"
API_SECRET = "4emn4qmkj1dn9bbws17ymyyea6dxrwil"

kite = KiteConnect(api_key=API_KEY)

print("===================================")
print("OPEN THIS URL IN BROWSER AND LOGIN:")
print(kite.login_url())
print("===================================")

request_token = input("Paste request token here: ").strip()

data = kite.generate_session(request_token, api_secret=API_SECRET)

print("\nACCESS TOKEN (COPY THIS):")
print(data["access_token"])
