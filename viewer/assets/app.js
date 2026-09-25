/* Offline service-manual viewer — vanilla SPA, no dependencies.
   The same shell reads legacy Ford build data or manufacturer-neutral records. */
'use strict';

const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s === null || s === undefined ? '' : s).replace(/[&<>"']/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const main = $('#main'), side = $('#sideInner');
const D = {};                      // lazily loaded json
const cache = new Map();           // fetched html fragments
let MANIFEST = null;

async function data(name) {
  if (!D[name]) {
    D[name] = fetch(`data/${name}.json`)
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`data/${name}.json: ${r.status}`)))
      .catch(e => { delete D[name]; throw e; });        // don't cache a failure
  }
  return D[name];
}
async function frag(book, id) {
  const k = book + '/' + id;
  if (!cache.has(k)) {
    cache.set(k, fetch(`content/${book}/${id}.html`)
      .then(r => r.ok ? r.text() : Promise.reject(new Error('not found')))
      .catch(e => { cache.delete(k); throw e; }));
  }
  return cache.get(k);
}

/* ------------------------------------------------------------------ router */
const BOOKS = [['wsm', 'Workshop Manual'], ['elb', 'Wiring'], ['pced', 'PCED']];

const SAFE = /^[a-z0-9][a-z0-9_.\-]*$/i;
const safeId = v => (v && SAFE.test(v) && !v.includes('..')) ? v : null;

/* Each book's files are named after its code (SLBLEFT.HTM, VL2S12L.HTM), and
   the codes differ from disc to disc — so the nav-shell patterns are built
   from the manifest rather than hardcoded. */
const rxEsc = s => String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
let _pfx = null;
async function prefix(role, fallback) {
  if (!_pfx) _pfx = (await data('manifest')).prefixes || {};
  return rxEsc(_pfx[role] || fallback);
}

