from odoo import models, fields, api, _
from odoo.exceptions import UserError


class NahjExpenseCategory(models.Model):
    _name = 'nahj.expense.category'
    _description = 'Expense Category'
    _rec_name = 'name'
    _order = 'name'

    name = fields.Char(string='Category Name', required=True, translate=True)
    expense_ids = fields.One2many(
        'nahj.expense', 'category_id', string='Expense List')
    expense_count = fields.Integer(
        compute='_compute_expense_count', string='Expenses')

    @api.depends('expense_ids')
    def _compute_expense_count(self):
        for rec in self:
            rec.expense_count = len(rec.expense_ids)


class NahjExpense(models.Model):
    _name = 'nahj.expense'
    _description = 'Building Expense'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'date desc'

    name = fields.Char(string='Description', required=True, tracking=True)
    tower_id = fields.Many2one(
        'nahj.tower', string='Tower', required=True,
        ondelete='cascade', index=True, tracking=True)
    category_id = fields.Many2one(
        'nahj.expense.category', string='Category', ondelete='set null', tracking=True)
    date = fields.Date(
        string='Date', required=True, default=fields.Date.today, tracking=True)
    amount = fields.Float(
        string='Amount', required=True, digits=(16, 2), tracking=True)
    asset_id = fields.Many2one(
        'nahj.tower.asset', string='Asset | الأصل',
        ondelete='set null', index=True, tracking=True,
        domain="[('tower_id', '=', tower_id)]",
        help='Link this expense to a specific tower asset (optional). | ربط المصروف بأصل معين (اختياري).')

    # ── Vendor & Reference ───────────────────────────────────────────────────
    vendor = fields.Char(
        string='Vendor / Contractor | المورد / المقاول', tracking=True,
        help='Name of the supplier or contractor who provided the service.')
    invoice_ref = fields.Char(
        string='Invoice / Receipt Ref | رقم الفاتورة / الإيصال', tracking=True,
        help='External invoice or receipt reference number.')

    # ── Workflow State ────────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft',     'Draft | مسودة'),
        ('confirmed', 'Confirmed | مؤكد'),
    ], string='Status | الحالة', default='draft', required=True, tracking=True)

    notes = fields.Text(string='Notes', tracking=True)
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'nahj_expense_attachment_rel',
        'expense_id', 'attachment_id',
        string='Attachments',
        help='Upload receipts or supporting documents.')

    # ── Actions ───────────────────────────────────────────────────────────────
    def action_confirm(self):
        for rec in self:
            if rec.amount <= 0:
                raise UserError(_(
                    'Cannot confirm an expense with zero or negative amount.\n'
                    'لا يمكن تأكيد مصروف بمبلغ صفر أو سالب.'))
            rec.state = 'confirmed'
            rec.message_post(
                body=_(
                    '<div style="color:#155724">✅ <b>تم تأكيد المصروف / Expense Confirmed</b></div>'
                    '<ul>'
                    '<li><b>بواسطة / By:</b> %s</li>'
                    '<li><b>المبلغ / Amount:</b> %.2f</li>'
                    '<li><b>التاريخ / Date:</b> %s</li>'
                    '</ul>'
                ) % (self.env.user.name, rec.amount, rec.date),
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )

    def action_reset_draft(self):
        for rec in self:
            rec.state = 'draft'
            rec.message_post(
                body=_(
                    '<div style="color:#856404">↩️ <b>تم إعادة المصروف للمسودة / Reset to Draft</b></div>'
                    '<ul><li><b>بواسطة / By:</b> %s</li></ul>'
                ) % self.env.user.name,
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
