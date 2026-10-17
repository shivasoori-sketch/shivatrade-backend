#!/usr/bin/env python3
"""Patch VPS render_chart_page + deploy kite-clean.js (run on VPS via stdin or copy)."""
import re
from pathlib import Path

VERSION = "layout-20261017m"
RELEASE = Path("/opt/shivtrade/releases/20261008_mc325_readonly_charts_r94")
PY = RELEASE / "mc325_readonly.py"
KITE_JS = RELEASE / "mc325" / "assets" / "kite-clean.js"
KITE_SRC = Path("/tmp/kite-clean.js")

text = PY.read_text()
start = text.index("def render_chart_page(ctx, source):")
end = text.index("\ndef install(ctx):", start)
new_fn = f'''def render_chart_page(ctx, source):
    """Use the same live site shell, without a second chart funds strip."""
    import re
    version = "{VERSION}"
    css_link = '<link rel="stylesheet" href="/mc325/assets/kite-clean.css?v=' + version + '">'
    kite_tag = '<script src="/mc325/assets/kite-clean.js?v=' + version + '"></script>'
    styles = ''.join(ctx[name] for name in (
        'COMMON_STYLE', 'DASHBOARD_STYLE', 'THEME_SHELL_STYLE',
        'UNIFORM_PAGE_STYLE', 'TYPOGRAPHY_SYSTEM_ASSETS',
        'TYPOGRAPHY_FINAL_ASSETS', 'RESPONSIVE_CONTRACT_STYLE',
        'SHARED_HEADER_STATUS_FINAL_STYLE', 'TOP_SHELL_GEOMETRY_FINAL_STYLE'))
    source = source.replace('<style>', styles + '<style>', 1)
    header = re.sub(r'<button\\b[^>]*class="sitePageRefresh".*?</button>', '', ctx['canonical_header']('mc325_charts', 'MC325 Charts'), count=1, flags=re.S)
    shell = '<div class="terminal homeTerminal mc325SharedShell">' + header + '</div>'
    source, count = re.subn(r'<header>.*?</header>\\s*<nav class="site-nav".*?</nav>', lambda _: shell, source, count=1, flags=re.S)
    if count != 1:
        raise ValueError('MC325 header mount missing')
    for sid in ('solo-chart-controller', 'fixed-trading-row-controller', 'kite-clean-layout'):
        source = re.sub(
            r'<script id="' + re.escape(sid) + r'">.*?</script>',
            '',
            source,
            count=1,
            flags=re.S,
        )
    for sid in ('kite-clean-style', 'fixed-trading-row-styles', 'solo-chart-layout'):
        source = re.sub(
            r'<style id="' + re.escape(sid) + r'">.*?</style>\\s*',
            '',
            source,
            count=1,
            flags=re.S,
        )
    source = re.sub(
        r'<link rel="stylesheet" href="/mc325/assets/kite-clean\\.css\\?v=[^"]+">\\s*',
        '',
        source,
    )
    source = re.sub(
        r'<script src="/mc325/assets/kite-clean\\.js\\?v=[^"]+"(?: defer)?></script>\\s*',
        '',
        source,
    )
    source = _sanitize_chart_html(source)
    source = source.replace('</head>', css_link + '</head>', 1)
    tape = ctx['SHARED_MARKET_TAPE_SCRIPT']
    source = source.replace('</body>', kite_tag + '\\n' + tape + '\\n</body>', 1)
    return source

'''
text = text[:start] + new_fn + text[end:]
PY.write_text(text)
print("patched", PY)

# multi-leg: patch multi_leg.py if it serves HTML directly
ml = RELEASE / "multi_leg.py"
if ml.exists():
    mlt = ml.read_text()
    if "render_multi_leg_page" in mlt or "multi-leg.html" in mlt:
        if VERSION not in mlt:
            mlt = re.sub(
                r'<style id="solo-chart-layout">.*?</style>\\s*',
                '',
                mlt,
                count=1,
                flags=re.S,
            )
            # ensure inject in route - grep multi_leg
    print("multi_leg.py len", len(mlt))

if KITE_SRC.exists():
    KITE_JS.write_bytes(KITE_SRC.read_bytes())
    print("wrote kite-clean.js", KITE_JS.stat().st_size)
