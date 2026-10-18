/* Meta (Facebook) Pixel loader. Inert until PIXEL_ID is set (paste the 15-16 digit ID from Meta Events Manager).
   Events: PageView (every page), Contact (call / WhatsApp click), Lead (lead form submitted, fired from lead-popup.js). */
(function () {
  var PIXEL_ID = ''; // <- paste Pixel ID here
  window.ugPixelLead = function () { try { if (window.fbq) window.fbq('track', 'Lead'); } catch (e) { /* ignore */ } };
  if (!PIXEL_ID) return;
  if (!window.fbq) {
    var n = window.fbq = function () { n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments); };
    if (!window._fbq) window._fbq = n;
    n.push = n; n.loaded = true; n.version = '2.0'; n.queue = [];
    var s = document.createElement('script'); s.async = true; s.src = 'https://connect.facebook.net/en_US/fbevents.js';
    document.head.appendChild(s);
  }
  window.fbq('init', PIXEL_ID);
  window.fbq('track', 'PageView');
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a'); if (!a) return;
    var h = a.getAttribute('href') || '';
    if (h.indexOf('tel:') === 0 || h.indexOf('wa.me') > -1) window.fbq('track', 'Contact', { content_name: h.indexOf('tel:') === 0 ? 'call' : 'whatsapp' });
  }, true);
})();
