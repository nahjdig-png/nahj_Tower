from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class NahjSubscription(models.Model):
    _name = 'nahj.subscription'
    _description = 'Monthly Subscription'
    _order = 'year desc, month desc, unit_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ── Core Fields ──────────────────────────────────────────────────────────
    unit_id = fields.Many2one(
        'nahj.unit', string='Unit', required=True,
        ondelete='cascade', index=True)
    tower_id = fields.Many2one(
        'nahj.tower', related='unit_id.tower_id',
        store=True, string='Tower', index=True)

    # ── Resident (related – for quick display in list view) ───────────────────
    resident_id = fields.Many2one(
        'nahj.resident', related='unit_id.resident_id',
        store=True, string='Resident | الساكن', index=True)
    resident_phone = fields.Char(
        related='unit_id.resident_id.phone',
        store=True, string='Phone | الهاتف')

    year = fields.Char(
        string='Year | السنة', required=True, size=4, tracking=True,
        default=lambda self: str(fields.Date.today().year))
    month = fields.Selection([
        ('1', 'January'),
        ('2', 'February'),
        ('3', 'March'),
        ('4', 'April'),
        ('5', 'May'),
        ('6', 'June'),
        ('7', 'July'),
        ('8', 'August'),
        ('9', 'September'),
        ('10', 'October'),
        ('11', 'November'),
        ('12', 'December'),
    ], string='Month', required=True, tracking=True,
        default=lambda self: str(fields.Date.today().month))

    amount = fields.Float(
        string='Amount | المبلغ', required=True, digits=(16, 2), tracking=True)

    # ── Discount Fields ───────────────────────────────────────────────────────
    discount_type = fields.Selection(
        related='unit_id.discount_type', store=True,
        string='Discount Type | نوع الخصم')
    discount_value = fields.Float(
        related='unit_id.discount_value', store=True,
        string='Discount Value | قيمة الخصم', digits=(16, 2))
    discount_amount = fields.Float(
        string='Discount Amount | مبلغ الخصم',
        compute='_compute_discount_amount', store=True, digits=(16, 2))
    amount_after_discount = fields.Float(
        string='Amount After Discount | المبلغ بعد الخصم',
        compute='_compute_discount_amount', store=True, digits=(16, 2))
    state = fields.Selection([
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
    ], string='Status', default='unpaid', required=True, tracking=True)
    payment_date = fields.Date(string='Payment Date', tracking=True)
    payment_method = fields.Selection([
        ('cash',     'Cash / نقدي'),
        ('transfer', 'Bank Transfer / تحويل بنكي'),
        ('check',    'Check / شيك'),
        ('other',    'Other / أخرى'),
    ], string='Payment Method', default='cash', tracking=True)
    receipt_number = fields.Char(
        string='Receipt No. | رقم الإيصال',
        readonly=True, copy=False, index=True, tracking=True,
        help='Auto-generated receipt number upon payment.')
    notes = fields.Text(string='Notes', tracking=True)

    @api.depends('amount', 'discount_type', 'discount_value')
    def _compute_discount_amount(self):
        for rec in self:
            base = rec.amount
            d_type = rec.discount_type or 'none'
            d_val = rec.discount_value or 0.0
            if d_type == 'percent':
                disc = base * min(d_val, 100) / 100.0
            elif d_type == 'fixed':
                disc = min(d_val, base)
            else:
                disc = 0.0
            rec.discount_amount = disc
            rec.amount_after_discount = base - disc

    # ── Computed: Overdue & Late Fee ──────────────────────────────────────────
    is_overdue = fields.Boolean(
        string='Overdue', compute='_compute_late_fee', store=True)
    late_fee_amount = fields.Float(
        string='Late Fee Amount', compute='_compute_late_fee',
        store=True, digits=(16, 2))

    # ── Display Name ─────────────────────────────────────────────────────────
    @api.depends('unit_id', 'unit_id.display_name', 'month', 'year')
    def _compute_display_name(self):
        for rec in self:
            month_label = dict(
                self._fields['month'].selection).get(rec.month, rec.month)
            rec.display_name = '%s – %s %s' % (
                rec.unit_id.display_name, month_label, rec.year)

    @api.depends('state', 'year', 'month', 'amount',
                 'tower_id', 'tower_id.late_fee_percent')
    def _compute_late_fee(self):
        import datetime
        today = datetime.date.today()
        for rec in self:
            if rec.state == 'unpaid' and rec.year and rec.month:
                y = int(rec.year)
                overdue = (
                    y < today.year or
                    (y == today.year and int(rec.month) < today.month)
                )
                rec.is_overdue = overdue
                pct = rec.tower_id.late_fee_percent if rec.tower_id else 0.0
                rec.late_fee_amount = (
                    rec.amount * (pct / 100.0) if (overdue and pct) else 0.0)
            else:
                rec.is_overdue = False
                rec.late_fee_amount = 0.0

    # ── Onchange ─────────────────────────────────────────────────────────────
    @api.onchange('unit_id')
    def _onchange_unit_id(self):
        if self.unit_id:
            self.amount = self.unit_id.net_subscription

    @api.onchange('state')
    def _onchange_state(self):
        if self.state == 'paid' and not self.payment_date:
            self.payment_date = fields.Date.today()
        elif self.state == 'unpaid':
            self.payment_date = False

    # ── Constraints ──────────────────────────────────────────────────────────
    @api.constrains('unit_id', 'year', 'month')
    def _check_unique_subscription(self):
        for rec in self:
            duplicate = self.search([
                ('unit_id', '=', rec.unit_id.id),
                ('year', '=', rec.year),
                ('month', '=', rec.month),
                ('id', '!=', rec.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'A subscription record already exists for unit "%s" '
                    'in %s %s.'
                ) % (rec.unit_id.display_name, rec.month, rec.year))

    def action_mark_paid(self):
        for rec in self:
            rec.state = 'paid'
            if not rec.payment_date:
                rec.payment_date = fields.Date.today()
            if not rec.receipt_number:
                rec.receipt_number = self.env['ir.sequence'].next_by_code(
                    'nahj.subscription.receipt') or '/'
            month_label = dict(self._fields['month'].selection).get(
                rec.month, rec.month)
            method_label = dict(self._fields['payment_method'].selection).get(
                rec.payment_method or '', rec.payment_method or '—')
            msg = _(
                '<div style="color:#155724">✅ <b>تم تسجيل الدفع / Payment Recorded</b></div>'
                '<ul>'
                '<li><b>الفترة / Period:</b> %s %s</li>'
                '<li><b>رقم الإيصال / Receipt:</b> %s</li>'
                '<li><b>طريقة الدفع / Method:</b> %s</li>'
                '<li><b>تاريخ الدفع / Date:</b> %s</li>'
                '<li><b>المبلغ / Amount:</b> %.2f</li>'
                '</ul>'
            ) % (
                month_label, rec.year,
                rec.receipt_number,
                method_label,
                rec.payment_date,
                rec.amount_after_discount,
            )
            if rec.late_fee_amount:
                msg += _('<div style="color:#856404">'
                         '⚠️ <b>غرامة تأخير مطبقة / Late fee applicable: %.2f</b></div>'
                         ) % rec.late_fee_amount
            rec.message_post(
                body=msg,
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )

    def action_mark_unpaid(self):
        # Only managers can reverse a payment
        if not self.env.user.has_group('nahj_Tower.group_nahj_manager'):
            from odoo.exceptions import AccessError
            raise AccessError(_(
                'Only Nahj Tower Managers can reverse a payment.\n'
                'يسمح فقط لمديري نهج تاور بإلغاء الدفع.'))
        for rec in self:
            old_receipt = rec.receipt_number
            old_date    = rec.payment_date
            old_method  = dict(self._fields['payment_method'].selection).get(
                rec.payment_method or '', rec.payment_method or '—')
            rec.state        = 'unpaid'
            rec.payment_date = False
            # Keep receipt number for audit trail – do NOT clear it
            rec.message_post(
                body=_(
                    '<div style="color:#721c24">❌ <b>تم إلغاء الدفع / Payment Reversed</b></div>'
                    '<ul>'
                    '<li><b>بواسطة / By:</b> %s</li>'
                    '<li><b>رقم الإيصال السابق / Previous Receipt:</b> %s</li>'
                    '<li><b>تاريخ الدفع السابق / Previous Date:</b> %s</li>'
                    '<li><b>طريقة الدفع السابقة / Previous Method:</b> %s</li>'
                    '</ul>'
                ) % (
                    self.env.user.name,
                    old_receipt or '—',
                    old_date or '—',
                    old_method,
                ),
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )

    def action_send_receipt_email(self):
        """Send a payment receipt email to the resident if email is available."""
        self.ensure_one()
        if self.state != 'paid':
            from odoo.exceptions import UserError
            raise UserError(_('Can only email receipts for paid subscriptions.'))

        resident = self.unit_id.resident_id
        if not resident or not resident.email:
            from odoo.exceptions import UserError
            raise UserError(_(
                'No email address found for the resident of this unit.\n'
                'لا يوجد بريد إلكتروني مسجل للساكن في هذه الوحدة.'))

        template = self.env.ref(
            'nahj_Tower.email_template_subscription_receipt', raise_if_not_found=False)
        if not template:
            from odoo.exceptions import UserError
            raise UserError(_('Email template not found. Please contact the administrator.'))

        template.send_mail(self.id, force_send=True)
        self.message_post(
            body=_('📧 <b>Receipt emailed | تم إرسال الإيصال</b><br/>To: <b>%s</b> (%s)') % (
                resident.name, resident.email),
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Email Sent'),
                'message': _('Receipt sent to %s') % resident.email,
                'type': 'success',
                'sticky': False,
            },
        }

    @api.constrains('year')
    def _check_year(self):
        for rec in self:
            if not rec.year or not rec.year.isdigit():
                raise ValidationError(_('Year must be a 4-digit number.'))
            y = int(rec.year)
            if y < 2000 or y > 2100:
                raise ValidationError(_(
                    'Year must be between 2000 and 2100.'))

    # ── Audit Trail → Unit Chatter ────────────────────────────────────────────
    # Tracked fields we report to the parent unit's chatter
    _TRACKED_FIELDS = {
        'amount':         'Amount | المبلغ',
        'year':           'Year | السنة',
        'month':          'Month | الشهر',
        'state':          'Status | الحالة',
        'payment_date':   'Payment Date | تاريخ الدفع',
        'payment_method': 'Payment Method | طريقة الدفع',
        'notes':          'Notes | الملاحظات',
    }

    def write(self, vals):
        # Capture old values before write for audit
        audit_map = {}
        tracked = {f: label for f, label in self._TRACKED_FIELDS.items() if f in vals}
        if tracked:
            for rec in self:
                audit_map[rec.id] = {
                    f: rec[f] for f in tracked
                }

        result = super().write(vals)

        # Post changes to the parent unit's chatter
        if tracked:
            month_labels = dict(self._fields['month'].selection)
            method_labels = dict(self._fields['payment_method'].selection)
            state_labels  = dict(self._fields['state'].selection)

            for rec in self:
                old = audit_map.get(rec.id, {})
                lines = []
                for f, label in tracked.items():
                    old_val = old.get(f)
                    new_val = rec[f]
                    if old_val == new_val:
                        continue
                    # Human-readable values
                    if f == 'month':
                        old_val = month_labels.get(str(old_val), old_val)
                        new_val = month_labels.get(str(new_val), new_val)
                    elif f == 'payment_method':
                        old_val = method_labels.get(old_val or '', old_val or '—')
                        new_val = method_labels.get(new_val or '', new_val or '—')
                    elif f == 'state':
                        old_val = state_labels.get(old_val or '', old_val)
                        new_val = state_labels.get(new_val or '', new_val)
                    old_val = old_val if old_val not in (False, None, '') else '—'
                    new_val = new_val if new_val not in (False, None, '') else '—'
                    lines.append(
                        '<li><b>%s</b>: <span style="color:#e74c3c">%s</span>'
                        ' → <span style="color:#27ae60">%s</span></li>'
                        % (label, old_val, new_val)
                    )
                if lines and rec.unit_id:
                    period = '%s %s' % (
                        month_labels.get(str(rec.month), rec.month), rec.year)
                    body = _(
                        'Subscription <b>%s</b> updated by <b>%s</b>:<ul>%s</ul>'
                    ) % (period, self.env.user.name, ''.join(lines))
                    rec.unit_id.message_post(
                        body=body,
                        message_type='comment',
                        subtype_xmlid='mail.mt_note',
                    )
        return result

    @api.constrains('payment_date')
    def _check_payment_date_not_future(self):
        today = fields.Date.today()
        for rec in self:
            if rec.payment_date and rec.payment_date > today:
                raise ValidationError(_(
                    'Payment date cannot be in the future.\n'
                    'لا يمكن أن يكون تاريخ الدفع في المستقبل.'))
