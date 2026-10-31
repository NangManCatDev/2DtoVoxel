// 2DtoVoxel UI — hash router + views. No build step; served by voxtool/ui/server.py.
import { LANGS, getLang, locale, setLang, t } from './i18n.js';

const TOKEN = document.querySelector('meta[name=token]').content;
const main = document.getElementById('main');

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const tt = (key, vars) => esc(t(key, vars));   // translated + HTML-escaped

async function api(path, opts = {}) {
  const o = { ...opts, headers: { 'X-Lang': getLang(), ...(opts.headers || {}) } };
  if (o.body !== undefined) {
    o.body = JSON.stringify(o.body);
    o.headers['Content-Type'] = 'application/json';
  }
  if (o.method && o.method !== 'GET') o.headers['X-Token'] = TOKEN;
  const r = await fetch(path, o);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}
const post = (path, body = {}) => api(path, { method: 'POST', body });

const state = { status: null, models: [], jobs: [], trash: [], timers: [], cleanup: [], route: '' };

function every(ms, fn) { state.timers.push(setInterval(fn, ms)); }
function onLeave(fn) { state.cleanup.push(fn); }
function leave() {
  state.timers.forEach(clearInterval);
  state.cleanup.forEach((fn) => { try { fn(); } catch (e) { console.warn(e); } });
  state.timers = []; state.cleanup = [];
}

function toast(msg, err = false) {
  const el = document.createElement('div');
  el.className = 'toast' + (err ? ' err' : '');
  el.textContent = msg;
  document.getElementById('toasts').append(el);
  setTimeout(() => el.remove(), err ? 7000 : 3500);
}
const fail = (e) => toast(e.message || String(e), true);

function ago(ts) {
  const s = Math.max(0, Date.now() / 1000 - ts);
  if (s < 60) return t('time.now');
  if (s < 3600) return t('time.min', { n: Math.floor(s / 60) });
  if (s < 86400) return t('time.hour', { n: Math.floor(s / 3600) });
  return t('time.day', { n: Math.floor(s / 86400) });
}
function dur(sec) {
  sec = Math.round(sec);
  const m = Math.floor(sec / 60), s = sec % 60;
  return m ? t('dur.ms', { m, s }) : t('dur.s', { s });
}
const jobTitle = (j) => `${t(`kind.${j.kind}`)} · ${j.name}`;
const scoreText = (iou, de) => (iou == null ? '' : `IoU ${Number(iou).toFixed(3)}${de != null ? ` · ΔE ${Number(de).toFixed(1)}` : ''}`);

// light markdown for Claude's replies: `code`, **bold**, line breaks kept by CSS
function md(s) {
  return esc(s).replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
}

