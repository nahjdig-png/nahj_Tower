from odoo import models, fields, api, _


class NahjTowerAsset(models.Model):
    _name = 'nahj.tower.asset'
    _description = 'Tower Asset | أصل البرج'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'tower_id, name'

    # ── Core Fields ──────────────────────────────────────────────────────────
    name = fields.Char(
        string='Asset Name | اسم الأصل', required=True, tracking=True)
    tower_id = fields.Many2one(
        'nahj.tower', string='Tower | البرج',
        required=True, ondelete='cascade', index=True, tracking=True)
    asset_type = fields.Selection([
        ('elevator',   'Elevator | أسانسير'),
        ('pump',       'Water Pump | ماتور مياه'),
        ('generator',  'Generator | مولد كهرباء'),
        ('tank',       'Water Tank | خزان مياه'),
        ('hvac',       'HVAC / AC | تكييف مركزي'),
        ('electrical', 'Electrical Panel | لوحة كهربائية'),
        ('gate',       'Gate / Barrier | بوابة'),
        ('camera',     'CCTV / Camera | كاميرا مراقبة'),
        ('other',      'Other | أخرى'),
    ], string='Asset Type | نوع الأصل', required=True, default='other', tracking=True)

    location = fields.Char(
        string='Location | الموقع', tracking=True,
        help='e.g. Basement / Roof / Floor 1 | مثال: بدروم / سطح / طابق 1')
    state = fields.Selection([
        ('working',           'Working | يعمل'),
        ('needs_maintenance', 'Needs Maintenance | يحتاج صيانة'),
        ('broken',            'Broken | معطل'),
        ('decommissioned',    'Decommissioned | خارج الخدمة'),
    ], string='State | الحالة', default='working', required=True, tracking=True)

    # ── Purchase Info ────────────────────────────────────────────────────────
    purchase_date = fields.Date(
        string='Purchase Date | تاريخ الشراء', tracking=True)
    purchase_cost = fields.Float(
        string='Purchase Cost | تكلفة الشراء', digits=(16, 2), default=0.0, tracking=True)
    serial_number = fields.Char(
        string='Serial / Model No. | الرقم التسلسلي / الموديل', tracking=True)
    supplier = fields.Char(
        string='Supplier / Brand | المورد / الماركة', tracking=True)

    # ── Maintenance Schedule ─────────────────────────────────────────────────
    last_maintenance_date = fields.Date(
        string='Last Maintenance | آخر صيانة', tracking=True)
    next_maintenance_date = fields.Date(
        string='Next Maintenance | الصيانة القادمة', tracking=True)
    maintenance_cycle_days = fields.Integer(
        string='Maintenance Cycle (days) | دورة الصيانة (أيام)',
        default=180, tracking=True,
        help='Number of days between scheduled maintenance sessions.')

    notes = fields.Text(string='Notes | ملاحظات', tracking=True)

    # ── Expense Relation ─────────────────────────────────────────────────────
    expense_ids = fields.One2many(
        'nahj.expense', 'asset_id',
        string='Maintenance Expenses | مصاريف الصيانة')
    expense_count = fields.Integer(
        compute='_compute_expense_stats',
        string='Expenses | مصاريف')
    total_maintenance_cost = fields.Float(
        compute='_compute_expense_stats', store=True,
        string='Total Maintenance Cost | إجمالي تكاليف الصيانة',
        digits=(16, 2))

    # ── Maintenance Log Relation ──────────────────────────────────────────────
    maintenance_log_ids = fields.One2many(
        'nahj.maintenance.log', 'asset_id',
        string='Maintenance Logs | سجلات الصيانة')
    maintenance_log_count = fields.Integer(
        compute='_compute_maintenance_log_count',
        string='Logs | السجلات')

    @api.depends('maintenance_log_ids')
    def _compute_maintenance_log_count(self):
        for rec in self:
            rec.maintenance_log_count = len(rec.maintenance_log_ids)

    # ── Computed ─────────────────────────────────────────────────────────────
    @api.depends('expense_ids', 'expense_ids.amount')
    def _compute_expense_stats(self):
        for rec in self:
            rec.expense_count = len(rec.expense_ids)
            rec.total_maintenance_cost = sum(rec.expense_ids.mapped('amount'))

    # ── Action: View Expenses ────────────────────────────────────────────────
    def action_view_expenses(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Maintenance Expenses | مصاريف الصيانة'),
            'res_model': 'nahj.expense',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('asset_id', '=', self.id)],
            'context': {
                'default_asset_id': self.id,
                'default_tower_id': self.tower_id.id,
            },
        }

    # ── Action: Quick Record Maintenance ─────────────────────────────────────
    def action_record_maintenance(self):
        """Open a new maintenance log form pre-filled for this asset."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Record Maintenance | تسجيل صيانة'),
            'res_model': 'nahj.maintenance.log',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'context': {
                'default_asset_id': self.id,
                'default_state_before': self.state if self.state != 'decommissioned' else 'broken',
            },
        }

    # ── Action: View Maintenance Logs ────────────────────────────────────────
    def action_view_maintenance_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Maintenance Logs | سجلات الصيانة'),
            'res_model': 'nahj.maintenance.log',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('asset_id', '=', self.id)],
            'context': {
                'default_asset_id': self.id,
                'default_state_before': self.state if self.state != 'decommissioned' else 'broken',
            },
        }

    # ── Action: Mark as Working (after repair) ────────────────────────────────
    def action_mark_working(self):
        for rec in self:
            rec.state = 'working'
            rec.last_maintenance_date = fields.Date.today()
            if rec.maintenance_cycle_days:
                import datetime
                rec.next_maintenance_date = (
                    fields.Date.today() +
                    datetime.timedelta(days=rec.maintenance_cycle_days)
                )

    # ── Scheduled Cron: Flag Due Assets ──────────────────────────────────────
    @api.model
    def _cron_check_maintenance_due(self):
        """
        Runs daily. Marks assets as 'needs_maintenance' when their
        next_maintenance_date has been reached, and posts a chatter note.
        """
        today = fields.Date.today()
        due_assets = self.search([
            ('next_maintenance_date', '<=', today),
            ('state', '=', 'working'),
            ('next_maintenance_date', '!=', False),
        ])
        for asset in due_assets:
            asset.write({'state': 'needs_maintenance'})
            asset.message_post(
                body=_(
                    '<div style="color:#856404">⚠ <b>Maintenance due | حلّ موعد الصيانة</b></div>'
                    '<p>%s — يرجى جدولة الصيانة / Please schedule maintenance.</p>'
                ) % asset.name,
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
