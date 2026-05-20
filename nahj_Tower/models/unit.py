from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class NahjUnit(models.Model):
    _name = 'nahj.unit'
    _description = 'Tower Unit'
    _order = 'tower_id, floor, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ── Basic Info ───────────────────────────────────────────────────────────
    name = fields.Char(string='Unit Number', required=True, tracking=True)
    floor = fields.Integer(string='Floor', required=True, default=1, tracking=True)
    tower_id = fields.Many2one(
        'nahj.tower', string='Tower', required=True,
        ondelete='cascade', index=True, tracking=True)
    state = fields.Selection([
        ('occupied', 'Occupied | مشغولة'),
        ('vacant', 'Vacant | شاغرة'),
    ], string='Status | الحالة', default='vacant', required=True, tracking=True)
    monthly_subscription = fields.Float(
        string='Monthly Subscription', digits=(16, 2), default=0.0, tracking=True)
    subscription_state = fields.Selection([
        ('active',   'Active | فعّال'),
        ('inactive', 'Inactive | غير فعّال'),
    ], string='Subscription State | حالة الاشتراك',
        default='active', required=True, tracking=True,
        help='Inactive units are excluded from auto-generated subscriptions.')
    discount_type = fields.Selection([
        ('none',    'No Discount | بدون خصم'),
        ('percent', 'Percentage % | نسبة مئوية'),
        ('fixed',   'Fixed Amount | مبلغ ثابت'),
    ], string='Discount Type | نوع الخصم', default='none', required=True, tracking=True)
    discount_value = fields.Float(
        string='Discount Value | قيمة الخصم', digits=(16, 2), default=0.0,
        tracking=True, help='Percentage (0–100) or fixed amount depending on Discount Type.')
    net_subscription = fields.Float(
        string='Net Monthly Amount | المبلغ الصافي',
        compute='_compute_net_subscription', store=True, digits=(16, 2))
    notes = fields.Text(string='Notes', tracking=True)

    # ── Resident ─────────────────────────────────────────────────────────────
    resident_id = fields.Many2one(
        'nahj.resident', string='Resident', ondelete='set null',
        tracking=True)
    lease_start = fields.Date(string='Lease Start', tracking=True)
    lease_end = fields.Date(string='Lease End', tracking=True)
    lease_notes = fields.Text(string='Lease Notes', tracking=True)
    lease_status = fields.Selection([
        ('none', 'No Lease'),
        ('active', 'Active'),
        ('expiring', 'Expiring Soon'),
        ('expired', 'Expired'),
    ], string='Lease Status', compute='_compute_lease_status', store=True)

    @api.depends('lease_start', 'lease_end')
    def _compute_lease_status(self):
        import datetime
        today = datetime.date.today()
        warning_days = 30
        for rec in self:
            if not rec.lease_start and not rec.lease_end:
                rec.lease_status = 'none'
            elif rec.lease_end and rec.lease_end < today:
                rec.lease_status = 'expired'
            elif rec.lease_end and (rec.lease_end - today).days <= warning_days:
                rec.lease_status = 'expiring'
            elif rec.lease_start and rec.lease_start <= today:
                rec.lease_status = 'active'
            else:
                rec.lease_status = 'none'

    @api.depends('monthly_subscription', 'discount_type', 'discount_value')
    def _compute_net_subscription(self):
        for rec in self:
            base = rec.monthly_subscription
            if rec.discount_type == 'percent':
                rec.net_subscription = base - (base * min(rec.discount_value, 100) / 100.0)
            elif rec.discount_type == 'fixed':
                rec.net_subscription = max(base - rec.discount_value, 0.0)
            else:
                rec.net_subscription = base

    # ── Subscriptions ────────────────────────────────────────────────────────
    subscription_ids = fields.One2many(
        'nahj.subscription', 'unit_id', string='Subscriptions')
    subscription_count = fields.Integer(
        compute='_compute_subscription_stats', string='Total')
    paid_count = fields.Integer(
        compute='_compute_subscription_stats', string='Paid')
    unpaid_count = fields.Integer(
        compute='_compute_subscription_stats', string='Unpaid')

    # ── Compute Methods ──────────────────────────────────────────────────────
    @api.depends('subscription_ids', 'subscription_ids.state')
    def _compute_subscription_stats(self):
        for rec in self:
            rec.subscription_count = len(rec.subscription_ids)
            rec.paid_count = len(
                rec.subscription_ids.filtered(lambda s: s.state == 'paid'))
            rec.unpaid_count = len(
                rec.subscription_ids.filtered(lambda s: s.state == 'unpaid'))

    @api.depends('name', 'floor', 'tower_id', 'tower_id.name')
    def _compute_display_name(self):
        for rec in self:
            parts = []
            if rec.tower_id:
                parts.append(rec.tower_id.name)
            parts.append('%s %s' % (_('Floor'), rec.floor))
            parts.append('%s %s' % (_('Unit'), rec.name))
            rec.display_name = ' - '.join(parts)

    # ── Onchange ─────────────────────────────────────────────────────────────
    @api.onchange('resident_id')
    def _onchange_resident(self):
        if self.resident_id:
            self.state = 'occupied'
        else:
            self.state = 'vacant'

    # ── Constraints ──────────────────────────────────────────────────────────
    @api.constrains('resident_id')
    def _check_resident_unique(self):
        for rec in self:
            if rec.resident_id:
                duplicate = self.search([
                    ('resident_id', '=', rec.resident_id.id),
                    ('id', '!=', rec.id),
                ], limit=1)
                if duplicate:
                    raise ValidationError(_(
                        'Resident "%s" is already assigned to another unit!'
                    ) % rec.resident_id.name)

    _sql_constraints = [
        (
            'unique_tower_floor_unit',
            'UNIQUE(tower_id, floor, name)',
            'A unit with this number already exists on this floor in the same tower.',
        ),
    ]

    # ── Action Buttons ───────────────────────────────────────────────────────
    def action_view_subscriptions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Subscriptions'),
            'res_model': 'nahj.subscription',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('unit_id', '=', self.id)],
            'context': {
                'default_unit_id': self.id,
                'default_tower_id': self.tower_id.id,
            },
        }
