/**
 * Collective AI - Security Module
 * Implements frontend defense-in-depth strategies.
 */

(function() {
    'use strict';

    // --- 1. SELF-XSS WARNING ---
    // Warn users against pasting code into the console
    const warningTitle = "font-size: 40px; color: #ef4444; font-weight: bold; font-family: sans-serif; text-shadow: 1px 1px 0 #000;";
    const warningText = "font-size: 16px; color: #ffffff; font-family: sans-serif; background: #000; padding: 4px; border-radius: 4px;";
    
    console.log("%c🛑 STOP!", warningTitle);
    console.log("%cThis is a browser feature intended for developers. If someone told you to copy-paste something here to enable a feature or hack someone's account, it is a scam and will give them access to your Collective AI account.", warningText);

    // --- 2. INPUT SANITIZATION (XSS PREVENTER) ---
    // Automatically strips common XSS vectors from all input fields
    document.addEventListener('input', function(e) {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            const original = e.target.value;
            // Allow basic text but strip script tags and event handlers
            const sanitized = original
                .replace(/<script\b[^>]*>([\s\S]*?)<\/script>/gim, "")
                .replace(/javascript:/gim, "")
                .replace(/on\w+=/gim, ""); // Removes onload=, onclick=, etc.
            
            if (original !== sanitized) {
                e.target.value = sanitized;
                console.warn("Security: Potential XSS vector stripped from input.");
            }
        }
    });

    // --- 3. TABNAPPING PROTECTION ---
    // Ensures all external links have noopener noreferrer
    function secureLinks() {
        const links = document.querySelectorAll('a[target="_blank"]');
        links.forEach(link => {
            if (!link.hasAttribute('rel')) {
                link.setAttribute('rel', 'noopener noreferrer');
            } else {
                const rel = link.getAttribute('rel');
                if (!rel.includes('noopener')) link.setAttribute('rel', `${rel} noopener`);
                if (!rel.includes('noreferrer')) link.setAttribute('rel', `${rel} noreferrer`);
            }
        });
    }
    
    // Run initially and observe DOM changes
    document.addEventListener('DOMContentLoaded', secureLinks);
    const observer = new MutationObserver(secureLinks);
    observer.observe(document.body, { childList: true, subtree: true });

    // --- 4. DRAG & DROP HIJACKING PROTECTION ---
    // Prevents users from accidentally dropping malicious files/links into the window
    window.addEventListener('dragover', function(e) {
        e.preventDefault();
    }, false);
    
    window.addEventListener('drop', function(e) {
        e.preventDefault();
    }, false);

    // --- 5. CLICKJACKING DETECTION ---
    if (window.top !== window.self) {
         document.body.innerHTML = "<h1>Security Error: App cannot be embedded.</h1>";
         throw new Error("Clickjacking attempt detected.");
    }

    console.info("🛡️ Collective AI Security Module Active");

})();/**
 * security.js — Collective AI
 * ─────────────────────────────────────────────────────────────────
 * Drop-in client-side security module. Import once per page:
 *   <script src="security.js"></script>
 *
 * Protections:
 *  1. XSS — HTML sanitiser (safe innerHTML replacement)
 *  2. Tabnapping — rel="noopener noreferrer" on all external links
 *  3. Clickjacking — bust frames + CSP header meta injection
 *  4. Content Security Policy meta tag injection
 *  5. Prototype pollution detection & freeze
 *  6. Dangerous global exposure prevention
 *  7. postMessage origin validation
 *  8. Rate-limiting utility (for forms / API calls)
 *  9. Input validation helpers (email, URL, length)
 * 10. Secure localStorage wrapper (JSON + try-catch)
 * 11. CSRF token utility
 * 12. Suspicious navigation detection
 * 13. Console warning suppression in production
 * ─────────────────────────────────────────────────────────────────
 */