function parseHash() {
  const raw = location.hash.replace(/^#\/?/, '');
  const [path, query] = raw.split('?');
  return { parts: path ? path.split('/') : [], q: new URLSearchParams(query || '') };
}

async function route() {
  const { parts, q } = parseHash();
  const [a, b, c] = parts;
  const manifest = MANIFEST || await data('manifest');
  MANIFEST = manifest;
  if (manifest.viewerMode === 'neutral') return await neutralRoute(parts, q, manifest);
  const tab = (a === 'conn') ? 'elb' : a;
  $$('#bookTabs a').forEach(el => el.classList.toggle('on', el.dataset.book === tab));
  document.body.classList.remove('nav-open');
  main.scrollTop = 0;
  try {
    if (!a)                       return await home();
    if (a === 'search')           return await search(q.get('q') || '', q.get('book') || '');
    if (a === 'wsm') {
      const id = safeId(b);
      if (!b) return await wsmHome();
      const P = await prefix('wsm', 'slb');
      if (new RegExp(`^${P}(left|main|right)$`).test(id || '')) { location.replace('#/wsm'); return; }
      if (new RegExp(`^${P}g\\d+l$`).test(id || ''))  return await wsmGroup(id);
      if (new RegExp(`^${P}s[\\w]+l$`).test(id || '')) return await wsmSection(id);
      return await wsmPage(id);
    }
    if (a === 'pced') {
      const id = safeId(b);
      if (!b) return await pcedHome();
      const P = await prefix('pced', 'vl2');
      if (new RegExp(`^${P}(left|main|right)$`).test(id || '')) { location.replace('#/pced'); return; }
      const sec = new RegExp(`^${P}s(\\d+)[lr]$`).exec(id || '');
      if (sec) return await pcedSection(sec[1]);
      return await pcedPage(id);
    }
    if (a === 'elb') {
      if (b === 'index')          return await wiringIndex(safeId(c) || 'component');
      if (b === 'cell')           return await cellPage(safeId(c));
      if (b === 'connectors')     return await connectorList();
      if (b)                      return await wiringPage(safeId(b));
      return await wiringHome();
    }
    if (a === 'conn' && b)        return await connectorPage(safeId(b));
    notFound();
  } catch (e) {
    side.innerHTML = '';
    main.innerHTML = `<div class="wrap"><h1 class="title">Something went wrong</h1>
      <p class="subtitle">${esc(e.message)}</p>
      <a class="card" href="#/" style="max-width:280px;margin-top:14px"><h3>← Back to start</h3></a>
      </div>`;
  }
}

const notFound = () => {
  side.innerHTML = '';
  main.innerHTML = `<div class="wrap"><h1 class="title">Page not found</h1>
    <p class="subtitle">That link points at something this disc doesn’t contain.</p>
    <a class="card" href="#/" style="max-width:280px"><h3>← Back to start</h3></a></div>`;
};

/* ---------------------------------------- manufacturer-neutral library mode */
const bookById = (manifest, id) => (manifest.books || []).find(book => book.id === id);
const neutralRouteOf = (publication, document, returnHash) => {
  const suffix = returnHash ? '?return=' + encodeURIComponent(returnHash) : '';
  return `#/manual/${publication}/${document}${suffix}`;
};
const safeReturn = value => (value && value.startsWith('#/search?')) ? value : '';

async function neutralRoute(parts, q, manifest) {
  const [a, b, c] = parts;
  const tab = a === 'manual' ? 'library' : a;
  $$('#bookTabs a').forEach(el => el.classList.toggle('on', el.dataset.book === tab));
  document.body.classList.remove('nav-open');
  main.scrollTop = 0;
  try {
    if (!a || a === 'library') return await neutralHome(manifest);
    if (a === 'search') return await search(q.get('q') || '', q.get('book') || '');
    if (a === 'manual' && safeId(b)) {
      if (!c) return await neutralPublication(b, manifest);
      if (safeId(c)) return await neutralPage(b, c, safeReturn(q.get('return') || ''), manifest);
    }
    return notFound();
  } catch (e) {
    side.innerHTML = '';
    main.innerHTML = `<div class="wrap"><h1 class="title">Something went wrong</h1>
      <p class="subtitle">${esc(e.message)}</p>
      <a class="card" href="#/" style="max-width:280px;margin-top:14px"><h3>← Back to start</h3></a>
      </div>`;
  }
}

function neutralHome(manifest) {
  side.innerHTML = '';
  const counts = manifest.counts || {};
  const warning = manifest.contentStatus === 'complete' ? '' : `<div class="note">
    <b>Partial manual material.</b> Some source pages could not be prepared. Missing items remain
    labeled in the viewer instead of being treated as complete.</div>`;
  main.innerHTML = `<div class="wrap"><div class="hero">
    <h1>${esc(manifest.title)}</h1>
    <p>${esc(manifest.sourceLabel || 'Offline service-manual library')} —
      ${counts.books || 0} publication${counts.books === 1 ? '' : 's'},
      ${counts.documents || 0} pages, and ${counts.searchable || 0} searchable records.</p>
    ${warning}</div><div class="grid">${(manifest.books || []).map(book => `
      <a class="card" href="#/manual/${book.id}"><h3>${esc(book.name)}</h3>
        <p>${esc(book.kind || 'manual')} · ${book.documents} page${book.documents === 1 ? '' : 's'} ·
          ${book.searchable} searchable</p>
        <p style="margin-top:9px"><span class="count">${esc(book.source_path)}</span></p></a>`).join('')}
      </div><p class="subtitle" style="margin-top:26px">Tip: press <kbd>/</kbd> to search every selected manual.</p>
    </div>`;
}

const navContains = (node, active) => node.document_id === active ||
  (node.children || []).some(child => navContains(child, active));

function neutralNav(nodes, publication, active, prefix) {
  let result = '';
  (nodes || []).forEach((node, index) => {
    const key = `n-${prefix}-${index}`;
    const children = node.children || [];
    const open = navContains(node, active);
    if (children.length) {
      result += `<button class="s-row${open ? ' open' : ''}" data-t="${key}">
        <svg class="caret" viewBox="0 0 24 24"><path d="M9 6l6 6-6 6"/></svg>
        <span>${esc(node.label)}</span></button><div class="s-kids${open ? ' open' : ''}" id="${key}">`;
      if (node.document_id)
        result += `<a class="s-link${node.document_id === active ? ' on' : ''}"
          href="#/manual/${publication}/${node.document_id}">Overview</a>`;
      result += neutralNav(children, publication, active, key) + '</div>';
    } else if (node.document_id) {
      result += `<a class="s-link${node.document_id === active ? ' on' : ''}"
        href="#/manual/${publication}/${node.document_id}">${esc(node.label)}</a>`;
    }
  });
  return result;
}

function neutralSidebar(book, active) {
  side.innerHTML = `<div class="s-head"><a href="#/manual/${book.id}">${esc(book.name)}</a></div>` +
    neutralNav(book.navigation, book.id, active, book.id.slice(-6));
  const current = $('.s-link.on', side);
  if (current) current.scrollIntoView({ block: 'center' });
}

async function neutralPublication(publication, manifest) {
  const book = bookById(manifest, publication);
  if (!book) return notFound();
  neutralSidebar(book, null);
  const first = book.landing_id ? `<a class="card" href="#/manual/${book.id}/${book.landing_id}">
    <h3>Open manual</h3><p>Start at the publication landing page.</p></a>` : '';
  const evidence = (book.applicability || []).map(item => esc(item.statement)).join(' · ');
  main.innerHTML = `<div class="wrap"><div class="crumbs"><a href="#/">Manual library</a></div>
    <div class="hero"><h1>${esc(book.name)}</h1>
      <p>${esc(book.kind || 'manual')} · ${book.documents} pages · ${book.searchable} searchable</p>
      ${evidence ? `<div class="note"><b>Source applicability:</b> ${evidence}</div>` : ''}</div>
    <div class="grid">${first}<a class="card" href="#/search?book=${book.id}&q=diagnostic">
      <h3>Search this manual</h3><p>Search only this publication first; edit the query after opening.</p></a></div>
    <p class="subtitle" style="margin-top:24px">Source path: ${esc(book.source_path)}</p></div>`;
}

async function neutralBacklinks(documentId, manifest, returnHash) {
  const [backlinks, library] = await Promise.all([data('backlinks'), data('library')]);
  const sources = (backlinks.pages || {})[documentId] || [];
  if (!sources.length) return '';
  return `<h2 style="font-size:15px;margin:28px 0 10px">Referenced by
      <span class="pill">${sources.length}</span></h2><div class="backs">${sources.slice(0, 20).map(id => {
        const document = library.documents[id];
        return `<a class="res" href="${neutralRouteOf(document.publication_id, id, returnHash)}">
          <div class="rt">${esc(document.title)}</div><div class="rb">${esc(document.path)}</div></a>`;
      }).join('')}</div>`;
}

function carryReturn(returnHash) {
  if (!returnHash) return;
  $$('.paper a[href^="#/manual/"]').forEach(link => {
    link.href += (link.href.includes('?') ? '&' : '?') + 'return=' + encodeURIComponent(returnHash);
  });
}

async function neutralPage(publication, documentId, returnHash, manifest) {
  const book = bookById(manifest, publication);
  const library = await data('library');
  const document = library.documents[documentId];
  if (!book || !document || document.publication_id !== publication) return notFound();
  neutralSidebar(book, documentId);
  let body;
  try { body = await frag('manual', documentId); } catch { return notFound(); }
  const context = (document.applicability || []).map(item => esc(item.statement)).join(' · ');
  const warnings = (document.warnings || []).concat(
    document.unavailable_references ? [`${document.unavailable_references} unavailable reference(s)`] : [],
    document.unavailable_figures ? [`${document.unavailable_figures} unavailable diagram(s)`] : []);
  const source = document.source_url ? `<a class="chip" href="${esc(document.source_url)}" target="_blank"
      rel="noopener">Open original PDF at page ${document.page}</a>` : '';
  main.innerHTML = `<div class="wrap"><div class="crumbs"><a href="#/">Manual library</a>
      <span class="sep">/</span><a href="#/manual/${book.id}">${esc(book.name)}</a>
      ${(document.breadcrumbs || []).map(value => `<span class="sep">/</span><span>${esc(value)}</span>`).join('')}</div>
    ${returnHash ? `<a class="chip" href="${esc(returnHash)}">← Return to search results</a>` : ''}
    <h1 class="title">${esc(document.title)}</h1>
    <div class="subtitle">${esc(document.path)} · ${esc(document.text_provenance)} text</div>
    ${context ? `<div class="note"><b>Applicability evidence:</b> ${context}</div>` : ''}
    ${warnings.length ? `<div class="note"><b>Unavailable or review-needed material:</b> ${warnings.map(esc).join(' · ')}</div>` : ''}
    ${source ? `<div class="chips">${source}</div>` : ''}
    ${body ? `<article class="paper">${body}</article>` : '<p class="empty">No prepared page body is available. The original citation is retained above.</p>'}
    <div id="backs"></div></div>`;
  carryReturn(returnHash);
  wireImages();
  neutralBacklinks(documentId, manifest, returnHash).then(value => {
    const element = $('#backs'); if (element) element.innerHTML = value;
  });
}

/* -------------------------------------------------------------------- home */
async function home() {
  const m = await data('manifest');
  side.innerHTML = '';
  const n = m.counts;
  main.innerHTML = `<div class="wrap">
    <div class="hero">
      <h1>${esc(m.title)}</h1>
      <p>${esc(m.sourceLabel || 'Service manual source')} —
         ${esc((m.books || []).map(b => b.name.toLowerCase()).join(', '))} — rebuilt as a browsable site.</p>
    </div>
    <div class="grid">
      <a class="card" href="#/wsm"><h3>Workshop Manual</h3>
        <p>Diagnosis &amp; testing, removal &amp; installation, specifications and torque values.</p>
        <p style="margin-top:9px"><span class="count">${n.wsm} procedures</span></p></a>
      <a class="card" href="#/elb"><h3>Wiring Diagrams</h3>
        <p>Schematics, component locations, grounds, splices and fuse charts.</p>
        <p style="margin-top:9px"><span class="count">${n.elb} sheets</span></p></a>
      <a class="card" href="#/elb/connectors"><h3>Connector Face Views</h3>
        <p>Pin-by-pin circuit, wire colour, gauge and terminal part numbers.</p>
        <p style="margin-top:9px"><span class="count">${n.conn} connectors</span></p></a>
      <a class="card" href="#/pced"><h3>PCED</h3>
        <p>Powertrain control &amp; emissions diagnosis — pinpoint tests, DTC charts, reference values.</p>
        <p style="margin-top:9px"><span class="count">${n.pced} pages</span></p></a>
    </div>
    <p class="subtitle" style="margin-top:26px">Tip: press <kbd>/</kbd> to search anywhere.</p>
  </div>`;
}

/* --------------------------------------------------------- workshop manual */
async function wsmSidebar(activeId) {
  const w = await data('wsm');
  let h = '<div class="s-head">Workshop Manual</div>';
  for (const ex of w.extras)
    h += `<a class="s-link" href="${ex.pdf ? `content/wsm/${ex.id}.pdf` : `#/wsm/${ex.id}`}"
            ${ex.pdf ? 'target="_blank"' : ''}>${esc(ex.title)}</a>`;
  w.tree.forEach((top, ti) => {
    h += `<div class="s-head">${esc(top.title)}</div>`;
    top.groups.forEach((g, gi) => {
      const open = (g.sections || []).some(s => (s.procs || []).some(p => p.id === activeId));
      h += `<button class="s-row${open ? ' open' : ''}" data-t="g${ti}-${gi}">
              <svg class="caret" viewBox="0 0 24 24"><path d="M9 6l6 6-6 6"/></svg>
              <span>${esc(g.title)}</span></button>
            <div class="s-kids${open ? ' open' : ''}" id="g${ti}-${gi}">`;
      g.sections.forEach(s => {
        const on = (s.procs || []).some(p => p.id === activeId);
        h += `<button class="s-row${on ? ' open' : ''}" data-t="s-${s.id}" style="font-size:12.5px">
                <svg class="caret" viewBox="0 0 24 24"><path d="M9 6l6 6-6 6"/></svg>
                <span>${esc(s.title)}</span></button>
              <div class="s-kids${on ? ' open' : ''}" id="s-${s.id}">`;
        let kind = null;
        (s.procs || []).forEach(p => {
          if (p.kind && p.kind !== kind) { kind = p.kind; h += `<div class="s-kind">${esc(kind)}</div>`; }
          h += `<a class="s-link${p.id === activeId ? ' on' : ''}" href="#/wsm/${p.id}">${esc(p.title)}</a>`;
        });
        h += '</div>';
      });
      h += '</div>';
    });
  });
  side.innerHTML = h;
  const cur = $('.s-link.on', side);
  if (cur) cur.scrollIntoView({ block: 'center' });
}

async function wsmHome() {
  await wsmSidebar(null);
  const w = await data('wsm');
  let h = `<div class="wrap"><div class="hero"><h1>Workshop Manual</h1>
    <p>Pick a group, or use search. Sections follow the publication’s numbering.</p></div>`;
  for (const top of w.tree) {
    h += `<h2 style="font-size:15px;margin:22px 0 10px;color:var(--dim)">${esc(top.title)}</h2><div class="grid">`;
    for (const g of top.groups)
      h += `<a class="card" href="#/wsm/${esc(g.id)}"><h3>${esc(g.title)}</h3>
              <p><span class="count">${g.sections.length} sections</span></p></a>`;
    h += '</div>';
  }
  main.innerHTML = h + '</div>';
}

async function wsmGroup(id) {
  const w = await data('wsm');
  let top = null, g = null;
  for (const t of w.tree) for (const x of t.groups) if (x.id === id) { top = t; g = x; }
  if (!g) return notFound();
  await wsmSidebar(null);
  main.innerHTML = `<div class="wrap">
    <div class="crumbs"><a href="#/wsm">Workshop Manual</a><span class="sep">/</span>
      <span>${esc(top.title)}</span></div>
    <h1 class="title">${esc(g.title)}</h1>
    <div class="subtitle">${g.sections.length} sections</div>
    <div class="grid">${g.sections.map(sec => `<a class="card" href="#/wsm/${esc(sec.id)}">
      <h3>${esc(sec.title)}</h3>
      <p><span class="count">${(sec.procs || []).length} procedures</span></p></a>`).join('')}</div>
  </div>`;
}

async function wsmSection(id) {
  const w = await data('wsm');
  let top = null, grp = null, sec = null;
  for (const t of w.tree) for (const g of t.groups) for (const x of g.sections)
    if (x.id === id) { top = t; grp = g; sec = x; }
  if (!sec) return notFound();
  await wsmSidebar(null);
  let kind = null, body = '';
  for (const p of (sec.procs || [])) {
    if (p.kind && p.kind !== kind) {
      kind = p.kind;
      body += `<h2 style="font-size:14px;margin:22px 0 9px;color:var(--dim);
        text-transform:uppercase;letter-spacing:.06em">${esc(kind)}</h2>`;
    }
    body += `<a class="res" href="#/wsm/${esc(p.id)}"><div class="rt">${esc(p.title)}</div>
      <div class="rb">${esc(p.id.toUpperCase())}</div></a>`;
  }
  main.innerHTML = `<div class="wrap">
    <div class="crumbs"><a href="#/wsm">Workshop Manual</a><span class="sep">/</span>
      <span>${esc(top.title)}</span><span class="sep">/</span>
      <a href="#/wsm/${esc(grp.id)}">${esc(grp.title)}</a></div>
    <h1 class="title">${esc(sec.title)}</h1>
    <div class="subtitle">${(sec.procs || []).length} procedures</div>
    ${body || '<p class="empty">No procedures listed for this section.</p>'}
    <div id="backs"></div></div>`;
  backlinksFor('wsm/' + id).then(h => { const el = $('#backs'); if (el) el.innerHTML = h; });
}

