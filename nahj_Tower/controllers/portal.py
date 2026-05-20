import hashlib
import hmac
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


def _normalize_url_token(token):
    """Strip URL token (proxies / copy-paste may add whitespace)."""
    if token is None:
        return ''
    return str(token).strip()


def _portal_phone_for_token(resident):
    """Normalize phone string used in HMAC so token matches after lookup."""
    return (resident.phone or '').strip()


def _resident_token(resident):
    """Generate a URL token using HMAC-SHA256 for timing-safe comparison."""
    secret = request.env['ir.config_parameter'].sudo().get_param(
        'database.secret', default='nahj_tower_secret')
    raw = '%d|%s|%s' % (resident.id, _portal_phone_for_token(resident), secret)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _safe_token_compare(a, b):
    """Constant-time string comparison to prevent timing attacks."""
    if not isinstance(a, str) or not isinstance(b, str) or len(a) != len(b):
        return False
    return hmac.compare_digest(a.encode(), b.encode())


MONTHS_AR = {
    '1': 'يناير', '2': 'فبراير', '3': 'مارس', '4': 'أبريل',
    '5': 'مايو', '6': 'يونيو', '7': 'يوليو', '8': 'أغسطس',
    '9': 'سبتمبر', '10': 'أكتوبر', '11': 'نوفمبر', '12': 'ديسمبر',
}
MONTHS_EN = {
    '1': 'Jan', '2': 'Feb', '3': 'Mar', '4': 'Apr',
    '5': 'May', '6': 'Jun', '7': 'Jul', '8': 'Aug',
    '9': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec',
}

ASSET_TYPE_LABELS = {
    'elevator':   'أسانسير / Elevator',
    'pump':       'ماتور مياه / Pump',
    'generator':  'مولد / Generator',
    'tank':       'خزان مياه / Tank',
    'hvac':       'تكييف / HVAC',
    'electrical': 'لوحة كهرباء / Electrical',
    'gate':       'بوابة / Gate',
    'camera':     'كاميرا / CCTV',
    'other':      'أخرى / Other',
}

ASSET_STATE_LABELS = {
    'working':            'يعمل / Working',
    'needs_maintenance':  'يحتاج صيانة',
    'broken':             'معطل / Broken',
    'decommissioned':     'خارج الخدمة',
}

MAINT_LOG_TYPE_LABELS = {
    'routine':    'روتينية / Routine',
    'corrective': 'إصلاح / Corrective',
    'emergency':  'طارئة / Emergency',
    'inspection': 'فحص / Inspection',
}


def _authenticate_resident(resident_id, token):
    """Return browsed resident if token valid, else None."""
    token = _normalize_url_token(token)
    resident = request.env['nahj.resident'].sudo().browse(int(resident_id))
    if not resident.exists():
        return None
    expected = _resident_token(resident)
    if not _safe_token_compare(token, expected):
        return None
    return resident


def _tower_ids_for_resident(resident):
    return resident.unit_ids.mapped('tower_id').ids


