# Copyright 2024 Tecnativa - Sergio Teruel
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Stock picking delivery valued",
    "summary": "Display in picking delivery valued amount",
    "version": "16.0.1.0.0",
    "development_status": "Beta",
    "category": "Inventory",
    "website": "https://gitlab.tecnativa.com/Tecnativa/marmenorda-odoo",
    "author": "Tecnativa",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "maintainers": ["sergio-teruel", "carlosdauden"],
    "depends": [
        "delivery",
        "stock_picking_report_valued",
    ],
    "data": ["views/report_deliveryslip.xml", "views/report_invoice.xml"],
}
