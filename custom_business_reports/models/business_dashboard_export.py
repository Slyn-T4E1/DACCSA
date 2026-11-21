# -*- coding: utf-8 -*-
"""Exportar un tablero a PDF y a Excel (19.0.11.0.0).

Los dos usan exactamente lo que se ve en pantalla: el resultado de
get_dashboard_data con los mismos filtros y el mismo comparativo.

* Excel (xlsxwriter): una hoja "Tablero" con los filtros y los indicadores, y
  una hoja por gráfica, tabla o listado, con sus números (y el comparativo,
  si hay). Las gráficas de barras y líneas llevan su gráfica nativa de Excel.
* PDF: hoja horizontal con los filtros, los indicadores, las gráficas (la
  interfaz manda cada gráfica como imagen, dibujada en colores claros) y las
  tablas y listados como tablas.

El archivo se guarda como adjunto con token (para que lo descargue cualquier
usuario que ve el tablero) y se borra solo después de una hora.
"""
import base64
import io
import logging
import re
from datetime import timedelta

from odoo import _, fields, models
from odoo.tools import format_date, format_datetime

_logger = logging.getLogger(__name__)

EXPORT_TAG = 'ccr_dashboard_export'
XLSX_FORMATS = {
    'monetary': '$#,##0.00', 'percent': '0.00%', 'integer': '#,##0', 'number': '#,##0.00', 'number1': '#,##0.0',
}


