# Copyright 2018 Tecnativa - Sergio Teruel
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    security_price_control = fields.Boolean(
        string="Security price control",
        groups="product_cost_security.group_product_cost",
    )

    def _commercial_fields(self):
        res = super()._commercial_fields()
        res.append("security_price_control")
        return res

    def _fields_sync(self, values):
        """Sync field as sudo due to security group restriction on commercial
        field "security_price_control"
        """
        return super(ResPartner, self.sudo())._fields_sync(values)
