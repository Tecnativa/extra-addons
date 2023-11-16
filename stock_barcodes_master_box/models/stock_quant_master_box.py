# Copyright 2023 Tecnativa - Sergio Teruel
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import _, fields, models


class StockQuantMasterBox(models.Model):
    _name = "stock.quant.master.box"
    _description = "Master box"
    _order = "id DESC"

    name = fields.Char(
        "Master box ref.",
        copy=False,
        required=True,
        default=lambda self: self.env["ir.sequence"].next_by_code(
            "stock.quant.master.box"
        )
        or _("Unknown Master Box"),
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company.id,
    )
    active = fields.Boolean(default=True)
    package_ids = fields.One2many(
        comodel_name="stock.quant.package", inverse_name="master_box_id"
    )
