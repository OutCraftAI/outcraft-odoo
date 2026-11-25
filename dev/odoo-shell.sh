#!/bin/sh
# Run Python from stdin in an Odoo shell on the test database: ./odoo-shell.sh < script.py
docker compose exec -T odoo odoo shell -d shop --db_host=db --db_user=odoo --db_password=odoo \
  --no-http --log-level=warn 2>&1 | { grep -v -e markdown2 -e Warning || true; }