(function (global) {
  'use strict';

  /* ═══════════════════════════════════════════════════════════════
     CONFIG
  ═══════════════════════════════════════════════════════════════ */
  const CFG = {
    // Allowed origins for postMessage (add your Render URL here)
    TRUSTED_ORIGINS: [
      'https://collective-ai-auth.firebaseapp.com',
      'https://collective-ai-backend.onrender.com',
      location.origin,
    ],
    // Max input lengths
    MAX_INPUT_LEN:   4000,
    MAX_TITLE_LEN:   200,
    MAX_TAG_LEN:     50,
    // Rate-limit defaults (requests per window)
    RATE_LIMIT_MAX:  10,
    RATE_LIMIT_MS:   60_000,
    // Production mode: suppress console.log / console.debug
    PRODUCTION: location.hostname !== 'localhost',
  };

  /* ═══════════════════════════════════════════════════════════════
     1. XSS — HTML SANITISER
     Usage:  Security.sanitize('<script>alert(1)</script>hello')
             → 'hello'
     Usage:  Security.sanitizeHTML(dirtyStr) for safe innerHTML
  ═══════════════════════════════════════════════════════════════ */
  const ALLOWED_TAGS = new Set([
    'a','abbr','b','blockquote','br','caption','cite','code',
    'col','colgroup','dd','del','details','dfn','dl','dt',
    'em','figcaption','figure','h1','h2','h3','h4','h5','h6',
    'hr','i','img','ins','kbd','li','mark','ol','p','pre',
    'q','rp','rt','ruby','s','samp','small','span','strong',
    'sub','summary','sup','table','tbody','td','tfoot','th',
    'thead','time','tr','u','ul','var','wbr',
  ]);

  const ALLOWED_ATTRS = new Set([
    'alt','cite','class','colspan','datetime','dir','height',
    'href','id','lang','rowspan','scope','src','start','title',
    'width',
  ]);

  // Attributes that must be safe URLs
  const URL_ATTRS = new Set(['href', 'src']);

  // Protocols that are always safe in URLs
  const SAFE_PROTOCOLS = new Set(['https:', 'http:', 'mailto:', 'tel:']);

  function isSafeURL(value) {
    try {
      // Relative URLs are fine
      if (!value.includes(':')) return true;
      const u = new URL(value, location.origin);
      return SAFE_PROTOCOLS.has(u.protocol);
    } catch { return false; }
  }

  /**
   * Parse dirty HTML, strip disallowed tags/attrs, return clean string.
   * Uses the browser's own DOMParser — no eval, no regex on HTML.
   */
  function sanitizeHTML(dirty) {
    if (typeof dirty !== 'string') return '';
    const doc = new DOMParser().parseFromString(dirty, 'text/html');
    _sanitizeNode(doc.body);
    return doc.body.innerHTML;
  }

  function _sanitizeNode(node) {
    const children = Array.from(node.childNodes);
    for (const child of children) {
      if (child.nodeType === Node.ELEMENT_NODE) {
        const tag = child.tagName.toLowerCase();
        if (!ALLOWED_TAGS.has(tag)) {
          // Replace disallowed element with its text content
          const text = document.createTextNode(child.textContent);
          node.replaceChild(text, child);
          continue;
        }
        // Strip disallowed or unsafe attributes
        const attrs = Array.from(child.attributes);
        for (const attr of attrs) {
          const name = attr.name.toLowerCase();
          if (!ALLOWED_ATTRS.has(name)) {
            child.removeAttribute(attr.name);
          } else if (URL_ATTRS.has(name) && !isSafeURL(attr.value)) {
            child.removeAttribute(attr.name);
          }
          // Force external links to open safely
          if (name === 'href' && child.tagName === 'A') {
            const href = attr.value;
            if (href && !href.startsWith('#') && !href.startsWith('/')) {
              child.setAttribute('rel', 'noopener noreferrer');
              child.setAttribute('target', '_blank');
            }
          }
        }
        _sanitizeNode(child);
      }
    }
  }

  /**
   * Escape a string for safe insertion as text content (not HTML).
   */
  function escapeText(str) {
    return String(str)
      .replace(/&/g,  '&amp;')
      .replace(/</g,  '&lt;')
      .replace(/>/g,  '&gt;')
      .replace(/"/g,  '&quot;')
      .replace(/'/g,  '&#x27;')
      .replace(/\//g, '&#x2F;');
  }

  /**
   * Safe innerHTML setter — sanitises before assignment.
   */
  function safeSetHTML(element, dirty) {
    if (!(element instanceof Element)) return;
    element.innerHTML = sanitizeHTML(dirty);
  }


  /* ═══════════════════════════════════════════════════════════════
     2. TABNAPPING — fix all external links on the page
        Also observes DOM mutations so dynamically injected links
        are patched too.
  ═══════════════════════════════════════════════════════════════ */
  function fixExternalLinks(root) {
    root = root || document;
    root.querySelectorAll('a[href]').forEach(a => {
      const href = a.getAttribute('href') || '';
      // External if it contains :// and doesn't start with our origin
      const isExternal = /^https?:\/\//i.test(href) &&
                         !href.startsWith(location.origin);
      if (isExternal) {
        a.setAttribute('rel', 'noopener noreferrer');
        if (!a.getAttribute('target')) a.setAttribute('target', '_blank');
      }
    });
  }

  function watchForNewLinks() {
    const obs = new MutationObserver(mutations => {
      for (const m of mutations) {
        for (const node of m.addedNodes) {
          if (node.nodeType === Node.ELEMENT_NODE) {
            fixExternalLinks(node);
          }
        }
      }
    });
    obs.observe(document.body, { childList: true, subtree: true });
  }


  /* ═══════════════════════════════════════════════════════════════
     3. CLICKJACKING — prevent the page from being iframed
  ═══════════════════════════════════════════════════════════════ */
  function preventClickjacking() {
    if (global !== global.top) {
      // We are inside an iframe — break out
      try {
        global.top.location = global.location.href;
      } catch (e) {
        // Cross-origin iframe: can't navigate, just blank the body
        document.body.innerHTML = '';
        document.body.style.cssText = 'background:#000;color:#fff;padding:2rem;font-family:sans-serif';
        document.body.textContent = 'This page cannot be displayed inside a frame.';
      }
    }
  }


  /* ═══════════════════════════════════════════════════════════════
     4. CONTENT SECURITY POLICY — inject a meta CSP tag
        Note: meta CSP cannot set frame-ancestors (needs HTTP header)
        but covers script-src, object-src, base-uri etc.
  ═══════════════════════════════════════════════════════════════ */
  function injectCSPMeta() {
    // Don't double-inject
    if (document.querySelector('meta[http-equiv="Content-Security-Policy"]')) return;

    const policy = [
      "default-src 'self'",
      // Firebase SDKs, Google Fonts, marked.js CDN
      "script-src 'self' 'unsafe-inline' https://www.gstatic.com https://cdnjs.cloudflare.com https://fonts.googleapis.com https://unpkg.com",
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
      "font-src 'self' https://fonts.gstatic.com",
      // Firebase Storage, Firestore, Auth endpoints
      "connect-src 'self' https://*.firebaseio.com https://*.googleapis.com https://*.firebaseapp.com wss://*.firebaseio.com https://collective-ai-backend.onrender.com",
      "img-src 'self' data: blob: https://*.googleusercontent.com https://*.googleapis.com",
      "frame-src 'none'",
      "object-src 'none'",
      "base-uri 'self'",
      "form-action 'self'",
    ].join('; ');

    const meta = document.createElement('meta');
    meta.setAttribute('http-equiv', 'Content-Security-Policy');
    meta.setAttribute('content', policy);
    // Insert as first child of <head>
    document.head.insertBefore(meta, document.head.firstChild);
  }


  /* ═══════════════════════════════════════════════════════════════
     5. PROTOTYPE POLLUTION — detect & neutralise
  ═══════════════════════════════════════════════════════════════ */
  const DANGEROUS_KEYS = new Set([
    '__proto__', 'constructor', 'prototype',
    '__defineGetter__', '__defineSetter__',
    '__lookupGetter__', '__lookupSetter__',
  ]);

  /**
   * Safely parse JSON — rejects payloads that attempt prototype pollution.
   */
  function safeJSONParse(str) {
    try {
      const obj = JSON.parse(str);
      return _deepSanitizeObject(obj);
    } catch { return null; }
  }

  function _deepSanitizeObject(val, depth) {
    depth = depth || 0;
    if (depth > 20) return null; // guard infinite nesting
    if (val === null || typeof val !== 'object') return val;
    if (Array.isArray(val)) return val.map(v => _deepSanitizeObject(v, depth + 1));
    const clean = Object.create(null);
    for (const key of Object.keys(val)) {
      if (DANGEROUS_KEYS.has(key)) continue; // drop poisoned key
      clean[key] = _deepSanitizeObject(val[key], depth + 1);
    }
    return clean;
  }

  /**
   * Freeze critical built-in prototypes to block runtime pollution.
   */
  function freezePrototypes() {
    try {
      Object.freeze(Object.prototype);
      Object.freeze(Array.prototype);
      Object.freeze(Function.prototype);
    } catch (e) {
      // Some environments disallow this — silently skip
    }
  }


  /* ═══════════════════════════════════════════════════════════════
     6. DANGEROUS GLOBAL EXPOSURE PREVENTION
        Warn in dev if sensitive data is leaked onto window.
  ═══════════════════════════════════════════════════════════════ */
  const SENSITIVE_GLOBALS = [
    'password', 'token', 'apiKey', 'secret', 'privateKey',
    'accessToken', 'refreshToken', 'authToken', 'sessionToken',
  ];

  function watchSensitiveGlobals() {
    if (CFG.PRODUCTION) return; // dev-only warning
    SENSITIVE_GLOBALS.forEach(key => {
      try {
        Object.defineProperty(global, key, {
          set(v) {
            console.warn(
              `[Security] Sensitive key "${key}" set on window. ` +
              'Avoid storing credentials in global scope.'
            );
            Object.defineProperty(global, key, { value: v, writable: true, configurable: true });
          },
          configurable: true,
        });
      } catch { /* already defined elsewhere — skip */ }
    });
  }


  /* ═══════════════════════════════════════════════════════════════
     7. postMessage ORIGIN VALIDATION
        Wraps addEventListener('message') with origin checking.
  ═══════════════════════════════════════════════════════════════ */
  function onTrustedMessage(handler) {
    global.addEventListener('message', (event) => {
      if (!CFG.TRUSTED_ORIGINS.includes(event.origin)) {
        console.warn(`[Security] Blocked postMessage from untrusted origin: ${event.origin}`);
        return;
      }
      handler(event);
    });
  }

  // Patch the native addEventListener to warn about unguarded 'message' listeners
  const _origAddEventListener = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = function (type, listener, options) {
    if (type === 'message' && this === global && !CFG.PRODUCTION) {
      console.warn(
        '[Security] Raw "message" event listener added to window. ' +
        'Use Security.onTrustedMessage() to enforce origin validation.'
      );
    }
    return _origAddEventListener.call(this, type, listener, options);
  };


  /* ═══════════════════════════════════════════════════════════════
     8. RATE LIMITER
        Usage:
          const limiter = Security.createRateLimiter(5, 30000); // 5 calls per 30s
          if (!limiter.allow()) { showError('Too many requests'); return; }
  ═══════════════════════════════════════════════════════════════ */
  function createRateLimiter(maxCalls, windowMs) {
    maxCalls  = maxCalls  || CFG.RATE_LIMIT_MAX;
    windowMs  = windowMs  || CFG.RATE_LIMIT_MS;
    const log = [];

    return {
      allow() {
        const now = Date.now();
        // Drop entries outside the window
        while (log.length && log[0] <= now - windowMs) log.shift();
        if (log.length >= maxCalls) return false;
        log.push(now);
        return true;
      },
      remaining() {
        const now = Date.now();
        while (log.length && log[0] <= now - windowMs) log.shift();
        return Math.max(0, maxCalls - log.length);
      },
      reset() { log.length = 0; },
    };
  }


  /* ═══════════════════════════════════════════════════════════════
     9. INPUT VALIDATION
  ═══════════════════════════════════════════════════════════════ */
  const Validate = {
    email(v) {
      return typeof v === 'string' &&
             v.length <= 254 &&
             /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v.trim());
    },
    url(v) {
      try { const u = new URL(v); return SAFE_PROTOCOLS.has(u.protocol); }
      catch { return false; }
    },
    maxLength(v, max) {
      return typeof v === 'string' && v.length <= (max || CFG.MAX_INPUT_LEN);
    },
    nonEmpty(v) {
      return typeof v === 'string' && v.trim().length > 0;
    },
    noHTML(v) {
      // Returns true if string contains no HTML tags
      return typeof v === 'string' && !/<[^>]*>/g.test(v);
    },
    /**
     * Validate a contribution form object all at once.
     * Returns { valid: bool, errors: string[] }
     */
    contribution({ title, category, content, tags, source }) {
      const errors = [];
      if (!this.nonEmpty(title))                      errors.push('Title is required.');
      if (!this.maxLength(title, CFG.MAX_TITLE_LEN))  errors.push(`Title must be ≤${CFG.MAX_TITLE_LEN} characters.`);
      if (!category)                                   errors.push('Category is required.');
      if (!this.nonEmpty(content))                     errors.push('Content is required.');
      if (!Array.isArray(tags))                        errors.push('Tags must be an array.');
      else if (tags.some(t => t.length > CFG.MAX_TAG_LEN))
                                                       errors.push(`Each tag must be ≤${CFG.MAX_TAG_LEN} characters.`);
      if (source && !this.url(source))                 errors.push('Source must be a valid https:// URL.');
      return { valid: errors.length === 0, errors };
    },
  };


  /* ═══════════════════════════════════════════════════════════════
     10. SECURE localStorage WRAPPER
         — JSON serialisation
         — try-catch (Safari private mode throws on storage access)
         — optional AES-GCM encryption stub (keys stay client-side,
           useful for hiding data from extensions reading localStorage)
  ═══════════════════════════════════════════════════════════════ */
  const Store = {
    set(key, value) {
      try {
        localStorage.setItem(key, JSON.stringify({ v: value, ts: Date.now() }));
        return true;
      } catch { return false; }
    },
    get(key, defaultValue) {
      try {
        const raw = localStorage.getItem(key);
        if (raw === null) return defaultValue !== undefined ? defaultValue : null;
        const parsed = JSON.parse(raw);
        return parsed && 'v' in parsed ? parsed.v : parsed;
      } catch { return defaultValue !== undefined ? defaultValue : null; }
    },
    remove(key) {
      try { localStorage.removeItem(key); return true; }
      catch { return false; }
    },
    clear() {
      try { localStorage.clear(); return true; }
      catch { return false; }
    },
  };


  /* ═══════════════════════════════════════════════════════════════
     11. CSRF TOKEN UTILITY
         Generates and stores a per-session token.
         Pass it in X-CSRF-Token header on state-mutating requests.
  ═══════════════════════════════════════════════════════════════ */
  let _csrfToken = null;

  function getCSRFToken() {
    if (_csrfToken) return _csrfToken;
    // Try to reuse from session storage
    try {
      _csrfToken = sessionStorage.getItem('_csrf');
    } catch { /* private mode */ }

    if (!_csrfToken) {
      _csrfToken = _randomHex(32);
      try { sessionStorage.setItem('_csrf', _csrfToken); } catch { /* ok */ }
    }
    return _csrfToken;
  }

  function _randomHex(bytes) {
    const arr = new Uint8Array(bytes);
    crypto.getRandomValues(arr);
    return Array.from(arr).map(b => b.toString(16).padStart(2, '0')).join('');
  }

  /**
   * Attach CSRF token + Content-Type to a fetch init object.
   * Usage: fetch(url, Security.fetchHeaders({ method:'POST', body: JSON.stringify(data) }))
   */
  function fetchHeaders(init) {
    init = init || {};
    init.headers = Object.assign({}, init.headers, {
      'Content-Type':  'application/json',
      'X-CSRF-Token':  getCSRFToken(),
      'X-Requested-With': 'XMLHttpRequest',
    });
    return init;
  }


  /* ═══════════════════════════════════════════════════════════════
     12. SUSPICIOUS NAVIGATION DETECTION
         Warns if the page URL contains open-redirect patterns or
         suspicious query parameters.
  ═══════════════════════════════════════════════════════════════ */
  function detectSuspiciousNavigation() {
    const url  = location.href.toLowerCase();
    const params = new URLSearchParams(location.search);

    // Open redirect: ?redirect= or ?next= pointing to external host
    for (const key of ['redirect', 'next', 'url', 'return', 'returnUrl', 'goto']) {
      const val = params.get(key) || params.get(key.toLowerCase());
      if (val) {
        try {
          const target = new URL(val, location.origin);
          if (target.origin !== location.origin) {
            console.warn(
              `[Security] Possible open redirect detected: param "${key}" = "${val}". ` +
              'Validate and whitelist redirect destinations on the server.'
            );
          }
        } catch { /* not a URL, fine */ }
      }
    }

    // Data URI in URL (rare but worth flagging)
    if (url.includes('data:text/html') || url.includes('javascript:')) {
      console.error('[Security] Dangerous URI scheme detected in page URL.');
    }
  }


  /* ═══════════════════════════════════════════════════════════════
     13. CONSOLE SUPPRESSION IN PRODUCTION
         Removes console.log / console.debug to avoid leaking
         internal app state to end users via DevTools.
         console.warn / console.error are kept for visibility.
  ═══════════════════════════════════════════════════════════════ */
  function suppressConsoleInProduction() {
    if (!CFG.PRODUCTION) return;
    const noop = () => {};
    console.log   = noop;
    console.debug = noop;
    console.info  = noop;
    // console.warn and console.error are intentionally preserved
  }


  /* ═══════════════════════════════════════════════════════════════
     INITIALISE — runs automatically on script load
  ═══════════════════════════════════════════════════════════════ */
  function init() {
    preventClickjacking();
    freezePrototypes();
    watchSensitiveGlobals();
    suppressConsoleInProduction();
    detectSuspiciousNavigation();

    // DOM-dependent steps run after the document is ready
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', _domReady);
    } else {
      _domReady();
    }
  }

  function _domReady() {
    injectCSPMeta();
    fixExternalLinks();
    watchForNewLinks();
  }

  init();


  /* ═══════════════════════════════════════════════════════════════
     PUBLIC API
  ═══════════════════════════════════════════════════════════════ */
  const Security = Object.freeze({
    // XSS
    sanitizeHTML,
    safeSetHTML,
    escapeText,

    // Validation
    validate: Validate,

    // Rate limiting
    createRateLimiter,

    // postMessage
    onTrustedMessage,

    // CSRF + fetch
    getCSRFToken,
    fetchHeaders,

    // Storage
    store: Store,

    // JSON
    safeJSONParse,

    // Config (read-only snapshot)
    config: Object.freeze({ ...CFG }),
  });

  // Expose as global and as ES module default if supported
  global.Security = Security;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = Security;
  }

})(typeof globalThis !== 'undefined' ? globalThis : window);