class NahjPortalController(http.Controller):

    # ── Landing Page ─────────────────────────────────────────────────────────
    @http.route('/nahj/portal', type='http', auth='public',
                website=False, csrf=False)
    def portal_index(self, **kwargs):
        error = kwargs.get('error', '')
        return request.render('nahj_Tower.portal_index_template', {
            'error': error,
        })

    # ── Phone Lookup ──────────────────────────────────────────────────────────
    @http.route('/nahj/portal/lookup', type='http', auth='public',
                methods=['POST'], website=False, csrf=False)
    def portal_lookup(self, phone='', **kwargs):
        phone = (phone or '').strip()
        if not phone:
            return request.redirect('/nahj/portal?error=empty_phone')

        resident = request.env['nahj.resident'].sudo().search([
            ('phone', '=', phone),
        ], limit=1)

        if not resident:
            return request.redirect('/nahj/portal?error=not_found')

        token = _resident_token(resident)
        return request.redirect(
            '/nahj/portal/resident/%d/%s' % (resident.id, token))

    def _resident_portal_redirect_invalid(self):
        return request.redirect('/nahj/portal?error=invalid_token')

    # ── Resident sub-pages (register BEFORE the bare /resident/<id>/<token>
    #     so routing never binds an extra path segment to <string:token>).
    # ─────────────────────────────────────────────────────────────────────────

    @http.route(
        '/nahj/portal/resident/<int:resident_id>/<string:token>/expenses',
        type='http', auth='public', website=False, csrf=False)
    def portal_resident_expenses(self, resident_id, token, **kwargs):
        resident = _authenticate_resident(resident_id, token)
        if not resident:
            return self._resident_portal_redirect_invalid()
        token = _normalize_url_token(token)
        tower_ids = _tower_ids_for_resident(resident)
        if not tower_ids:
            expenses = request.env['nahj.expense'].sudo().browse()
        else:
            expenses = request.env['nahj.expense'].sudo().search([
                ('tower_id', 'in', tower_ids),
                ('state', '=', 'confirmed'),
            ], order='date desc, id desc', limit=200)
        total = sum(expenses.mapped('amount'))
        return request.render('nahj_Tower.portal_resident_expenses_template', {
            'resident': resident,
            'portal_token': token,
            'nav_active': 'exp',
            'expenses': expenses,
            'expenses_total': total,
        })

    @http.route(
        '/nahj/portal/resident/<int:resident_id>/<string:token>/maintenance',
        type='http', auth='public', website=False, csrf=False)
    def portal_resident_maintenance(self, resident_id, token, **kwargs):
        token = _normalize_url_token(token)
        resident = _authenticate_resident(resident_id, token)
        if not resident:
            return self._resident_portal_redirect_invalid()
        tower_ids = _tower_ids_for_resident(resident)
        if not tower_ids:
            logs = request.env['nahj.maintenance.log'].sudo().browse()
        else:
            logs = request.env['nahj.maintenance.log'].sudo().search([
                ('tower_id', 'in', tower_ids),
            ], order='date desc, id desc', limit=200)
        return request.render('nahj_Tower.portal_resident_maintenance_template', {
            'resident': resident,
            'portal_token': token,
            'nav_active': 'mnt',
            'logs': logs,
            'log_type_labels': MAINT_LOG_TYPE_LABELS,
        })

    @http.route(
        '/nahj/portal/resident/<int:resident_id>/<string:token>/assets',
        type='http', auth='public', website=False, csrf=False)
    def portal_resident_assets(self, resident_id, token, **kwargs):
        token = _normalize_url_token(token)
        resident = _authenticate_resident(resident_id, token)
        if not resident:
            return self._resident_portal_redirect_invalid()
        tower_ids = _tower_ids_for_resident(resident)
        if not tower_ids:
            assets = request.env['nahj.tower.asset'].sudo().browse()
        else:
            assets = request.env['nahj.tower.asset'].sudo().search([
                ('tower_id', 'in', tower_ids),
            ], order='tower_id, name', limit=200)
        return request.render('nahj_Tower.portal_resident_assets_template', {
            'resident': resident,
            'portal_token': token,
            'nav_active': 'ast',
            'assets': assets,
            'asset_type_labels': ASSET_TYPE_LABELS,
            'asset_state_labels': ASSET_STATE_LABELS,
        })

    @http.route(
        '/nahj/portal/resident/<int:resident_id>/<string:token>/charges',
        type='http', auth='public', website=False, csrf=False)
    def portal_resident_charges(self, resident_id, token, **kwargs):
        token = _normalize_url_token(token)
        resident = _authenticate_resident(resident_id, token)
        if not resident:
            return self._resident_portal_redirect_invalid()
        unit_ids = resident.unit_ids.ids
        if not unit_ids:
            charges = request.env['nahj.unit.charge'].sudo().browse()
        else:
            charges = request.env['nahj.unit.charge'].sudo().search([
                ('unit_id', 'in', unit_ids),
            ], order='distribution_id desc, id desc', limit=200)
        return request.render('nahj_Tower.portal_resident_charges_template', {
            'resident': resident,
            'portal_token': token,
            'nav_active': 'chg',
            'charges': charges,
        })

    # ── Resident subscription page (shorter URL — must come after sub-routes)
    # ─────────────────────────────────────────────────────────────────────────
    @http.route('/nahj/portal/resident/<int:resident_id>/<string:token>',
                type='http', auth='public', website=False, csrf=False)
    def portal_resident(self, resident_id, token, **kwargs):
        token = _normalize_url_token(token)
        resident = request.env['nahj.resident'].sudo().browse(resident_id)
        if not resident.exists():
            return request.redirect('/nahj/portal?error=not_found')
        expected = _resident_token(resident)
        if not _safe_token_compare(token, expected):
            return request.redirect('/nahj/portal?error=invalid_token')

        units = resident.unit_ids
        subscriptions = request.env['nahj.subscription'].sudo().search([
            ('unit_id', 'in', units.ids),
        ], order='year desc, month desc')

        paid_total = sum(subscriptions.filtered(
            lambda s: s.state == 'paid').mapped('amount_after_discount'))
        unpaid_total = sum(subscriptions.filtered(
            lambda s: s.state == 'unpaid').mapped('amount_after_discount'))

        return request.render('nahj_Tower.portal_resident_template', {
            'resident': resident,
            'portal_token': token,
            'nav_active': 'subs',
            'units': units,
            'subscriptions': subscriptions,
            'paid_total': paid_total,
            'unpaid_total': unpaid_total,
            'months_ar': MONTHS_AR,
            'months_en': MONTHS_EN,
        })
