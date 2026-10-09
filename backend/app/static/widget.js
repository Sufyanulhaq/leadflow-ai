/*
 * LeadFlow chat widget. One file, no dependencies.
 * Add to a clinic website:
 *   <script src="https://YOUR-API/widget.js" defer></script>
 * It talks to the API it was loaded from, unless you set data-api on the script tag.
 */
(function () {
  'use strict';
  var script = document.currentScript;
  var api = (script && script.getAttribute('data-api')) || (script && script.src ? new URL(script.src).origin : '');
  var accent = (script && script.getAttribute('data-accent')) || '#0f766e';
  var store = {
    get: function (k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { sessionStorage.setItem(k, v); } catch (e) { /* storage may be blocked */ } }
  };
  var conversationId = store.get('leadflow_conversation');
  var lastQuestion = '';
  var clinicName = 'our clinic';

  var host = document.createElement('div');
  host.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:2147483000;display:flex;flex-direction:column;align-items:flex-end;';
  var root = host.attachShadow({ mode: 'open' });
  root.innerHTML =
    '<style>' +
    ':host{all:initial}*{box-sizing:border-box;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif}' +
    '.fab{width:56px;height:56px;border-radius:50%;border:0;background:' + accent + ';color:#fff;font-size:24px;cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,.25)}' +
    '.panel{display:none;flex-direction:column;width:min(380px,calc(100vw - 32px));height:min(560px,calc(100vh - 100px));background:#fff;color:#1c1917;border-radius:14px;box-shadow:0 10px 40px rgba(0,0,0,.3);overflow:hidden;margin-bottom:12px}' +
    '.panel.open{display:flex}' +
    '.head{background:' + accent + ';color:#fff;padding:12px 14px;display:flex;justify-content:space-between;align-items:center}' +
    '.head b{font-size:15px}.head small{display:block;opacity:.85;font-size:12px}' +
    '.x{background:none;border:0;color:#fff;font-size:22px;cursor:pointer;line-height:1}' +
    '.log{flex:1;overflow:auto;padding:12px;display:flex;flex-direction:column;gap:8px;background:#f5f5f4}' +
    '.m{max-width:86%;padding:8px 11px;border-radius:12px;font-size:14px;line-height:1.4;white-space:pre-wrap;word-wrap:break-word}' +
    '.m.bot{background:#fff;border:1px solid #e7e5e4;align-self:flex-start}' +
    '.m.me{background:' + accent + ';color:#fff;align-self:flex-end}' +
    '.m.safety{background:#fef2f2;border-color:#fecaca}' +
    '.src{font-size:11px;color:#57534e;margin-top:6px;border-top:1px solid #e7e5e4;padding-top:5px}' +
    '.src span{display:inline-block;background:#f0fdfa;border:1px solid #99f6e4;border-radius:999px;padding:1px 8px;margin:2px 4px 0 0}' +
    '.form{padding:10px 12px;border-top:1px solid #e7e5e4;background:#fff;display:none;flex-direction:column;gap:6px;max-height:60%;overflow:auto}' +
    '.form.open{display:flex}.form p{margin:0;font-size:13px;font-weight:600}' +
    '.form input[type=text],.form textarea{width:100%;padding:7px 9px;border:1px solid #d6d3d1;border-radius:8px;font-size:14px}' +
    '.form label{font-size:12px;color:#44403c;display:flex;gap:6px;align-items:flex-start}' +
    '.row{display:flex;gap:6px}.btn{background:' + accent + ';color:#fff;border:0;border-radius:8px;padding:8px 12px;font-size:14px;cursor:pointer}' +
    '.btn.ghost{background:#e7e5e4;color:#1c1917}.btn[disabled]{opacity:.6;cursor:default}' +
    '.err{color:#b91c1c;font-size:12px;min-height:14px}' +
    '.send{display:flex;gap:6px;padding:10px 12px;border-top:1px solid #e7e5e4;background:#fff}' +
    '.send input{flex:1;padding:9px 10px;border:1px solid #d6d3d1;border-radius:8px;font-size:14px}' +
    '.note{font-size:11px;color:#78716c;text-align:center;padding:0 12px 8px;background:#fff}' +
    '@media (prefers-reduced-motion:no-preference){.panel.open{animation:up .15s ease-out}@keyframes up{from{opacity:0;transform:translateY(8px)}}}' +
    '</style>' +
    '<div class="panel" role="dialog" aria-label="Chat with the clinic">' +
    '<div class="head"><div><b class="title">Chat with us</b><small>AI assistant for the clinic</small></div><button class="x" aria-label="Close chat">&times;</button></div>' +
    '<div class="log" aria-live="polite"></div>' +
    '<div class="form"><p>Leave your details and the team will get back to you</p>' +
    '<input type="text" class="f-name" placeholder="Your name" autocomplete="name" maxlength="100">' +
    '<input type="text" class="f-contact" placeholder="Email or phone number" autocomplete="email" maxlength="160">' +
    '<textarea class="f-reason" rows="2" placeholder="What do you need help with?" maxlength="2000"></textarea>' +
    '<input type="text" class="f-when" placeholder="Preferred day or time (optional)" maxlength="120">' +
    '<label><input type="checkbox" class="f-consent"> I agree to the clinic contacting me about this enquiry.</label>' +
    '<div class="err" role="alert"></div>' +
    '<div class="row"><button class="btn submit">Send details</button><button class="btn ghost cancel">Not now</button></div></div>' +
    '<form class="send"><input type="text" class="q" placeholder="Ask a question…" maxlength="1000" aria-label="Your message"><button class="btn">Send</button></form>' +
    '<div class="note">AI assistant. It cannot give medical advice. In an emergency call 999.</div></div>' +
    '<button class="fab" aria-label="Open chat">&#128172;</button>';

  var $ = function (s) { return root.querySelector(s); };
  var panel = $('.panel'), log = $('.log'), form = $('.form'), input = $('.q'), err = $('.err');

  function add(text, who, extra) {
    var el = document.createElement('div');
    el.className = 'm ' + who + (extra && extra.safety ? ' safety' : '');
    el.textContent = text;
    if (extra && extra.citations && extra.citations.length) {
      var src = document.createElement('div');
      src.className = 'src';
      src.appendChild(document.createTextNode('Based on: '));
      extra.citations.forEach(function (c) {
        var tag = document.createElement('span');
        tag.textContent = c.title;
        tag.title = c.snippet;
        src.appendChild(tag);
      });
      el.appendChild(src);
    }
    log.appendChild(el);
    log.scrollTop = log.scrollHeight;
    return el;
  }

  function request(path, body) {
    return fetch(api + path, { method: body ? 'POST' : 'GET', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (data) {
          if (!r.ok) {
            var detail = data.detail;
            if (Array.isArray(detail)) detail = detail.map(function (d) { return d.msg; }).join(' ');
            throw new Error(typeof detail === 'string' ? detail : 'Something went wrong. Please call the clinic.');
          }
          return data;
        });
      });
  }

  function open() {
    panel.classList.add('open');
    input.focus();
    if (!log.children.length) add('Hello! Ask me about opening hours, prices or booking. I only answer from the clinic\'s own information.', 'bot');
  }

  function showForm() {
    $('.f-reason').value = $('.f-reason').value || lastQuestion;
    form.classList.add('open');
  }

  $('.fab').addEventListener('click', function () { panel.classList.contains('open') ? panel.classList.remove('open') : open(); });
  $('.x').addEventListener('click', function () { panel.classList.remove('open'); });
  $('.cancel').addEventListener('click', function () { form.classList.remove('open'); });

  $('.send').addEventListener('submit', function (e) {
    e.preventDefault();
    var text = input.value.trim();
    if (!text) return;
    input.value = '';
    lastQuestion = text;
    add(text, 'me');
    var wait = add('…', 'bot');
    request('/api/chat', { message: text, conversation_id: conversationId })
      .then(function (data) {
        conversationId = data.conversation_id;
        store.set('leadflow_conversation', conversationId);
        wait.remove();
        add(data.reply.text, 'bot', { citations: data.reply.citations, safety: data.reply.mode === 'safety' });
        if (data.offer_lead) showForm();
      })
      .catch(function (error) { wait.remove(); add(error.message, 'bot'); });
  });

  $('.submit').addEventListener('click', function () {
    var button = $('.submit');
    err.textContent = '';
    button.disabled = true;
    request('/api/leads', {
      name: $('.f-name').value, contact: $('.f-contact').value, reason: $('.f-reason').value,
      preferred_time: $('.f-when').value || null, consent: $('.f-consent').checked, conversation_id: conversationId
    }).then(function (data) {
      form.classList.remove('open');
      add(data.message, 'bot');
    }).catch(function (error) { err.textContent = error.message; })
      .then(function () { button.disabled = false; });
  });

  request('/api/public/config').then(function (c) { clinicName = c.clinic_name; $('.title').textContent = 'Chat with ' + clinicName; }).catch(function () {});
  document.body.appendChild(host);
})();