// tiny inline line chart (values left to right), e.g. IoU per build
function sparkline(values, { w = 120, h = 28 } = {}) {
  const v = values.filter((x) => x != null);
  if (v.length < 2) return '';
  const lo = Math.min(...v), hi = Math.max(...v), span = hi - lo || 1;
  const pts = v.map((x, i) => `${(i / (v.length - 1)) * (w - 4) + 2},${h - 2 - ((x - lo) / span) * (h - 4)}`).join(' ');
  const [lx, ly] = pts.split(' ').pop().split(',');
  return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true">
    <polyline points="${pts}" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>
    <circle cx="${lx}" cy="${ly}" r="2.4" fill="currentColor"/></svg>`;
}

// ------------------------------------------------------------------ shell (static text, language picker)
function applyShell() {
  document.querySelectorAll('[data-i18n]').forEach((el) => { el.textContent = t(el.dataset.i18n); });
  const sel = document.getElementById('lang');
  sel.setAttribute('aria-label', t('nav.language'));
  sel.value = getLang();
}
function initLangPicker() {
  const sel = document.getElementById('lang');
  sel.innerHTML = Object.entries(LANGS).map(([k, label]) => `<option value="${k}">${label}</option>`).join('');
  sel.addEventListener('change', () => {
    setLang(sel.value);
    applyShell();
    renderEnv();
    lastSidebar = '';
    refreshSidebar();
    route();
  });
}

// ------------------------------------------------------------------ lightbox
const lightbox = document.getElementById('lightbox');
lightbox.addEventListener('click', () => { lightbox.hidden = true; });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') lightbox.hidden = true; });
document.addEventListener('click', (e) => {
  const img = e.target.closest('img[data-zoom]');
  if (!img) return;
  lightbox.querySelector('img').src = img.src;
  lightbox.hidden = false;
});

// ------------------------------------------------------------------ confirmation dialog
// Resolves true when the confirm button is clicked; Escape, Cancel or a click outside resolve false.
function confirmDialog({ title, body = '', confirm, disabled = false, danger = true }) {
  return new Promise((resolve) => {
    const before = document.activeElement;
    const wrap = document.createElement('div');
    wrap.className = 'modal-backdrop';
    wrap.innerHTML = `<div class="modal" role="alertdialog" aria-modal="true" aria-labelledby="modal-title" aria-describedby="modal-body">
        <h2 id="modal-title">${esc(title)}</h2>
        ${body ? `<div id="modal-body" class="modal-body">${body}</div>` : ''}
        <div class="modal-actions">
          <button class="btn" type="button" data-act="cancel">${tt('dlg.cancel')}</button>
          <button class="btn ${danger ? 'danger-solid' : 'primary'}" type="button" data-act="ok" ${disabled ? 'disabled' : ''}>${esc(confirm)}</button>
        </div></div>`;
    const buttons = () => [...wrap.querySelectorAll('button:not([disabled])')];
    const onKey = (e) => {
      if (e.key === 'Escape') { e.stopPropagation(); close(false); }
      if (e.key === 'Tab') {                 // keep focus inside the dialog
        const b = buttons(), i = b.indexOf(document.activeElement);
        e.preventDefault();
        b[(i + (e.shiftKey ? b.length - 1 : 1)) % b.length].focus();
      }
    };
    function close(ok) {
      document.removeEventListener('keydown', onKey, true);
      wrap.remove();
      before?.focus?.();
      resolve(ok);
    }
    wrap.addEventListener('click', (e) => {
      if (e.target === wrap) return close(false);
      const act = e.target.closest('[data-act]')?.dataset.act;
      if (act) close(act === 'ok');
    });
    document.addEventListener('keydown', onKey, true);
    document.body.append(wrap);
    wrap.querySelector('[data-act="cancel"]').focus();
  });
}

// ------------------------------------------------------------------ deleting a model
const TRASH_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" '
  + 'stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M10 11v6M14 11v6M5 7l1 12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/></svg>';

async function askDelete(slug) {
  let info;
  try { info = await api(`/api/models/${encodeURIComponent(slug)}/delete-check`); } catch (e) { return fail(e); }
  const warn = [];
  if (info.running) warn.push(tt('del.running'));
  if (info.used_by.length) warn.push(tt('del.usedBy', { list: info.used_by.join(', ') }));
  if (info.edited) warn.push(tt('del.edited'));
  const body = `<p>${tt('del.body')}</p>
    <ul>${info.items.map((p) => `<li><code>${esc(p)}</code></li>`).join('')}</ul>
    <p class="muted">${tt('del.keepRef')}</p>
    ${warn.map((w) => `<p class="warn-line">${w}</p>`).join('')}`;
  const ok = await confirmDialog({ title: t('del.title', { name: slug }), body, confirm: t('del.confirm'),
    disabled: info.running });
  if (!ok) return;
  try {
    const r = await post(`/api/models/${encodeURIComponent(slug)}/delete`);
    toast(t('del.done', { name: slug, path: r.trash }));
    const [, kind, id] = state.route.split('/');
    if (kind === 'model' && decodeURIComponent(id || '') === slug) location.hash = '#/';
    lastSidebar = '';
    refreshSidebar();
  } catch (e) { fail(e); }
}
document.getElementById('model-list').addEventListener('click', (e) => {
  const btn = e.target.closest('[data-del]');
  if (!btn) return;
  e.preventDefault();
  askDelete(btn.dataset.del);
});

// ------------------------------------------------------------------ trash
async function viewTrash() {
  let entries;
  try { entries = await api('/api/trash'); } catch (e) { return fail(e); }
  main.innerHTML = `<section class="page">
    <div class="page-head">
      <div><h1>${tt('trash.title')}</h1><div class="muted">${tt('trash.hint')}</div></div>
      <div class="actions">${entries.length ? `<button class="btn danger" id="trash-empty">${tt('trash.empty')}</button>` : ''}</div>
    </div>
    ${entries.length ? entries.map((en) => `
      <div class="card trash-item">
        <div class="row"><b class="mono">${esc(en.id)}</b><span class="muted small">${esc(ago(en.time))}</span><span class="spacer"></span>
          <button class="btn primary" data-restore-trash="${esc(en.id)}">${tt('trash.restore')}</button>
          <button class="btn danger" data-purge="${esc(en.id)}">${tt('trash.purge')}</button></div>
        <ul class="files">${en.items.map((i) => `<li><code>${esc(i)}</code></li>`).join('')}</ul>
      </div>`).join('') : `<p class="muted">${tt('trash.none')}</p>`}
  </section>`;
  const after = (msg) => { toast(msg); lastSidebar = ''; refreshSidebar(); viewTrash(); };
  main.querySelectorAll('[data-restore-trash]').forEach((b) => b.addEventListener('click', async () => {
    b.disabled = true;
    try {
      const r = await post(`/api/trash/${encodeURIComponent(b.dataset.restoreTrash)}/restore`);
      after(t('trash.restored', { list: r.restored.join(', ') }));
    } catch (e) { fail(e); b.disabled = false; }
  }));
  main.querySelectorAll('[data-purge]').forEach((b) => b.addEventListener('click', async () => {
    if (!await confirmDialog({ title: t('trash.purgeTitle', { name: b.dataset.purge }),
      body: `<p>${tt('trash.purgeBody')}</p>`, confirm: t('trash.purge') })) return;
    try { await post(`/api/trash/${encodeURIComponent(b.dataset.purge)}/purge`); after(t('trash.purged')); } catch (e) { fail(e); }
  }));
  document.getElementById('trash-empty')?.addEventListener('click', async () => {
    if (!await confirmDialog({ title: t('trash.emptyTitle', { n: entries.length }),
      body: `<p>${tt('trash.purgeBody')}</p>`, confirm: t('trash.empty') })) return;
    try { await post('/api/trash/purge'); after(t('trash.purged')); } catch (e) { fail(e); }
  });
}

// ------------------------------------------------------------------ sidebar
let lastSidebar = '';
async function refreshSidebar() {
  try {
    const [models, jobs, trash] = await Promise.all([api('/api/models'), api('/api/jobs'), api('/api/trash')]);
    state.models = models; state.jobs = jobs; state.trash = trash;
  } catch (e) { return; }
  const sig = JSON.stringify([state.models, state.jobs.slice(0, 8), state.trash.length, Math.floor(Date.now() / 60000)]);
  if (sig !== lastSidebar) {
    lastSidebar = sig;
    const trashLink = document.getElementById('trash-link');
    trashLink.hidden = !state.trash.length;
    trashLink.innerHTML = `${TRASH_ICON}<span>${tt('trash.link', { n: state.trash.length })}</span>`;
    document.getElementById('model-list').innerHTML = state.models.length ? state.models.map((m) => {
      const sub = m.running ? (m.pending ? t('nav.generating') : t('nav.running')) : (m.title || (m.has_vox ? '' : t('nav.noVox')));
      return `
      <li><a href="#/model/${esc(m.slug)}" data-slug="${esc(m.slug)}">
        <span class="thumb" style="${m.thumb ? `background-image:url('${m.thumb}')` : ''}"></span>
        <span class="meta"><div class="nm">${esc(m.slug)}</div><div class="sub">${esc(sub)}</div></span>
        ${m.running ? '<span class="dot running"></span>' : ''}
      </a>${m.pending ? '' : `<button class="del" type="button" data-del="${esc(m.slug)}" title="${tt('del.button')}"
        aria-label="${tt('del.aria', { name: m.slug })}">${TRASH_ICON}</button>`}</li>`;
    }).join('') : `<li class="empty">${tt('nav.noModels')}</li>`;
    document.getElementById('job-list').innerHTML = state.jobs.length ? state.jobs.slice(0, 8).map((j) => `
      <li><a href="#/job/${esc(j.id)}" data-job="${esc(j.id)}">
        <span class="dot ${j.status}"></span><span>${esc(jobTitle(j))}</span><span class="when">${esc(ago(j.started))}</span>
      </a></li>`).join('') : `<li class="empty">${tt('nav.noJobs')}</li>`;
  }
  highlight();
}
function highlight() {
  const [, kind, id] = state.route.split('/');
  document.querySelectorAll('#model-list a').forEach((a) => a.classList.toggle('active', kind === 'model' && a.dataset.slug === id));
  document.querySelectorAll('#job-list a').forEach((a) => a.classList.toggle('active', kind === 'job' && a.dataset.job === id));
  document.getElementById('trash-link').classList.toggle('active', kind === 'trash');
}

async function loadStatus() {
  state.status = await api('/api/status');
  renderEnv();
}
function renderEnv() {
  const s = state.status;
  if (!s) return;
  document.getElementById('env').innerHTML = `
    <span class="chip ${s.claude ? 'ok' : 'bad'}" title="${esc(s.claude || t('env.claudeHint'))}">Claude Code</span>
    <span class="chip ${s.magicavoxel ? 'ok' : 'bad'}" title="${esc(s.magicavoxel || t('env.mvHint'))}">MagicaVoxel</span>`;
}

// ------------------------------------------------------------------ router
function route() {
  leave();
  state.route = location.hash.slice(1) || '/';
  const [, kind, id, sub] = state.route.split('/');
  window.scrollTo(0, 0);
  if (kind === 'new') viewNew();
  else if (kind === 'model' && id) viewModel(decodeURIComponent(id), sub || 'compare');
  else if (kind === 'job' && id) viewJob(id);
  else if (kind === 'trash') viewTrash();
  else viewHome();
  highlight();
}
window.addEventListener('hashchange', route);

const modelOptions = (short = false) => `
  <option value="">${tt(short ? 'model.defaultShort' : 'model.default')}</option>
  <option value="opus" selected>${short ? 'Opus' : tt('model.opus')}</option>
  <option value="sonnet">${short ? 'Sonnet' : tt('model.sonnet')}</option>`;

// cost / build limits shared by "new model" and "request changes"
const limitFields = (prefix) => `
  <div class="row two">
    <label class="field">${tt('limit.budget')} <span class="hint">${tt('new.optional')}</span>
      <input type="text" inputmode="decimal" id="${prefix}-budget" placeholder="${tt('limit.budgetPh')}"></label>
    <label class="field">${tt('limit.builds')} <span class="hint">${tt('new.optional')}</span>
      <input type="text" inputmode="numeric" id="${prefix}-builds" placeholder="${tt('limit.buildsPh')}"></label>
  </div>`;
const limitValues = (prefix) => ({
  budget: document.getElementById(`${prefix}-budget`).value.trim(),
  max_builds: document.getElementById(`${prefix}-builds`).value.trim(),
});

// ------------------------------------------------------------------ home
function viewHome() {
  const models = state.models.filter((m) => m.has_vox);
  main.innerHTML = `
    <section class="page">
      <div class="page-head">
        <div><h1>${tt('home.title')}</h1><p class="lead">${tt('home.lead')}</p></div>
        <a class="btn primary big" href="#/new">${tt('home.cta')}</a>
      </div>
      ${models.length ? `<div class="gallery">${models.map((m) => `
        <a class="tile" href="#/model/${esc(m.slug)}">
          <div class="img" style="${m.thumb ? `background-image:url('${m.thumb}')` : ''}"></div>
          <div class="cap"><b>${esc(m.slug)}</b><span>${esc(m.title)}</span></div>
        </a>`).join('')}</div>`
        : `<div class="card"><p class="muted" style="margin:0">${tt('home.empty')}</p></div>`}
    </section>`;
}

// ------------------------------------------------------------------ new model
function slugFrom(filename) {
  let s = filename.toLowerCase().replace(/\.[^.]+$/, '').replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
  if (!/^[a-z]/.test(s) || s.length < 2) {
    const d = new Date();
    const p2 = (n) => String(n).padStart(2, '0');
    s = `model_${d.getMonth() + 1}${p2(d.getDate())}_${p2(d.getHours())}${p2(d.getMinutes())}`;
  }
  s = s.slice(0, 36);
  const taken = new Set(state.models.map((m) => m.slug));
  let out = s, i = 2;
  while (taken.has(out)) out = `${s}_${i++}`;
  return out;
}

async function viewNew() {
  const noClaude = state.status && !state.status.claude;
  main.innerHTML = `
    <section class="page">
      <h1>${tt('new.title')}</h1>
      <p class="lead">${tt('new.lead')}</p>
      <div class="grid2">
        <div class="card">
          <h2>${tt('new.step1')}</h2>
          <label class="drop" id="drop">
            <input type="file" accept="image/*" hidden id="file">
            <strong>${tt('new.drop')}</strong>
            <span>${tt('new.dropHint')}</span>
          </label>
          <div class="ref-preview" id="ref-preview"><span class="muted">${tt('new.noSelection')}</span></div>
          <div class="ref-grid" id="ref-grid"></div>
        </div>
        <div class="card">
          <h2>${tt('new.step2')}</h2>
          <div class="modes" role="radiogroup">
            <label class="mode"><input type="radio" name="mode" value="claude" checked>
              <b>${tt('mode.claude')}</b><span>${tt('mode.claudeHint')}</span></label>
            <label class="mode"><input type="radio" name="mode" value="convert">
              <b>${tt('mode.convert')}</b><span>${tt('mode.convertHint')}</span></label>
          </div>
          <label class="field">${tt('new.name')} <span class="hint">${tt('new.nameHint')}</span>
            <input type="text" id="name" placeholder="player_house" autocomplete="off" spellcheck="false"></label>
          <div id="claude-fields">
            ${noClaude ? `<div class="banner warn">${tt('new.noClaude')}</div>` : ''}
            <label class="field">${tt('new.notes')} <span class="hint">${tt('new.optional')}</span>
              <textarea id="notes" placeholder="${tt('new.notesPh')}"></textarea></label>
            <label class="field">${tt('new.model')}<select id="model">${modelOptions()}</select></label>
            ${limitFields('new')}
          </div>
          <div id="convert-fields" hidden>
            <div class="row two">
              <label class="field">${tt('convert.depth')}<input type="text" inputmode="numeric" id="depth" value="4"></label>
              <label class="field check"><input type="checkbox" id="inflate"> ${tt('convert.inflate')}</label>
            </div>
            <p class="muted small">${tt('convert.hint')}</p>
          </div>
          <button class="btn primary big block" id="start">${tt('new.start')}</button>
          <ol class="steps" id="steps">
            <li>${tt('new.s1')}</li><li>${tt('new.s2')}</li><li>${tt('new.s3')}</li><li>${tt('new.s4')}</li>
          </ol>
        </div>
      </div>
    </section>`;

  let selected = null;
  let nameDirty = false;
  const nameEl = document.getElementById('name');
  const startBtn = document.getElementById('start');
  nameEl.addEventListener('input', () => { nameDirty = true; });

  const mode = () => document.querySelector('input[name=mode]:checked').value;
  const syncMode = () => {
    const conv = mode() === 'convert';
    document.getElementById('claude-fields').hidden = conv;
    document.getElementById('convert-fields').hidden = !conv;
    document.getElementById('steps').hidden = conv;
    startBtn.textContent = t(conv ? 'convert.start' : 'new.start');
    startBtn.disabled = !conv && noClaude;
  };
  document.querySelectorAll('input[name=mode]').forEach((r) => r.addEventListener('change', syncMode));
  syncMode();

  const select = (ref) => {
    selected = ref;
    document.getElementById('ref-preview').innerHTML = `<img src="${ref.url}" alt="" data-zoom>`;
    document.querySelectorAll('#ref-grid button').forEach((b) => b.classList.toggle('sel', b.dataset.path === ref.path));
    if (!nameDirty) nameEl.value = slugFrom(ref.name);
  };
  const drawRefs = async (pick) => {
    const refs = await api('/api/references');
    const grid = document.getElementById('ref-grid');
    grid.innerHTML = refs.map((r) => `<button type="button" data-path="${esc(r.path)}" title="${esc(r.name)}"><img src="${r.url}" alt=""></button>`).join('');
    grid.querySelectorAll('button').forEach((b) => b.addEventListener('click', () => select(refs.find((r) => r.path === b.dataset.path))));
    if (pick) select(refs.find((r) => r.path === pick) || refs[0]);
    return refs;
  };
  drawRefs().catch(fail);

  const upload = (file) => {
    if (!file || !file.type.startsWith('image/')) return toast(t('new.pickImage'), true);
    const fr = new FileReader();
    fr.onload = async () => {
      try {
        const ref = await post('/api/references', { filename: file.name, data: fr.result });
        await drawRefs(ref.path);
        toast(t('new.saved', { name: ref.name }));
      } catch (e) { fail(e); }
    };
    fr.readAsDataURL(file);
  };
  const drop = document.getElementById('drop');
  document.getElementById('file').addEventListener('change', (e) => upload(e.target.files[0]));
  ['dragenter', 'dragover'].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add('over'); }));
  ['dragleave', 'drop'].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove('over'); }));
  drop.addEventListener('drop', (e) => upload(e.dataTransfer.files[0]));

  startBtn.addEventListener('click', async () => {
    if (!selected) return toast(t('new.needRef'), true);
    startBtn.disabled = true;
    const base = { name: nameEl.value.trim(), reference: selected.path };
    const body = mode() === 'convert'
      ? { ...base, kind: 'convert', depth: document.getElementById('depth').value, inflate: document.getElementById('inflate').checked }
      : { ...base, kind: 'generate', notes: document.getElementById('notes').value, model: document.getElementById('model').value, ...limitValues('new') };
    try {
      const job = await post('/api/jobs', body);
      await refreshSidebar();
      location.hash = `#/job/${job.id}`;
    } catch (err) { fail(err); startBtn.disabled = false; }
  });
}

