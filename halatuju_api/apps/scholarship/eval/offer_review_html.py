"""The offer-letter review pages' shared look and script (split out of `offer_review_page.py`,
2026-11-01, to keep that tool under the code-standards line limit — no behaviour change).

`page_html` wraps the cards in ONE self-contained, offline page: inline CSS, inline script, no
external file. The script keeps the owner's ticks in `localStorage`, counts letters looked at,
and "Save my answers" downloads the results JSON (`{"page": <page id>, "mode", "saved_at",
"letters"}`). Values are escaped by the caller; `intro` and `cards` are trusted HTML.
"""
import html


def _e(value):
    return html.escape(str(value), quote=True)


_CSS = '''
:root { --ink:#1a1a1a; --paper:#ffffff; --soft:#f3f3f0; --line:#c9c9c4; --accent:#1f5fa8;
        --warn:#9a3b00; --warnbg:#fff1e0; --ok:#1e6b2f; }
* { box-sizing:border-box; }
body { margin:0; padding:16px; font:18px/1.5 "Segoe UI", Arial, sans-serif; color:var(--ink);
       background:var(--soft); font-variant-numeric:lining-nums; }
h1 { font-size:28px; margin:0 0 8px; }
h2 { font-size:22px; margin:0 0 12px; }
.intro { max-width:900px; background:var(--paper); padding:16px; border:1px solid var(--line); }
#progress { font-size:20px; font-weight:bold; }
.card { background:var(--paper); border:1px solid var(--line); padding:16px; margin:24px 0; }
.cols { display:flex; flex-wrap:wrap; gap:24px; }
.left { flex:0 1 620px; min-width:0; position:sticky; top:8px; align-self:flex-start; }
.right { flex:1 1 360px; min-width:0; }
.doc { display:block; width:100%; max-width:600px; height:800px; border:1px solid var(--line);
       overflow:auto; background:#fafafa; }
.doc img { display:block; width:100%; height:auto; }
.problem { background:var(--warnbg); color:var(--warn); padding:8px 12px; font-weight:bold; }
.line { border:1px solid var(--line); margin:0 0 12px; padding:8px 12px; }
.line legend { font-weight:bold; padding:0 4px; }
.value { font-size:20px; margin:4px 0 8px; word-break:break-word; }
.value.blank { color:#666; font-style:italic; }
.unsure { background:var(--warnbg); color:var(--warn); border:1px solid var(--warn);
          padding:0 6px; font-size:16px; font-weight:bold; margin-left:6px; }
.choices label { display:inline-block; margin-right:24px; padding:4px 0; cursor:pointer; }
input[type=radio] { width:20px; height:20px; vertical-align:middle; }
.fix label, .note label { display:block; margin:8px 0 4px; }
input[type=text], textarea { width:100%; font:inherit; padding:6px 8px; border:1px solid #888; }
:focus-visible { outline:3px solid var(--accent); outline-offset:2px; }
.done-badge { color:var(--ok); font-size:18px; margin-left:8px; }
.save { text-align:center; padding:24px 0 48px; }
#save { font:inherit; font-size:24px; font-weight:bold; padding:16px 40px; color:#fff;
        background:var(--accent); border:0; cursor:pointer; }
#saved { font-size:20px; }
.readonly { border:1px dashed var(--line); margin:0 0 12px; padding:8px 12px; background:var(--soft); }
.ro-label { font-weight:bold; margin:0; }
.card-end { height:1px; }
'''

