import logging
import re
import time
from datetime import timedelta

import requests

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

TIMEOUT = 5  # seconds; Outcraft answers in well under one


def _post(url, payload):
    """POST one event to Outcraft. Never raises: a failure is logged and returns False."""
    try:
        requests.post(url, json=payload, timeout=TIMEOUT).raise_for_status()
        return True
    except Exception as e:  # noqa: BLE001 - Outcraft must never break Odoo
        _logger.warning("Outcraft: %s for order %s not delivered: %s",
                        payload.get("outcraft_event"), payload.get("unique_id"), e)
        return False


def _clean(values):
    return {k: v for k, v in values.items() if v or v == []}


def _phone(partner):
    return partner.phone and (partner._phone_format(fname="phone") or partner.phone)


def _split_name(name):
    first, _, last = (name or "").partition(" ")
    return first, last


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    outcraft_consent = fields.Boolean("Send customer data to Outcraft", config_parameter="outcraft.consent")
    outcraft_trigger_url = fields.Char("Outcraft trigger URL", config_parameter="outcraft.trigger_url")
    outcraft_delay = fields.Integer("Abandoned after (minutes)", config_parameter="outcraft.delay", default=60)

    def action_outcraft_test(self):
        """Send a sample cart and, right after, its completion, so Outcraft shows the event but never contacts anyone."""
        self.ensure_one()
        if not (self.outcraft_consent and self.outcraft_trigger_url):
            raise UserError(self.env._("Tick \"Send carts to Outcraft\" and paste your Outcraft trigger URL first."))
        company = self.env.company
        sample = _clean({
            "unique_id": f"odoo-test-{int(time.time())}",
            "phone": _phone(company.partner_id),
            "email": company.email,
            "first_name": "Test",
            "last_name": "Shopper",
            "country_code": company.country_id.code,
            "final_price": "10.00",
            "currency": company.currency_id.name,
            "items": [{"id": "test", "name": "Test product", "quantity": 1, "price": "10.00"}],
            "cart_link": f"{(self.website_id or self).get_base_url()}/shop/cart",
            "context": {"odoo_test_event": True},
        })
        sent = all(_post(self.outcraft_trigger_url, {**sample, "outcraft_event": event})
                   for event in ("checkout/updated", "checkout/completed"))
        message = (self.env._("Test event sent. Open your trigger in Outcraft to see it. Click Save here if you haven't.")
                   if sent else self.env._("Outcraft did not accept the test event. Check the URL; details are in the server log."))
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"message": message, "type": "success" if sent else "danger"}}


class SaleOrder(models.Model):
    _inherit = "sale.order"

    outcraft_state = fields.Selection(
        [("updated", "Abandoned cart sent"), ("completed", "Order sent")], "Outcraft", copy=False, readonly=True)

    @api.model
    def _outcraft_url(self):
        icp = self.env["ir.config_parameter"].sudo()
        return icp.get_bool("outcraft.consent") and icp.get_str("outcraft.trigger_url")

    def _outcraft_payload(self, event):
        self.ensure_one()
        partner, ship = self.partner_id, self.partner_shipping_id
        money = lambda amount: f"{amount:.{self.currency_id.decimal_places}f}"  # noqa: E731
        first, last = _split_name(partner.name)
        ship_first, ship_last = _split_name(ship.name)
        codes = []
        if "applied_coupon_ids" in self._fields:  # sale_loyalty installed
            codes = (self.applied_coupon_ids.mapped("code") + self.code_enabled_rule_ids.mapped("code"))
        payload = _clean({
            "outcraft_event": event,
            "unique_id": str(self.id),
            "phone": _phone(partner) or _phone(ship),
            "email": partner.email,
            "first_name": first,
            "last_name": last,
            "country_code": partner.country_id.code,
            "language": partner.lang and re.split("[_@]", partner.lang)[0],
            "timezone": partner.tz,
            "final_price": money(self.amount_total),
            "currency": self.currency_id.name,
            "tax_price": money(self.amount_tax),
            "shipping_price": money(self.amount_delivery),
            "items": [{
                "id": str(line.product_id.id),
                "name": line.product_id.display_name,
                "quantity": int(line.product_uom_qty) if line.product_uom_qty.is_integer() else line.product_uom_qty,
                "price": money(line.price_unit),
            } for line in self.website_order_line],
            "discount_codes": [c for c in codes if c],
            "shipping_details": _clean({
                "first_name": ship_first,
                "last_name": ship_last,
                "address1": ship.street,
                "address2": ship.street2,
                "city": ship.city,
                "province_code": ship.state_id.code,
                "zip": ship.zip,
                "country_code": ship.country_id.code,
                "phone": _phone(ship),
            }),
            "context": {"odoo_order": self.name},
        })
        if event == "checkout/updated":
            payload["cart_link"] = (f"{self.get_base_url()}/shop/cart"
                                    f"?id={self.id}&access_token={self._portal_ensure_token()}")
        return payload

    @api.model
    def _cron_outcraft(self):
        """Send abandoned carts (checkout/updated) and confirmed orders (checkout/completed).
        Failed sends stay pending and are retried on the next run."""
        url = self._outcraft_url()
        if not url:
            return
        icp = self.env["ir.config_parameter"].sudo()
        delay = icp.get_int("outcraft.delay") or 60
        now = fields.Datetime.now()
        opted_in_at = icp.search([("key", "=", "outcraft.consent")]).write_date
        since = max(now - timedelta(days=2), opted_in_at)  # nothing stale, nothing from before opt-in
        orders = self.sudo().search([
            ("website_id", "!=", False),
            ("state", "=", "sale"),
            ("outcraft_state", "!=", "completed"),
            ("date_order", ">=", since),  # confirmation date
        ])
        carts = self.sudo().search([
            ("website_id", "!=", False),
            ("state", "=", "draft"),
            ("order_line", "!=", False),
            ("outcraft_state", "=", False),
            ("write_date", "<=", now - timedelta(minutes=delay)),
            ("write_date", ">=", since),
            "|", ("partner_id.phone", "!=", False), ("partner_shipping_id.phone", "!=", False),
        ])
        cron = self.env["ir.cron"]
        cron._commit_progress(remaining=len(orders) + len(carts))
        for order in orders + carts:
            event, state = ("checkout/completed", "completed") if order.state == "sale" else ("checkout/updated", "updated")
            try:
                payload = order._outcraft_payload(event)
            except Exception:  # noqa: BLE001
                _logger.exception("Outcraft: could not build payload for %s", order.name)
                payload = None
            if payload and _post(url, payload):
                order.outcraft_state = state
            if not cron._commit_progress(1):
                break

    def action_confirm(self):
        res = super().action_confirm()
        # No HTTP call here: just ask the cron to run now, after this transaction commits.
        if self.filtered("website_id") and self._outcraft_url():
            if cron := self.env.ref("outcraft_cart_recovery.ir_cron_outcraft", raise_if_not_found=False):
                cron.sudo()._trigger()
        return res
