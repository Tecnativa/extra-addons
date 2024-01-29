# Copyright 2024 Tecnativa - Carolina Fernandez
# License AGPL-3 - See http://www.gnu.org/licenses/
import base64
from datetime import datetime, timedelta
from io import BytesIO

import pytz
import xlsxwriter

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HrAttendanceTimeRecord(models.TransientModel):
    _name = "hr.attendance.time.record.report.wizard"
    _description = "Hr Attendance Time Record Wizard"

    date_from = fields.Datetime(required=True)
    date_to = fields.Datetime(required=True)
    department_ids = fields.Many2many(
        comodel_name="hr.department",
        string="Departments",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    employee_ids = fields.Many2many(
        comodel_name="hr.employee",
        string="Employees",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company.id,
        required=True,
        string="Company",
    )
    datas = fields.Binary()

    @api.constrains("date_from", "date_to")
    def _check_date_range(self):
        for record in self:
            if record.date_from > record.date_to:
                raise ValidationError(_("Date from must be lower than Date to"))

    def _get_attendances_domain(self):
        domain = [
            ("check_in", ">=", self.date_from),
            ("check_out", "<=", self.date_to),
            ("employee_id.company_id", "=", self.company_id.id),
        ]
        if self.employee_ids:
            domain.append(("employee_id", "in", self.employee_ids.ids))
        if self.department_ids:
            domain.append(("department_id", "in", self.department_ids.ids))
        return domain

    def _get_report_columns_xlsx(self):
        res = {
            0: {"header": _("Department"), "field": "department_id", "width": 40},
            1: {"header": _("Employee"), "field": "employee_id", "width": 40},
            2: {"header": _("Real Check in"), "field": "check_in", "width": 40},
            3: {"header": _("Real Check Out"), "field": "check_out", "width": 40},
            4: {
                "header": _("Theoretical Check In"),
                "field": "theorical_check_in",
                "width": 40,
            },
            5: {
                "header": _("Theoretical Check Out"),
                "field": "theorical_check_out",
                "width": 40,
            },
            6: {
                "header": _("Company"),
                "field": "company_id",
                "width": 40,
            },
        }
        return res

    def _get_work_interval_for_employee(self, employee_id, check_in, check_out):
        employee_tz = pytz.timezone(employee_id.tz or "UTC")
        work_interval = employee_id.resource_id._get_work_interval(
            check_in.replace(tzinfo=employee_tz), check_out.replace(tzinfo=employee_tz)
        )[employee_id.resource_id]
        if work_interval:
            check_in = work_interval[0]
            check_out = work_interval[1]
        return check_in, check_out

    def _get_theorical_check_in_or_out_for_employee(
        self, employee_id, check_in, check_out, is_check_in
    ):
        check_in_theorical, check_out_theorical = self._get_work_interval_for_employee(
            employee_id, check_in, check_out
        )
        tolerance_time = self.company_id.overtime_employee_threshold
        check_theorical = check_in_theorical if is_check_in else check_out_theorical
        check = check_in if is_check_in else check_out
        check_theorical = check_theorical.replace(tzinfo=check.tzinfo)
        if (check_theorical - timedelta(minutes=tolerance_time)) > check:
            check_theorical = check
        return check_theorical

    def _prepare_data_report_xlsx(self, columns, workbook, report, attendances):
        row_num = 0
        alignment_format = workbook.add_format({"align": "center", "valign": "vcenter"})
        date_format = workbook.add_format(
            {
                "num_format": "dd/mm/yyyy hh:mm:ss",
                "align": "center",
                "valign": "vcenter",
            }
        )
        for attendance in attendances:
            row_num += 1
            for col_num, column in columns.items():
                field_name = column["field"]
                value = None
                if field_name in (
                    "check_in",
                    "check_out",
                    "theorical_check_out",
                    "theorical_check_in",
                ):
                    if field_name == "theorical_check_out":
                        value = self._get_theorical_check_in_or_out_for_employee(
                            attendance.employee_id,
                            attendance.check_in,
                            attendance.check_out,
                            False,
                        )
                    if field_name == "theorical_check_in":
                        value = self._get_theorical_check_in_or_out_for_employee(
                            attendance.employee_id,
                            attendance.check_in,
                            attendance.check_out,
                            True,
                        )
                    elif field_name == "check_in":
                        value = attendance.check_in
                    elif field_name == "check_out":
                        value = attendance.check_out if attendance.check_out else ""
                    report.write(row_num, col_num, value, date_format)
                elif field_name == "department_id":
                    value = (
                        attendance.employee_id.department_id.name
                        if attendance.employee_id.department_id
                        else ""
                    )
                    report.write(row_num, col_num, value, alignment_format)
                elif field_name == "employee_id":
                    value = attendance.employee_id.name
                    report.write(row_num, col_num, value, alignment_format)
                elif field_name == "company_id":
                    value = attendance.employee_id.company_id.name
                    report.write(row_num, col_num, value, alignment_format)
        return report

    def _prepare_header_report_xlsx(self, columns, workbook, report):
        header_format = workbook.add_format(
            {"bold": True, "align": "center", "valign": "vcenter"}
        )
        for col_num, column in columns.items():
            report.write(0, col_num, column["header"], header_format)

    def _set_width_columns(self, columns, report):
        for col_num, column in columns.items():
            report.set_column(col_num, col_num, column["width"])

    def _generate_report_xlsx(self, workbook, report, attendances):
        columns = self._get_report_columns_xlsx()
        self._set_width_columns(columns, report)
        self._prepare_header_report_xlsx(columns, workbook, report)
        return self._prepare_data_report_xlsx(columns, workbook, report, attendances)

    def _get_report_name_xlsx(self):
        date_from_str = datetime.strftime(self.date_from, "%Y-%m-%d")
        date_to_str = datetime.strftime(self.date_to, "%Y-%m-%d")
        return _("Time record {}-{}.xlsx").format(date_from_str, date_to_str)

    def button_export_xlsx(self):
        attendances = self.env["hr.attendance"].search(
            self._get_attendances_domain(), order="check_in, employee_id asc"
        )
        if not attendances:
            raise ValidationError(_("No records found"))
        temp_file = BytesIO()
        workbook = xlsxwriter.Workbook(temp_file, {"in_memory": True})
        worksheet = workbook.add_worksheet()

        self._generate_report_xlsx(workbook, worksheet, attendances)

        workbook.close()

        temp_file.seek(0)
        file_content = temp_file.read()
        temp_file.close()

        self.datas = base64.b64encode(file_content)

        filename = self._get_report_name_xlsx()

        action = {
            "name": _("Download HR Attendance Time Record Report"),
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=true&model=%s&field=datas&id=%s&filename=%s"
            % (self.id, self._name, self.id, filename),
            "target": "self",
        }
        return action