class BusinessDashboard(models.Model):
    _inherit = 'business.dashboard'

    # ------------------------------------------------------------------
    # API para la interfaz
    # ------------------------------------------------------------------
    def export_xlsx(self, filter_values=None, compare=None):
        self.ensure_one()
        data = self.get_dashboard_data(filter_values, compare)
        content = self.sudo()._xlsx_content(data)
        return self._export_download(content, '%s.xlsx' % self._export_name(),
                                     'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    def export_pdf(self, filter_values=None, compare=None, images=None):
        """images: {id del elemento (texto): imagen PNG en data URL} de cada gráfica."""
        self.ensure_one()
        data = self.get_dashboard_data(filter_values, compare)
        images = {str(key): value for key, value in (images or {}).items()
                  if isinstance(value, str) and value.startswith('data:image/png;base64,')}
        report = self.env.ref('custom_business_reports.action_report_dashboard_export').sudo()
        content, kind = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
            report, self.ids, data={'dashboard': data, 'images': images})
        # En pruebas automáticas Odoo regresa HTML en lugar de PDF
        extension = 'pdf' if kind == 'pdf' else 'html'
        return self._export_download(content, '%s.%s' % (self._export_name(), extension),
                                     'application/pdf' if kind == 'pdf' else 'text/html')

    # ------------------------------------------------------------------
    # Apoyo
    # ------------------------------------------------------------------
    def _export_name(self):
        stamp = fields.Datetime.context_timestamp(self, fields.Datetime.now()).strftime('%Y-%m-%d %H%M')
        return re.sub(r'[\\/:*?"<>|]+', ' ', '%s %s' % (self.name, stamp)).strip()

    def _export_download(self, content, filename, mimetype):
        Attachment = self.env['ir.attachment'].sudo()
        # Limpia exportaciones de más de una hora
        Attachment.search([('description', '=', EXPORT_TAG),
                           ('create_date', '<', fields.Datetime.now() - timedelta(hours=1))]).unlink()
        attachment = Attachment.create({
            'name': filename, 'raw': content, 'mimetype': mimetype, 'description': EXPORT_TAG,
            'res_model': self._name, 'res_id': self.id,
        })
        token = attachment.generate_access_token()[0]
        return {
            'type': 'ir.actions.act_url', 'target': 'self',
            'url': '/web/content/%s?download=true&access_token=%s' % (attachment.id, token),
        }

    def _filters_text(self, data):
        """Filtros como texto: "Periodo: 01/01/2026 – 31/12/2026 · Vendedor: Ana"."""
        parts = []
        filters = {flt.id: flt for flt in self.filter_ids}
        for item in data['filters']:
            flt, value = filters.get(item['id']), item.get('value')
            if not flt:
                continue
            if item['type'] == 'date':
                if value.get('from') or value.get('to'):
                    text = '%s – %s' % (format_date(self.env, value['from']) if value.get('from') else '…',
                                        format_date(self.env, value['to']) if value.get('to') else '…')
                else:
                    text = _('Todo')
            elif item['type'] == 'many2one':
                records = self.env[flt.comodel_name].sudo(False).browse(value or []).exists() if value else False
                text = ', '.join(records.mapped('display_name')) if records else _('Todos')
            elif item['type'] == 'selection':
                labels = dict(item.get('options') or [])
                text = ', '.join(labels.get(v, v) for v in value) if value else _('Todos')
            else:
                text = value or _('Todos')
            parts.append('%s: %s' % (item['name'], text))
        return ' · '.join(parts)

    def _fmt(self, value, value_format, symbol='$'):
        """Número para el PDF (montos sin centavos, como los listados)."""
        if value in (False, None, ''):
            return ''
        if not isinstance(value, (int, float)):
            return str(value)
        if value_format == 'percent':
            return '%.2f %%' % (value * 100)
        if value_format == 'monetary':
            return '%s%s' % ('-' if value < 0 else '', symbol + '{:,.0f}'.format(abs(value)))
        if value_format == 'number1':
            return '{:,.1f}'.format(value)
        if value_format == 'integer' or float(value).is_integer():
            return '{:,.0f}'.format(value)
        return '{:,.2f}'.format(value)

    @staticmethod
    def _delta_text(delta):
        if delta is False or delta is None:
            return ''
        return '%s%.1f %%' % ('+' if delta >= 0 else '', delta * 100)

    # ------------------------------------------------------------------
    # Excel
    # ------------------------------------------------------------------
    def _xlsx_content(self, data):
        import xlsxwriter  # noqa: PLC0415 - viene con Odoo

        output = io.BytesIO()
        book = xlsxwriter.Workbook(output, {'in_memory': True})
        bold = book.add_format({'bold': True})
        title = book.add_format({'bold': True, 'font_size': 14})
        head = book.add_format({'bold': True, 'bg_color': '#2F5BEA', 'font_color': '#FFFFFF', 'border': 1})
        formats = {key: book.add_format({'num_format': fmt}) for key, fmt in XLSX_FORMATS.items()}
        total_formats = {key: book.add_format({'num_format': fmt, 'bold': True, 'top': 1})
                         for key, fmt in XLSX_FORMATS.items()}
        compare = data.get('compare')
        used = set()

        def sheet_name(text):
            base = re.sub(r'[\[\]:*?/\\]', ' ', text or _('Hoja')).strip()[:28] or _('Hoja')
            name, n = base, 2
            while name.lower() in used:
                name, n = '%s %s' % (base[:25], n), n + 1
            used.add(name.lower())
            return name

        def put(sheet, row, col, value, fmt=None, total=False):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                sheet.write_number(row, col, value, (total_formats if total else formats).get(fmt or 'number'))
            else:
                sheet.write(row, col, value if value not in (False, None) else '', bold if total else None)

        # ---------------- Hoja principal: filtros e indicadores ----------------
        main = book.add_worksheet(sheet_name(_('Tablero')))
        main.write(0, 0, data['name'], title)
        main.write(1, 0, self._filters_text(data))
        if compare:
            main.write(2, 0, _('Comparativo: %s', compare.get('label') or ''))
        main.write(3, 0, _('Generado: %s', format_datetime(self.env, fields.Datetime.now())))
        row = 5
        kpis = [w for w in data['widgets'] if w['type'] == 'kpi' and not w['error']]
        if kpis:
            headers = [_('Indicador'), _('Valor')] + ([_('Comparativo'), _('Variación')] if compare else []) + [_('Nota')]
            for col, text in enumerate(headers):
                main.write(row, col, text, head)
            for widget in kpis:
                row += 1
                main.write(row, 0, widget['title'])
                put(main, row, 1, widget['value'], widget['format'])
                col = 2
                if compare:
                    comp = widget.get('compare') or {}
                    put(main, row, 2, comp.get('value', ''), widget['format'])
                    put(main, row, 3, comp.get('delta') if comp.get('delta') is not False else '', 'percent')
                    col = 4
                main.write(row, col, widget.get('subtitle') or '')
            main.set_column(0, 0, 38)
            main.set_column(1, 3, 18)
            main.set_column(col, col, 60)

        # ---------------- Una hoja por gráfica, tabla o listado ----------------
        for widget in data['widgets']:
            if widget['type'] not in ('chart', 'table', 'list') or widget['error']:
                continue
            sheet = book.add_worksheet(sheet_name(widget['title']))
            sheet.write(0, 0, widget['title'], title)
            if widget.get('subtitle'):
                sheet.write(1, 0, widget['subtitle'])
            if widget['type'] == 'chart':
                self._xlsx_chart(book, sheet, widget, compare, head, put)
            elif widget['type'] == 'table':
                self._xlsx_table(sheet, widget, compare, head, put)
            else:
                self._xlsx_list(sheet, widget, head, put)
        book.close()
        return output.getvalue()

    def _xlsx_chart(self, book, sheet, widget, compare, head, put):
        start = 3
        datasets = list(widget['datasets'])
        extra = [dict(d, label='%s (%s)' % (d['label'], compare.get('label'))) for d in widget.get('compare_datasets') or []] \
            if compare else []
        sheet.write(start, 0, _('Grupo'), head)
        for col, dataset in enumerate(datasets + extra, start=1):
            sheet.write(start, col, dataset['label'], head)
        for i, label in enumerate(widget['labels']):
            sheet.write(start + 1 + i, 0, label)
            for col, dataset in enumerate(datasets + extra, start=1):
                value = dataset['data'][i] if i < len(dataset['data']) else 0
                put(sheet, start + 1 + i, col, value, dataset.get('format') or widget.get('format'))
        sheet.set_column(0, 0, 28)
        sheet.set_column(1, len(datasets + extra), 18)
        # Gráfica nativa de Excel (barras o líneas) con las series actuales
        if not widget['labels'] or widget['chart_type'] in ('pie', 'doughnut'):
            return
        kind = {'hbar': ('bar', None), 'bar_stacked': ('column', 'stacked'), 'line': ('line', None)}.get(
            widget['chart_type'], ('column', None))
        options = {'type': kind[0]}
        if kind[1]:
            options['subtype'] = kind[1]
        chart = book.add_chart(options)
        last = start + len(widget['labels'])
        for col, dataset in enumerate(datasets, start=1):
            series = {'name': [sheet.name, start, col], 'categories': [sheet.name, start + 1, 0, last, 0],
                      'values': [sheet.name, start + 1, col, last, col]}
            if dataset.get('color_mode') == 'sign' and kind[0] != 'line':
                # Verde o rojo por barra, como en el tablero
                series['points'] = [{'fill': {'color': '#DC2626' if (v or 0) < 0 else '#16A34A'}}
                                    for v in dataset['data']]
            elif dataset.get('color'):
                series['fill' if kind[0] != 'line' else 'line'] = {'color': dataset['color']}
            chart.add_series(series)
        chart.set_title({'name': widget['title']})
        chart.set_size({'width': 760, 'height': 380})
        sheet.insert_chart(start, len(datasets + extra) + 2, chart)

    def _xlsx_table(self, sheet, widget, compare, head, put):
        row = 3
        columns = widget['columns']
        sheet.write(row, 0, widget.get('row_label') or '', head)
        for col, column in enumerate(columns, start=1):
            sheet.write(row, col, column['name'], head)
        sheet.set_column(0, 0, 36)
        sheet.set_column(1, len(columns), 16)
        rows = list(widget['rows'])
        if widget.get('total') and widget.get('total_first'):
            rows.insert(0, dict(widget['total'], is_total=True))
        elif widget.get('total'):
            rows.append(dict(widget['total'], is_total=True))
        for item in rows:
            row += 1
            total = item.get('is_total', False)
            put(sheet, row, 0, item['label'], total=total)
            for col, cell in enumerate(item['cells'], start=1):
                fmt = cell.get('format') or columns[col - 1].get('format')
                put(sheet, row, col, cell['value'], fmt, total=total)
            if compare and item.get('compare'):
                row += 1
                sheet.write(row, 0, '   %s (%s)' % (item['label'], compare.get('label')))
                for col, value in enumerate(item['compare'], start=1):
                    cell = item['cells'][col - 1] if col - 1 < len(item['cells']) else {}
                    fmt = cell.get('format') or columns[col - 1].get('format')
                    if value is not None:
                        put(sheet, row, col, value, fmt)

    def _xlsx_list(self, sheet, widget, head, put):
        row = 3
        columns = widget['columns']
        offset = 1 if widget.get('show_number') else 0
        if offset:
            sheet.write(row, 0, '#', head)
        for col, column in enumerate(columns):
            sheet.write(row, col + offset, column['label'], head)
            sheet.set_column(col + offset, col + offset, 18 if column['type'] in ('monetary', 'float', 'integer') else 30)
        kinds = {'monetary': 'monetary', 'integer': 'integer', 'float': 'number'}
        for record in widget['records']:
            row += 1
            if record.get('group'):
                sheet.write(row, 0, '%s (%s)' % (record['group'], record['count']))
                continue
            if offset:
                sheet.write_number(row, 0, record['number'])
            for col, value in enumerate(record['cells']):
                put(sheet, row, col + offset, value, kinds.get(columns[col]['type']))
        if widget.get('total'):
            row += 1
            put(sheet, row, offset, _('Total'), total=True)
            for col, value in enumerate(widget['total']):
                if value != '':
                    put(sheet, row, col + offset, value, kinds.get(columns[col]['type']), total=True)


