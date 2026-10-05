/**
 * Udyog Growth — lead capture backend (Google Apps Script)
 * Deploy under the udyoggrowth@gmail.com account:
 *   Deploy > New deployment > Web app > Execute as: Me > Who has access: Anyone
 * Mail is sent from, and to, the account that owns this script (udyoggrowth@gmail.com).
 * Every new lead: one row in the "Leads" sheet + an email with the full, updated .xlsx attached.
 * Repeat clicks from the same mobile update that lead's row (Clicks, Last activity, Pages clicked) — no extra email.
 */
var CFG = {
  NOTIFY_TO: 'udyoggrowth@gmail.com',
  SITE_KEY: 'ug-site-1',            // must match CFG.key in assets/lead-popup.js
  SITE_URL: 'https://udyoggrowth.com',
  SHEET: 'Leads',
  DASH: 'Dashboard',
  TZ: 'Asia/Kolkata',
  MAX_EMAILS_PER_DAY: 80,           // consumer Gmail allows 100 MailApp recipients/day
  MAX_PER_MOBILE_PER_HOUR: 6
};

var HEAD = ['Lead ID', 'First seen (IST)', 'Name', 'Mobile', 'Email', 'First channel', 'First page',
  'Service asked (WhatsApp text)', 'Source', 'Medium', 'Campaign', 'Device', 'Referrer', 'GA client ID',
  'Status', 'Owner', 'Follow-up date', 'Notes', 'Clicks', 'Last activity (IST)', 'Pages clicked', 'Chat'];
var C = {}; HEAD.forEach(function (h, i) { C[h] = i + 1; });
var STATUSES = ['New', 'Called', 'WhatsApp sent', 'Interested', 'Quote sent', 'Won', 'Lost', 'Not reachable'];

/* ---------- web endpoints ---------- */
function doGet() {
  return json_({ ok: true, service: 'udyog-lead-endpoint', time: new Date().toISOString() });
}

function doPost(e) {
  try {
    var d = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    if (d.key !== CFG.SITE_KEY) return json_({ ok: false, err: 'key' });
    if (d.hp) return json_({ ok: true });                       // honeypot
    var v = clean_(d);
    if (!v.ok) return json_({ ok: false, err: v.err });
    if (!rateOk_(v.mobile)) return json_({ ok: true, throttled: true });

    var lock = LockService.getScriptLock();
    lock.waitLock(20000);
    var isNew = false, sheet, row;
    try {
      sheet = leadSheet_();
      row = findRow_(sheet, v.mobile);
      var now = new Date();
      if (row) {
        var cur = sheet.getRange(row, 1, 1, HEAD.length).getValues()[0];
        sheet.getRange(row, C['Clicks']).setValue((Number(cur[C['Clicks'] - 1]) || 1) + 1);
        sheet.getRange(row, C['Last activity (IST)']).setValue(now);
        var pages = String(cur[C['Pages clicked'] - 1] || '');
        if (pages.indexOf(v.page) < 0) sheet.getRange(row, C['Pages clicked']).setValue((pages ? pages + ', ' : '') + v.page);
        if (!cur[C['Email'] - 1] && v.email) sheet.getRange(row, C['Email']).setValue(v.email);
        if (!cur[C['Name'] - 1] && v.name) sheet.getRange(row, C['Name']).setValue(v.name);
      } else {
        isNew = true;
        var id = nextId_(sheet, now);
        var vals = [id, now, v.name, v.mobile, v.email, v.channel, v.page, v.waText, v.source, v.medium, v.campaign,
          v.device, v.ref, v.gcid, 'New', '', '', '', 1, now, v.page, ''];
        sheet.appendRow(vals.map(safe_));
        row = sheet.getLastRow();
        sheet.getRange(row, C['Mobile']).setNumberFormat('@').setValue(v.mobile);
        sheet.getRange(row, C['Chat']).setFormula('=HYPERLINK("https://wa.me/91"&D' + row + ',"WhatsApp")');
        SpreadsheetApp.flush();
      }
    } finally { lock.releaseLock(); }

    if (isNew) notify_(v, sheet);
    return json_({ ok: true, isNew: isNew });
  } catch (err) {
    console.error(err);
    return json_({ ok: false, err: String(err) });
  }
}

