from . import models


def uninstall_hook(env):
    # Forget the opt-in and URL, so a later reinstall starts disabled.
    env["ir.config_parameter"].sudo().search([("key", "=like", "outcraft.%")]).unlink()
