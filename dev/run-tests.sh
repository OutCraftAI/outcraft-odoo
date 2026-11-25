#!/bin/sh
# End-to-end test on a fresh Odoo 20 database, with dev/catcher.py standing in for Outcraft.
# Usage: dev/run-tests.sh   (needs Docker; uses port 18069)
set -e
cd "$(dirname "$0")"
SH=./odoo-shell.sh
URL=http://catcher:8000/api/v1/trigger/test-token

step()     { printf '\n=== %s\n' "$*"; }
settings() { echo "env['res.config.settings'].create($1).execute(); env.cr.commit()" | $SH; }
cron()     { echo "env.ref('outcraft_cart_recovery.ir_cron_outcraft').method_direct_trigger()" | $SH; }
cron_2h_later() {  # run the real cron as if 2 hours had passed (patches now(); no data is rewritten)
  echo "from unittest.mock import patch; from datetime import timedelta; from odoo import fields
later = fields.Datetime.now() + timedelta(hours=2)
with patch.object(fields.Datetime, 'now', lambda *a, **k: later):
    env.ref('outcraft_cart_recovery.ir_cron_outcraft').method_direct_trigger()" | $SH; }
last_order() { echo "o = env['sale.order'].search([('website_id','!=',False)], order='id desc', limit=1); print('   order', o.name, 'id', o.id, 'state', o.state, 'phone', o.partner_id.phone, 'outcraft_state', o.outcraft_state)" | $SH; }
count()    { echo "   catcher has received $(cat out/captured.jsonl 2>/dev/null | wc -l | tr -d ' ') event(s) in total"; }
wait_sale() { for i in $(seq 1 30); do echo "print(env['sale.order'].search([('website_id','!=',False)], order='id desc', limit=1).state)" | $SH | grep -q sale && return; sleep 1; done; }

step "Fresh stack: postgres + catcher, then a new database with website_sale, payment_demo, outcraft_cart_recovery"
docker compose down -v --remove-orphans >/dev/null 2>&1 || true
rm -rf out && mkdir out
docker compose up -d db catcher
sleep 3
docker compose run --rm odoo odoo -d shop --with-demo -i website_sale,payment_demo,outcraft_cart_recovery --stop-after-init --log-level=warn 2>&1 | grep -v -e markdown2 -e Container
docker compose up -d odoo
until curl -sf -o /dev/null http://localhost:18069/web/login; do sleep 1; done
echo "   installed: $(echo "print(env['ir.module.module'].search([('name','=','outcraft_cart_recovery')]).state)" | $SH)"

step "1. URL set, opt-in OFF: abandoned cart with phone + cron + paid order -> expect nothing sent"
settings "{'outcraft_consent': False, 'outcraft_trigger_url': '$URL'}"
python3 shop.py cart out/1.cookies "+1 415 555 0100" >/dev/null
cron_2h_later
python3 shop.py pay out/1.cookies; wait_sale; cron
last_order; count

step "2. Opt-in ON: order 41 and demo orders predate opt-in -> not sent; new cart with phone not idle for 60 min yet -> not sent"
settings "{'outcraft_consent': True, 'outcraft_trigger_url': '$URL'}"
python3 shop.py cart out/2.cookies "+1 415 555 0123" >/dev/null
cron; last_order; count

step "3. Two hours later the cart is still untouched -> ONE checkout/updated (cron run twice)"
cron_2h_later; cron_2h_later
last_order; count

step "4. Shopper pays that cart on the storefront -> checkout/completed with the same unique_id"
python3 shop.py pay out/2.cookies; wait_sale; sleep 5
last_order; count

step "5. Cart from a visitor who never gave a phone -> nothing sent"
python3 shop.py cart out/5.cookies "" | head -1
cron_2h_later
last_order; count

step "6. Outcraft unreachable (catcher stopped): cart + cron + checkout still work"
docker compose stop catcher
python3 shop.py cart out/6.cookies "+1 415 555 0166" >/dev/null
cron_2h_later
start=$(date +%s); python3 shop.py pay out/6.cookies; echo "   checkout took $(( $(date +%s) - start ))s"
wait_sale; sleep 5; last_order
docker compose logs odoo --since 2m 2>&1 | grep "Outcraft" | sed 's/^/   /' | tail -4

step "7. Outcraft back: next cron run retries and delivers the pending checkout/completed"
docker compose start catcher; sleep 2; cron
last_order; count

step "Captured payloads (out/captured.jsonl)"
python3 -c "
import json
for i, line in enumerate(open('out/captured.jsonl'), 1):
    print(f'--- event {i}'); print(json.dumps(json.loads(line), indent=2))"