/* ---------- validation ---------- */
function clean_(d) {
  var name = String(d.name || '').replace(/\s+/g, ' ').trim().slice(0, 60);
  var mobile = String(d.mobile || '').replace(/\D/g, '');
  if (mobile.length === 12 && mobile.indexOf('91') === 0) mobile = mobile.slice(2);
  if (mobile.length === 11 && mobile.charAt(0) === '0') mobile = mobile.slice(1);
  var email = String(d.email || '').trim().toLowerCase().slice(0, 120);
  if (name.length < 2) return { ok: false, err: 'name' };
  if (!/^[6-9]\d{9}$/.test(mobile)) return { ok: false, err: 'mobile' };
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) return { ok: false, err: 'email' };
  var utm = d.utm || {};
  var page = String(d.page || '/').slice(0, 200);
  if (page.charAt(0) !== '/') page = '/' + page;
  return {
    ok: true, name: name, mobile: mobile, email: email,
    channel: d.channel === 'call' ? 'Call' : 'WhatsApp',
    page: page, title: String(d.title || '').slice(0, 150), waText: String(d.wa_text || '').slice(0, 300),
    source: String(utm.utm_source || (d.ref ? hostOf_(d.ref) : 'direct')).slice(0, 60),
    medium: String(utm.utm_medium || '').slice(0, 60), campaign: String(utm.utm_campaign || '').slice(0, 80),
    device: String(d.device || '').slice(0, 20), ref: String(d.ref || '').slice(0, 200), gcid: String(d.gcid || '').slice(0, 40)
  };
}
function hostOf_(u) { var m = String(u).match(/^https?:\/\/([^\/]+)/i); return m ? m[1].replace(/^www\./, '') : 'direct'; }
function safe_(x) { return (typeof x === 'string' && /^[=+\-@]/.test(x)) ? "'" + x : x; }   // block formula injection
function json_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }

function rateOk_(mobile) {
  var cache = CacheService.getScriptCache(), k = 'm_' + mobile, n = Number(cache.get(k) || 0);
  if (n >= CFG.MAX_PER_MOBILE_PER_HOUR) return false;
  cache.put(k, String(n + 1), 3600);
  return true;
}

/* ---------- sheet ---------- */
function ss_() {
  var id = PropertiesService.getScriptProperties().getProperty('SHEET_ID');
  if (id) { try { return SpreadsheetApp.openById(id); } catch (e) { /* recreate below */ } }
  return setup();
}
function leadSheet_() { return ss_().getSheetByName(CFG.SHEET); }
function findRow_(sheet, mobile) {
  var last = sheet.getLastRow(); if (last < 2) return 0;
  var col = sheet.getRange(2, C['Mobile'], last - 1, 1).getValues();
  for (var i = 0; i < col.length; i++) if (String(col[i][0]).replace(/\D/g, '').slice(-10) === mobile) return i + 2;
  return 0;
}
function nextId_(sheet, now) {
  var day = Utilities.formatDate(now, CFG.TZ, 'yyMMdd'), last = sheet.getLastRow(), n = 1;
  if (last > 1) {
    var ids = sheet.getRange(2, 1, last - 1, 1).getValues();
    for (var i = 0; i < ids.length; i++) if (String(ids[i][0]).indexOf('UG-' + day) === 0) n++;
  }
  return 'UG-' + day + '-' + ('00' + n).slice(-3);
}

