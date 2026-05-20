from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class NahjUnitTransferWizard(models.TransientModel):
    """Transfer a resident from their current unit to a new vacant unit."""
    _name = 'nahj.unit.transfer.wizard'
    _description = 'Unit Transfer Wizard'

    source_unit_id = fields.Many2one(
        'nahj.unit', string='From Unit', required=True,
        domain=[('state', '=', 'occupied')],
        default=lambda self: self.env.context.get('default_source_unit_id'))
    resident_id = fields.Many2one(
        'nahj.resident', string='Resident', readonly=True,
        compute='_compute_resident_id', store=False)
    target_unit_id = fields.Many2one(
        'nahj.unit', string='To Unit', required=True,
        domain=[('state', '=', 'vacant')])
    new_monthly_subscription = fields.Float(
        string='New Monthly Subscription',
        help='Leave 0 to keep the target unit\'s existing subscription amount.')
    transfer_date = fields.Date(
        string='Transfer Date', required=True,
        default=fields.Date.today)
    notes = fields.Text(string='Transfer Notes')

    @api.depends('source_unit_id')
    def _compute_resident_id(self):
        for rec in self:
            rec.resident_id = rec.source_unit_id.resident_id

    @api.constrains('source_unit_id', 'target_unit_id')
    def _check_different_units(self):
        for rec in self:
            if rec.source_unit_id == rec.target_unit_id:
                raise ValidationError(_('Source and target units must be different.'))

    def action_transfer(self):
        self.ensure_one()
        source = self.source_unit_id
        target = self.target_unit_id
        resident = source.resident_id

        if not resident:
            raise UserError(_('The source unit has no resident assigned.'))
        if target.state != 'vacant':
            raise UserError(_(
                'Target unit "%s" is not vacant.') % target.display_name)

        # ── Execute transfer ──────────────────────────────────────────────────
        old_sub = source.monthly_subscription

        # Remove resident from source
        source.write({
            'resident_id': False,
            'state': 'vacant',
            'lease_end': self.transfer_date,
        })

        # Assign to target
        new_sub = self.new_monthly_subscription or target.monthly_subscription
        target.write({
            'resident_id': resident.id,
            'state': 'occupied',
            'lease_start': self.transfer_date,
            'monthly_subscription': new_sub if new_sub else target.monthly_subscription,
        })

        # ── Post chatter messages ─────────────────────────────────────────────
        note = self.notes or ''
        source.message_post(
            body=_(
                '<div style="color:#155724">🔄 <b>Resident Transferred Out | نقل الساكن</b></div>'
                '<ul>'
                '<li><b>Resident | الساكن:</b> %(res)s</li>'
                '<li><b>To | إلى:</b> %(target)s</li>'
                '<li><b>Date | التاريخ:</b> %(date)s</li>'
                '%(notes)s'
                '</ul>'
            ) % {
                'res': resident.name,
                'target': target.display_name,
                'date': self.transfer_date,
                'notes': ('<li>' + note + '</li>') if note else '',
            },
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )
        target.message_post(
            body=_(
                '<div style="color:#155724">🏠 <b>Resident Moved In | استقبال ساكن</b></div>'
                '<ul>'
                '<li><b>Resident | الساكن:</b> %(res)s</li>'
                '<li><b>From | من:</b> %(source)s</li>'
                '<li><b>Date | التاريخ:</b> %(date)s</li>'
                '%(notes)s'
                '</ul>'
            ) % {
                'res': resident.name,
                'source': source.display_name,
                'date': self.transfer_date,
                'notes': ('<li>' + note + '</li>') if note else '',
            },
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Transfer Complete'),
                'message': _(
                    '%(resident)s has been moved from %(source)s to %(target)s.'
                ) % {
                    'resident': resident.name,
                    'source': source.display_name,
                    'target': target.display_name,
                },
                'type': 'success',
                'sticky': False,
            },
        }
