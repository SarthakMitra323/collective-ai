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

})();