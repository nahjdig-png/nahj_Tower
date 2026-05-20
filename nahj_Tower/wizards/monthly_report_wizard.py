from odoo import models, fields, api, _
from odoo.exceptions import UserError


class NahjMonthlyReportWizard(models.TransientModel):
    _name = 'nahj.monthly.report.wizard'
    _description = 'Monthly Summary Report Wizard'

    tower_id = fields.Many2one(
        'nahj.tower', string='Tower', required=True,
        default=lambda self: self.env.context.get('default_tower_id'))
    year = fields.Integer(
        string='Year', required=True,
        default=lambda self: fields.Date.today().year)
    month = fields.Selection([
        ('1', 'January'), ('2', 'February'), ('3', 'March'),
        ('4', 'April'), ('5', 'May'), ('6', 'June'),
        ('7', 'July'), ('8', 'August'), ('9', 'September'),
        ('10', 'October'), ('11', 'November'), ('12', 'December'),
    ], string='Month', required=True,
        default=lambda self: str(fields.Date.today().month))

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref(
            'nahj_Tower.action_report_monthly_summary'
        ).report_action(self)

    def action_view_subscriptions(self):
        """Quick navigation to the filtered list instead of PDF."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Subscriptions – %s %s') % (self.month, self.year),
            'res_model': 'nahj.subscription',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [
                ('tower_id', '=', self.tower_id.id),
                ('year',     '=', str(self.year)),
                ('month',    '=', self.month),
            ],
        }
