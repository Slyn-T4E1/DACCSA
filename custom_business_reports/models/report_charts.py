# -*- coding: utf-8 -*-
"""Gráficas SVG para el PDF del Reporte Semanal de Dirección (Etapa 7).

El PDF se genera con wkhtmltopdf, que no ejecuta bien librerías de gráficas en
JavaScript; por eso las gráficas se dibujan aquí como SVG (texto) y se
insertan en la plantilla QWeb.
"""
from markupsafe import Markup, escape

PALETTE = ['#2F5BEA', '#E8556F', '#F59E0B', '#10B981', '#8B5CF6', '#06B6D4']


def money(value, decimals=2):
    """$1,234,567.89 (negativos: -$1,234.00)."""
    value = value or 0.0
    text = '{:,.{d}f}'.format(abs(value), d=decimals)
    return ('-$' if value < 0 else '$') + text


def short(value):
    """Monto abreviado: $12.3 M, $450 k."""
    value = value or 0.0
    sign = '-' if value < 0 else ''
    number = abs(value)
    if number >= 1e6:
        return '%s$%s M' % (sign, '{:,.1f}'.format(number / 1e6))
    if number >= 1e4:
        return '%s$%s k' % (sign, '{:,.0f}'.format(number / 1e3))
    return '%s$%s' % (sign, '{:,.0f}'.format(number))


def pct(value, decimals=2):
    return '{:,.{d}f} %'.format((value or 0.0) * 100, d=decimals)


def _nice_max(value):
    """Máximo "redondo" para el eje."""
    if value <= 0:
        return 1.0
    magnitude = 10 ** (len(str(int(value))) - 1)
    for step in (1, 2, 2.5, 5, 10):
        if step * magnitude >= value:
            return step * magnitude
    return 10 * magnitude


def _axis(min_value, max_value):
    top = _nice_max(max(max_value, 0.0))
    bottom = -_nice_max(-min_value) if min_value < 0 else 0.0
    return bottom, top


def bar_chart(categories, series, width=1180, height=330, value_labels=True):
    """Barras agrupadas. series = [(nombre, color, [valores por categoría])]."""
    left, right, top, bottom = 80, 20, 34, 46
    plot_w, plot_h = width - left - right, height - top - bottom
    values = [v for _name, _color, vals in series for v in vals] or [0.0]
    low, high = _axis(min(values), max(values))
    span = (high - low) or 1.0

    def y(v):
        return top + plot_h * (high - v) / span

    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
             'font-family="Helvetica, Arial, sans-serif">' % (width, height, width, height)]
    # Leyenda
    x = left
    for name, color, _vals in series:
        parts.append('<rect x="%d" y="6" width="14" height="14" rx="2" fill="%s"/>' % (x, color))
        parts.append('<text x="%d" y="18" font-size="14" fill="#374151">%s</text>' % (x + 20, escape(name)))
        x += 30 + 8 * len(name)
    # Ejes y líneas guía
    for i in range(5):
        value = low + span * i / 4
        yy = y(value)
        parts.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="#E5E7EB"/>' % (left, width - right, yy, yy))
        parts.append('<text x="%d" y="%.1f" font-size="12" fill="#6B7280" text-anchor="end">%s</text>'
                     % (left - 8, yy + 4, escape(short(value))))
    parts.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="#9CA3AF"/>' % (left, width - right, y(0), y(0)))
    # Barras
    groups = max(len(categories), 1)
    group_w = plot_w / groups
    bar_w = min(60, group_w * 0.8 / max(len(series), 1))
    for gi, label in enumerate(categories):
        gx = left + gi * group_w + (group_w - bar_w * len(series)) / 2
        for si, (_name, color, vals) in enumerate(series):
            value = vals[gi] if gi < len(vals) else 0.0
            y0, y1 = sorted((y(0), y(value)))
            bx = gx + si * bar_w
            parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" rx="2"/>'
                         % (bx + 2, y0, bar_w - 4, max(y1 - y0, 0.5), color))
            if value_labels and value:
                ly = y(value) - 6 if value >= 0 else y(value) + 14
                parts.append('<text x="%.1f" y="%.1f" font-size="11" fill="#1F2937" text-anchor="middle">%s</text>'
                             % (bx + bar_w / 2, ly, escape(short(value))))
        parts.append('<text x="%.1f" y="%d" font-size="13" fill="#374151" text-anchor="middle">%s</text>'
                     % (left + gi * group_w + group_w / 2, height - bottom + 22, escape(label)))
    parts.append('</svg>')
    return Markup(''.join(parts))


def line_chart(labels, series, width=1180, height=330):
    """Líneas. series = [(nombre, color, [valores por etiqueta])]."""
    left, right, top, bottom = 80, 30, 34, 46
    plot_w, plot_h = width - left - right, height - top - bottom
    values = [v for _name, _color, vals in series for v in vals] or [0.0]
    low, high = _axis(min(values), max(values))
    span = (high - low) or 1.0

    def y(v):
        return top + plot_h * (high - v) / span

    def x(i):
        return left + (plot_w * i / (len(labels) - 1) if len(labels) > 1 else plot_w / 2)

    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
             'font-family="Helvetica, Arial, sans-serif">' % (width, height, width, height)]
    lx = left
    for name, color, _vals in series:
        parts.append('<rect x="%d" y="10" width="18" height="4" fill="%s"/>' % (lx, color))
        parts.append('<text x="%d" y="18" font-size="14" fill="#374151">%s</text>' % (lx + 24, escape(name)))
        lx += 36 + 8 * len(name)
    for i in range(5):
        value = low + span * i / 4
        yy = y(value)
        parts.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="#E5E7EB"/>' % (left, width - right, yy, yy))
        parts.append('<text x="%d" y="%.1f" font-size="12" fill="#6B7280" text-anchor="end">%s</text>'
                     % (left - 8, yy + 4, escape(short(value))))
    for i, label in enumerate(labels):
        parts.append('<text x="%.1f" y="%d" font-size="13" fill="#374151" text-anchor="middle">%s</text>'
                     % (x(i), height - bottom + 22, escape(label)))
    for si, (_name, color, vals) in enumerate(series):
        points = ' '.join('%.1f,%.1f' % (x(i), y(v)) for i, v in enumerate(vals))
        if len(vals) > 1:
            parts.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="3"/>' % (points, color))
        for i, v in enumerate(vals):
            parts.append('<circle cx="%.1f" cy="%.1f" r="5" fill="%s"/>' % (x(i), y(v), color))
            offset = -10 if si == 0 else 20
            parts.append('<text x="%.1f" y="%.1f" font-size="12" font-weight="bold" fill="%s" text-anchor="middle">%s</text>'
                         % (x(i), y(v) + offset, color, escape(short(v))))
    parts.append('</svg>')
    return Markup(''.join(parts))


def hbar_list(items, width=560, row_height=34, max_value=None):
    """Barras horizontales con etiqueta y valor. items = [(etiqueta, valor, color)]."""
    label_w, value_w = 190, 130
    bar_space = width - label_w - value_w
    top = max([abs(v) for _l, v, _c in items] + [max_value or 0.0, 1.0])
    height = row_height * len(items) + 4
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
             'font-family="Helvetica, Arial, sans-serif">' % (width, height, width, height)]
    for i, (label, value, color) in enumerate(items):
        yy = i * row_height + 4
        bar = max(bar_space * abs(value or 0.0) / top, 2)
        parts.append('<text x="0" y="%d" font-size="13" fill="#1F2937">%s</text>' % (yy + 18, escape(label)))
        parts.append('<rect x="%d" y="%d" width="%.1f" height="%d" rx="3" fill="%s"/>'
                     % (label_w, yy + 4, bar, row_height - 12, color))
        parts.append('<text x="%.1f" y="%d" font-size="12" font-weight="bold" fill="#1F2937">%s</text>'
                     % (label_w + bar + 6, yy + 18, escape(money(value))))
    parts.append('</svg>')
    return Markup(''.join(parts))
