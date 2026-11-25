"""Ordo's look: graphite and steel, with a highlighter yellow on the lines a person must check."""

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
:root{--paper:#F6F7F5;--sheet:#FFFFFF;--ink:#1D2430;--steel:#5B6676;--rule:#DCE0E5;--marker:#FFE066;--marker-ink:#6B5300;--ok:#2F7D5B;--block:#B4361E;--blockbg:#FBE9E5}
html,body,.stApp,.stMarkdown,button,input,textarea,select,[data-testid="stWidgetLabel"]{font-family:'IBM Plex Sans',system-ui,sans-serif !important}
.stApp{background:var(--paper);color:var(--ink)}
[data-testid="stToolbar"],[data-testid="stDecoration"],footer,#MainMenu,[data-testid="stHeaderActionElements"]{display:none !important}
[data-testid="stHeader"]{background:transparent}
.block-container{max-width:1180px;padding-top:2rem;padding-bottom:4rem}
textarea,input{font-family:'IBM Plex Sans',system-ui,sans-serif !important}

.o-top{display:flex;align-items:baseline;justify-content:space-between;gap:16px;flex-wrap:wrap;border-bottom:1px solid var(--rule);padding-bottom:14px;margin-bottom:6px}
.o-mark{font-size:28px;font-weight:600;letter-spacing:-.02em}
.o-mark span{display:inline-block;width:11px;height:11px;background:var(--marker);margin-left:6px;border-radius:2px;transform:translateY(-3px)}
.o-tag{color:var(--steel);font-size:15px}
.o-pill{display:inline-block;font-size:13px;border:1px solid var(--rule);border-radius:20px;padding:2px 10px;color:var(--steel);background:var(--sheet);margin-left:10px}

.o-step{display:flex;align-items:center;gap:12px;margin:30px 0 10px}
.o-step b{width:26px;height:26px;border-radius:50%;border:1.5px solid var(--ink);display:inline-flex;align-items:center;justify-content:center;font-size:13px;font-weight:600;flex:none}
.o-step h3{margin:0 !important;padding:0 !important;font-size:20px !important;font-weight:600 !important}
.o-step.off{opacity:.35}
.o-hint{color:var(--steel);font-size:14.5px;margin:-4px 0 12px 38px;max-width:75ch}

.o-mail{background:var(--sheet);border:1px solid var(--rule);border-radius:8px;padding:14px 18px;font-size:14px}
.o-mail .h{color:var(--steel);font-size:13px;margin-bottom:8px;word-break:break-word}
.o-mail pre{white-space:pre-wrap;font-family:'IBM Plex Sans',system-ui,sans-serif;font-size:14px;margin:0;max-height:260px;overflow:auto;color:var(--ink);background:none;padding:0}

.o-order{background:var(--sheet);border:1px solid var(--rule);border-radius:8px;padding:16px 20px}
.o-order .who{font-size:22px;font-weight:600;letter-spacing:-.01em}
.o-order .meta{color:var(--steel);font-size:14px;margin-top:2px}
.o-figs{display:flex;gap:32px;flex-wrap:wrap;margin-top:14px;padding-top:12px;border-top:1px solid var(--rule)}
.o-figs div{font-size:13.5px;color:var(--steel)}
.o-figs strong{display:block;font-size:24px;font-weight:500;color:var(--ink);font-variant-numeric:tabular-nums}
.o-figs .warn strong{color:var(--marker-ink)}
.o-figs .bad strong{color:var(--block)}
.o-note{color:var(--steel);font-size:13.5px;margin-top:10px}

.o-sheet{width:100%;border-collapse:collapse;background:var(--sheet);border:1px solid var(--rule);border-radius:8px;overflow:hidden;font-size:14.5px;margin-top:6px}
.o-sheet th{text-align:left;font-weight:500;color:var(--steel);font-size:13px;padding:10px 12px;border-bottom:1px solid var(--rule) !important;background:#FAFBFA}
.o-sheet td{padding:11px 12px;border-bottom:1px solid #EEF0F2 !important;vertical-align:top}
.o-sheet th,.o-sheet td{border-left:none !important;border-right:none !important}
.o-sheet .n{color:var(--steel);width:28px}
.o-sheet .q,.o-sheet .p{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.o-sheet code,.o-ref{font-family:'IBM Plex Mono',monospace !important;font-size:13px;background:none !important;color:var(--ink) !important;padding:0 !important}
.o-sheet .src{color:var(--steel)}
.o-sheet .des{color:var(--steel);font-size:13.5px}
.o-sheet tr.doubt td{background:linear-gradient(transparent 8%,var(--marker) 8%,var(--marker) 92%,transparent 92%)}
.o-sheet tr.block td{background:var(--blockbg)}
.o-sheet tr.gone td{color:#9AA3AE;text-decoration:line-through}
.st{font-size:13px;white-space:nowrap;font-weight:500}
.st.ok{color:var(--ok)}
.st.ok::before{content:"";display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--ok);margin-right:6px;transform:translateY(-1px)}
.st.doubt{color:var(--marker-ink);font-weight:600}
.st.block{color:var(--block);font-weight:600}
.why{color:var(--steel);font-size:13px;margin-top:2px}

[class*="st-key-fix_"]{background:var(--sheet);border:1px solid var(--rule);border-left:6px solid var(--marker);border-radius:8px;padding:14px 18px 16px}
[class*="st-key-fixb_"]{background:var(--sheet);border:1px solid var(--rule);border-left:6px solid var(--block);border-radius:8px;padding:14px 18px 16px}
.o-q{font-size:15px}
.o-q small{color:var(--steel);font-size:14px}
.o-reasons{color:var(--steel);font-size:14px;margin:2px 0 8px}
.o-cand{font-size:14px;line-height:1.4;min-height:58px}
.o-cand em{font-style:normal;color:var(--steel);font-size:13px}

.stButton>button,.stDownloadButton>button,.stLinkButton>a{border-radius:6px;border:1px solid var(--rule);background:var(--sheet);color:var(--ink);font-weight:500;box-shadow:none}
.stButton>button:hover,.stDownloadButton>button:hover,.stLinkButton>a:hover{border-color:var(--ink);color:var(--ink)}
.stButton>button[kind="primary"],.stDownloadButton>button[kind="primary"],.stLinkButton>a[kind="primary"]{background:var(--ink);color:#fff;border-color:var(--ink)}
.stButton>button[kind="primary"]:hover,.stDownloadButton>button[kind="primary"]:hover,.stLinkButton>a[kind="primary"]:hover{background:#303a4a;color:#fff}
.stButton>button:disabled{opacity:.45}

.o-done{background:var(--sheet);border:1px solid var(--rule);border-left:6px solid var(--ok);border-radius:8px;padding:14px 18px;font-size:15px}
.o-done b{color:var(--ok)}
.o-wait{color:var(--marker-ink);font-size:14.5px;margin:4px 0 8px}
.o-blocked{color:var(--block);font-size:14.5px;margin:4px 0 8px}

[data-testid="stSidebar"]{background:#EEF0EF;border-right:1px solid var(--rule)}
[data-baseweb="tab-highlight"]{background:var(--ink) !important}
[data-testid="stMetricValue"]{font-weight:500}
@media(max-width:640px){.o-figs{gap:18px}.o-sheet .hide-sm{display:none}}
</style>
"""
