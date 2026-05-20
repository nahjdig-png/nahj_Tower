from odoo import models, fields, api, _
from odoo.exceptions import UserError


class NahjDistributeExpenseLine(models.TransientModel):
    """Preview line for each unit's computed share."""
    _name = 'nahj.distribute.expense.line'
    _description = 'Distribution Preview Line'

    wizard_id = fields.Many2one(
        'nahj.distribute.expense.wizard', ondelete='cascade')
    unit_id = fields.Many2one(
        'nahj.unit', string='Unit | الوحدة', readonly=True)
    floor = fields.Integer(
        related='unit_id.floor', string='Floor | الطابق', readonly=True)
    resident_id = fields.Many2one(
        'nahj.resident', related='unit_id.resident_id',
        string='Resident | الساكن', readonly=True)
    monthly_subscription = fields.Float(
        related='unit_id.monthly_subscription',
        string='Monthly Sub. | الاشتراك الشهري', readonly=True, digits=(16, 2))
    amount = fields.Float(
        string='Share | الحصة', digits=(16, 2))
    include = fields.Boolean(
        string='Include | تضمين', default=True)


class NahjDistributeExpenseWizard(models.TransientModel):
    """
    Wizard to distribute an emergency expense across tower units.
    Step 1 – Configure (draft)
    Step 2 – Preview and adjust (preview)
    Step 3 – Confirm → creates nahj.expense.distribution
    """
    _name = 'nahj.distribute.expense.wizard'
    _description = 'Distribute Emergency Expense | توزيع مصروف طارئ'

    # ── Configuration ─────────────────────────────────────────────────────────
    tower_id = fields.Many2one(
        'nahj.tower', string='Tower | البرج', required=True)
    total_amount = fields.Float(
        string='Total Amount | المبلغ الإجمالي',
        required=True, digits=(16, 2))
    description = fields.Char(
        string='Description | الوصف', required=True,
        placeholder='e.g. Emergency elevator repair | إصلاح طارئ للأسانسير')
    date = fields.Date(
        string='Date | التاريخ', required=True, default=fields.Date.today)
    distribution_method = fields.Selection([
        ('equal',           'Equal Split | بالتساوي'),
        ('by_subscription', 'By Subscription Amount | بنسبة الاشتراك الشهري'),
    ], string='Distribution Method | طريقة التوزيع',
        required=True, default='equal')
    unit_filter = fields.Selection([
        ('occupied',            'Occupied Units Only | الوحدات المشغولة فقط'),
        ('active_subscription', 'Active Subscription Units | وحدات الاشتراك الفعّال'),
        ('all',                 'All Units | كل الوحدات'),
    ], string='Apply To | طبّق على', required=True, default='occupied')
    notes = fields.Text(string='Notes | ملاحظات')

    # ── Preview Lines ─────────────────────────────────────────────────────────
    line_ids = fields.One2many(
        'nahj.distribute.expense.line', 'wizard_id',
        string='Distribution Preview | معاينة التوزيع')

    # ── State & Result ────────────────────────────────────────────────────────
    result_state = fields.Selection([
        ('draft',   'Configure | الإعداد'),
        ('preview', 'Preview | المعاينة'),
        ('done',    'Done | تم'),
    ], default='draft')
    distribution_id = fields.Many2one(
        'nahj.expense.distribution',
        string='Created Distribution | التوزيع المنشأ', readonly=True)

    # ── Computed Totals ───────────────────────────────────────────────────────
    included_count = fields.Integer(
        compute='_compute_preview_stats', string='Units Included | الوحدات')
    total_distributed = fields.Float(
        compute='_compute_preview_stats',
        string='Total Distributed | إجمالي الموزَّع', digits=(16, 2))
    rounding_diff = fields.Float(
        compute='_compute_preview_stats',
        string='Rounding Diff | فرق التقريب', digits=(16, 2))

    @api.depends('line_ids', 'line_ids.include', 'line_ids.amount', 'total_amount')
    def _compute_preview_stats(self):
        for rec in self:
            included = rec.line_ids.filtered('include')
            rec.included_count = len(included)
            rec.total_distributed = sum(included.mapped('amount'))
            rec.rounding_diff = rec.total_amount - rec.total_distributed

    # ── Step 1 → Step 2: Compute Preview ─────────────────────────────────────
    def action_compute_preview(self):
        self.ensure_one()
        if self.total_amount <= 0:
            raise UserError(_('Total amount must be greater than zero.'))

        # Build domain
        domain = [('tower_id', '=', self.tower_id.id)]
        if self.unit_filter == 'occupied':
            domain.append(('state', '=', 'occupied'))
        elif self.unit_filter == 'active_subscription':
            domain += [('state', '=', 'occupied'),
                       ('subscription_state', '=', 'active')]
        # 'all' → no extra domain

        units = self.env['nahj.unit'].search(domain, order='floor, name')
        if not units:
            raise UserError(_(
                'No units found for the selected criteria. '
                'Please adjust the "Apply To" filter.'))

        # Clear existing lines
        self.line_ids.unlink()

        # Compute amounts
        if self.distribution_method == 'equal':
            per_unit = self.total_amount / len(units)
            lines = [(0, 0, {
                'unit_id': u.id,
                'amount': round(per_unit, 2),
                'include': True,
            }) for u in units]
        else:
            # by_subscription
            total_sub = sum(units.mapped('monthly_subscription'))
            if total_sub == 0:
                raise UserError(_(
                    'Cannot distribute by subscription: all selected units '
                    'have zero monthly subscription amount.'))
            lines = [(0, 0, {
                'unit_id': u.id,
                'amount': round(
                    self.total_amount * (u.monthly_subscription / total_sub), 2),
                'include': True,
            }) for u in units]

        self.write({'line_ids': lines, 'result_state': 'preview'})
        # Refresh the wizard form
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ── Back to configuration ─────────────────────────────────────────────────
    def action_back_to_draft(self):
        self.ensure_one()
        self.line_ids.unlink()
        self.result_state = 'draft'
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ── Step 2 → Confirm: Create permanent records ────────────────────────────
    def action_confirm(self):
        self.ensure_one()
        included_lines = self.line_ids.filtered('include')
        if not included_lines:
            raise UserError(_('No units are included in the distribution.'))

        distribution = self.env['nahj.expense.distribution'].create({
            'name': self.description,
            'tower_id': self.tower_id.id,
            'total_amount': self.total_amount,
            'distribution_method': self.distribution_method,
            'date': self.date,
            'notes': self.notes or False,
            'charge_ids': [(0, 0, {
                'unit_id': line.unit_id.id,
                'amount': line.amount,
            }) for line in included_lines],
        })

        self.write({'result_state': 'done', 'distribution_id': distribution.id})
        # Open the created distribution record
        return {
            'type': 'ir.actions.act_window',
            'name': _('Emergency Distribution | توزيع طارئ'),
            'res_model': 'nahj.expense.distribution',
            'res_id': distribution.id,
            'view_mode': 'form',
            'target': 'current',
        }
