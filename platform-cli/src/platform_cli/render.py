"""Render the catalog as a static page.

No web application to run or secure: ``platform catalog render`` produces a
single self-contained HTML file from the same catalog the cluster deploys
from. CI can publish it; reviewers can open it locally. The portal is a
build artifact, not a service to operate.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment

from .catalog import Entry

PAGE_TEMPLATE = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>andamio — service catalog</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 60rem; color: #1a1a1a; }
  h1 { font-weight: 600; }
  p.sub { color: #555; }
  table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
  th, td { text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid #ddd; }
  th { border-bottom: 2px solid #1a1a1a; }
  code { background: #f4f4f4; padding: 0.1rem 0.3rem; border-radius: 3px; }
  .tier-t1 { color: #b30000; font-weight: 600; }
  .tier-t2 { color: #b36b00; }
  .tier-t3 { color: #555; }
  .lifecycle-deprecated { text-decoration: line-through; }
</style>
</head>
<body>
<h1>andamio &mdash; service catalog</h1>
<p class="sub">{{ entries | length }} entries. Generated from <code>catalog/*.yaml</code> by <code>platform catalog render</code>.</p>
<table>
<thead>
<tr><th>Name</th><th>Kind</th><th>Owner</th><th>Tier</th><th>Lifecycle</th><th>Description</th><th>Links</th></tr>
</thead>
<tbody>
{% for e in entries %}
<tr class="lifecycle-{{ e.lifecycle.value }}">
  <td><code>{{ e.name }}</code></td>
  <td>{{ e.kind.value }}</td>
  <td>{{ e.owner }}</td>
  <td class="tier-{{ e.tier.value }}">{{ e.tier.value }}</td>
  <td>{{ e.lifecycle.value }}</td>
  <td>{{ e.description }}</td>
  <td>
    {%- if e.links.runbook %}<a href="{{ e.links.runbook }}">runbook</a> {% endif -%}
    {%- if e.links.dashboard %}<a href="{{ e.links.dashboard }}">dashboard</a> {% endif -%}
    {%- if e.links.source %}<a href="{{ e.links.source }}">source</a>{% endif -%}
  </td>
</tr>
{% endfor %}
</tbody>
</table>
</body>
</html>
"""


def render_html(entries: list[Entry], destination: Path) -> Path:
    env = Environment(autoescape=True)
    page = env.from_string(PAGE_TEMPLATE).render(entries=entries)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(page, encoding="utf-8")
    return destination
