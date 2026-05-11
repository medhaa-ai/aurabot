'use strict';

// Manages avatar expression swaps and the header avatar image.
// Expressions must match the filenames in frontend/avatars/

const EXPRESSIONS = ['idle','thinking','happy','empathetic','excited','confused','focused','celebrating'];
const AVATAR_DIR  = 'avatars/';

const AvatarController = (() => {
  let currentExpr = 'idle';
  let headerEl    = null;
  let mainEl      = null; // optional larger display element

  function init() {
    headerEl = document.getElementById('header-avatar');
    mainEl   = document.getElementById('main-avatar'); // may be null for Phase 1
  }

  function setExpression(expr) {
    if (!EXPRESSIONS.includes(expr)) expr = 'idle';
    if (expr === currentExpr) return;
    currentExpr = expr;

    const src = `${AVATAR_DIR}${expr}.svg`;
    if (headerEl) {
      headerEl.style.opacity = '0';
      setTimeout(() => {
        headerEl.src = src;
        headerEl.style.opacity = '1';
      }, 80);
    }
    if (mainEl) {
      mainEl.style.opacity = '0';
      setTimeout(() => {
        mainEl.src = src;
        mainEl.style.opacity = '1';
      }, 80);
    }
  }

  function getExpression() { return currentExpr; }

  return { init, setExpression, getExpression };
})();

// Apply smooth transition style once
document.addEventListener('DOMContentLoaded', () => {
  const style = document.createElement('style');
  style.textContent = `
    #header-avatar, #main-avatar {
      transition: opacity 0.08s ease;
    }
  `;
  document.head.appendChild(style);
  AvatarController.init();
});
