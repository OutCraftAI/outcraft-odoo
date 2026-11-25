{
    "name": "Outcraft Cart Recovery",
    "version": "20.0.1.0.0",
    "summary": "Send abandoned eCommerce carts to Outcraft for AI call, SMS and email recovery",
    "description": """
Sends abandoned website carts and confirmed website orders to your Outcraft
"Custom API" trigger. Requires an Outcraft account.

Nothing is sent until an administrator sets the trigger URL and ticks the
opt-in box in Website settings. Data sent per cart or order: order id and
reference, customer name, phone, email, country, language and timezone, cart
lines (product id, name, quantity, unit price), totals (total, tax, shipping,
currency), applied discount codes, shipping address, and a link back to the
cart. Only carts with a phone number are sent as abandoned.
""",
    "category": "Website/Website",
    "author": "Outcraft",
    "website": "https://outcraft.ai",
    "license": "LGPL-3",
    "depends": ["website_sale", "phone_validation"],
    "data": [
        "data/ir_cron.xml",
        "views/res_config_settings_views.xml",
    ],
    "images": ["static/description/cover.png"],
    "installable": True,
    "uninstall_hook": "uninstall_hook",
}
