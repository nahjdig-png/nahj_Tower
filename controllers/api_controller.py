"""
Nahj Tower – REST API Controller
=================================
Provides read-only JSON endpoints for a potential external frontend.
All endpoints require an API key passed in the Authorization header:
    Authorization: Bearer <api_key>

The api_key must match the system parameter 'nahj_tower.api_key'.
Set it via Settings > Technical > Parameters > System Parameters.
"""
import hmac
import json
import logging
from odoo import http, _
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

API_PREFIX = '/api/nahj'


def _json_response(data, status=200):
    return Response(
        json.dumps(data, default=str),
        status=status,
        mimetype='application/json',
    )


def _error(message, status=400):
    return _json_response({'error': message}, status=status)


def _authenticate():
    """Validate Bearer API key. Returns True if valid, Response otherwise."""
    auth_header = request.httprequest.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return _error('Missing or invalid Authorization header.', 401)
    provided_key = auth_header[7:].strip()
    if not provided_key:
        return _error('Empty API key.', 401)
    stored_key = request.env['ir.config_parameter'].sudo().get_param(
        'nahj_tower.api_key', default='')
    if not stored_key or not hmac.compare_digest(provided_key, stored_key):
        return _error('Invalid API key.', 403)
    return True


class NahjTowerApiController(http.Controller):

    # ── Tower Endpoints ──────────────────────────────────────────────────────

    @http.route(
        API_PREFIX + '/towers',
        type='http', auth='public', methods=['GET'], csrf=False)
    def get_towers(self, **kwargs):
        auth = _authenticate()
        if auth is not True:
            return auth
        towers = request.env['nahj.tower'].sudo().search([])
        data = [{
            'id': t.id,
            'name': t.name,
            'address': t.address or '',
            'city': t.city or '',
            'unit_count': t.unit_count,
            'occupied_count': t.occupied_count,
            'vacant_count': t.vacant_count,
            'total_subscriptions': t.total_subscriptions,
            'total_expenses': t.total_expenses,
            'balance': t.balance,
            'overdue_count': t.overdue_count,
        } for t in towers]
        return _json_response({'towers': data})

    @http.route(
        API_PREFIX + '/towers/<int:tower_id>',
        type='http', auth='public', methods=['GET'], csrf=False)
    def get_tower(self, tower_id, **kwargs):
        auth = _authenticate()
        if auth is not True:
            return auth
        tower = request.env['nahj.tower'].sudo().browse(tower_id)
        if not tower.exists():
            return _error('Tower not found.', 404)
        return _json_response({
            'id': tower.id,
            'name': tower.name,
            'address': tower.address or '',
            'city': tower.city or '',
            'unit_count': tower.unit_count,
            'occupied_count': tower.occupied_count,
            'vacant_count': tower.vacant_count,
            'total_subscriptions': tower.total_subscriptions,
            'total_expenses': tower.total_expenses,
            'balance': tower.balance,
            'overdue_count': tower.overdue_count,
            'notes': tower.notes or '',
        })

    # ── Unit Endpoints ───────────────────────────────────────────────────────

    @http.route(
        API_PREFIX + '/towers/<int:tower_id>/units',
        type='http', auth='public', methods=['GET'], csrf=False)
    def get_units(self, tower_id, **kwargs):
        auth = _authenticate()
        if auth is not True:
            return auth
        tower = request.env['nahj.tower'].sudo().browse(tower_id)
        if not tower.exists():
            return _error('Tower not found.', 404)
        data = [{
            'id': u.id,
            'name': u.name,
            'floor': u.floor,
            'state': u.state,
            'monthly_subscription': u.monthly_subscription,
            'resident': {
                'id': u.resident_id.id,
                'name': u.resident_id.name,
                'phone': u.resident_id.phone or '',
            } if u.resident_id else None,
            'paid_count': u.paid_count,
            'unpaid_count': u.unpaid_count,
        } for u in tower.unit_ids]
        return _json_response({'units': data})

    # ── Subscription Endpoints ───────────────────────────────────────────────

    @http.route(
        API_PREFIX + '/subscriptions',
        type='http', auth='public', methods=['GET'], csrf=False)
    def get_subscriptions(self, tower_id=None, state=None,
                          year=None, month=None, **kwargs):
        auth = _authenticate()
        if auth is not True:
            return auth
        domain = []
        if tower_id:
            domain.append(('tower_id', '=', int(tower_id)))
        if state and state in ('paid', 'unpaid'):
            domain.append(('state', '=', state))
        if year:
            domain.append(('year', '=', int(year)))
        if month:
            domain.append(('month', '=', str(month)))
        subs = request.env['nahj.subscription'].sudo().search(domain,
                                                               limit=500)
        data = [{
            'id': s.id,
            'tower_id': s.tower_id.id,
            'tower_name': s.tower_id.name,
            'unit_id': s.unit_id.id,
            'unit_name': s.unit_id.name,
            'year': s.year,
            'month': s.month,
            'amount': s.amount,
            'state': s.state,
            'payment_date': s.payment_date.isoformat() if s.payment_date else None,
        } for s in subs]
        return _json_response({'subscriptions': data})

    # ── Expense Endpoints ────────────────────────────────────────────────────

    @http.route(
        API_PREFIX + '/expenses',
        type='http', auth='public', methods=['GET'], csrf=False)
    def get_expenses(self, tower_id=None, **kwargs):
        auth = _authenticate()
        if auth is not True:
            return auth
        domain = []
        if tower_id:
            domain.append(('tower_id', '=', int(tower_id)))
        expenses = request.env['nahj.expense'].sudo().search(domain, limit=500)
        data = [{
            'id': e.id,
            'tower_id': e.tower_id.id,
            'tower_name': e.tower_id.name,
            'name': e.name,
            'category': e.category_id.name if e.category_id else '',
            'date': e.date.isoformat() if e.date else None,
            'amount': e.amount,
        } for e in expenses]
        return _json_response({'expenses': data})
