from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class NahjExpenseDistribution(models.Model):
    """Header record for an emergency expense distributed across tower units."""
    _name = 'nahj.expense.distribution'
    _description = 'Emergency Expense Distribution | توزيع مصروف طارئ'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'date desc'

    # ── Core Fields ───────────────────────────────────────────────────────────
    name = fields.Char(
        string='Description | الوصف', required=True, tracking=True)
    tower_id = fields.Many2one(
        'nahj.tower', string='Tower | البرج',
        required=True, ondelete='restrict', index=True, tracking=True)
    date = fields.Date(
        string='Date | التاريخ', required=True,
        default=fields.Date.today, tracking=True)
    total_amount = fields.Float(
        string='Total Amount | المبلغ الإجمالي',
        required=True, digits=(16, 2), tracking=True)
    distribution_method = fields.Selection([
        ('equal',           'Equal Split | بالتساوي'),
        ('by_subscription', 'By Subscription | بنسبة الاشتراك'),
    ], string='Distribution Method | طريقة التوزيع',
        required=True, default='equal', tracking=True)
    notes = fields.Text(string='Notes | ملاحظات')

    # ── Charge Lines ──────────────────────────────────────────────────────────
    charge_ids = fields.One2many(
        'nahj.unit.charge', 'distribution_id',
        string='Unit Charges | رسوم الوحدات')

    # ── Statistics ────────────────────────────────────────────────────────────
    unit_count = fields.Integer(
        compute='_compute_stats', store=True, string='Units | وحدات')
    paid_count = fields.Integer(
        compute='_compute_stats', store=True, string='Paid | مدفوع')
    unpaid_count = fields.Integer(
        compute='_compute_stats', store=True, string='Unpaid | غير مدفوع')
    total_collected = fields.Float(
        compute='_compute_stats', store=True,
        string='Collected | المحصّل', digits=(16, 2))
    collection_rate = fields.Float(
        compute='_compute_stats', store=True,
        string='Collection % | نسبة التحصيل', digits=(5, 1))

    @api.depends('charge_ids', 'charge_ids.state', 'charge_ids.amount')
    def _compute_stats(self):
        for rec in self:
            charges = rec.charge_ids
            rec.unit_count = len(charges)
            paid = charges.filtered(lambda c: c.state == 'paid')
            rec.paid_count = len(paid)
            rec.unpaid_count = len(charges) - len(paid)
            rec.total_collected = sum(paid.mapped('amount'))
            if rec.total_amount:
                rec.collection_rate = (rec.total_collected / rec.total_amount) * 100.0
            else:
                rec.collection_rate = 0.0

    # ── Bulk Actions ──────────────────────────────────────────────────────────
    def action_mark_all_paid(self):
        """Mark all unpaid charges in this distribution as paid."""
        for rec in self:
            unpaid = rec.charge_ids.filtered(lambda c: c.state == 'unpaid')
            unpaid.action_mark_paid()

    def action_view_charges(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Unit Charges | رسوم الوحدات'),
            'res_model': 'nahj.unit.charge',
            'view_mode': 'list,form',
            'domain': [('distribution_id', '=', self.id)],
            'context': {'default_distribution_id': self.id},
        }


class NahjUnitCharge(models.Model):
    """A single unit's share of an emergency expense distribution."""
    _name = 'nahj.unit.charge'
    _description = 'Unit Charge | رسوم الوحدة'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'
    _order = 'distribution_id, unit_id'

    # ── Core Fields ───────────────────────────────────────────────────────────
    distribution_id = fields.Many2one(
        'nahj.expense.distribution', string='Distribution | التوزيع',
        required=True, ondelete='cascade', index=True)
    tower_id = fields.Many2one(
        'nahj.tower', related='distribution_id.tower_id',
        store=True, string='Tower | البرج', index=True)
    unit_id = fields.Many2one(
        'nahj.unit', string='Unit | الوحدة',
        required=True, ondelete='restrict', index=True)
    resident_id = fields.Many2one(
        'nahj.resident', related='unit_id.resident_id',
        string='Resident | الساكن', store=True)
    amount = fields.Float(
        string='Amount | المبلغ', required=True,
        digits=(16, 2), tracking=True)

    # ── Payment Fields ────────────────────────────────────────────────────────
    state = fields.Selection([
        ('unpaid', 'Unpaid | غير مدفوع'),
        ('paid',   'Paid | مدفوع'),
    ], string='Status | الحالة', default='unpaid',
        required=True, tracking=True)
    payment_date = fields.Date(
        string='Payment Date | تاريخ الدفع')
    payment_method = fields.Selection([
        ('cash',     'Cash / نقدي'),
        ('transfer', 'Bank Transfer / تحويل بنكي'),
        ('check',    'Check / شيك'),
        ('other',    'Other / أخرى'),
    ], string='Payment Method | طريقة الدفع', default='cash')
    notes = fields.Text(string='Notes | ملاحظات')

    # ── Display Name ──────────────────────────────────────────────────────────
    @api.depends('distribution_id', 'distribution_id.name',
                 'unit_id', 'unit_id.display_name')
    def _compute_display_name(self):
        for rec in self:
            dist_name = rec.distribution_id.name or ''
            unit_name = rec.unit_id.display_name or ''
            rec.display_name = '%s – %s' % (dist_name, unit_name)

    # ── Onchange ──────────────────────────────────────────────────────────────
    @api.onchange('state')
    def _onchange_state(self):
        if self.state == 'paid' and not self.payment_date:
            self.payment_date = fields.Date.today()
        elif self.state == 'unpaid':
            self.payment_date = False

    # ── Actions ───────────────────────────────────────────────────────────────
    def action_mark_paid(self):
        for rec in self:
            rec.state = 'paid'
            if not rec.payment_date:
                rec.payment_date = fields.Date.today()

    def action_mark_unpaid(self):
        for rec in self:
            rec.state = 'unpaid'
            rec.payment_date = False
