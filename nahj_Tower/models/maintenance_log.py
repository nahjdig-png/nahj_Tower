import datetime
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class NahjMaintenanceLog(models.Model):
    """
    Detailed log for every maintenance intervention on a tower asset.
    Each entry records: who did it, what was done, cost, parts used,
    and the asset state before/after.
    """
    _name = 'nahj.maintenance.log'
    _description = 'Maintenance Log | سجل الصيانة'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'
    _order = 'date desc, id desc'

    # ── Identity ──────────────────────────────────────────────────────────────
    asset_id = fields.Many2one(
        'nahj.tower.asset', string='Asset | الأصل',
        required=True, ondelete='cascade', index=True, tracking=True)
    tower_id = fields.Many2one(
        'nahj.tower', related='asset_id.tower_id',
        store=True, string='Tower | البرج', index=True)

    date = fields.Date(
        string='Maintenance Date | تاريخ الصيانة',
        required=True, default=fields.Date.today, tracking=True)
    log_type = fields.Selection([
        ('routine',    'Routine | روتينية'),
        ('corrective', 'Corrective / Repair | إصلاح خلل'),
        ('emergency',  'Emergency | طارئة'),
        ('inspection', 'Inspection | فحص'),
    ], string='Type | النوع', required=True, default='routine', tracking=True)

    # ── Technician ────────────────────────────────────────────────────────────
    technician = fields.Char(
        string='Technician / Contractor | الفني / المقاول', tracking=True)
    contractor_phone = fields.Char(
        string='Phone | رقم الهاتف', tracking=True)

    # ── Work Description ──────────────────────────────────────────────────────
    description = fields.Text(
        string='Work Description | وصف العمل',
        required=True,
        help='Describe what was done during this maintenance.')
    parts_replaced = fields.Text(
        string='Parts Replaced / Materials | القطع المستبدلة / المواد')

    # ── State Transition ──────────────────────────────────────────────────────
    state_before = fields.Selection([
        ('working',           'Working | يعمل'),
        ('needs_maintenance', 'Needs Maintenance | يحتاج صيانة'),
        ('broken',            'Broken | معطل'),
    ], string='State Before | الحالة قبل', required=True, tracking=True)
    state_after = fields.Selection([
        ('working',           'Working | يعمل'),
        ('needs_maintenance', 'Needs Maintenance | يحتاج صيانة'),
        ('broken',            'Broken | معطل'),
    ], string='State After | الحالة بعد', required=True, default='working', tracking=True)

    # ── Cost ─────────────────────────────────────────────────────────────────
    labor_cost = fields.Float(
        string='Labor Cost | تكلفة العمالة', digits=(16, 2), default=0.0, tracking=True)
    parts_cost = fields.Float(
        string='Parts / Materials Cost | تكلفة القطع', digits=(16, 2), default=0.0, tracking=True)
    total_cost = fields.Float(
        string='Total Cost | الإجمالي',
        compute='_compute_total_cost', store=True, digits=(16, 2))

    # ── Schedule ─────────────────────────────────────────────────────────────
    next_maintenance_date = fields.Date(
        string='Next Scheduled | الصيانة القادمة', tracking=True,
        help='Recommended date for next maintenance. Updates the asset record on confirm.')
    warranty_expiry = fields.Date(
        string='Warranty Expiry | انتهاء الضمان', tracking=True)

    # ── Linked Expense ────────────────────────────────────────────────────────
    expense_id = fields.Many2one(
        'nahj.expense', string='Linked Expense | المصروف المرتبط',
        readonly=True,
        help='Expense record auto-created when this log is confirmed.')

    notes = fields.Text(string='Notes | ملاحظات', tracking=True)
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'nahj_maint_log_attachment_rel',
        'log_id', 'attachment_id',
        string='Attachments | المرفقات')

    # ── Computed ──────────────────────────────────────────────────────────────
    @api.depends('labor_cost', 'parts_cost')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = rec.labor_cost + rec.parts_cost

    @api.depends('asset_id', 'asset_id.name', 'date', 'log_type')
    def _compute_display_name(self):
        type_label = {
            'routine': 'Routine',
            'corrective': 'Repair',
            'emergency': 'Emergency',
            'inspection': 'Inspection',
        }
        for rec in self:
            rec.display_name = '[%s] %s – %s' % (
                type_label.get(rec.log_type, ''),
                rec.asset_id.name or '',
                rec.date or '',
            )

    # ── Onchange ──────────────────────────────────────────────────────────────
    @api.onchange('asset_id')
    def _onchange_asset_id(self):
        if self.asset_id:
            self.state_before = self.asset_id.state if self.asset_id.state != 'decommissioned' else 'broken'

    # ── Confirm: update asset + create expense ─────────────────────────────────
    def action_confirm(self):
        self.ensure_one()
        asset = self.asset_id

        # Update asset state and maintenance schedule
        vals = {
            'last_maintenance_date': self.date,
            'state': self.state_after,
        }
        if self.next_maintenance_date:
            vals['next_maintenance_date'] = self.next_maintenance_date
        elif asset.maintenance_cycle_days:
            maintenance_date = self.date or fields.Date.today()
            vals['next_maintenance_date'] = (
                maintenance_date +
                datetime.timedelta(days=asset.maintenance_cycle_days)
            )
        asset.write(vals)

        # Auto-create expense if total cost > 0 and no expense yet
        if self.total_cost > 0 and not self.expense_id:
            category = self.env['nahj.expense.category'].search(
                [('name', 'ilike', 'Maintenance')], limit=1)
            expense = self.env['nahj.expense'].create({
                'name': _('[Maintenance] %s – %s') % (asset.name, self.date),
                'tower_id': asset.tower_id.id,
                'asset_id': asset.id,
                'category_id': category.id if category else False,
                'date': self.date,
                'amount': self.total_cost,
                'notes': self.description,
            })
            self.expense_id = expense.id

        # Post chatter note on asset
        asset.message_post(
            body=_(
                '<div style="color:#004085">🔧 <b>Maintenance logged | تم تسجيل صيانة</b></div>'
                '<ul>'
                '<li><b>Date | التاريخ:</b> %(date)s</li>'
                '<li><b>Type | النوع:</b> %(type)s</li>'
                '<li><b>State | الحالة:</b> %(before)s → %(after)s</li>'
                '<li><b>Cost | التكلفة:</b> %(cost)s</li>'
                '</ul>'
            ) % {
                'date': self.date,
                'type': dict(self._fields['log_type'].selection).get(
                    self.log_type, ''),
                'before': dict(self._fields['state_before'].selection).get(
                    self.state_before, ''),
                'after': dict(self._fields['state_after'].selection).get(
                    self.state_after, ''),
                'cost': self.total_cost,
            },
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )
