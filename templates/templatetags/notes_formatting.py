# core/templatetags/notes_formatting.py
#
# A deliberately tiny, dependency-free "markdown-ish" renderer for the
# Content.notes field. No pip install needed — this is a stopgap until a
# real rich-text editor (CKEditor) replaces the plain textarea. It reads a
# simple, typeable-in-a-plain-textarea convention and turns it into the
# same HTML classes public_content.html's CSS already styles (h2, strong,
# ul/li, .callout).
#
# Usage in a template:
#   {% load notes_formatting %}
#   {{ content.notes|render_notes }}

import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

_BOLD_RE = re.compile(r'\*\*(.+?)\*\*')
_ITALIC_RE = re.compile(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)')


def _inline(text):
    """Escape raw HTML first (so stray < > & from typing don't break the
    page), then apply **bold** / *italic* on top of the escaped text."""
    text = escape(text)
    text = _BOLD_RE.sub(r'<strong>\1</strong>', text)
    text = _ITALIC_RE.sub(r'<em>\1</em>', text)
    return text


@register.filter(name='render_notes')
def render_notes(value):
    """
    Line-based conversion, processed top to bottom:
      # Heading text        -> <h2>
      - bullet point        -> grouped into <ul><li>
      > callout text        -> grouped into a highlighted callout box
      blank line            -> paragraph break
      anything else         -> plain paragraph, with **bold**/*italic* applied
    """
    if not value:
        return ''

    lines = value.replace('\r\n', '\n').split('\n')
    html_parts = []
    paragraph_buffer = []
    i = 0
    n = len(lines)

    def flush_paragraph():
        if paragraph_buffer:
            text = ' '.join(paragraph_buffer).strip()
            if text:
                html_parts.append(f'<p>{_inline(text)}</p>')
            paragraph_buffer.clear()

    while i < n:
        raw_line = lines[i]
        stripped = raw_line.strip()

        if stripped == '':
            flush_paragraph()
            i += 1
            continue

        if stripped.startswith('# '):
            flush_paragraph()
            html_parts.append(f'<h2>{_inline(stripped[2:])}</h2>')
            i += 1
            continue

        if stripped.startswith('- '):
            flush_paragraph()
            items = []
            while i < n and lines[i].strip().startswith('- '):
                items.append(f'<li>{_inline(lines[i].strip()[2:])}</li>')
                i += 1
            html_parts.append('<ul>' + ''.join(items) + '</ul>')
            continue

        if stripped.startswith('> '):
            flush_paragraph()
            quote_lines = []
            while i < n and lines[i].strip().startswith('> '):
                quote_lines.append(_inline(lines[i].strip()[2:]))
                i += 1
            html_parts.append('<div class="callout">' + '<br>'.join(quote_lines) + '</div>')
            continue

        paragraph_buffer.append(stripped)
        i += 1

    flush_paragraph()
    return mark_safe(''.join(html_parts))