async function wsmPage(id) {
  if (!id) return notFound();
  const w = await data('wsm');
  let crumb = [], title = id.toUpperCase();
  outer: for (const top of w.tree) for (const g of top.groups) for (const s of g.sections)
    for (const p of (s.procs || [])) if (p.id === id) {
      crumb = [top.title, g.title, s.title]; title = p.title; break outer;
    }
  await wsmSidebar(id);
  let body;
  try { body = await frag('wsm', id); } catch { return notFound(); }
  main.innerHTML = `<div class="wrap">
    <div class="crumbs"><a href="#/wsm">Workshop Manual</a>
      ${crumb.map(c => `<span class="sep">/</span><span>${esc(c)}</span>`).join('')}</div>
    <h1 class="title">${esc(title)}</h1>
    <div class="subtitle">${esc(id.toUpperCase())}</div>
    <article class="paper">${body}</article>
    <div id="backs"></div></div>`;
  wireImages();
  backlinksFor('wsm/' + id).then(h => { const el = $('#backs'); if (el) el.innerHTML = h; });
}

/* ------------------------------------------------------------------- PCED */
async function pcedSidebar(activeId) {
  const p = await data('pced');
  let h = '<div class="s-head">PCED · Gasoline Engines</div>';
  p.forEach((s, i) => {
    const open = s.pages.some(x => x.id === activeId);
    h += `<button class="s-row${open ? ' open' : ''}" data-t="p${i}">
            <svg class="caret" viewBox="0 0 24 24"><path d="M9 6l6 6-6 6"/></svg>
            <span class="num">${esc(s.num)}</span><span>${esc(s.title)}</span></button>
          <div class="s-kids${open ? ' open' : ''}" id="p${i}">`;
    s.pages.forEach(x => {
      h += `<a class="s-link${x.id === activeId ? ' on' : ''}" href="#/pced/${x.id}">${esc(x.title)}</a>`;
    });
    h += '</div>';
  });
  side.innerHTML = h;
  const cur = $('.s-link.on', side);
  if (cur) cur.scrollIntoView({ block: 'center' });
}

async function pcedHome() {
  await pcedSidebar(null);
  const p = await data('pced');
  const man = await data('manifest');
  const veh = man.pcedVehicles || [];
  const yrs = (man.years || []).join('/');
  const scope = [yrs, man.pcedTitle || ''].filter(Boolean).join(' ');
  main.innerHTML = `<div class="wrap"><div class="hero"><h1>Powertrain Control / Emissions Diagnosis</h1>
    <p>${esc(scope || 'Powertrain diagnostics')}. Pinpoint tests, DTC charts, reference values
       and diagnostic methods.</p>
    ${veh.length > 1 ? `<div class="note"><b>Shared volume.</b> ${esc(man.manufacturer || 'The publisher')} supplies this book for
      ${veh.length} models, not just this one: ${esc(veh.join(', '))}.
      Check the applicability of a procedure before following it.</div>` : ''}</div>
    <div class="grid">${p.map(s => `<a class="card" href="#/pced/${s.pages[0].id}">
      <h3>${esc(s.num ? s.num + ': ' : '')}${esc(s.title)}</h3>
      <p><span class="count">${s.pages.length} pages</span></p></a>`).join('')}</div></div>`;
}