/** Run once from the editor: creates the lead workbook (Leads + Dashboard), formatting, dropdowns, formulas. */
function setup() {
  var props = PropertiesService.getScriptProperties();
  var ss = props.getProperty('SHEET_ID') ? SpreadsheetApp.openById(props.getProperty('SHEET_ID')) : SpreadsheetApp.create('Udyog Growth — Leads');
  props.setProperty('SHEET_ID', ss.getId());
  ss.setSpreadsheetTimeZone(CFG.TZ);
  var sh = ss.getSheetByName(CFG.SHEET) || ss.getSheets()[0].setName(CFG.SHEET);
  sh.clear(); sh.getRange(1, 1, 1, HEAD.length).setValues([HEAD])
    .setFontWeight('bold').setBackground('#16232F').setFontColor('#FFFFFF').setVerticalAlignment('middle');
  sh.setFrozenRows(1); sh.setFrozenColumns(3); sh.setRowHeight(1, 34);
  sh.getRange('B2:B').setNumberFormat('dd-mmm-yyyy hh:mm'); sh.getRange('T2:T').setNumberFormat('dd-mmm-yyyy hh:mm');
  sh.getRange('Q2:Q').setNumberFormat('dd-mmm-yyyy'); sh.getRange('D2:D').setNumberFormat('@');
  var widths = [120, 150, 150, 110, 210, 90, 220, 260, 110, 90, 130, 80, 180, 110, 120, 100, 110, 260, 60, 150, 260, 90];
  widths.forEach(function (w, i) { sh.setColumnWidth(i + 1, w); });
  sh.getRange('O2:O').setDataValidation(SpreadsheetApp.newDataValidation().requireValueInList(STATUSES, true).setAllowInvalid(false).build());
  sh.getRange('Q2:Q').setDataValidation(SpreadsheetApp.newDataValidation().requireDate().setAllowInvalid(false).build());
  var st = sh.getRange('O2:O'), rules = [];
  [['New', '#FFF2CC'], ['Called', '#DDEBF7'], ['WhatsApp sent', '#DDEBF7'], ['Interested', '#D9EAD3'],
   ['Quote sent', '#CFE2F3'], ['Won', '#93C47D'], ['Lost', '#EAD1DC'], ['Not reachable', '#E6E6E6']].forEach(function (p) {
    rules.push(SpreadsheetApp.newConditionalFormatRule().whenTextEqualTo(p[0]).setBackground(p[1]).setRanges([st]).build());
  });
  rules.push(SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=AND($Q2<>"",$Q2<=TODAY(),$O2<>"Won",$O2<>"Lost")')
    .setBackground('#F4CCCC').setRanges([sh.getRange('Q2:Q')]).build());                       // follow-up due
  rules.push(SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=$S2>=3')
    .setBold(true).setFontColor('#B45F06').setRanges([sh.getRange('S2:S')]).build());          // hot: 3+ clicks
  rules.push(SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=COUNTIF($E$2:$E,$E2)>1')
    .setBackground('#FCE5CD').setRanges([sh.getRange('E2:E')]).build());                        // same email, different mobile
  sh.setConditionalFormatRules(rules);
  if (sh.getFilter()) sh.getFilter().remove();
  sh.getRange(1, 1, sh.getMaxRows(), HEAD.length).createFilter();

  var d = ss.getSheetByName(CFG.DASH) || ss.insertSheet(CFG.DASH);
  d.clear();
  var L = "Leads!";
  var rows = [
    ['Udyog Growth — lead dashboard', ''],
    ['Total leads', '=COUNTA(' + L + 'A2:A)'],
    ['New today', '=COUNTIFS(' + L + 'B2:B,">="&TODAY())'],
    ['Last 7 days', '=COUNTIFS(' + L + 'B2:B,">="&(TODAY()-7))'],
    ['Status = New (not yet worked)', '=COUNTIF(' + L + 'O2:O,"New")'],
    ['Follow-ups due', '=COUNTIFS(' + L + 'Q2:Q,"<="&TODAY(),' + L + 'Q2:Q,"<>",' + L + 'O2:O,"<>Won",' + L + 'O2:O,"<>Lost")'],
    ['Won', '=COUNTIF(' + L + 'O2:O,"Won")'],
    ['Hot (3+ clicks)', '=COUNTIF(' + L + 'S2:S,">=3")'],
    ['WhatsApp leads', '=COUNTIF(' + L + 'F2:F,"WhatsApp")'],
    ['Call leads', '=COUNTIF(' + L + 'F2:F,"Call")']
  ];
  d.getRange(1, 1, rows.length, 2).setValues(rows);
  d.getRange('A1').setFontSize(14).setFontWeight('bold');
  d.getRange('A2:A10').setFontWeight('bold'); d.getRange('B2:B10').setHorizontalAlignment('left');
  d.getRange('D1').setValue('Top pages').setFontWeight('bold');
  d.getRange('D2').setFormula('=IFERROR(QUERY(' + L + 'G2:G,"select G, count(G) where G<>\'\' group by G order by count(G) desc limit 10 label G \'Page\', count(G) \'Leads\'",1),"")');
  d.getRange('G1').setValue('Source / medium').setFontWeight('bold');
  d.getRange('G2').setFormula('=IFERROR(QUERY(' + L + 'I2:J,"select I, J, count(I) where I<>\'\' group by I, J order by count(I) desc limit 10 label I \'Source\', J \'Medium\', count(I) \'Leads\'",1),"")');
  d.getRange('K1').setValue('By status').setFontWeight('bold');
  d.getRange('K2').setFormula('=IFERROR(QUERY(' + L + 'O2:O,"select O, count(O) where O<>\'\' group by O order by count(O) desc label O \'Status\', count(O) \'Leads\'",1),"")');
  d.setColumnWidth(1, 230); d.setColumnWidth(4, 260); d.setColumnWidth(7, 160);
  ss.setActiveSheet(sh);
  Logger.log('Workbook: ' + ss.getUrl());
  return ss;
}

