import datetime
from odoo import models, fields, api, _


class NahjTower(models.Model):
    _name = 'nahj.tower'
    _description = 'Tower'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'name'

    # ── Basic Info ──────────────────────────────────────────────────────────
    name = fields.Char(
        string='Tower Name', required=True, tracking=True,
        help='The name of the residential tower.'
    )
    address = fields.Text(string='Address', tracking=True)
    city = fields.Char(string='City', tracking=True)
    notes = fields.Text(string='Notes', tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    late_fee_percent = fields.Float(
        string='Late Fee %', digits=(5, 2), default=0.0, tracking=True,
        help='Percentage charged as late fee on overdue subscriptions (e.g. 5 = 5%).')

    # ── Relations ────────────────────────────────────────────────────────────
    unit_ids = fields.One2many('nahj.unit', 'tower_id', string='Units')
    expense_ids = fields.One2many('nahj.expense', 'tower_id', string='Expenses')
    asset_ids = fields.One2many('nahj.tower.asset', 'tower_id', string='Assets | الأصول')
    asset_count = fields.Integer(
        compute='_compute_asset_count', string='Assets | أصول')

    # ── Unit Statistics (computed) ───────────────────────────────────────────
    unit_count = fields.Integer(
        compute='_compute_unit_stats', string='Total Units')
    occupied_count = fields.Integer(
        compute='_compute_unit_stats', string='Occupied Units')
    vacant_count = fields.Integer(
        compute='_compute_unit_stats', string='Vacant Units')

    # ── Financial Statistics (computed) ──────────────────────────────────────
    total_subscriptions = fields.Float(
        compute='_compute_financials',
        string='Total Subscriptions Collected',
        digits=(16, 2))
    total_expenses = fields.Float(
        compute='_compute_financials',
        string='Total Expenses',
        digits=(16, 2))
    balance = fields.Float(
        compute='_compute_financials',
        string='Current Balance',
        digits=(16, 2))
    overdue_count = fields.Integer(
        compute='_compute_overdue', string='Overdue Units')

    # ── Compute Methods ──────────────────────────────────────────────────────
    @api.depends('asset_ids')
    def _compute_asset_count(self):
        for rec in self:
            rec.asset_count = len(rec.asset_ids)

    @api.depends('unit_ids', 'unit_ids.state')
    def _compute_unit_stats(self):
        for rec in self:
            rec.unit_count = len(rec.unit_ids)
            rec.occupied_count = len(
                rec.unit_ids.filtered(lambda u: u.state == 'occupied'))
            rec.vacant_count = len(
                rec.unit_ids.filtered(lambda u: u.state == 'vacant'))

    @api.depends(
        'unit_ids.subscription_ids.state',
        'unit_ids.subscription_ids.amount',
        'unit_ids.subscription_ids.amount_after_discount',
        'expense_ids.amount',
    )
    def _compute_financials(self):
        for rec in self:
            paid = rec.unit_ids.mapped('subscription_ids').filtered(
                lambda s: s.state == 'paid')
            rec.total_subscriptions = sum(paid.mapped('amount_after_discount'))
            rec.total_expenses = sum(rec.expense_ids.mapped('amount'))
            rec.balance = rec.total_subscriptions - rec.total_expenses

    @api.depends(
        'unit_ids.subscription_ids.state',
        'unit_ids.subscription_ids.year',
        'unit_ids.subscription_ids.month',
    )
    def _compute_overdue(self):
        today = datetime.date.today()
        for rec in self:
            overdue_units = set()
            for unit in rec.unit_ids:
                for sub in unit.subscription_ids:
                    if sub.state == 'unpaid':
                        if (int(sub.year) < today.year or
                                (int(sub.year) == today.year and
                                 int(sub.month) < today.month)):
                            overdue_units.add(unit.id)
                            break
            rec.overdue_count = len(overdue_units)

    # ── Action Buttons ───────────────────────────────────────────────────────
    def action_view_units(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Units'),
            'res_model': 'nahj.unit',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('tower_id', '=', self.id)],
            'context': {'default_tower_id': self.id},
        }

    def action_view_occupied_units(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Occupied Units | الوحدات المشغولة'),
            'res_model': 'nahj.unit',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('tower_id', '=', self.id), ('state', '=', 'occupied')],
            'context': {'default_tower_id': self.id},
        }

    def action_view_vacant_units(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vacant Units | الوحدات الشاغرة'),
            'res_model': 'nahj.unit',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('tower_id', '=', self.id), ('state', '=', 'vacant')],
            'context': {'default_tower_id': self.id},
        }

    def action_view_subscriptions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Subscriptions'),
            'res_model': 'nahj.subscription',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('tower_id', '=', self.id)],
            'context': {'default_tower_id': self.id},
        }

    def action_view_paid_subscriptions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Paid Subscriptions | الاشتراكات المدفوعة'),
            'res_model': 'nahj.subscription',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('tower_id', '=', self.id), ('state', '=', 'paid')],
            'context': {'default_tower_id': self.id},
        }

    def action_view_overdue_subscriptions(self):
        self.ensure_one()
        import datetime
        today = datetime.date.today()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Overdue Subscriptions | الاشتراكات المتأخرة'),
            'res_model': 'nahj.subscription',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [
                ('tower_id', '=', self.id),
                ('state', '=', 'unpaid'),
                ('is_overdue', '=', True),
            ],
            'context': {'default_tower_id': self.id},
        }

    def action_view_expenses(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Expenses'),
            'res_model': 'nahj.expense',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('tower_id', '=', self.id)],
            'context': {'default_tower_id': self.id},
        }

    def action_view_assets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assets | الأصول'),
            'res_model': 'nahj.tower.asset',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('tower_id', '=', self.id)],
            'context': {'default_tower_id': self.id},
        }

    # ── Scheduled Cron: Overdue Notifications ────────────────────────────────
    @api.model
    def _cron_notify_overdue_subscriptions(self):
        """
        Runs on the 1st of each month.
        Posts a chatter note on every tower that has unpaid subscriptions
        from the previous month, listing the overdue units.
        """
        today = datetime.date.today()
        if today.month == 1:
            check_year  = today.year - 1
            check_month = '12'
        else:
            check_year  = today.year
            check_month = str(today.month - 1)

        month_names = {
            '1': 'January', '2': 'February', '3': 'March', '4': 'April',
            '5': 'May',  '6': 'June', '7': 'July', '8': 'August',
            '9': 'September', '10': 'October', '11': 'November', '12': 'December',
        }
        month_names_ar = {
            '1': 'يناير', '2': 'فبراير', '3': 'مارس', '4': 'أبريل',
            '5': 'مايو', '6': 'يونيو', '7': 'يوليو', '8': 'أغسطس',
            '9': 'سبتمبر', '10': 'أكتوبر', '11': 'نوفمبر', '12': 'ديسمبر',
        }

        towers = self.search([])
        for tower in towers:
            overdue = self.env['nahj.subscription'].search([
                ('tower_id', '=', tower.id),
                ('year',     '=', check_year),
                ('month',    '=', check_month),
                ('state',    '=', 'unpaid'),
            ])
            if not overdue:
                continue

            total_overdue = sum(overdue.mapped('amount'))
            period = '%s / %s %s' % (
                month_names_ar.get(check_month, check_month),
                month_names.get(check_month, check_month),
                check_year,
            )

            lines = [
                '<p><b>⚠️ تنبيه اشتراكات متأخرة – Overdue Subscriptions Alert</b></p>',
                '<p>الفترة / Period: <b>%s</b></p>' % period,
                '<table style="border-collapse:collapse;width:100%%;font-size:12px;">',
                '<tr style="background:#1a2942;color:#fff;">',
                '<th style="padding:6px;text-align:right;">الوحدة</th>',
                '<th style="padding:6px;text-align:right;">الساكن</th>',
                '<th style="padding:6px;text-align:right;">الهاتف</th>',
                '<th style="padding:6px;text-align:left;">المبلغ</th>',
                '</tr>',
            ]
            for i, sub in enumerate(overdue):
                bg = '#fff5f5' if i % 2 == 0 else '#ffffff'
                lines.append(
                    '<tr style="background:%s;">'
                    '<td style="padding:5px 6px;border-bottom:1px solid #fde8e8;">%s</td>'
                    '<td style="padding:5px 6px;border-bottom:1px solid #fde8e8;">%s</td>'
                    '<td style="padding:5px 6px;border-bottom:1px solid #fde8e8;">%s</td>'
                    '<td style="padding:5px 6px;border-bottom:1px solid #fde8e8;color:#e74c3c;font-weight:bold;">%.2f</td>'
                    '</tr>' % (
                        bg,
                        sub.unit_id.name,
                        sub.unit_id.resident_id.name or '—',
                        sub.unit_id.resident_id.phone or '—',
                        sub.amount,
                    )
                )
            lines.append(
                '<tr style="background:#fde8e8;">'
                '<td colspan="3" style="padding:6px;font-weight:bold;">المجموع / Total</td>'
                '<td style="padding:6px;font-weight:bold;color:#e74c3c;">%.2f</td>'
                '</tr>' % total_overdue
            )
            lines.append('</table>')

            tower.message_post(
                body=''.join(lines),
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