async function pcedSection(num) {
  const p = await data('pced');
  const sec = p.find(x => x.num === num);
  if (!sec) return notFound();
  await pcedSidebar(null);
  main.innerHTML = `<div class="wrap">
    <div class="crumbs"><a href="#/pced">PCED</a><span class="sep">/</span><span>Section ${esc(num)}</span></div>
    <h1 class="title">${esc(sec.title)}</h1>
    <div class="subtitle">${sec.pages.length} pages</div>
    ${sec.pages.map(x => `<a class="res" href="#/pced/${esc(x.id)}">
      <div class="rt">${esc(x.title)}</div>
      <div class="rb">${esc(x.id.toUpperCase())}</div></a>`).join('')}
  </div>`;
}

async function pcedPage(id) {
  if (!id) return notFound();
  const p = await data('pced');
  let sec = '', title = id.toUpperCase();
  for (const s of p) for (const x of s.pages) if (x.id === id) { sec = s.title; title = x.title; }
  await pcedSidebar(id);
  let body;
  try { body = await frag('pced', id); } catch { return notFound(); }
  main.innerHTML = `<div class="wrap">
    <div class="crumbs"><a href="#/pced">PCED</a><span class="sep">/</span><span>${esc(sec)}</span>
      <span class="sep">·</span><span title="This volume covers several vehicle models">shared volume</span></div>
    <h1 class="title">${esc(title)}</h1>
    <div class="subtitle">${esc(id.toUpperCase())}</div>
    <article class="paper">${body}</article>
    <div id="backs"></div></div>`;
  wireImages();
  backlinksFor('pced/' + id).then(h => { const el = $('#backs'); if (el) el.innerHTML = h; });
}

/* ---------------------------------------------------------------- wiring */
async function wiringSidebar(activeId) {
  const w = await data('wiring');
  let h = `<div class="s-head">Wiring</div>
    <a class="s-link" href="#/elb/connectors">Connector face views</a>
    <a class="s-link" href="#/elb/index/component">Component index</a>
    <a class="s-link" href="#/elb/index/connector">Connector index</a>
    <a class="s-link" href="#/elb/index/ground">Ground index</a>
    <a class="s-link" href="#/elb/index/splice">Splice index</a>
    <a class="s-link" href="#/elb/index/harness">Harness index</a>
    <div class="s-head">Cells</div>`;
  w.cells.filter(c => c.pages.length).forEach(c => {
    const open = c.pages.some(p => p.id === activeId);
    h += `<button class="s-row${open ? ' open' : ''}" data-t="c${c.cell}">
            <svg class="caret" viewBox="0 0 24 24"><path d="M9 6l6 6-6 6"/></svg>
            <span class="num">${esc(c.cell)}</span><span>${esc(c.title || 'Cell ' + c.cell)}</span></button>
          <div class="s-kids${open ? ' open' : ''}" id="c${c.cell}">`;
    c.pages.forEach(p => {
      h += `<a class="s-link${p.id === activeId ? ' on' : ''}" href="#/elb/${p.id}">
              <span class="num" style="margin-right:6px">${esc(p.num)}</span>${esc(p.title || '—')}</a>`;
    });
    h += '</div>';
  });
  side.innerHTML = h;
  const cur = $('.s-link.on', side);
  if (cur) cur.scrollIntoView({ block: 'center' });
}

async function wiringHome() {
  await wiringSidebar(null);
  const w = await data('wiring');
  const cells = w.cells.filter(c => c.pages.length);
  const man = await data('manifest');
  main.innerHTML = `<div class="wrap"><div class="hero"><h1>Wiring Diagrams</h1>
    <p>Electrical &amp; Vacuum Troubleshooting Manual${man.title ? ' — ' + esc(man.title.replace(/ Service Information$/, '')) : ''} —
       ${cells.reduce((a, c) => a + c.pages.length, 0)} sheets across ${cells.length} cells.</p></div>
    <div class="grid">${cells.map(c => `<a class="card" href="#/elb/${c.pages[0].id}">
      <h3><span class="count">${esc(c.cell)}</span> &nbsp;${esc(c.title || 'Cell ' + c.cell)}</h3>
      <p>${c.pages.length} sheet${c.pages.length > 1 ? 's' : ''}</p></a>`).join('')}</div></div>`;
}

async function cellPage(num) {
  if (!num) return notFound();
  await wiringSidebar(null);
  const w = await data('wiring');
  const c = w.cells.find(x => x.cell === num);
  if (!c) return notFound();
  main.innerHTML = `<div class="wrap">
    <div class="crumbs"><a href="#/elb">Wiring</a><span class="sep">/</span><span>Cell ${esc(num)}</span></div>
    <h1 class="title">${esc(c.title || 'Cell ' + num)}</h1>
    <div class="subtitle">Cell ${esc(num)} · ${c.pages.length} sheet${c.pages.length === 1 ? '' : 's'}</div>
    <div class="grid">${c.pages.map(p => `<a class="card" href="#/elb/${p.id}">
      <h3><span class="count">${esc(p.num)}</span> &nbsp;${esc(p.title || '—')}</h3>
      <p><span class="pill ${esc((p.type || '').toLowerCase())}">${esc(p.type || '—')}</span></p></a>`).join('')}</div>
  </div>`;
}

async function wiringPage(id) {
  if (!id) return notFound();
  const w = await data('wiring');
  let cell = null, page = null;
  for (const c of w.cells) for (const p of c.pages) if (p.id === id) { cell = c; page = p; }
  if (!page) return notFound();
  await wiringSidebar(id);
  const lists = [
    ['Connectors', page.conns, true], ['Grounds', page.grounds, false],
    ['Splices', page.splices, false], ['Fuses', page.fuses, false]
  ].filter(([, arr]) => arr && arr.length);

  main.innerHTML = `<div class="wrap">
    <div class="crumbs"><a href="#/elb">Wiring</a><span class="sep">/</span>
      <span>${esc(cell.cell)} ${esc(cell.title)}</span></div>
    <h1 class="title">${esc(page.title || 'Sheet ' + page.num)}</h1>
    <div class="subtitle"><span class="pill ${esc((page.type || '').toLowerCase())}">${esc(page.type || '—')}</span>
      &nbsp; Cell ${esc(cell.cell)} · Sheet ${esc(page.num)}</div>
    ${page.svg ? `<div class="viewer" id="vw">
        <div class="canvas" id="vwCanvas" data-src="content/elb/${esc(page.svg)}"></div>
        <div class="zbadge" id="vwZoom">100%</div>
        <div class="vtools">
          <button class="icon-btn" data-v="out"><svg viewBox="0 0 24 24"><path d="M5 12h14"/></svg></button>
          <button class="icon-btn" data-v="fit">FIT</button>
          <button class="icon-btn" data-v="1">1:1</button>
          <button class="icon-btn" data-v="in"><svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg></button>
          <a class="icon-btn" href="content/elb/${esc(page.svg)}" target="_blank" title="Open full sheet">
            <svg viewBox="0 0 24 24"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg></a>
        </div></div>` : '<p class="empty">This sheet is text-only — no diagram on the disc.</p>'}
    ${lists.map(([label, arr, link]) => `
      <h2 style="font-size:15px;margin:26px 0 10px">${label} <span class="pill">${arr.length}</span></h2>
      <table class="dt"><thead><tr><th>Name</th><th>Location</th><th>Zone</th><th>Sheet</th></tr></thead><tbody>
      ${arr.map(x => `<tr><td class="mono">${link && x.face
          ? `<a href="#/conn/${esc(x.face)}">${esc(x.name)}</a>` : esc(x.name)}</td>
        <td>${esc(x.loc || '')}</td><td class="mono">${esc(x.zone || '')}</td>
        <td class="mono">${x.locview
          ? `<a href="#/elb/${esc(x.locview)}">location</a>` : ''}</td></tr>`).join('')}
      </tbody></table>`).join('')}
  </div>`;
  if (page.svg) makeViewer($('#vw'));
}