_JS = r'''
(function () {
  var KEY = "__STORAGE_KEY__";
  var SEEN_KEY = KEY + "-looked-at";
  var MODE = "__MODE__";          /* "prefilled": every line starts Right; "blank": none ticked */
  var cards = Array.prototype.slice.call(document.querySelectorAll(".card"));
  var seen = {};
  try { seen = JSON.parse(localStorage.getItem(SEEN_KEY) || "{}") || {}; } catch (e) { seen = {}; }
  function markSeen(card) {
    var k = card && card.getAttribute("data-key");
    if (!k || seen[k]) { return; }
    seen[k] = true;
    try { localStorage.setItem(SEEN_KEY, JSON.stringify(seen)); } catch (e) { /* no storage */ }
    refresh();
  }
  function collect() {
    var out = {};
    cards.forEach(function (card) {
      var fields = {};
      card.querySelectorAll(".line").forEach(function (line) {
        var picked = line.querySelector("input[type=radio]:checked");
        fields[line.getAttribute("data-field")] = {
          verdict: picked ? picked.value : "not_checked",
          correction: line.querySelector(".correction").value
        };
      });
      var noteBox = card.querySelector(".note-box");   /* the S2 page has no note box */
      out[card.getAttribute("data-key")] = {fields: fields,
                                            note: noteBox ? noteBox.value : "",
                                            looked_at: !!seen[card.getAttribute("data-key")]};
    });
    return out;
  }
  function refresh() {
    var done = 0;
    cards.forEach(function (card) {
      var lines = card.querySelectorAll(".line"), ticked = 0;
      lines.forEach(function (line) {
        var picked = line.querySelector("input[type=radio]:checked");
        if (picked) { ticked += 1; }
        line.querySelector(".fix").hidden = !(picked && picked.value === "wrong");
      });
      var isDone = MODE === "blank" ? ticked === lines.length
                                    : !!seen[card.getAttribute("data-key")];
      card.querySelector(".done-badge").hidden = !isDone;
      if (isDone) { done += 1; }
    });
    document.getElementById("progress").textContent = done + " of " + cards.length +
      (MODE === "blank" ? " done" : " letters looked at or changed");
  }
  function remember() {
    try { localStorage.setItem(KEY, JSON.stringify(collect())); } catch (e) { /* no storage */ }
  }
  function restore() {
    var saved = null;
    try { saved = JSON.parse(localStorage.getItem(KEY) || "null"); } catch (e) { saved = null; }
    if (!saved || typeof saved !== "object") { return; }
    cards.forEach(function (card) {
      var s = saved[card.getAttribute("data-key")];
      if (!s || typeof s !== "object") { return; }
      card.querySelectorAll(".line").forEach(function (line) {
        var f = (s.fields || {})[line.getAttribute("data-field")];
        if (!f) { return; }
        line.querySelector(".correction").value = f.correction || "";
        if (f.verdict !== "right" && f.verdict !== "wrong") { return; }  /* keeps the default */
        line.querySelectorAll("input[type=radio]").forEach(function (r) {
          r.checked = (r.value === f.verdict);
        });
      });
      var noteBox = card.querySelector(".note-box");
      if (noteBox) { noteBox.value = s.note || ""; }
    });
  }
  document.querySelectorAll("img[data-broken]").forEach(function (img) {
    img.addEventListener("error", function () {
      var p = document.createElement("p");
      p.className = "problem";
      p.textContent = img.getAttribute("data-broken");
      img.parentNode.replaceChild(p, img);
    });
  });
  function cardOf(ev) { return ev.target.closest ? ev.target.closest(".card") : null; }
  document.addEventListener("change", function (ev) {
    markSeen(cardOf(ev)); refresh(); remember();
  });
  document.addEventListener("input", function (ev) { markSeen(cardOf(ev)); remember(); });
  if ("IntersectionObserver" in window) {   /* a letter is looked at once its card end shows */
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { markSeen(en.target.closest(".card")); }
      });
    });
    document.querySelectorAll(".note, .card-end").forEach(function (n) { io.observe(n); });
  }
  document.getElementById("save").addEventListener("click", function () {
    var data = {page: "__PAGE__", mode: MODE, saved_at: new Date().toISOString(),
                letters: collect()};
    var blob = new Blob([JSON.stringify(data, null, 1)], {type: "application/json"});
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "__RESULTS_NAME__";
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
    remember();
    document.getElementById("saved").textContent =
      "Saved. Look for __RESULTS_NAME__ in your Downloads folder and send it back.";
  });
  restore();
  refresh();
})();
'''


def page_html(title, intro, cards, total, page_id, storage_key, results_name, blank):
    js = (_JS.replace('__STORAGE_KEY__', storage_key).replace('__RESULTS_NAME__', results_name)
          .replace('__PAGE__', page_id).replace('__MODE__', 'blank' if blank else 'prefilled'))
    progress = f'0 of {total} done' if blank else f'0 of {total} letters looked at or changed'
    return f'''<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(title)}</title>
<style>{_CSS}</style>
</head>
<body>
<header class="intro">
<h1>{_e(title)}</h1>
{intro}
<p id="progress" aria-live="polite">{progress}</p>
</header>
<main>
{cards}
</main>
<footer class="save">
<button type="button" id="save">Save my answers</button>
<p id="saved" aria-live="polite"></p>
</footer>
<script>{js}</script>
</body>
</html>
'''
