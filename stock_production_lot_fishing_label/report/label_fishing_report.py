# Copyright 2023 Tecnativa - Carlos Roca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import time

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero


class LabelFishingReportMixin(models.AbstractModel):
    _name = "label.fishing.report.mixin"
    based_model = ""

    def _compute_langs_print_partner(self, model_name, line):
        report_langs = ["ca_ES", "es_ES", "en_GB", "fr_FR"]
        print_partner = False
        if model_name not in ["stock.quant", "stock.quant.master.box"]:
            move_line = (
                line if model_name == "stock.move.line" else line["move_line_id"]
            )
            moves = self.env["stock.move"].browse(
                list(move_line["move_id"]._rollup_move_dests({move_line["move_id"].id}))
            )
            move_sale = moves.filtered("sale_line_id")[:1]
            if move_sale:
                print_partner = True
                lang = move_sale.partner_id.lang
                if lang in ["es_ES", "ca_ES", "fr_FR"]:
                    report_langs = ["es_ES"]
                    if lang != "es_ES":
                        report_langs.append(lang)
                else:
                    report_langs = ["en_GB"]
                    if lang not in ["en_US", "en_GB"]:
                        report_langs.append(lang)
        return report_langs, print_partner

    def _get_summarized_lines(self, lines):
        summarized_lines = []
        while lines:
            reference_line = lines[0]
            net_weight = (
                reference_line.product_id.weight_type != "variable"
                and reference_line.product_id.net_weight
                or 1.0
            )
            if reference_line._name == "stock.quant":
                filtered_quants = lines.filtered(
                    lambda line: line.product_id == reference_line.product_id
                    and line.package_id.master_box_id
                    == reference_line.package_id.master_box_id
                    and line.lot_id == reference_line.lot_id
                )
                lines -= filtered_quants
                qty_done = sum(filtered_quants.mapped("quantity"))
                summarized_lines.append(
                    {
                        "id": str(reference_line.product_id.id)
                        + str(reference_line.package_id.master_box_id.id),
                        "lot_id": reference_line.lot_id,
                        "product_id": reference_line.product_id,
                        "product_uom_id": reference_line.product_uom_id,
                        "qty_done": qty_done,
                        "result_package_id": reference_line.package_id,
                        "result_package_ids": filtered_quants.package_id,
                        "master_box_id": reference_line.package_id.master_box_id,
                        "net_weight": round(qty_done * net_weight, 2),
                    }
                )
            else:
                picking_smls = reference_line.move_line_id.picking_id.move_line_ids
                filtered_smls = picking_smls.filtered(
                    lambda line: line.product_id == reference_line.product_id
                    and line.result_package_id.master_box_id
                    == reference_line.result_package_id.master_box_id
                    and line.lot_id == reference_line.lot_id
                )
                lines = lines.filtered(
                    lambda line: line.move_line_id not in filtered_smls
                )
                qty_done = sum(filtered_smls.mapped("qty_done"))
                summarized_lines.append(
                    {
                        "id": str(reference_line.product_id.id)
                        + str(reference_line.result_package_id.master_box_id.id),
                        "lot_id": reference_line.lot_id,
                        "product_id": reference_line.product_id,
                        "label_qty": reference_line.label_qty,
                        "picking_partner_id": reference_line.move_line_id.picking_partner_id,
                        "move_id": reference_line.move_line_id.move_id,
                        "product_uom_id": reference_line.move_line_id.product_uom_id,
                        "qty_done": qty_done,
                        "result_package_id": reference_line.result_package_id,
                        "result_package_ids": filtered_smls.result_package_id,
                        "move_line_id": reference_line.move_line_id,
                        "master_box_id": reference_line.result_package_id.master_box_id,
                        "net_weight": round(qty_done * net_weight, 2),
                    }
                )
        return summarized_lines

    @api.model
    def get_multilang_limited_value(self, langs, record, field, separator, limit=None):
        if not record or field not in record._fields:
            return ""
        values = []
        for lang in langs:
            values.append(record.with_context(lang=lang)[field])
        res = separator.join(values)
        if limit and len(res) > limit:
            res = res[:limit] + "..."
        return res

    @api.model
    def _get_report_values(self, docids, data=None):
        model_name = self.based_model
        summarized = False
        lines_to_print = self.env[model_name].browse(docids)
        report_langs = {}
        client_elaborations = {}
        if model_name in ["stock.picking.line.print", "stock.quant.master.box"]:
            if model_name == "stock.quant.master.box":
                summarized = True
                master_boxes = lines_to_print
                quants = master_boxes.package_ids.quant_ids
                lines_to_print = self._get_summarized_lines(quants)
            else:
                wiz = lines_to_print[:1].wizard_id
                if wiz.barcode_report == self.env.ref(
                    "stock_production_lot_fishing_label.action_label_master_box_report"
                ):
                    summarized = True
                    lines_to_print = self._get_summarized_lines(lines_to_print)
            if not lines_to_print:
                raise UserError(_("Master box is empty"))
        for line in lines_to_print:
            langs, client_el = self._compute_langs_print_partner(model_name, line)
            report_langs[line["id"]] = langs
            client_elaborations[line["id"]] = client_el
        docargs = {
            "summarized": summarized,
            "env": self.env,
            "doc_ids": docids,
            "doc_model": model_name,
            "docs": lines_to_print,
            "time": time,
            "report_langs": report_langs,
            "float_is_zero": float_is_zero,
            "show_nutritional_table": self.env.context.get(
                "show_nutritional_table", False
            ),
            "use_second_page": self.env.context.get("use_second_page", False),
            "client_elaborations": client_elaborations,
            "company_id": self.env.company,
            "get_gs1_barcode": self.env["barcode.gs1.label.mixin"].get_gs1_barcode,
            "product_filter": self.env.ref(
                "stock_production_lot_fishing_label.filter_product_one_label"
            ),
            "get_multilang_limited_value": self.get_multilang_limited_value,
        }
        return docargs