// ------------------------------------------------------------------ model detail
async function waitJob(id) {
  for (;;) {
    await new Promise((r) => setTimeout(r, 700));
    const j = await api(`/api/jobs/${id}?since=0`);
    if (j.status !== 'running') return j;
  }
}
const logTail = (j) => j.log.filter((l) => l.kind !== 'info').slice(-6).map((l) => (l.key ? t(`log.${l.key}`, l) : l.text)).join('\n');

function exportList(exports) {
  const groups = Object.entries(exports || {}).filter(([, files]) => files.length);
  if (!groups.length) return `<p class="muted small" style="margin:8px 0 0">${tt('export.none')}</p>`;
  return groups.map(([sub, files]) => {
    const sheet = sub === 'sprites' ? files.find((f) => f.name.endsWith('_sheet.png')) : null;
    return `<div class="export-group"><div class="muted small">${tt(`export.dir.${sub}`)}</div>
      ${sheet ? `<img class="sheet-thumb" src="${sheet.url}" alt="" data-zoom>` : ''}
      <ul class="files">${files.map((f) => `<li><a href="${f.url}&download=1">${esc(f.name)}</a></li>`).join('')}</ul></div>`;
  }).join('');
}

async function viewModel(slug, tab) {
  let d;
  try { d = await api(`/api/models/${slug}`); } catch (e) {
    main.innerHTML = `<section class="page"><h1>${esc(slug)}</h1><p class="muted">${esc(e.message)}</p></section>`;
    return;
  }
  if (d.pending) {
    main.innerHTML = `<section class="page"><h1>${esc(slug)}</h1>
      <div class="banner"><span class="dot running"></span>${tt('model.pending')} <a href="#/job/${d.running}">${tt('model.viewLog')}</a></div></section>`;
    every(4000, async () => { const m = await api(`/api/models/${slug}`).catch(() => null); if (m && !m.pending) route(); });
    return;
  }
  const docLines = (d.doc || '').split('\n');
  const tabs = [['compare', d.images.compare], ['score', d.images.score], ['zoom', d.images.zoom], ['sheet', d.images.sheet],
    ['turn', d.images.turn], ['3d', d.vox_url], ['angles', d.images.angles], ['fit', d.images.fit], ['script', true]]
    .filter((x) => x[1]).map((x) => x[0]);
  if (!tabs.includes(tab)) tab = tabs[0];
  const st = d.stats;
  const n = (v) => v.toLocaleString(locale());
  const hist = d.score_history || [];
  const last = hist[hist.length - 1];
  main.innerHTML = `
    <section class="page">
      <div class="page-head">
        <div>
          <h1>${esc(d.slug)}</h1>
          <div class="muted">${esc(docLines[0] || '')}</div>
        </div>
        <div class="actions">
          <button class="btn" data-act="build">${tt('act.build')}</button>
          <button class="btn" data-act="open" ${d.vox_url ? '' : 'disabled'}>${tt('act.open')}</button>
          <button class="btn" data-act="shot" title="${tt('act.shotTitle')}">${tt('act.shot')}</button>
          ${d.vox_url ? `<a class="btn" href="${d.vox_url}&download=1">${tt('act.download')}</a>` : ''}
        </div>
      </div>
      ${d.running ? `<div class="banner"><span class="dot running"></span>${tt('model.running')} <a href="#/job/${d.running}">${tt('model.viewLogShort')}</a></div>` : ''}
      ${st ? `<div class="stats"><span>${tt('stat.size')} <b>${st.size.join(' × ')}</b></span>
        <span>${tt('stat.voxels')} <b>${n(st.voxels)}</b></span><span>${tt('stat.colors')} <b>${st.colors}</b></span>
        <span>${tt('stat.file')} <b>${n(Math.round(st.bytes / 1024))} KB</b></span>
        ${last ? `<span class="score-stat" title="${tt('stat.scoreHint')}">${tt('stat.score')} <b>${esc(scoreText(last.iou, last.delta_e))}</b> ${sparkline(hist.map((h) => h.iou))}</span>` : ''}
        ${d.reference ? `<span>${tt('stat.reference')} <b>${esc(d.reference)}</b></span>` : ''}</div>`
        : `<div class="banner warn">${tt('model.noVox')}</div>`}
      <nav class="tabs">${tabs.map((k) => `<a href="#/model/${esc(slug)}/${k}" class="${k === tab ? 'on' : ''}">${tt(`tab.${k}`)}</a>`).join('')}</nav>
      <div id="tab"></div>
      <div class="grid2 section">
        <div class="card">
          <h2>${tt('refine.title')}</h2>
          <textarea id="refine" placeholder="${tt('refine.ph')}"></textarea>
          ${limitFields('ref')}
          ${d.last_session ? `<label class="field check"><input type="checkbox" id="resume" checked> ${tt('refine.resume')}
            <span class="hint">${tt('refine.resumeHint')}</span></label>` : ''}
          <div class="row" style="margin-top:4px">
            <select id="refine-model" style="width:auto;margin:0">${modelOptions(true)}</select>
            <span class="spacer"></span>
            <button class="btn primary" id="refine-go" ${d.running || !state.status?.claude ? 'disabled' : ''}>${tt('refine.go')}</button>
          </div>
        </div>
        <div class="card">
          <h2>${tt('export.title')}</h2>
          <p class="muted small" style="margin:0 0 10px">${tt('export.hint')}</p>
          <div class="row">
            <button class="btn" data-export="sprites">${tt('export.sprites')}</button>
            <button class="btn" data-export="glb">GLB</button>
            <button class="btn" data-export="obj">OBJ</button>
            <button class="btn" data-export="ply">PLY</button>
          </div>
          <div id="exports">${exportList(d.exports)}</div>
        </div>
      </div>
      <div class="grid2 section">
        <div class="card">
          <h2>${tt('model.jobs')}</h2>
          ${d.jobs.length ? `<ul class="job-list">${d.jobs.map((j) => `<li><a href="#/job/${j.id}"><span class="dot ${j.status}"></span>
            <span>${tt(`kind.${j.kind}`)}${j.meta?.request ? ` — ${esc(j.meta.request.slice(0, 40))}` : ''}${j.best_iou != null ? ` · IoU ${Number(j.best_iou).toFixed(3)}` : ''}</span><span class="when">${esc(ago(j.started))}</span></a></li>`).join('')}</ul>`
            : `<p class="muted" style="margin:0">${tt('model.noJobs')}</p>`}
        </div>
        <div class="card">
          ${d.backups?.length ? `<h2>${tt('model.backups')}</h2>
            <p class="muted small" style="margin:0 0 6px">${tt('model.backupsHint')}</p>
            <ul class="files">${d.backups.map((b) => `<li><a href="${b.url}&download=1">${esc(b.name)}</a></li>`).join('')}</ul>` : ''}
          ${docLines.length > 1 ? `<details class="doc ${d.backups?.length ? 'section' : ''}"><summary>${tt('model.docNotes')}</summary><pre>${esc(d.doc)}</pre></details>` : ''}
        </div>
      </div>
    </section>`;

  const tabEl = document.getElementById('tab');
  if (tab === '3d') {
    tabEl.innerHTML = `<div class="viewer" id="viewer"><div class="msg">${tt('viewer.loading')}</div></div>`;
    import('./viewer.js').then(async ({ mountViewer }) => {
      const dispose = await mountViewer(document.getElementById('viewer'), `/api/models/${slug}/voxels`, d.view);
      onLeave(dispose);
    }).catch((e) => {
      tabEl.innerHTML = `<div class="viewer"><div class="msg">${tt('viewer.failed')}<br>${esc(e.message)}</div></div>`;
    });
  } else if (tab === 'script') {
    const vs = 'vscode://file/' + d.script_path.replace(/\\/g, '/');
    tabEl.innerHTML = `<div class="row" style="margin-bottom:8px"><span class="muted mono">models/${esc(slug)}.py</span><span class="spacer"></span>
      <a class="btn" href="${esc(vs)}">${tt('script.vscode')}</a></div><pre class="code">${esc(d.script)}</pre>`;
  } else {
    const hint = { score: 'tab.scoreHint', fit: 'tab.fitHint', zoom: 'tab.zoomHint', turn: 'tab.turnHint' }[tab];
    tabEl.innerHTML = `${hint ? `<p class="muted small" style="margin:0 0 8px">${tt(hint)}</p>` : ''}
      <div class="media"><img src="${d.images[tab]}" alt="" data-zoom></div>`;
  }

  main.querySelectorAll('[data-act]').forEach((b) => b.addEventListener('click', async () => {
    const act = b.dataset.act;
    b.disabled = true;
    try {
      if (act === 'build') {
        const job = await post('/api/jobs', { kind: 'build', name: slug });
        const done = await waitJob(job.id);
        if (done.status === 'done') {
          const backup = done.log.find((l) => l.text?.startsWith('backup:'));
          toast(backup ? t('toast.backup', { name: backup.text.split(/[\\/]/).pop() }) : t('toast.built'));
          route();
        } else {
          toast(`${t('toast.buildFailed')}\n${logTail(done)}`, true);
        }
      } else if (act === 'open') {
        await post(`/api/models/${slug}/open`);
        toast(t('toast.opened'));
      } else if (act === 'shot') {
        const r = await post(`/api/models/${slug}/shot`);
        lightbox.querySelector('img').src = r.url;
        lightbox.hidden = false;
      }
    } catch (e) { fail(e); }
    b.disabled = false;
  }));

  main.querySelectorAll('[data-export]').forEach((b) => b.addEventListener('click', async () => {
    main.querySelectorAll('[data-export]').forEach((x) => { x.disabled = true; });
    try {
      const job = await post('/api/jobs', { kind: 'export', name: slug, format: b.dataset.export });
      const done = await waitJob(job.id);
      if (done.status === 'done') {
        toast(t('toast.exported'));
        const fresh = await api(`/api/models/${slug}`);
        document.getElementById('exports').innerHTML = exportList(fresh.exports);
      } else {
        toast(`${t('toast.exportFailed')}\n${logTail(done)}`, true);
      }
    } catch (e) { fail(e); }
    main.querySelectorAll('[data-export]').forEach((x) => { x.disabled = false; });
  }));

  document.getElementById('refine-go').addEventListener('click', async (e) => {
    const notes = document.getElementById('refine').value.trim();
    if (!notes) return toast(t('refine.empty'), true);
    e.target.disabled = true;
    try {
      const job = await post('/api/jobs', {
        kind: 'refine', name: slug, notes, model: document.getElementById('refine-model').value,
        resume: document.getElementById('resume')?.checked || false, ...limitValues('ref'),
      });
      await refreshSidebar();
      location.hash = `#/job/${job.id}`;
    } catch (err) { fail(err); e.target.disabled = false; }
  });
}