async function wiringIndex(kind) {
  await wiringSidebar(null);
  const w = await data('wiring');
  if (!Object.prototype.hasOwnProperty.call(w.indexes, kind)) return notFound();
  const rows = w.indexes[kind];
  const labels = { component: 'Component', connector: 'Connector', ground: 'Ground',
                   splice: 'Splice', harness: 'Harness' };
  main.innerHTML = `<div class="wrap">
    <div class="crumbs"><a href="#/elb">Wiring</a><span class="sep">/</span><span>Index</span></div>
    <h1 class="title">${esc(labels[kind] || kind)} index</h1>
    <div class="subtitle">${rows.length} entries — sheet numbers open the location diagram.</div>
    <input class="filter" id="flt" placeholder="Filter…" autocomplete="off">
    <table class="dt"><thead><tr><th>Item</th><th>Location</th><th>Sheet</th><th>Grid</th><th>Applies to</th></tr></thead>
    <tbody id="tb"></tbody></table></div>`;
  const ids = new Set();
  for (const c of w.cells) for (const p of c.pages) ids.add(p.id);
  const sheetExists = id => ids.has(id);
  const draw = f => {
    const q = f.trim().toLowerCase();
    const list = q ? rows.filter(r => (r.item + ' ' + r.loc).toLowerCase().includes(q)) : rows;
    $('#tb').innerHTML = list.map(r => `<tr>
      <td class="mono">${esc(r.item)}</td><td>${esc(r.loc)}</td>
      <td class="mono">${r.page && sheetExists('elb151' + String(r.page).padStart(3, '0'))
          ? `<a href="#/elb/elb151${String(r.page).padStart(3, '0')}">${esc(r.page)}</a>`
          : esc(r.page)}</td><td class="mono">${esc(r.grid)}</td>
      <td>${esc(r.qual)}</td></tr>`).join('') ||
      '<tr><td colspan="5" class="empty">No matches.</td></tr>';
  };
  draw('');
  $('#flt').addEventListener('input', e => draw(e.target.value));
}

async function connectorList() {
  await wiringSidebar(null);
  const cs = await data('connectors');
  const rows = Object.entries(cs).sort((a, b) =>
    a[1].name.localeCompare(b[1].name, undefined, { numeric: true }));
  main.innerHTML = `<div class="wrap">
    <div class="crumbs"><a href="#/elb">Wiring</a><span class="sep">/</span><span>Connectors</span></div>
    <h1 class="title">Connector face views</h1>
    <div class="subtitle">${rows.length} connectors with full pin-out data.</div>
    <input class="filter" id="flt" placeholder="Filter by number or description…" autocomplete="off">
    <table class="dt"><thead><tr><th>Connector</th><th>Description</th><th>Pins</th><th>Type</th></tr></thead>
    <tbody id="tb"></tbody></table></div>`;
  const draw = f => {
    const q = f.trim().toLowerCase();
    const list = q ? rows.filter(([, c]) => (c.name + ' ' + c.desc).toLowerCase().includes(q)) : rows;
    $('#tb').innerHTML = list.map(([k, c]) => `<tr>
      <td class="mono"><a href="#/conn/${esc(k)}">${esc(c.name)}</a></td>
      <td>${esc(c.desc)}</td><td class="mono">${esc(c.pincount)}</td>
      <td>${esc(c.type || '')}${(c.faces || []).length > 1 ? ' <span class="pill">2 halves</span>' : ''}</td>
      </tr>`).join('') ||
      '<tr><td colspan="4" class="empty">No matches.</td></tr>';
  };
  draw('');
  $('#flt').addEventListener('input', e => draw(e.target.value));
}

async function connectorPage(key) {
  if (!key) return notFound();
  await wiringSidebar(null);
  const cs = await data('connectors');
  const c = cs[key];
  if (!c) return notFound();
  const faces = c.faces || [];
  const pinTable = pins => `<table class="dt"><thead><tr><th>Cav</th><th>Circuit</th>
      <th>Colour</th><th>Ga</th><th>Function</th><th>Terminal</th></tr></thead><tbody>
      ${pins.map(p => `<tr><td class="mono">${esc(p.cav)}</td><td class="mono">${esc(p.ckt)}</td>
        <td class="mono">${esc(p.color)}</td><td class="mono">${esc(p.gauge)}</td>
        <td>${esc(p.fn)}</td><td class="mono">${esc(p.term)}</td></tr>`).join('')}
      </tbody></table>`;

  const many = faces.length > 1;
  main.innerHTML = `<div class="wrap">
    <div class="crumbs"><a href="#/elb">Wiring</a><span class="sep">/</span>
      <a href="#/elb/connectors">Connectors</a></div>
    <h1 class="title">${esc(c.name)}</h1>
    <div class="subtitle">${esc(c.desc)} · ${esc(c.pincount)} cavities
      ${c.type ? '· ' + esc(c.type) : ''} ${c.shell ? '· shell ' + esc(c.shell) : ''}</div>
    <div id="onSheets"></div>
    ${many ? `<div class="note" style="border-left-color:var(--accent);background:rgba(58,160,255,.07)">
        <b>Two halves.</b> This is an inline connector — each side has its own drawing and
        pin-out below. Cavity numbers repeat between them.</div>` : ''}
    ${faces.map((f, i) => `
      <h2 style="font-size:15px;margin:26px 0 10px">
        ${many ? `Half ${i + 1}` : 'Face view'}${f.gender ? ' · ' + esc(f.gender) : ''}
        ${f.fpn ? `<span class="pill">${esc(f.fpn)}</span>` : ''}
        ${f.harness ? `<span class="pill">harness ${esc(f.harness)}</span>` : ''}</h2>
      ${f.file ? `<div class="viewer" data-vw="${i}">
        <div class="canvas" data-src="content/elb/${esc(f.file)}"></div>
        <div class="zbadge">100%</div>
        <div class="vtools">
          <button class="icon-btn" data-v="out"><svg viewBox="0 0 24 24"><path d="M5 12h14"/></svg></button>
          <button class="icon-btn" data-v="fit">FIT</button>
          <button class="icon-btn" data-v="1">1:1</button>
          <button class="icon-btn" data-v="in"><svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg></button>
          <a class="icon-btn" href="content/elb/${esc(f.file)}" target="_blank" title="Open full size">
            <svg viewBox="0 0 24 24"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg></a>
        </div></div>` : '<p class="empty">No drawing on the disc for this half.</p>'}
      ${f.pins.length ? pinTable(f.pins) : '<p class="empty">No pin data.</p>'}`).join('')}
  </div>`;
  $$('.viewer', main).forEach(makeViewer);

  const [bl, w] = await Promise.all([data('backlinks'), data('wiring')]);
  const sheets = (bl.connSheets || {})[key] || [];
  if (sheets.length) {
    const info = {};
    for (const cc of w.cells) for (const p of cc.pages)
      info[p.id] = `${cc.cell}-${p.num} ${p.title || ''}`.trim();
    const el = $('#onSheets');
    if (el) el.innerHTML = `<h2 style="font-size:15px;margin:22px 0 10px">Appears on
      <span class="pill">${sheets.length}</span> sheet${sheets.length === 1 ? '' : 's'}</h2>
      <div class="chips">${sheets.map(id =>
        `<a class="chip" href="#/elb/${esc(id)}">${esc(info[id] || id)}</a>`).join('')}</div>`;
  }
}

