import base64
import io
from markupsafe import escape
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class NahjImportWizard(models.TransientModel):
    _name = 'nahj.import.wizard'
    _description = 'Import Units & Residents from Excel/CSV'

    tower_id = fields.Many2one(
        'nahj.tower', string='Tower', required=True,
        default=lambda self: self.env.context.get('default_tower_id'))
    import_file = fields.Binary(string='Excel / CSV File', required=True)
    import_file_name = fields.Char(string='File Name')
    state = fields.Selection([
        ('draft', 'Ready'),
        ('done', 'Done'),
    ], default='draft')
    result_html = fields.Html(string='Result', readonly=True)

    # ── Download Template ─────────────────────────────────────────────────────
    def action_download_template(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/nahj_tower/import_template',
            'target': 'new',
        }

    # ── Main Import ───────────────────────────────────────────────────────────
    def action_import(self):
        self.ensure_one()
        if not self.import_file:
            raise UserError(_('Please upload a file first.'))

        fname = (self.import_file_name or '').lower()
        raw   = base64.b64decode(self.import_file)

        # ── Security: 5 MB hard limit ─────────────────────────────────────────
        MAX_BYTES = 5 * 1024 * 1024  # 5 MB
        if len(raw) > MAX_BYTES:
            raise UserError(_(
                'File size exceeds the 5 MB limit. Please split the file and '
                'import in batches.\n'
                'حجم الملف يتجاوز الحد المسموح به (5 ميجابايت). '
                'يرجى تقسيم الملف والاستيراد على دفعات.'))

        if fname.endswith('.xlsx') or fname.endswith('.xls'):
            rows = self._parse_xlsx(raw)
        elif fname.endswith('.csv'):
            rows = self._parse_csv(raw)
        else:
            raise UserError(_(
                'Unsupported format. Use .xlsx or .csv\n'
                'الصيغة غير مدعومة. استخدم .xlsx أو .csv'))

        created_units     = 0
        updated_units     = 0
        created_residents = 0
        errors            = []

        for i, row in enumerate(rows, start=2):
            try:
                unit_name = str(row.get('unit_no') or row.get('unit no') or '').strip()
                floor_raw = row.get('floor') or '1'
                sub_raw   = row.get('monthly_subscription') or \
                            row.get('monthly subscription') or '0'
                res_name  = str(row.get('resident_name') or
                                row.get('resident name') or '').strip()
                res_phone = str(row.get('resident_phone') or
                                row.get('resident phone') or '').strip()

                if not unit_name:
                    errors.append(_('Row %d: Unit No. is required.') % i)
                    continue

                try:
                    floor = int(float(str(floor_raw)))
                except (ValueError, TypeError):
                    floor = 1

                try:
                    subscription = float(str(sub_raw).replace(',', ''))
                except (ValueError, TypeError):
                    subscription = 0.0

                # ── Resident ─────────────────────────────────────────────────
                resident = None
                if res_name:
                    resident = self.env['nahj.resident'].search(
                        [('name', '=', res_name)], limit=1)
                    if not resident:
                        resident = self.env['nahj.resident'].create({
                            'name':  res_name,
                            'phone': res_phone,
                        })
                        created_residents += 1
                    elif res_phone and not resident.phone:
                        resident.phone = res_phone

                # ── Unit ─────────────────────────────────────────────────────
                unit_vals = {
                    'tower_id':             self.tower_id.id,
                    'name':                 unit_name,
                    'floor':                floor,
                    'monthly_subscription': subscription,
                }
                if resident:
                    unit_vals['resident_id'] = resident.id
                    unit_vals['state']       = 'occupied'

                existing = self.env['nahj.unit'].search([
                    ('tower_id', '=', self.tower_id.id),
                    ('name',     '=', unit_name),
                    ('floor',    '=', floor),
                ], limit=1)

                if existing:
                    existing.write(unit_vals)
                    updated_units += 1
                else:
                    self.env['nahj.unit'].create(unit_vals)
                    created_units += 1

            except Exception as e:
                errors.append(_('Row %d: %s') % (i, str(e)))

        # ── Build Result ──────────────────────────────────────────────────────
        html = ['<div style="font-family:Cairo,sans-serif;font-size:13px;">']
        html.append(
            '<p>✅ <b>%d</b> وحدة تم إنشاؤها &nbsp;|&nbsp; '
            '<b>%d</b> وحدة تم تحديثها &nbsp;|&nbsp; '
            '<b>%d</b> ساكن تم إضافته</p>' % (
                created_units, updated_units, created_residents))
        if errors:
            html.append(
                '<p style="color:#e74c3c;">⚠️ %d خطأ / error(s):</p><ul>' %
                len(errors))
            for err in errors[:20]:
                html.append('<li style="color:#e74c3c;">%s</li>' % escape(str(err)))
            if len(errors) > 20:
                html.append(
                    '<li>... و %d خطأ إضافي</li>' % (len(errors) - 20))
            html.append('</ul>')
        html.append('</div>')

        self.result_html = ''.join(html)
        self.state = 'done'

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'nahj.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
        }

    # ── Parsers ───────────────────────────────────────────────────────────────
    def _parse_xlsx(self, raw):
        try:
            import openpyxl
        except ImportError:
            raise UserError(_(
                'openpyxl is not installed. Please use CSV format instead.'))
        wb = openpyxl.load_workbook(
            io.BytesIO(raw), read_only=True, data_only=True)
        ws = wb.active
        rows = []
        headers = None
        for idx, row in enumerate(ws.iter_rows(values_only=True)):
            if idx == 0:
                headers = [
                    str(h or '').strip().lower().replace(' ', '_')
                    for h in row
                ]
                continue
            if all(v is None for v in row):
                continue
            rows.append(dict(zip(headers, row)))
        wb.close()
        return rows

    def _parse_csv(self, raw):
        import csv
        text = raw.decode('utf-8-sig', errors='replace')
        reader = csv.DictReader(io.StringIO(text))
        return [
            {k.strip().lower().replace(' ', '_'): v
             for k, v in row.items()}
            for row in reader
        ]
