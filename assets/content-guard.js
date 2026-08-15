/* Casual content-copy deterrent for udyoggrowth.com.
   NOTE: this does not, and cannot, stop screenshots (OS-level, outside
   any website's control) and does not stop anyone using View Source,
   browser DevTools, or a scraper/bot — those read the page's raw HTML
   directly and are unaffected by any script here. This only discourages
   the average visitor from right-clicking or hitting Ctrl+C on the page.
   Phone/WhatsApp contact links are intentionally left copyable. */
(function () {
  function isContactLink(el) {
    return el && el.closest && el.closest('.callbar, a[href^="tel:"]');
  }
  document.addEventListener('contextmenu', function (e) {
    if (!isContactLink(e.target)) e.preventDefault();
  });
  document.addEventListener('copy', function (e) {
    if (!isContactLink(e.target)) e.preventDefault();
  });
  document.addEventListener('cut', function (e) {
    if (!isContactLink(e.target)) e.preventDefault();
  });
  document.addEventListener('keydown', function (e) {
    var k = e.key ? e.key.toLowerCase() : '';
    var blockCombo = (e.ctrlKey || e.metaKey) && ['c', 'x', 'u', 's'].indexOf(k) !== -1;
    var blockDevtools = e.key === 'F12' ||
      ((e.ctrlKey || e.metaKey) && e.shiftKey && ['i', 'j', 'c'].indexOf(k) !== -1);
    if ((blockCombo && !isContactLink(e.target)) || blockDevtools) e.preventDefault();
  });
})();