/* ---------- email ---------- */
function notify_(v, sheet) {
  var props = PropertiesService.getScriptProperties();
  var dayKey = 'mail_' + Utilities.formatDate(new Date(), CFG.TZ, 'yyyyMMdd');
  var sent = Number(props.getProperty(dayKey) || 0);
  if (sent >= CFG.MAX_EMAILS_PER_DAY) return;
  props.setProperty(dayKey, String(sent + 1));
  var when = Utilities.formatDate(new Date(), CFG.TZ, 'dd MMM yyyy, hh:mm a');
  var what = v.waText || v.title || v.page;
  var wa = 'https://wa.me/91' + v.mobile + '?text=' + encodeURIComponent('Hi ' + v.name + ', this is Udyog Growth. Thanks for your enquiry — how can we help?');
  var rows = [['Name', esc_(v.name)], ['Mobile', '<a href="tel:+91' + v.mobile + '">+91 ' + v.mobile + '</a> · <a href="' + wa + '">WhatsApp</a>'],
    ['Email', '<a href="mailto:' + esc_(v.email) + '">' + esc_(v.email) + '</a>'], ['Clicked', v.channel],
    ['Page', '<a href="' + CFG.SITE_URL + v.page + '">' + esc_(v.page) + '</a>'], ['Asked about', esc_(what)],
    ['Source / medium', esc_(v.source + (v.medium ? ' / ' + v.medium : '') + (v.campaign ? ' / ' + v.campaign : ''))],
    ['Device', esc_(v.device)], ['Time (IST)', when]];
  var table = rows.map(function (r) {
    return '<tr><td style="padding:6px 14px 6px 0;color:#5A6672;font-weight:600;vertical-align:top">' + r[0] + '</td><td style="padding:6px 0">' + r[1] + '</td></tr>';
  }).join('');
  var html = '<div style="font-family:Arial,sans-serif;font-size:15px;color:#16232F;max-width:560px">' +
    '<h2 style="margin:0 0 4px;font-size:18px">New lead — ' + esc_(v.name) + '</h2>' +
    '<p style="margin:0 0 12px;color:#5A6672">via udyoggrowth.com · full updated Excel attached</p>' +
    '<table style="border-collapse:collapse">' + table + '</table>' +
    '<p style="margin-top:14px"><a href="' + wa + '" style="background:#2A7457;color:#fff;padding:10px 16px;border-radius:6px;text-decoration:none;font-weight:700">Reply on WhatsApp</a> ' +
    '<a href="' + sheet.getParent().getUrl() + '" style="padding:10px 12px;text-decoration:none;color:#16232F">Open lead sheet</a></p></div>';
  var text = 'New lead: ' + v.name + '\nMobile: +91 ' + v.mobile + '\nEmail: ' + v.email + '\nClicked: ' + v.channel +
    '\nPage: ' + CFG.SITE_URL + v.page + '\nAsked about: ' + what + '\nTime (IST): ' + when;
  var opts = { to: CFG.NOTIFY_TO, subject: 'New lead: ' + v.name + ' — ' + what.slice(0, 70), htmlBody: html, body: text,
    name: 'Udyog Growth Leads', replyTo: v.email };
  var blob = xlsx_(sheet.getParent());
  if (blob) opts.attachments = [blob];
  MailApp.sendEmail(opts);
}
function esc_(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }

/** Full workbook as .xlsx (Leads + Dashboard) */
function xlsx_(ss) {
  try {
    SpreadsheetApp.flush();
    DriveApp.getFileById(ss.getId());                         // makes sure the Drive scope is granted for the export call
    var r = UrlFetchApp.fetch('https://docs.google.com/spreadsheets/d/' + ss.getId() + '/export?format=xlsx',
      { headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() }, muteHttpExceptions: true });
    if (r.getResponseCode() !== 200) return null;
    return r.getBlob().setName('Udyog-Leads-' + Utilities.formatDate(new Date(), CFG.TZ, 'yyyy-MM-dd') + '.xlsx');
  } catch (e) { console.error(e); return null; }
}

/* ---------- optional: 9 AM IST daily digest ---------- */
function installTriggers() {
  ScriptApp.getProjectTriggers().forEach(function (t) { if (t.getHandlerFunction() === 'dailyDigest') ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('dailyDigest').timeBased().atHour(9).nearMinute(0).everyDays(1).inTimezone(CFG.TZ).create();
}
function dailyDigest() {
  var ss = ss_(), sh = ss.getSheetByName(CFG.SHEET), last = sh.getLastRow();
  if (last < 2) return;
  var data = sh.getRange(2, 1, last - 1, HEAD.length).getValues(), now = new Date(), y = new Date(now.getTime() - 24 * 3600 * 1000);
  var fresh = data.filter(function (r) { return r[C['First seen (IST)'] - 1] >= y; });
  var due = data.filter(function (r) {
    var f = r[C['Follow-up date'] - 1], s = r[C['Status'] - 1];
    return f && f <= now && s !== 'Won' && s !== 'Lost';
  });
  var untouched = data.filter(function (r) { return r[C['Status'] - 1] === 'New' && r[C['First seen (IST)'] - 1] < y; });
  if (!fresh.length && !due.length && !untouched.length) return;
  var li = function (rs) { return rs.map(function (r) { return '<li>' + esc_(r[C['Name'] - 1]) + ' — +91 ' + esc_(r[C['Mobile'] - 1]) + ' — ' + esc_(r[C['Service asked (WhatsApp text)'] - 1] || r[C['First page'] - 1]) + '</li>'; }).join(''); };
  var html = '<div style="font-family:Arial,sans-serif;font-size:15px;color:#16232F"><h3>Lead digest</h3>' +
    '<p><b>New in the last 24 hours: ' + fresh.length + '</b></p><ul>' + li(fresh) + '</ul>' +
    '<p><b>Follow-ups due: ' + due.length + '</b></p><ul>' + li(due) + '</ul>' +
    '<p><b>Still "New" after 24 hours: ' + untouched.length + '</b></p><ul>' + li(untouched) + '</ul>' +
    '<p><a href="' + ss.getUrl() + '">Open lead sheet</a></p></div>';
  var opts = { to: CFG.NOTIFY_TO, subject: 'Lead digest — ' + fresh.length + ' new, ' + due.length + ' follow-ups due', htmlBody: html, name: 'Udyog Growth Leads' };
  var blob = xlsx_(ss); if (blob) opts.attachments = [blob];
  MailApp.sendEmail(opts);
}

/** Run from the editor to test the whole chain (row + email with Excel). Uses a fake mobile; delete the row afterwards. */
function testLead() {
  var r = doPost({ postData: { contents: JSON.stringify({
    key: CFG.SITE_KEY, name: 'Test Lead', mobile: '9000000001', email: 'test@example.com', channel: 'whatsapp',
    page: '/din-dsc-director-kyc-dir-3/', title: 'DIN, DSC and DIR-3 KYC', wa_text: 'Hi, I need DIN / DSC / DIR-3 KYC filing for our directors.',
    utm: { utm_source: 'test' }, ref: '', device: 'desktop', gcid: '' }) } });
  Logger.log(r.getContent());
}