class ReportDashboardExport(models.AbstractModel):
    """Datos del PDF de un tablero (ver report/dashboard_export_report.xml)."""
    _name = 'report.custom_business_reports.report_dashboard_export'
    _description = 'PDF de un tablero'

    def _get_report_values(self, docids, data=None):
        data = data or {}
        dashboard = self.env['business.dashboard'].browse(docids[:1])
        payload = data.get('dashboard') or {}
        symbol = (payload.get('currency') or {}).get('symbol') or '$'
        # Renglones del PDF: los elementos se acomodan como en pantalla (12 columnas)
        rows, current, width = [], [], 0
        for widget in payload.get('widgets', []):
            size = 12 if widget['type'] == 'section' else int(widget.get('width') or 12)
            if current and (width + size > 12 or widget['type'] == 'section'):
                rows.append(current)
                current, width = [], 0
            current.append(widget)
            width += size
            if widget['type'] == 'section':
                rows.append(current)
                current, width = [], 0
        if current:
            rows.append(current)
        return {
            'doc_ids': docids,
            'doc_model': 'business.dashboard',
            'docs': dashboard,
            'data': payload,
            'rows': rows,
            'images': data.get('images') or {},
            'filters_text': dashboard._filters_text(payload) if payload else '',
            'compare': payload.get('compare'),
            'generated': format_datetime(self.env, fields.Datetime.now()),
            'company': self.env.company,
            'fmt': lambda value, value_format: dashboard._fmt(value, value_format, symbol),
            'delta_text': dashboard._delta_text,
        }