# pylint: disable=R7980
class LabelFishingReport(models.AbstractModel):
    _inherit = "label.fishing.report.mixin"
    _name = "report.stock_production_lot_fishing_label.label_fishing"
    _description = "Report Fishing Label"
    based_model = "stock.picking.line.print"


# pylint: disable=R7980
class LabelFishingReportNutri(models.AbstractModel):
    _inherit = "label.fishing.report.mixin"
    _name = "report.stock_production_lot_fishing_label.label_fishing_nutri"
    _description = "Report Fishing Label"
    based_model = "stock.picking.line.print"

    @api.model
    def _get_report_values(self, docids, data=None):
        self = self.with_context(use_second_page=True, show_nutritional_table=True)
        return super()._get_report_values(docids, data=data)


# pylint: disable=R7980
class LabelFishingReportMasterBox(models.AbstractModel):
    _inherit = "label.fishing.report.mixin"
    _name = "report.stock_production_lot_fishing_label.label_master_box"
    _description = "Report Fishing Label"
    based_model = "stock.picking.line.print"


# pylint: disable=R7980
class LabelFishingReportMove(models.AbstractModel):
    _inherit = "label.fishing.report.mixin"
    _name = "report.stock_production_lot_fishing_label.label_fishing_move"
    _description = "Report Fishing Label Move"
    based_model = "stock.move.line"


# pylint: disable=R7980
class LabelFishingReportQuant(models.AbstractModel):
    _inherit = "label.fishing.report.mixin"
    _name = "report.stock_production_lot_fishing_label.label_fishing_quant"
    _description = "Report Fishing Label Quant"
    based_model = "stock.quant"


class LabelFishingReportStockQuantMasterBox(models.AbstractModel):
    _inherit = "label.fishing.report.mixin"
    _name = "report.stock_production_lot_fishing_label.label_master_box_sqmb"
    _description = "Report Fishing Label Master Box"
    based_model = "stock.quant.master.box"
