from odoo import models, fields, api, _
from odoo.exceptions import UserError


class NahjGenerateSubscriptions(models.TransientModel):
    _name = 'nahj.generate.subscriptions'
    _description = 'Generate Monthly Subscriptions'

    tower_id = fields.Many2one(
        'nahj.tower', string='Tower', required=True,
        default=lambda self: self.env.context.get('default_tower_id'))
    year = fields.Integer(
        string='Year', required=True,
        default=lambda self: fields.Date.today().year)
    month = fields.Selection([
        ('1', 'January'),  ('2', 'February'), ('3', 'March'),
        ('4', 'April'),    ('5', 'May'),       ('6', 'June'),
        ('7', 'July'),     ('8', 'August'),    ('9', 'September'),
        ('10', 'October'), ('11', 'November'), ('12', 'December'),
    ], string='From Month', required=True,
        default=lambda self: str(fields.Date.today().month))
    month_to = fields.Selection([
        ('1', 'January'),  ('2', 'February'), ('3', 'March'),
        ('4', 'April'),    ('5', 'May'),       ('6', 'June'),
        ('7', 'July'),     ('8', 'August'),    ('9', 'September'),
        ('10', 'October'), ('11', 'November'), ('12', 'December'),
    ], string='To Month (optional)',
        help='Leave empty to generate for a single month only.')
    only_occupied = fields.Boolean(
        string='Occupied Units Only', default=True,
        help='Generate subscriptions only for occupied units.')

    def action_generate(self):
        self.ensure_one()
        if not self.tower_id.unit_ids:
            raise UserError(_('This tower has no units.'))

        units = self.tower_id.unit_ids
        if self.only_occupied:
            units = units.filtered(lambda u: u.state == 'occupied')
        # Always skip subscription-inactive units
        units = units.filtered(lambda u: u.subscription_state == 'active')
        if not units:
            raise UserError(_(
                'No occupied units found in this tower. '
                'Disable "Occupied Units Only" to generate for all units.'))

        # Determine month range
        month_from = int(self.month)
        month_end  = int(self.month_to) if self.month_to else month_from
        if month_end < month_from:
            raise UserError(_('To Month must be equal to or after From Month.'))

        created = 0
        skipped = 0
        Subscription = self.env['nahj.subscription']

        for month_num in range(month_from, month_end + 1):
            for unit in units:
                existing = Subscription.search([
                    ('unit_id', '=', unit.id),
                    ('year',    '=', str(self.year)),
                    ('month',   '=', str(month_num)),
                ], limit=1)
                if existing:
                    skipped += 1
                    continue
                Subscription.create({
                    'unit_id': unit.id,
                    'year':    str(self.year),
                    'month':   str(month_num),
                    'amount':  unit.net_subscription,
                    'state':   'unpaid',
                })
                created += 1

        months_generated = month_end - month_from + 1
        message = _(
            'Done! %(months)d month(s) processed. '
            'Created: %(created)d subscription(s). '
            'Skipped (already exist): %(skipped)d.'
        ) % {'months': months_generated, 'created': created, 'skipped': skipped}

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Subscriptions Generated'),
                'message': message,
                'sticky': False,
                'type': 'success',
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': _('Subscriptions'),
                    'res_model': 'nahj.subscription',
                    'view_mode': 'list,form',
                    'views': [[False, 'list'], [False, 'form']],
                    'domain': [
                        ('tower_id', '=', self.tower_id.id),
                        ('year',     '=', self.year),
                    ],
                    'context': {'default_tower_id': self.tower_id.id},
                },
            },
        }
