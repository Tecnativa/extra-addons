# Copyright 2024 Tecnativa - Sergio Teruel

from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _compute_amount_all(self):
        res = super()._compute_amount_all()
        for pick in self:
            delivery_lines = pick.sale_id.order_line.filtered("is_delivery")
            delivery_amount_untaxed = sum(delivery_lines.mapped("price_subtotal"))
            delivery_amount_taxed = sum(delivery_lines.mapped("price_tax"))
            delivery_amount_total = delivery_amount_untaxed + delivery_amount_taxed
            pick.update(
                {
                    "amount_untaxed": pick.amount_untaxed + delivery_amount_untaxed,
                    "amount_tax": pick.amount_tax + delivery_amount_taxed,
                    "amount_total": pick.amount_total + delivery_amount_total,
                }
            )
        return res
