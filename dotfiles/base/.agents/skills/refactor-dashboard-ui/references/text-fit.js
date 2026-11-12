(() => {
  const issues = [];
  const sel = "h1,h2,h3,p,span,strong,em,b,a,button,li>span,output,figcaption span,div.fin-tip span";
  for (const el of document.querySelectorAll(sel)) {
    if (!el.offsetParent || el.closest("svg")) continue;
    const cs = getComputedStyle(el);
    if (el.scrollWidth > el.clientWidth + 1 && (cs.overflow === "hidden" || cs.textOverflow === "ellipsis")) issues.push("CLIPPED: " + el.textContent.trim().slice(0, 60));
    if (cs.display.startsWith("inline") || el.children.length) continue;
    const range = document.createRange(); range.selectNodeContents(el);
    const lines = new Set([...range.getClientRects()].map(r => Math.round(r.top))).size;
    const text = el.textContent.trim();
    if (lines > 1 && text.length < 60 && !el.closest(".fin-group-head p, .fin-bullets, .fin-foot, .fin-panel-note")) issues.push("WRAPPED(" + lines + "): " + text);
  }
  const r = document.documentElement;
  return JSON.stringify({ overflowX: r.scrollWidth > r.clientWidth, issues: [...new Set(issues)].slice(0, 40) });
})()
