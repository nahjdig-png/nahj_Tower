from odoo import models, api

MONTHS_EN = {
    '1': 'January', '2': 'February', '3': 'March', '4': 'April',
    '5': 'May', '6': 'June', '7': 'July', '8': 'August',
    '9': 'September', '10': 'October', '11': 'November', '12': 'December',
}
MONTHS_AR = {
    '1': 'يناير', '2': 'فبراير', '3': 'مارس', '4': 'أبريل',
    '5': 'مايو', '6': 'يونيو', '7': 'يوليو', '8': 'أغسطس',
    '9': 'سبتمبر', '10': 'أكتوبر', '11': 'نوفمبر', '12': 'ديسمبر',
}


class NahjReportSubscriptionReceipt(models.AbstractModel):
    _name = 'report.nahj_tower.report_subscription_receipt'
    _description = 'Subscription Receipt'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['nahj.subscription'].browse(docids)
        return {
            'docs': docs,
            'months_en': MONTHS_EN,
            'months_ar': MONTHS_AR,
            'company': self.env.company,
        }


class NahjReportMonthlySummary(models.AbstractModel):
    _name = 'report.nahj_tower.report_monthly_summary'
    _description = 'Monthly Summary Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        from datetime import date as _date
        wizard = self.env['nahj.monthly.report.wizard'].browse(docids)
        tower  = wizard.tower_id
        year   = str(wizard.year)
        month  = wizard.month

        subscriptions = self.env['nahj.subscription'].search([
            ('tower_id', '=', tower.id),
            ('year',     '=', year),
            ('month',    '=', month),
        ], order='unit_id')

        expenses = self.env['nahj.expense'].search([
            ('tower_id', '=', tower.id),
        ]).filtered(
            lambda e: e.date and
                      e.date.year == int(year) and
                      e.date.month == int(month)
        )

        paid_subs   = subscriptions.filtered(lambda s: s.state == 'paid')
        unpaid_subs = subscriptions.filtered(lambda s: s.state == 'unpaid')

        # Expense breakdown by category
        cat_totals = {}
        for exp in expenses:
            cat = exp.category_id.name if exp.category_id else 'Other'
            cat_totals[cat] = cat_totals.get(cat, 0.0) + exp.amount

        total_collected = sum(paid_subs.mapped('amount'))
        total_expected  = sum(subscriptions.mapped('amount'))
        total_expenses  = sum(expenses.mapped('amount'))

        return {
            'docs': wizard,
            'tower': tower,
            'year': year,
            'month': month,
            'month_en': MONTHS_EN.get(month, month),
            'month_ar': MONTHS_AR.get(month, month),
            'subscriptions': subscriptions,
            'paid_subs': paid_subs,
            'unpaid_subs': unpaid_subs,
            'expenses': expenses,
            'cat_totals': cat_totals,
            'total_collected': total_collected,
            'total_expected': total_expected,
            'total_expenses': total_expenses,
            'balance': total_collected - total_expenses,
            'collection_rate': (total_collected / total_expected * 100)
                               if total_expected else 0.0,
            'company': self.env.company,
            'print_date': _date.today(),
        }
