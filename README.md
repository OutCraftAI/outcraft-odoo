# Outcraft Cart Recovery for Odoo

A free Odoo 20.0 module (`outcraft_cart_recovery`) that sends abandoned eCommerce carts and confirmed website orders to an [Outcraft](https://outcraft.ai) "Custom API" trigger. Outcraft's AI agents then call, text and email the shopper to recover the cart.

The module runs on the merchant's Odoo server. It POSTs JSON to the trigger URL the merchant pastes in and does nothing else.

- Odoo version: **20.0** (the git branch is `20.0`, module version `20.0.1.0.0`)
- Depends on: `website_sale` (eCommerce) and `phone_validation` (standard, auto-installed with eCommerce)
- License: LGPL-3. Free: the manifest has no `price`.

## Install (merchants)

Requires Odoo 20.0 on-premise or on Odoo.sh, with the eCommerce app installed. Odoo Online (SaaS) can't run third-party modules that contain Python code, so this module can't be used there.

1. **Outcraft:** create an abandoned-checkout campaign with a **Custom API** trigger and copy the URL shown under **Send events to this endpoint** (`https://app.outcraft.ai/api/v1/trigger/<token>`).
2. **Install the module**, using one of these:
   - From the Odoo Apps Store: download the module and unzip it into your addons path.
   - On Odoo.sh: add it to your repository.
   - From source: copy the `outcraft_cart_recovery` folder into a directory on your `addons_path`.

   Then restart Odoo, go to **Apps**, choose **Update Apps List**, search for "Outcraft" and click **Activate**.
3. **Configure:** go to **Website → Configuration → Settings → Send carts to Outcraft**. The same steps are shown there. Tick the box (this is the opt-in, and it lists exactly what is sent), paste the trigger URL and click **Save**.
4. **Test:** click **Send test event**. Outcraft receives a sample `checkout/updated` immediately followed by its `checkout/completed` (unique_id `odoo-test-<timestamp>`), so the trigger shows an event and nobody is contacted. Odoo shows a green or red notification.
5. Optional: change **Abandoned after**. The default is 60 minutes.

Nothing is sent until the box is ticked and a URL is saved. Carts and orders from before the box was ticked are never sent. Untick the box to stop all sending. Uninstalling the module also deletes its settings, so a later reinstall starts disabled.

## How it works

The module has one scheduled action, **Outcraft: send abandoned carts and confirmed orders**. It runs every 15 minutes and also starts right away whenever a website order is confirmed. Each run does two things:

| Finds | Sends | Then marks the order |
|---|---|---|
| Website quotations in draft, with lines and a customer phone, not modified for *N* minutes (default 60) | `checkout/updated`, once per cart | `outcraft_state = updated` |
| Confirmed website orders | `checkout/completed` | `outcraft_state = completed` |

- **`unique_id`** is the Odoo `sale.order` id. A cart and the order it becomes share that id, which is how Outcraft matches `checkout/completed` to the earlier `checkout/updated` and stops outreach.
- **Checkout never makes an HTTP call.** Confirming an order only queues the scheduled action, which runs after the transaction commits. In the test, the event reached Outcraft 3 s after confirmation.
- **Failures are logged and retried.** Each send has a 5 s timeout, and every error is caught and logged as a `WARNING` (`Outcraft: ... not delivered: ...`). A failed send stays pending and is retried on the next run. Nothing older than 2 days is ever sent.
- **`cart_link`** is Odoo's own abandoned-cart recovery link, `/shop/cart?id=<id>&access_token=<token>`. It is the same link Odoo's recovery email uses.

## Data sent to Outcraft

Every event is a JSON POST to the configured trigger URL, and nothing goes anywhere else.

| Field | Source in Odoo |
|---|---|
| `outcraft_event` | `checkout/updated` (abandoned cart) or `checkout/completed` (confirmed order) |
| `unique_id` | sale order id |
| `phone` | customer phone, E.164 (falls back to the shipping address phone) |
| `email`, `first_name`, `last_name` | customer |
| `country_code`, `language`, `timezone` | customer country (ISO-2), language (e.g. `en`), timezone if set |
| `final_price`, `tax_price`, `shipping_price`, `currency` | order total, tax, delivery, currency (ISO-4217) |
| `items[]` | `{id: product id, name, quantity, price: unit price}` for each cart line |
| `discount_codes[]` | applied coupon and promotion codes (when Odoo's loyalty module is installed) |
| `shipping_details` | shipping name, street, street2, city, state code, zip, country, phone |
| `cart_link` | cart recovery link (abandoned carts only) |
| `context.odoo_order` | order reference, e.g. `S00042` |

## Store listing draft (apps.odoo.com)

**Name** (25 characters max): `Outcraft Cart Recovery` (22)

**Short description / summary**
> Send abandoned eCommerce carts to Outcraft for AI call, SMS and email recovery

**Full description** (this is what `static/description/index.html` contains)

> **Outcraft Cart Recovery**
>
> Send abandoned eCommerce carts to Outcraft, whose AI agents call, text and email the shopper to help them finish the order. Confirmed orders are sent too, so outreach stops as soon as the shopper pays.
>
> - **Abandoned carts.** Every 15 minutes, website carts that have a phone number and have not changed for 60 minutes (configurable) are sent to Outcraft once, with a link that reopens the cart.
> - **Confirmed orders.** When a website order is confirmed, it is sent with the same id as its cart. Outcraft then stops contacting that shopper and can report recovered revenue.
> - **Checkout is never slowed down.** Nothing is sent from the checkout itself. A scheduled action sends events in the background with a short timeout and retries failed sends on its next run.
>
> **Requirements:** an Outcraft account (this module only sends events; the calls, SMS and emails are made by Outcraft, a separate service), Odoo 20.0 with eCommerce, and Odoo on-premise or Odoo.sh. Like every third-party module that contains Python code, it can't be installed on Odoo Online.
>
> **Setup:** create a Custom API trigger in Outcraft, install the module, then in Website › Configuration › Settings tick "Send carts to Outcraft" and paste the trigger URL.
>
> **Data sent to Outcraft:** order id and reference, customer name, phone, email, country, language and timezone, cart lines (product id, name, quantity, unit price), totals (total, tax, shipping, currency), applied discount codes, shipping address, and a link that reopens the cart. Data is sent only after the administrator opts in, and only to the trigger URL they configure.

**What data is sent:** see the table above. The same list appears in the manifest `description`, in `index.html` and in the opt-in setting itself, as Odoo's vendor guidelines require for apps that send data to an external service.

### Listing assets

- `outcraft_cart_recovery/static/description/icon.png`: 256×256 PNG app icon, the white Outcraft mark on a purple gradient.
- `outcraft_cart_recovery/static/description/cover.png`: 1120×560 cover ("Win back abandoned checkouts"). It is the first entry in the manifest `images` key.
- `how_it_works.png`, `channels.png`, `recovered_revenue.png`, `conversation_review.png` (same folder): 1120×560 carousel images, listed in `images` in this order.

All listing images are 1120×560 (2:1), so keep new ones at that size.

### Before publishing

- **Vendor name.** `author` in `__manifest__.py` is "Outcraft". It must match the vendor name of your apps.odoo.com account exactly. Support goes to `hey@outcraft.ai`, set in the manifest `support` key and linked with `mailto:` in the description.
- **Description content.** `index.html` must have no external links other than YouTube or `mailto:`, and no JavaScript. The only link in the current file is the `mailto:` support address.
- **Repository.** Push this repo to GitHub with branch `20.0`, then register it on apps.odoo.com as `ssh://git@github.com/<org>/outcraft-odoo#20.0`.

## Development and tests

`dev/` is not a module: Odoo and the Apps Store ignore folders without a manifest. It contains:

- `docker-compose.yml`: Postgres 16, the official `odoo:20.0` image with this repo mounted as an addons path, and `catcher`, a tiny HTTP server that stands in for Outcraft and writes every body to `dev/out/captured.jsonl`.
- `shop.py`: drives a real guest checkout over HTTP. It adds products, submits the address with a phone, and pays with Odoo's Demo payment provider.
- `run-tests.sh`: the end-to-end test. It builds a fresh database, then checks seven scenarios: no opt-in, not idle yet, abandoned, paid, no phone, Outcraft down, and the retry.
- `odoo-shell.sh`: runs Python in an Odoo shell against the test database.

```sh
dev/run-tests.sh            # ~2 minutes; prints each scenario and every captured payload
open http://localhost:18069 # the test shop (database "shop", demo data)
docker compose -f dev/docker-compose.yml down -v
```

## Phone numbers at checkout

Merchants don't need to change anything. Odoo 20's checkout address form already requires a phone number (`portal` adds `phone` to the mandatory billing and delivery fields). The exceptions are checkouts that need no address at all, such as Odoo's quick checkout for event tickets, and express checkout with Apple Pay or Google Pay when the wallet doesn't share a phone. Carts from shoppers who leave before the address step have no phone, so they aren't sent.

## Known limitations

- **Merged carts.** Suppose a shopper opens the recovery link while another cart is already in their browser session. Odoo then moves the items into the session cart and cancels the old one, so the order is confirmed under a different id. Outcraft still gets a `checkout/completed` with the same phone and email, but its `unique_id` won't match the abandoned cart.
- **One `checkout/updated` per cart.** If the shopper edits the cart after it was sent, the change is not re-sent. Outcraft gets the final contents in `checkout/completed`.
- **Missing timezone for guests.** `timezone` is only sent when the customer has one, and guest checkouts usually don't.