/* ------------------------------------------------------------------ search */
let SIDX = null, SDOC = null, AVGDL = 1;
const TOKEN = /\d+\.\d+[a-z]*|[a-z0-9][a-z0-9\-']{2,}/g;
const tokenize = s => s.toLowerCase().match(TOKEN) || [];
const K1 = 1.2, B = 0.35;   // low b: wiring stubs are short, don't reward that
const LABEL = { wsm: 'Workshop', elb: 'Wiring', pced: 'PCED', conn: 'Connector',
                ix: 'Index', cell: 'Wiring' };
// sheets, cell landing pages and indexes are all "Wiring" as far as filtering goes
const GROUP = { elb: 'elb', cell: 'elb', ix: 'elb', wsm: 'wsm', pced: 'pced', conn: 'conn' };
const routeOf = d => d[0] === 'conn' ? `#/conn/${d[1]}`
  : d[0] === 'elb' ? `#/elb/${d[1]}`
  : d[0] === 'ix'  ? `#/elb/index/${d[1]}`
  : d[0] === 'cell' ? `#/elb/cell/${d[1]}`
  : d[0] === 'manual' ? `#/manual/${d[4]}/${d[1]}`
  : `#/${d[0]}/${d[1]}`;

function rank(q) {
  const terms = [...new Set(tokenize(q))];
  const N = SDOC.length, acc = new Map(), IDF = new Map();
  let used = 0;
  for (const t of terms) {
    /* Always fold in longer words starting with the same stem, at reduced
       weight: otherwise "ground" misses every page that only says "grounds". */
    const hits = new Map();
    const add = (arr, w) => {
      for (let i = 0; i < arr.length; i += 2)
        hits.set(arr[i], (hits.get(arr[i]) || 0) + arr[i + 1] * w);
    };
    if (SIDX[t]) add(SIDX[t], 1);
    let widened = 0;
    for (const k in SIDX) {
      if (k === t || !k.startsWith(t)) continue;
      add(SIDX[k], 0.6);
      if (++widened > 80) break;
    }
    if (!hits.size) continue;
    used++;
    const df = hits.size;
    const idf = Math.log(1 + (N - df + 0.5) / (df + 0.5));   // common words count for little
    IDF.set(t, idf);
    for (const [id, tf] of hits) {
      const dl = SDOC[id][3] || 1;
      const norm = tf * (K1 + 1) / (tf + K1 * (1 - B + B * dl / AVGDL));
      const e = acc.get(id) || { s: 0, m: 0 };
      e.s += idf * norm; e.m++; acc.set(id, e);
    }
  }
  const ql = q.trim().toLowerCase();
  const out = [];
  for (const [id, e] of acc) {
    const d = SDOC[id], title = d[2].toLowerCase(), tt = tokenize(title);
    // body: matching every word beats matching one word many times
    let s = e.s * Math.pow(e.m / Math.max(1, used), 2);
    if (used > 1 && e.m < used) s *= 0.3;
    /* A word in the title is a far stronger signal than the same word buried in
       a long procedure — "ground" should surface the Grounds sheets and the
       Ground index ahead of 500 pages that merely say "ground". */
    let hits = 0, ts = 0;
    for (const t of terms) {
      if (tt.some(w => w.startsWith(t))) { hits++; ts += IDF.get(t) || 1; }
    }
    s += ts * 7;
    if (hits && hits === terms.length) s *= 2.2;             // whole query in the title
    if (ql && title.includes(ql)) s *= 3;                    // as an exact phrase
    out.push([id, s]);
  }
  out.sort((a, b) => b[1] - a[1]);
  return { out, used };
}

async function neutralSearch(q, book, manifest) {
  side.innerHTML = '';
  const box = $('#q');
  if (document.activeElement !== box) box.value = q;
  if (!q.trim()) {
    main.innerHTML = `<div class="wrap"><h1 class="title">Search</h1>
      <p class="subtitle">Type at least two characters.</p></div>`;
    return;
  }
  main.innerHTML = `<div class="wrap"><h1 class="title">Searching…</h1></div>`;
  if (!SIDX) {
    [SIDX, SDOC] = await Promise.all([data('search-index'), data('search-docs')]);
    AVGDL = SDOC.length ? SDOC.reduce((total, document) => total + (document[3] || 1), 0) /
      SDOC.length : 1;
  }
  const ranked = rank(q);
  const selected = bookById(manifest, book) ? book : '';
  const counts = {};
  for (const [id] of ranked.out) {
    const publication = SDOC[id][4];
    counts[publication] = (counts[publication] || 0) + 1;
  }
  const matches = selected
    ? ranked.out.filter(([id]) => SDOC[id][4] === selected)
    : ranked.out;
  const list = matches.slice(0, 150);
  const returnHash = `#/search?q=${encodeURIComponent(q)}${selected ? '&book=' + selected : ''}`;
  const chip = (id, name, count) => `<a class="chip${selected === id ? ' on' : ''}"
    href="#/search?q=${encodeURIComponent(q)}${id ? '&book=' + id : ''}">${esc(name)} <b>${count}</b></a>`;
  const chips = [chip('', 'All manuals', ranked.out.length)].concat((manifest.books || [])
    .filter(item => counts[item.id])
    .map(item => chip(item.id, item.name, counts[item.id]))).join('');
  main.innerHTML = `<div class="wrap"><h1 class="title">${matches.length || 'No'} result${matches.length === 1 ? '' : 's'}</h1>
    <div class="subtitle">for “${esc(q)}”${selected ? ' in ' + esc(bookById(manifest, selected).name) : ''}${
      matches.length > list.length ? ` · showing first ${list.length}` : ''}</div>
    <div class="chips">${chips}</div>${list.map(([id]) => {
      const document = SDOC[id];
      const publication = bookById(manifest, document[4]);
      return `<a class="res" href="${neutralRouteOf(document[4], document[1], returnHash)}">
        <div class="rt"><span class="tagline tag-manual">${esc(publication.kind || 'manual')}</span>${esc(document[2])}</div>
        <div class="rb">${esc(publication.name)}</div></a>`;
    }).join('') || `<p class="empty">Nothing matched${ranked.used ? '' : ' — try fewer or shorter words'}.</p>`}</div>`;
}

async function search(q, book) {
  const manifest = MANIFEST || await data('manifest');
  MANIFEST = manifest;
  if (manifest.viewerMode === 'neutral') return neutralSearch(q, book, manifest);
  side.innerHTML = '';
  const box = $('#q');
  if (document.activeElement !== box) box.value = q;   // don't fight live typing
  if (!q.trim()) {
    main.innerHTML = `<div class="wrap"><h1 class="title">Search</h1>
      <p class="subtitle">Type at least two characters.</p></div>`;
    return;
  }
  main.innerHTML = `<div class="wrap"><h1 class="title">Searching…</h1></div>`;
  if (!SIDX) {
    [SIDX, SDOC] = await Promise.all([data('search-index'), data('search-docs')]);
    AVGDL = SDOC.reduce((a, d) => a + (d[3] || 1), 0) / SDOC.length;
  }
  const { out, used } = rank(q);

  const counts = {};
  for (const [id] of out) { const b = GROUP[SDOC[id][0]] || SDOC[id][0]; counts[b] = (counts[b] || 0) + 1; }
  let list = book ? out.filter(([id]) => (GROUP[SDOC[id][0]] || SDOC[id][0]) === book) : out;

  /* One cell can hold a dozen near-identically titled sheets; showing all of
     them buries everything else. Keep two, then collapse the rest. */
  const cellTotal = {};
  for (const [id] of list) {
    const d = SDOC[id];
    if (d[0] === 'elb') { const c = d[1].slice(3, 6); cellTotal[c] = (cellTotal[c] || 0) + 1; }
  }
  const seen = {}, rows = [];
  for (const [id] of list) {
    const d = SDOC[id];
    if (d[0] === 'elb') {
      const c = d[1].slice(3, 6);
      seen[c] = (seen[c] || 0) + 1;
      if (seen[c] > 2) {
        if (seen[c] === 3 && cellTotal[c] > 2)
          rows.push({ group: c, n: cellTotal[c] - 2 });
        continue;
      }
    }
    rows.push({ d });
    if (rows.length >= 150) break;
  }

  const chip = (id, name, n) => `<a class="chip${book === id ? ' on' : ''}"
      href="#/search?q=${encodeURIComponent(q)}${id ? '&book=' + id : ''}">${name} <b>${n}</b></a>`;
  const chips = [chip('', 'All', out.length)]
    .concat(Object.entries(counts).sort((a, b) => b[1] - a[1])
      .map(([b, n]) => chip(b, LABEL[b] || b, n))).join('');

  main.innerHTML = `<div class="wrap">
    <h1 class="title">${out.length || 'No'} result${out.length === 1 ? '' : 's'}</h1>
    <div class="subtitle">for “${esc(q)}”</div>
    <div class="chips">${chips}</div>
    ${rows.map(r => r.group
      ? `<a class="res" href="#/elb/cell/${r.group}">
           <div class="rt"><span class="tagline tag-elb">Wiring</span>${r.n} more sheet${r.n === 1 ? '' : 's'} in cell ${r.group}</div>
           <div class="rb">Open the whole cell</div></a>`
      : `<a class="res" href="${routeOf(r.d)}">
           <div class="rt"><span class="tagline tag-${r.d[0] === 'cell' || r.d[0] === 'ix' ? 'elb' : r.d[0]}">${LABEL[r.d[0]]}</span>${esc(r.d[2])}</div>
           <div class="rb">${esc(r.d[1].toUpperCase())}</div></a>`).join('') ||
      `<p class="empty">Nothing matched${used ? '' : ' — try fewer or shorter words'}.</p>`}
  </div>`;
}

/* --------------------------------------------------------- reverse links */
async function backlinksFor(key) {
  const [bl, docs] = await Promise.all([data('backlinks'), data('search-docs')]);
  const srcs = (bl.pages || {})[key] || [];
  if (!srcs.length) return '';
  const title = {};
  for (const d of docs) title[d[0] + '/' + d[1]] = d[2];
  const shown = srcs.slice(0, 14);
  return `<h2 style="font-size:15px;margin:28px 0 10px">Referenced by
      <span class="pill">${srcs.length}</span></h2>
    <div class="backs">${shown.map(k => `<a class="res" href="#/${k}">
        <div class="rt">${esc(title[k] || k.split('/')[1].toUpperCase())}</div>
        <div class="rb">${esc(k.split('/')[1].toUpperCase())}</div></a>`).join('')}
      ${srcs.length > shown.length
        ? `<p class="subtitle" style="margin:8px 0 0">and ${srcs.length - shown.length} more</p>` : ''}</div>`;
}

/* -------------------------------------------------- pan / zoom for diagrams */
function makeViewer(root) {
  const canvas = $('.canvas', root), badge = $('.zbadge', root);
  const src = canvas.dataset.src;
  let node = null, scale = 1, tx = 0, ty = 0, natural = null, fitted = false;

  const apply = () => {
    if (node) node.style.transform = `translate(${tx}px,${ty}px) scale(${scale})`;
    if (badge) badge.textContent = Math.round(scale * 100) + '%';
  };
  const fit = () => {
    if (!natural) return;
    const r = canvas.getBoundingClientRect();
    // a hidden pane / not-yet-laid-out container measures 0; refitting later
    // is handled by the ResizeObserver below
    if (r.width < 2 || r.height < 2) return;
    scale = Math.min(r.width / natural.w, r.height / natural.h);
    tx = (r.width - natural.w * scale) / 2;
    ty = (r.height - natural.h * scale) / 2;
    fitted = true;
    apply();
  };
  const zoomAt = (f, cx, cy) => {
    const r = canvas.getBoundingClientRect();
    const px = (cx - r.left - tx) / scale, py = (cy - r.top - ty) / scale;
    scale = Math.min(24, Math.max(.05, scale * f));
    tx = cx - r.left - px * scale; ty = cy - r.top - py * scale;
    apply();
  };
  /* These SVGs declare width/height="100%", so an <img> has no intrinsic size.
     Inline them instead and take the dimensions from the viewBox. */
  (async () => {
    if (/\.svg$/i.test(src)) {
      let text;
      try { text = await fetch(src).then(r => r.text()); }
      catch { canvas.innerHTML = '<p class="empty" style="padding:20px">Diagram missing.</p>'; return; }
      /* Must be parsed as XML: the <desc> block holds custom tags such as
         <Qualifier /> that the HTML parser would treat as unclosed, swallowing
         the rest of the drawing. */
      let xml = text.replace(/<script[\s\S]*?<\/script>/gi, '');
      if (!/<svg[^>]*\sxmlns\s*=/i.test(xml))
        xml = xml.replace(/<svg\b/i, '<svg xmlns="http://www.w3.org/2000/svg"');
      const doc = new DOMParser().parseFromString(xml, 'image/svg+xml');
      if (doc.querySelector('parsererror') || doc.documentElement.tagName !== 'svg') {
        canvas.innerHTML = '<p class="empty" style="padding:20px">Diagram could not be parsed.</p>';
        return;
      }
      canvas.textContent = '';
      node = canvas.appendChild(document.importNode(doc.documentElement, true));
      const vb = (node.getAttribute('viewBox') || '').split(/[\s,]+/).map(Number);
      natural = (vb.length === 4 && vb[2] > 0)
        ? { w: vb[2], h: vb[3] }
        : { w: parseFloat(node.getAttribute('width')) || 1100,
            h: parseFloat(node.getAttribute('height')) || 850 };
      node.setAttribute('width', natural.w);
      node.setAttribute('height', natural.h);
      node.style.width = natural.w + 'px';
      node.style.height = natural.h + 'px';
      fit();
    } else {
      node = new Image(); node.src = src; canvas.appendChild(node);
      const go = () => {
        natural = { w: node.naturalWidth || 1100, h: node.naturalHeight || 850 };
        node.style.width = natural.w + 'px'; node.style.height = natural.h + 'px'; fit();
      };
      node.complete && node.naturalWidth ? go() : node.addEventListener('load', go);
    }
  })();

  canvas.addEventListener('wheel', e => {
    e.preventDefault(); zoomAt(Math.exp(-e.deltaY * 0.0016), e.clientX, e.clientY);
  }, { passive: false });

  const pts = new Map(); let last = null, pinch = 0;
  canvas.addEventListener('pointerdown', e => {
    canvas.setPointerCapture(e.pointerId); pts.set(e.pointerId, e);
    canvas.classList.add('drag'); last = e; pinch = 0;
  });
  canvas.addEventListener('pointermove', e => {
    if (!pts.has(e.pointerId)) return;
    pts.set(e.pointerId, e);
    if (pts.size === 2) {
      const [a, b] = [...pts.values()];
      const d = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
      if (pinch) zoomAt(d / pinch, (a.clientX + b.clientX) / 2, (a.clientY + b.clientY) / 2);
      pinch = d;
    } else if (last) {
      tx += e.clientX - last.clientX; ty += e.clientY - last.clientY; apply();
    }
    last = e;
  });
  const up = e => { pts.delete(e.pointerId); if (!pts.size) { canvas.classList.remove('drag'); last = null; } pinch = 0; };
  canvas.addEventListener('pointerup', up);
  canvas.addEventListener('pointercancel', up);
  canvas.addEventListener('dblclick', e => zoomAt(1.9, e.clientX, e.clientY));

  root.addEventListener('click', e => {
    const b = e.target.closest('[data-v]'); if (!b) return;
    const r = canvas.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    if (b.dataset.v === 'in')  zoomAt(1.35, cx, cy);
    if (b.dataset.v === 'out') zoomAt(1 / 1.35, cx, cy);
    if (b.dataset.v === 'fit') fit();
    if (b.dataset.v === '1')   { scale = 1; tx = 0; ty = 0; apply(); }
  });
  /* Refit when the container first gains a size (or changes), and stop
     observing once the node is gone so listeners don't pile up per page. */
  if (typeof ResizeObserver === 'function') {
    const ro = new ResizeObserver(() => {
      if (!document.contains(canvas)) { ro.disconnect(); return; }
      if (!fitted) fit();   // container had no size when the diagram loaded
    });
    ro.observe(canvas);
  } else {
    window.addEventListener('resize', fit, { passive: true });
  }
}

/* --------------------------------------------------------------- lightbox */
const lb = $('#lightbox'), lbImg = $('#lbImg'), lbStage = $('#lbStage');
let ls = 1, lx = 0, ly = 0, lnat = null;
const lbApply = () => lbImg.style.transform = `translate(${lx}px,${ly}px) scale(${ls})`;
const lbFit = () => {
  if (!lnat) return;
  const r = lbStage.getBoundingClientRect();
  ls = Math.min(r.width / lnat.w, r.height / lnat.h, 1);
  lx = (r.width - lnat.w * ls) / 2; ly = (r.height - lnat.h * ls) / 2; lbApply();
};
function openLightbox(src, caption) {
  lb.hidden = false; $('#lbCaption').textContent = caption || '';
  lbImg.src = src;
  const go = () => {
    lnat = { w: lbImg.naturalWidth, h: lbImg.naturalHeight };
    lbImg.style.width = lnat.w + 'px'; lbImg.style.height = lnat.h + 'px'; lbFit();
  };
  lbImg.complete && lbImg.naturalWidth ? go() : lbImg.addEventListener('load', go, { once: true });
}
const closeLb = () => { lb.hidden = true; lbImg.src = ''; };
$('#lbClose').addEventListener('click', closeLb);
lb.addEventListener('click', e => { if (e.target === lb || e.target === lbStage) closeLb(); });
lb.addEventListener('click', e => {
  const b = e.target.closest('[data-z]'); if (!b) return;
  const r = lbStage.getBoundingClientRect(), cx = r.width / 2, cy = r.height / 2;
  const z = f => { const px = (cx - lx) / ls, py = (cy - ly) / ls;
    ls = Math.min(20, Math.max(.05, ls * f)); lx = cx - px * ls; ly = cy - py * ls; lbApply(); };
  if (b.dataset.z === 'in') z(1.35);
  if (b.dataset.z === 'out') z(1 / 1.35);
  if (b.dataset.z === 'fit') lbFit();
});
lbStage.addEventListener('wheel', e => {
  e.preventDefault();
  const r = lbStage.getBoundingClientRect(), cx = e.clientX - r.left, cy = e.clientY - r.top;
  const px = (cx - lx) / ls, py = (cy - ly) / ls;
  ls = Math.min(20, Math.max(.05, ls * Math.exp(-e.deltaY * 0.0016)));
  lx = cx - px * ls; ly = cy - py * ls; lbApply();
}, { passive: false });
{
  const pts = new Map(); let last = null, pinch = 0;
  lbStage.addEventListener('pointerdown', e => {
    lbStage.setPointerCapture(e.pointerId); pts.set(e.pointerId, e);
    lbStage.classList.add('drag'); last = e; pinch = 0;
  });
  lbStage.addEventListener('pointermove', e => {
    if (!pts.has(e.pointerId)) return;
    pts.set(e.pointerId, e);
    if (pts.size === 2) {
      const [a, b] = [...pts.values()];
      const d = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
      if (pinch) {
        const r = lbStage.getBoundingClientRect();
        const cx = (a.clientX + b.clientX) / 2 - r.left, cy = (a.clientY + b.clientY) / 2 - r.top;
        const px = (cx - lx) / ls, py = (cy - ly) / ls;
        ls = Math.min(20, Math.max(.05, ls * (d / pinch)));
        lx = cx - px * ls; ly = cy - py * ls; lbApply();
      }
      pinch = d;
    } else if (last) { lx += e.clientX - last.clientX; ly += e.clientY - last.clientY; lbApply(); }
    last = e;
  });
  const up = e => { pts.delete(e.pointerId); if (!pts.size) { lbStage.classList.remove('drag'); last = null; } pinch = 0; };
  lbStage.addEventListener('pointerup', up);
  lbStage.addEventListener('pointercancel', up);
}
function wireImages() {
  $$('.paper img').forEach(im => {
    im.addEventListener('click', () => openLightbox(im.src, im.getAttribute('alt') ||
      im.src.split('/').pop().toUpperCase()));
  });
}

/* ------------------------------------------------------------------- chrome */
$('#searchForm').addEventListener('submit', e => {
  e.preventDefault();
  location.hash = '#/search?q=' + encodeURIComponent($('#q').value.trim());
});
let stimer;
$('#q').addEventListener('input', e => {
  clearTimeout(stimer);
  const v = e.target.value.trim();
  if (v.length < 2) return;
  stimer = setTimeout(() => {
    location.hash = '#/search?q=' + encodeURIComponent(v);
  }, 320);
});
$('#navToggle').addEventListener('click', () => document.body.classList.toggle('nav-open'));
$('#scrim').addEventListener('click', () => document.body.classList.remove('nav-open'));

side.addEventListener('click', e => {
  const row = e.target.closest('.s-row'); if (!row) return;
  row.classList.toggle('open');
  const kids = document.getElementById(row.dataset.t);
  if (kids) kids.classList.toggle('open');
});

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { if (!lb.hidden) closeLb(); else document.body.classList.remove('nav-open'); }
  if (e.key === '/' && document.activeElement !== $('#q')) { e.preventDefault(); $('#q').focus(); $('#q').select(); }
});

window.addEventListener('hashchange', route);

async function bootstrap() {
  MANIFEST = await data('manifest');
  $('#bookTabs').innerHTML = MANIFEST.viewerMode === 'neutral'
    ? '<a href="#/" data-book="library">Manual library</a>'
    : BOOKS.filter(([id]) => (MANIFEST.books || []).some(book => book.id === id))
      .map(([id, name]) => `<a href="#/${id}" data-book="${id}">${name}</a>`).join('');
  await route();
}

bootstrap().catch(error => {
  side.innerHTML = '';
  main.innerHTML = `<div class="wrap"><h1 class="title">Viewer could not start</h1>
    <p class="subtitle">${esc(error.message)}</p></div>`;
});
