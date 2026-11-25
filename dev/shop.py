"""Drive a real guest checkout on the local Odoo storefront (stdlib only).

  python3 shop.py cart <cookie_file> [phone]   add a product, fill the address (with phone)
  python3 shop.py pay  <cookie_file>           pay the cart with the Demo provider
"""
import http.cookiejar
import json
import re
import sys
import urllib.parse
import urllib.request

BASE = "http://localhost:18069"
cmd, cookie_file = sys.argv[1], sys.argv[2]
jar = http.cookiejar.LWPCookieJar(cookie_file)
if cmd == "pay":
    jar.load(ignore_discard=True)
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def get(path):
    return opener.open(BASE + path, timeout=60).read().decode()


def post(path, data):
    return opener.open(BASE + path, urllib.parse.urlencode(data).encode(), timeout=60).read().decode()


def rpc(path, **params):
    req = urllib.request.Request(BASE + path, json.dumps({"jsonrpc": "2.0", "params": params}).encode(),
                                 {"Content-Type": "application/json"})
    res = json.loads(opener.open(req, timeout=60).read())
    if "error" in res:
        raise SystemExit(json.dumps(res["error"], indent=1)[:2000])
    return res.get("result")


def csrf(html):
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


if cmd == "cart":
    phone = sys.argv[3] if len(sys.argv) > 3 else ""
    get("/shop")
    rpc("/shop/cart/add", product_template_id=12, product_id=21, quantity=2)  # Storage Box
    rpc("/shop/cart/add", product_template_id=14, product_id=26, quantity=1)  # Pedal Bin
    token = csrf(get("/shop/address"))
    print(post("/shop/address/submit", {
        "csrf_token": token, "address_type": "billing", "use_delivery_as_billing": "true",
        "name": "Jane Shopper", "email": "jane@example.com", "phone": phone,
        "street": "950 Mason Street", "street2": "Apt 4B", "city": "San Francisco", "zip": "94108",
        "country_id": "233", "state_id": "13",
    }))
    print("checkout page:", len(get("/shop/checkout")), "bytes")
elif cmd == "pay":
    page = get("/shop/payment")
    order_id = re.search(r'/shop/payment/transaction/(\d+)', page).group(1)
    access_token = re.search(r'data-access-token="([^"]+)"', page).group(1)
    pm_id, provider_id = map(int, re.search(
        r'data-payment-option-id="(\d+)" data-payment-method-code="demo" data-provider-id="(\d+)"', page).groups())
    tx = rpc(f"/shop/payment/transaction/{order_id}", access_token=access_token,
             provider_id=provider_id, payment_method_id=pm_id, token_id=None, flow="direct",
             tokenization_requested=False, landing_route="/shop/payment/validate", is_validation=False)
    print("transaction:", tx.get("reference"))
    rpc("/payment/demo/simulate_payment", reference=tx["reference"], payment_details="4242", simulated_state="done")
    rpc("/payment/process")
    get("/shop/payment/validate")
    print("paid order id", order_id)
jar.save(ignore_discard=True)
