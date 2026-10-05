/* Udyog Growth — lead popup.
   Click on any Call / WhatsApp link -> small form (name, mobile, email) -> details go to the lead backend
   (Google Sheet + email to udyoggrowth@gmail.com) -> then the call / WhatsApp opens as usual.
   Returning visitors (details saved in this browser for 30 days) go straight through; the click is still logged. */
(function () {
  'use strict';
  var CFG = {
    endpoint: '',            // Apps Script web-app URL (…/exec). Empty = popup disabled, links behave as before.
    key: 'ug-site-1',        // must match SITE_KEY in scripts/lead-backend/Code.gs
    rememberDays: 30,
    allowSkip: false         // true adds a "Skip and continue" link
  };
  if (!CFG.endpoint || window.__ugLead) return;
  window.__ugLead = true;

  var SEL = 'a[href^="tel:"],a[href*="wa.me/"],a[href*="api.whatsapp.com"]';
  var LS = 'ug_lead', ov, box, form, errEl, goBtn, chEl, fName, fMob, fMail, fHp, pending = null, lastFocus = null;

  function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } }
  function chanOf(h) { return h.indexOf('tel:') === 0 ? 'call' : (h.indexOf('wa.me') > -1 || h.indexOf('whatsapp.com') > -1) ? 'whatsapp' : ''; }
  function saved() {
    try {
      var o = JSON.parse(store(LS) || 'null');
      if (o && o.n && o.m && o.e && Date.now() - o.t < CFG.rememberDays * 864e5) return o;
    } catch (e) { /* ignore */ }
    return null;
  }
  function utm() {
    var o = {}, keys = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'gclid'];
    try {
      var p = new URLSearchParams(location.search), any = false;
      keys.forEach(function (k) { if (p.get(k)) { o[k] = p.get(k).slice(0, 80); any = true; } });
      if (any) sessionStorage.setItem('ug_utm', JSON.stringify(o));
      else o = JSON.parse(sessionStorage.getItem('ug_utm') || '{}');
    } catch (e) { /* ignore */ }
    return o;
  }
  function gcid() { var m = document.cookie.match(/(?:^|; )_ga=GA\d\.\d\.(\d+\.\d+)/); return m ? m[1] : ''; }
  function payload(d, ch, href, repeat) {
    var wa = '';
    if (ch === 'whatsapp' && href.indexOf('text=') > -1) { try { wa = decodeURIComponent(href.split('text=')[1].split('&')[0]); } catch (e) { /* ignore */ } }
    return {
      key: CFG.key, ver: 1, repeat: !!repeat, name: d.n, mobile: d.m, email: d.e, channel: ch, link: href, wa_text: wa,
      page: location.pathname, title: document.title, ref: document.referrer || '', utm: utm(), gcid: gcid(),
      device: /Mobi|Android|iPhone/i.test(navigator.userAgent) ? 'mobile' : 'desktop', hp: ''
    };
  }
  function send(p) {
    var body = JSON.stringify(p);
    try {
      if (navigator.sendBeacon && navigator.sendBeacon(CFG.endpoint, new Blob([body], { type: 'text/plain;charset=UTF-8' }))) return;
    } catch (e) { /* fall through */ }
    try { fetch(CFG.endpoint, { method: 'POST', mode: 'no-cors', keepalive: true, headers: { 'Content-Type': 'text/plain;charset=UTF-8' }, body: body }); } catch (e) { /* ignore */ }
  }
  function ga(name, ch) { try { if (typeof gtag === 'function') gtag('event', name, { channel: ch, page: location.pathname, link_url: pending ? pending.href : '' }); } catch (e) { /* ignore */ } }

  /* ---------- UI ---------- */
  var CSS = '.ug-ov{position:fixed;inset:0;z-index:1000;background:rgb(22 35 47/.58);display:flex;align-items:center;justify-content:center;padding:16px;overflow-y:auto}' +
    '.ug-ov[hidden]{display:none}' +
    '.ug-box{position:relative;width:100%;max-width:420px;background:#FBFBF9;color:#16232F;border-radius:10px;border-top:4px solid #DDA032;padding:22px 20px 16px;box-shadow:0 24px 60px -12px rgb(0 0 0/.45);font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif}' +
    '.ug-box h2{margin:0 28px 4px 0;font-family:Archivo,Inter,system-ui,sans-serif;font-size:1.25rem;line-height:1.25}' +
    '.ug-box p{margin:0 0 12px;font-size:.95rem;line-height:1.45;color:#5A6672}' +
    '.ug-x{position:absolute;top:8px;right:8px;width:44px;height:44px;border:0;background:transparent;color:#16232F;font-size:28px;line-height:1;cursor:pointer;border-radius:8px}' +
    '.ug-x:hover{background:#ECECE7}' +
    '.ug-box label{display:block;margin:10px 0 4px;font-size:.85rem;font-weight:700;color:#16232F}' +
    '.ug-box input[type=text],.ug-box input[type=tel],.ug-box input[type=email]{display:block;width:100%;box-sizing:border-box;min-height:46px;padding:10px 12px;font:inherit;font-size:16px;color:#16232F;background:#fff;border:1.5px solid #B9BDB7;border-radius:8px}' +
    '.ug-box input:focus-visible,.ug-x:focus-visible,.ug-go:focus-visible,.ug-skip:focus-visible,.ug-fine a:focus-visible{outline:3px solid #16232F;outline-offset:2px}' +
    '.ug-box input[aria-invalid=true]{border-color:#B3261E;background:#FFF8F7}' +
    '.ug-tel{display:flex;align-items:stretch;gap:0}' +
    '.ug-tel span{display:flex;align-items:center;padding:0 12px;background:#ECECE7;border:1.5px solid #B9BDB7;border-right:0;border-radius:8px 0 0 8px;font-weight:700;font-size:16px}' +
    '.ug-tel input{border-radius:0 8px 8px 0!important}' +
    '.ug-hp{position:absolute!important;left:-9999px!important;width:1px;height:1px;opacity:0}' +
    '.ug-err{min-height:1.2em;margin:8px 0 0!important;color:#B3261E!important;font-weight:600;font-size:.9rem!important}' +
    '.ug-go{display:block;width:100%;min-height:48px;margin-top:10px;border:0;border-radius:8px;background:#2A7457;color:#fff;font:700 1rem Archivo,Inter,system-ui,sans-serif;letter-spacing:.02em;cursor:pointer}' +
    '.ug-go:hover{background:#1F5C45}.ug-go[disabled]{opacity:.7;cursor:wait}' +
    '.ug-skip{display:block;margin:10px auto 0;background:none;border:0;color:#16232F;font:inherit;font-size:.9rem;text-decoration:underline;cursor:pointer;min-height:44px}' +
    '.ug-box .ug-fine{margin:12px 0 0;font-size:.78rem;line-height:1.4}' +
    '.ug-fine a{color:#16232F;text-decoration:underline}' +
    'html.ug-lock{overflow:hidden}' +
    '@media(max-width:600px){.ug-ov{align-items:flex-end;padding:0}.ug-box{max-width:none;border-radius:16px 16px 0 0;padding:22px 18px calc(16px + env(safe-area-inset-bottom))}}' +
    '@media(prefers-reduced-motion:no-preference){.ug-box{animation:ugin .18s ease-out}@keyframes ugin{from{transform:translateY(12px);opacity:0}to{transform:none;opacity:1}}}';

  function build() {
    var st = document.createElement('style'); st.textContent = CSS; document.head.appendChild(st);
    ov = document.createElement('div'); ov.className = 'ug-ov'; ov.hidden = true;
    ov.innerHTML =
      '<div class="ug-box" role="dialog" aria-modal="true" aria-labelledby="ug-t" aria-describedby="ug-d">' +
      '<button type="button" class="ug-x" aria-label="Close">&times;</button>' +
      '<h2 id="ug-t">Before we connect</h2>' +
      '<p id="ug-d">Share your details so we can follow up on your enquiry. Next step: <strong data-ug-ch></strong>.</p>' +
      '<form novalidate>' +
      '<label for="ug-n">Your name</label><input id="ug-n" name="name" type="text" autocomplete="name" required>' +
      '<label for="ug-m">Mobile number</label><div class="ug-tel"><span aria-hidden="true">+91</span><input id="ug-m" name="mobile" type="tel" inputmode="numeric" autocomplete="tel-national" maxlength="14" placeholder="10-digit mobile" required></div>' +
      '<label for="ug-e">Email</label><input id="ug-e" name="email" type="email" autocomplete="email" placeholder="you@company.com" required>' +
      '<input class="ug-hp" name="website" type="text" tabindex="-1" autocomplete="off" aria-hidden="true">' +
      '<p class="ug-err" role="alert" aria-live="assertive"></p>' +
      '<button class="ug-go" type="submit"></button>' +
      (CFG.allowSkip ? '<button type="button" class="ug-skip">Skip and continue</button>' : '') +
      '<p class="ug-fine">By continuing you agree that Udyog Growth may contact you about this enquiry by call, WhatsApp or email. Details: <a href="/privacy/">privacy notice</a>.</p>' +
      '</form></div>';
    document.body.appendChild(ov);
    box = ov.firstChild; form = box.querySelector('form'); errEl = box.querySelector('.ug-err'); goBtn = box.querySelector('.ug-go'); chEl = box.querySelector('[data-ug-ch]');
    fName = box.querySelector('#ug-n'); fMob = box.querySelector('#ug-m'); fMail = box.querySelector('#ug-e'); fHp = box.querySelector('.ug-hp');
    box.querySelector('.ug-x').addEventListener('click', close);
    ov.addEventListener('mousedown', function (e) { if (e.target === ov) close(); });
    form.addEventListener('submit', onSubmit);
    var sk = box.querySelector('.ug-skip'); if (sk) sk.addEventListener('click', function () { var p = pending; close(true); if (p) go(p); });
    document.addEventListener('keydown', onKey);
  }
  function onKey(e) {
    if (!ov || ov.hidden) return;
    if (e.key === 'Escape') { e.preventDefault(); close(); return; }
    if (e.key !== 'Tab') return;
    var f = box.querySelectorAll('button:not([disabled]),input:not([tabindex="-1"]),a[href]'); if (!f.length) return;
    var first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
  function open(a, href, ch) {
    if (!ov) build();
    pending = { href: href, ch: ch, newTab: a.target === '_blank' }; lastFocus = a;
    chEl.textContent = ch === 'call' ? 'we will take your call' : 'WhatsApp opens';
    goBtn.textContent = ch === 'call' ? 'Continue to call' : 'Continue to WhatsApp'; goBtn.disabled = false;
    errEl.textContent = ''; [].forEach.call(form.elements, function (el) { el.removeAttribute('aria-invalid'); });
    ov.hidden = false; document.documentElement.classList.add('ug-lock');
    var d = null; try { d = JSON.parse(store(LS) || 'null'); } catch (e) { /* ignore */ }
    if (d) { fName.value = d.n || ''; fMob.value = d.m || ''; fMail.value = d.e || ''; }
    setTimeout(function () { (fName.value ? fMob : fName).focus(); }, 30);
  }
  function close(keep) {
    if (!ov || ov.hidden) return;
    ov.hidden = true; document.documentElement.classList.remove('ug-lock');
    if (!keep) pending = null;
    if (lastFocus && lastFocus.focus) { try { lastFocus.focus(); } catch (e) { /* ignore */ } }
  }
  function fail(el, msg) { errEl.textContent = msg; el.setAttribute('aria-invalid', 'true'); el.focus(); return false; }
  function onSubmit(e) {
    e.preventDefault();
    [].forEach.call(form.elements, function (el) { el.removeAttribute('aria-invalid'); }); errEl.textContent = '';
    var name = fName.value.replace(/\s+/g, ' ').trim(), mob = fMob.value.replace(/\D/g, ''), mail = fMail.value.trim();
    if (mob.length === 12 && mob.indexOf('91') === 0) mob = mob.slice(2);
    if (mob.length === 11 && mob.charAt(0) === '0') mob = mob.slice(1);
    if (name.length < 2) return fail(fName, 'Please enter your name.');
    if (!/^[6-9]\d{9}$/.test(mob)) return fail(fMob, 'Please enter a valid 10-digit Indian mobile number.');
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(mail)) return fail(fMail, 'Please enter a valid email address.');
    goBtn.disabled = true;
    var d = { n: name, m: mob, e: mail, t: Date.now() }, p = pending;
    if (!fHp.value) {                         // honeypot empty = human
      store(LS, JSON.stringify(d));
      ga('generate_lead', p.ch);
      send(payload(d, p.ch, p.href, false));
    }
    close(true); go(p);
  }
  function go(p) {
    pending = null;
    if (p.newTab) window.open(p.href, '_blank', 'noopener'); else window.location.href = p.href;
  }

  /* ---------- click interception (capture phase, so it runs before navigation) ---------- */
  document.addEventListener('click', function (e) {
    if (e.defaultPrevented || e.button > 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var a = e.target.closest && e.target.closest(SEL); if (!a) return;
    var href = a.getAttribute('href') || '', ch = chanOf(href); if (!ch) return;
    var d = saved();
    if (d) { send(payload(d, ch, href, true)); return; }          // known visitor: log the click, let the link work
    e.preventDefault(); open(a, href, ch);
  }, true);
})();