// ------------------------------------------------------------------ job log
function entryHtml(e, job) {
  const time = new Date(e.t * 1000).toLocaleTimeString(locale(), { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const text = e.key ? t(`log.${e.key}`, e) : e.text;   // keyed entries follow the UI language
  switch (e.kind) {
    case 'info': return `<div class="entry info">${time} · ${esc(text)}</div>`;
    case 'prompt': return `<details class="entry prompt"><summary>${tt('log.prompt')}</summary><pre>${esc(text)}</pre></details>`;
    case 'text': return `<div class="entry text">${md(text)}</div>`;
    case 'tool': return `<div class="entry tool"><div class="line"><span class="badge ${esc(e.tool)}">${esc(e.tool)}</span>
        <span class="cmd mono" title="${esc(text)}">${esc(text)}</span></div>
        ${e.image ? `<img src="${e.image}" alt="" data-zoom loading="lazy">` : ''}</div>`;
    case 'iteration': return `<div class="entry iteration"><b>${tt('iter.build', { n: e.n })}</b>
        <span>${esc(scoreText(e.iou, e.delta_e)) || tt('iter.noScore')}</span>${e.worst ? `<span class="muted small">${esc(e.worst)}</span>` : ''}</div>`;
    case 'output':
      if (['build', 'convert', 'export'].includes(job.kind)) return `<div class="entry plain">${esc(text)}</div>`;
      return `<details class="entry output"><summary>${tt('log.output')} · ${esc(text.split('\n')[0].slice(0, 90))}</summary><pre>${esc(text)}</pre></details>`;
    case 'error': return `<div class="entry error">${esc(text)}</div>`;
    case 'result': {
      const meta = [e.cost != null ? t('log.cost', { v: Number(e.cost).toFixed(2) }) : '',
        e.duration ? t('log.duration', { d: dur(e.duration / 1000) }) : '',
        e.turns ? t('log.turns', { n: e.turns }) : ''].filter(Boolean).join(' · ');
      return `<div class="entry result ${e.ok ? '' : 'fail'}"><div class="head">${tt(e.ok ? 'log.done' : 'log.failed')}</div>
        ${text ? `<div class="body">${md(text)}</div>` : ''}${meta ? `<div class="meta">${esc(meta)}</div>` : ''}</div>`;
    }
    default: return `<div class="entry info">${esc(text)}</div>`;
  }
}

function iterationsHtml(j) {
  const its = j.iterations || [];
  if (!its.length || !['generate', 'refine'].includes(j.kind)) return '';
  const builds = its.filter((i) => i.n > 0);
  const best = builds.reduce((b, i) => (i.iou != null && (b == null || i.iou > b.iou) ? i : b), null);
  const locked = j.status === 'running';
  return `<div class="card iters">
    <div class="row"><h2 style="margin:0">${tt('iter.title')}</h2>${sparkline(builds.map((i) => i.iou), { w: 160, h: 30 })}
      <span class="spacer"></span><span class="muted small">${tt(locked ? 'iter.lockedHint' : 'iter.restoreHint')}</span></div>
    <div class="iter-strip">${its.map((i) => `
      <div class="iter ${best && i === best ? 'best' : ''}">
        ${i.score || i.compare ? `<img src="${i.score || i.compare}" alt="" data-zoom loading="lazy">` : `<div class="noimg">${tt('iter.before')}</div>`}
        <div class="cap"><b>${i.n === 0 ? tt('iter.before') : tt('iter.build', { n: i.n })}</b>
          <span>${esc(scoreText(i.iou, i.delta_e))}</span></div>
        ${i.script_path ? `<button class="btn small-btn" data-restore="${i.n}" ${locked ? 'disabled' : ''}>${tt('iter.restore')}</button>` : ''}
      </div>`).join('')}</div></div>`;
}

async function viewJob(id) {
  let next = 0;
  let job;
  try { job = await api(`/api/jobs/${id}?since=0`); } catch (e) {
    main.innerHTML = `<section class="page"><h1>${tt('job.title')}</h1><p class="muted">${esc(e.message)}</p></section>`;
    return;
  }
  const lim = [job.meta?.budget ? t('limit.budgetShort', { v: job.meta.budget }) : '',
    job.meta?.max_builds ? t('limit.buildsShort', { n: job.meta.max_builds }) : '',
    job.meta?.resumed ? t('refine.resumed') : ''].filter(Boolean).join(' · ');
  main.innerHTML = `
    <section class="page" style="max-width:980px">
      <div class="page-head">
        <div><h1>${esc(jobTitle(job))}</h1><div class="row muted" style="font-size:13px">
          <span class="pill ${job.status}" id="pill"></span>
          <span id="elapsed"></span>${lim ? `<span>${esc(lim)}</span>` : ''}
          <a href="#/model/${esc(job.name)}">${tt('job.modelPage')}</a></div></div>
        <div class="actions"><button class="btn danger" id="cancel" hidden>${tt('job.cancel')}</button></div>
      </div>
      <div id="iters"></div>
      <div class="log" id="log"></div>
      <div class="typing" id="typing" hidden><span class="dot running"></span>${tt('job.working')}</div>
      <div class="row section" id="after" hidden><a class="btn primary" href="#/model/${esc(job.name)}">${tt('job.viewModel')}</a></div>
    </section>`;
  const logEl = document.getElementById('log');
  let itersSig = '';

  const apply = (j) => {
    const nearBottom = window.innerHeight + window.scrollY >= document.body.scrollHeight - 160;
    logEl.insertAdjacentHTML('beforeend', j.log.map((e) => entryHtml(e, j)).join(''));
    next = j.next;
    const sig = JSON.stringify([j.iterations, j.status]);
    if (sig !== itersSig) { itersSig = sig; document.getElementById('iters').innerHTML = iterationsHtml(j); }
    const pill = document.getElementById('pill');
    pill.className = `pill ${j.status}`; pill.textContent = t(`status.${j.status}`);
    const end = j.ended || Date.now() / 1000;
    document.getElementById('elapsed').textContent = t('job.elapsed', { d: dur(end - j.started) });
    const running = j.status === 'running';
    document.getElementById('cancel').hidden = !running;
    document.getElementById('typing').hidden = !running;
    document.getElementById('after').hidden = running || j.status !== 'done' || j.kind === 'export';
    if (nearBottom && j.log.length) window.scrollTo(0, document.body.scrollHeight);
    return running;
  };
  apply(job);

  document.getElementById('iters').addEventListener('click', async (e) => {
    const b = e.target.closest('[data-restore]');
    if (!b) return;
    const n = Number(b.dataset.restore);
    const label = n === 0 ? t('iter.before') : t('iter.build', { n });
    if (!await confirmDialog({ title: t('iter.confirmTitle', { n: label }), body: `<p>${tt('iter.confirm', { n: label })}</p>`,
      confirm: t('iter.restore'), danger: false })) return;
    b.disabled = true;
    try {
      const build = await post(`/api/jobs/${id}/restore`, { n });
      const done = await waitJob(build.id);
      toast(done.status === 'done' ? t('iter.restored') : `${t('toast.buildFailed')}\n${logTail(done)}`, done.status !== 'done');
      location.hash = `#/model/${job.name}`;
    } catch (err) { fail(err); b.disabled = false; }
  });

  if (job.status === 'running') {
    let busy = false;
    every(1200, async () => {
      if (busy) return;
      busy = true;
      try {
        const j = await api(`/api/jobs/${id}?since=${next}`);
        if (!apply(j)) {
          leave();
          refreshSidebar();
          toast(`${jobTitle(j)}: ${t(`status.${j.status}`)}`, j.status !== 'done');
        }
      } catch (e) { console.warn(e); }
      busy = false;
    });
  }
  document.getElementById('cancel').addEventListener('click', async () => {
    if (!await confirmDialog({ title: t('job.confirmCancel'), confirm: t('job.cancel') })) return;
    try { await post(`/api/jobs/${id}/cancel`); } catch (e) { fail(e); }
  });
}

// ------------------------------------------------------------------ boot
(async () => {
  initLangPicker();
  applyShell();
  try { await loadStatus(); } catch (e) { fail(e); }
  await refreshSidebar();
  setInterval(refreshSidebar, 4000);
  route();
})();
