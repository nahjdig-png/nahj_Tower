from odoo import models, fields, api, _


class NahjResident(models.Model):
    _name = 'nahj.resident'
    _description = 'Resident'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'name'

    name = fields.Char(string='Full Name', required=True, tracking=True)
    phone = fields.Char(string='Phone Number', tracking=True)
    email = fields.Char(string='Email', tracking=True)
    id_number = fields.Char(string='ID Number', tracking=True)
    notes = fields.Text(string='Notes', tracking=True)
    active = fields.Boolean(default=True, tracking=True)

    # ── Unit Relation (reverse) ───────────────────────────────────────────────
    unit_ids = fields.One2many('nahj.unit', 'resident_id', string='Unit List')
    unit_count = fields.Integer(
        compute='_compute_unit_count', string='Units')

    @api.depends('unit_ids')
    def _compute_unit_count(self):
        for rec in self:
            rec.unit_count = len(rec.unit_ids)

    def action_view_units(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Units'),
            'res_model': 'nahj.unit',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('resident_id', '=', self.id)],
        }
