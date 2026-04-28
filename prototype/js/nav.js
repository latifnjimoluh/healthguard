/**
 * HealthGuard IA — nav.js
 * Ce fichier gère deux responsabilités :
 *  1. MODAL SYSTEM  — remplace alert() et confirm() par des popups Material Design
 *  2. NAVIGATION    — sidebar desktop (fixe) + sidebar mobile (hamburger off-canvas)
 *
 * Inclure dans tous les écrans sauf si SKIP_NAV est configuré.
 */
(function () {
  'use strict';

  var DESKTOP_MIN = 768;
  /* Pages où la sidebar ne doit PAS être injectée */
  var SKIP_NAV_PAGES = ['e1_login.html'];

  /* ================================================================
     SECTION 1 — MODAL SYSTÈME
     Expose window.hgAlert et window.hgConfirm
     ================================================================ */

  var _overlay, _title, _body, _icon, _okBtn, _cancelBtn;
  var _onOk = null, _onCancel = null;

  function _ensureModal() {
    if (document.getElementById('hg-modal-overlay')) {
      _overlay   = document.getElementById('hg-modal-overlay');
      _title     = document.getElementById('hg-modal-title');
      _body      = document.getElementById('hg-modal-body');
      _icon      = document.getElementById('hg-modal-icon');
      _okBtn     = document.getElementById('hg-modal-ok');
      _cancelBtn = document.getElementById('hg-modal-cancel');
      return;
    }

    var wrap = document.createElement('div');
    wrap.id = 'hg-modal-overlay';
    wrap.className = 'hg-modal-overlay';
    wrap.style.display = 'none';
    wrap.setAttribute('role', 'dialog');
    wrap.setAttribute('aria-modal', 'true');
    wrap.innerHTML =
      '<div class="hg-modal-sheet">'
      + '<div class="hg-modal-icon-row" id="hg-modal-icon">ℹ️</div>'
      + '<div class="hg-modal-title"     id="hg-modal-title">Information</div>'
      + '<div class="hg-modal-body"      id="hg-modal-body"></div>'
      + '<div class="hg-modal-actions">'
      +   '<button id="hg-modal-cancel" class="btn btn-outline" style="display:none">Annuler</button>'
      +   '<button id="hg-modal-ok"     class="btn btn-primary">OK</button>'
      + '</div>'
      + '</div>';
    document.body.appendChild(wrap);

    _overlay   = wrap;
    _title     = document.getElementById('hg-modal-title');
    _body      = document.getElementById('hg-modal-body');
    _icon      = document.getElementById('hg-modal-icon');
    _okBtn     = document.getElementById('hg-modal-ok');
    _cancelBtn = document.getElementById('hg-modal-cancel');

    _okBtn.addEventListener('click', function () {
      _closeModal();
      if (_onOk) _onOk();
    });
    _cancelBtn.addEventListener('click', function () {
      _closeModal();
      if (_onCancel) _onCancel();
    });
    /* Fermer en cliquant sur le fond sombre */
    wrap.addEventListener('click', function (e) {
      if (e.target === wrap) _closeModal();
    });
    /* Fermer avec Échap */
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && _overlay && _overlay.style.display !== 'none') _closeModal();
    });
  }

  function _closeModal() {
    if (_overlay) _overlay.style.display = 'none';
    _onOk = null;
    _onCancel = null;
  }

  /**
   * Affiche une info-popup (remplace alert).
   * @param {string}  message  Texte ou HTML du corps
   * @param {string}  title    Titre de la fenêtre (optionnel)
   * @param {string}  icon     Emoji (optionnel, défaut ℹ️)
   * @param {boolean} isHtml   true pour interpréter message comme HTML
   */
  window.hgAlert = function (message, title, icon, isHtml) {
    _ensureModal();
    _icon.textContent = icon || 'ℹ️';
    _title.textContent = title || 'Information';
    if (isHtml) { _body.innerHTML = message; }
    else        { _body.textContent = message; }
    _cancelBtn.style.display = 'none';
    _okBtn.textContent = 'OK';
    _okBtn.className = 'btn btn-primary';
    _onOk = null;
    _onCancel = null;
    _overlay.style.display = 'flex';
    setTimeout(function () { if (_okBtn) _okBtn.focus(); }, 50);
  };

  /**
   * Affiche une confirmation (remplace confirm).
   * @param {string}   message    Texte du corps
   * @param {string}   title      Titre
   * @param {Function} onConfirm  Callback si "Confirmer"
   * @param {Function} onCancel   Callback si "Annuler" (optionnel)
   * @param {string}   icon       Emoji (optionnel, défaut ❓)
   * @param {string}   okLabel    Texte du bouton OK (optionnel)
   * @param {string}   okClass    Classe CSS du bouton OK (optionnel)
   */
  window.hgConfirm = function (message, title, onConfirm, onCancel, icon, okLabel, okClass) {
    _ensureModal();
    _icon.textContent = icon || '❓';
    _title.textContent = title || 'Confirmation';
    _body.textContent = message;
    _cancelBtn.style.display = '';
    _cancelBtn.textContent = 'Annuler';
    _okBtn.textContent = okLabel || 'Confirmer';
    _okBtn.className = 'btn ' + (okClass || 'btn-primary');
    _onOk = onConfirm || null;
    _onCancel = onCancel || null;
    _overlay.style.display = 'flex';
    setTimeout(function () { if (_cancelBtn) _cancelBtn.focus(); }, 50);
  };

  /* ================================================================
     SECTION 2 — NAVIGATION / SIDEBAR
     ================================================================ */

  function _getAgentNom() {
    try {
      var nom = localStorage.getItem('hg_agent_nom');
      if (nom) return nom;
      var agents = JSON.parse(localStorage.getItem('hg_agents') || '[]');
      var agentId = localStorage.getItem('hg_agent_id') || '';
      var found = null;
      for (var i = 0; i < agents.length; i++) {
        if (agents[i].id === agentId) { found = agents[i]; break; }
      }
      if (found) return found.nom;
      if (agentId === 'agent_aminatou')  return 'Aminatou Wali';
      if (agentId === 'urgence_anonyme') return 'Urgence (anonyme)';
      return 'Agent';
    } catch (e) { return 'Agent'; }
  }

  function _currentPage() {
    return window.location.pathname.split('/').pop() || '';
  }

  function _shouldSkipNav() {
    var page = _currentPage();
    for (var i = 0; i < SKIP_NAV_PAGES.length; i++) {
      if (SKIP_NAV_PAGES[i] === page) return true;
    }
    return false;
  }

  function _navLink(href, icon, label) {
    var active = href === _currentPage() ? ' hg-nav-active' : '';
    return '<a href="' + href + '" class="hg-nav-item' + active + '" title="' + label + '">'
      + '<span class="hg-nav-icon">' + icon + '</span>'
      + '<span class="hg-nav-label">' + label + '</span>'
      + '</a>';
  }

  function _buildSidebar() {
    var el = document.createElement('aside');
    el.id = 'hg-sidebar';
    el.className = 'hg-sidebar';
    el.setAttribute('aria-label', 'Navigation principale');
    el.innerHTML =
      '<div class="hg-sidebar-brand">'
      +   '<div class="hg-sidebar-logo">🏥</div>'
      +   '<div class="hg-sidebar-brand-text">'
      +     '<div class="hg-sidebar-brand-title">HealthGuard IA</div>'
      +     '<div class="hg-sidebar-agent">' + _getAgentNom() + '</div>'
      +   '</div>'
      + '</div>'
      + '<nav class="hg-sidebar-nav">'
      +   _navLink('e2_dashboard.html',     '📊', 'Tableau de bord')
      +   _navLink('e3_consultation.html',  '🩺', 'Nouvelle consultation')
      +   _navLink('e6_patient_record.html','👤', 'Patients')
      +   _navLink('e7_settings.html',      '⚙️', 'Paramètres & Sync')
      + '</nav>'
      + '<div class="hg-sidebar-footer">'
      +   '<div class="hg-connectivity" id="hg-sidebar-status">● Vérification…</div>'
      +   '<a href="e1_login.html" class="hg-logout-btn"'
      +     ' onclick="localStorage.removeItem(\'hg_agent_id\');localStorage.removeItem(\'hg_agent_nom\');">'
      +     '↩ Changer de compte'
      +   '</a>'
      + '</div>';
    return el;
  }

  function _watchConnectivity() {
    function update() {
      var el = document.getElementById('hg-sidebar-status');
      if (!el) return;
      if (navigator.onLine) { el.textContent = '● En ligne';  el.style.color = '#81C784'; }
      else                  { el.textContent = '● Hors ligne'; el.style.color = '#FF8A65'; }
    }
    update();
    window.addEventListener('online',  update);
    window.addEventListener('offline', update);
  }

  /* ---- DESKTOP : sidebar fixe, contenu décalé ---- */
  function _initDesktopLayout() {
    var app = document.querySelector('.app-container');
    if (!app || app.classList.contains('hg-desktop-init')) return;
    app.classList.add('hg-desktop-init', 'hg-desktop');

    var sidebar = _buildSidebar();

    var main = document.createElement('div');
    main.className = 'hg-main';
    while (app.firstChild) main.appendChild(app.firstChild);

    app.appendChild(sidebar);
    app.appendChild(main);
    _watchConnectivity();
  }

  /* ---- MOBILE : sidebar off-canvas + bouton hamburger ---- */
  var _sidebarOpen = false;

  function _openSidebar() {
    var sb = document.getElementById('hg-sidebar');
    var bd = document.getElementById('hg-sidebar-backdrop');
    if (sb) sb.classList.add('open');
    if (bd) bd.classList.add('open');
    _sidebarOpen = true;
    document.body.style.overflow = 'hidden';
  }

  function _closeSidebar() {
    var sb = document.getElementById('hg-sidebar');
    var bd = document.getElementById('hg-sidebar-backdrop');
    if (sb) sb.classList.remove('open');
    if (bd) bd.classList.remove('open');
    _sidebarOpen = false;
    document.body.style.overflow = '';
  }

  function _toggleSidebar() {
    if (_sidebarOpen) _closeSidebar(); else _openSidebar();
  }

  function _initMobileNav() {
    /* Backdrop */
    var backdrop = document.createElement('div');
    backdrop.id = 'hg-sidebar-backdrop';
    backdrop.className = 'hg-sidebar-backdrop';
    backdrop.addEventListener('click', _closeSidebar);
    document.body.appendChild(backdrop);

    /* Sidebar (injectée dans body pour éviter les problèmes de z-index) */
    var sidebar = _buildSidebar();
    document.body.appendChild(sidebar);

    /* Bouton hamburger dans .screen-header */
    var header = document.querySelector('.screen-header');
    if (header) {
      var btn = document.createElement('button');
      btn.className = 'hg-hamburger';
      btn.setAttribute('aria-label', 'Ouvrir le menu');
      btn.setAttribute('aria-expanded', 'false');
      btn.innerHTML = '&#9776;'; /* ☰ */
      btn.style.display = 'flex';
      btn.addEventListener('click', function () {
        _toggleSidebar();
        btn.setAttribute('aria-expanded', String(_sidebarOpen));
      });
      header.insertBefore(btn, header.firstChild);
    }

    /* Fermer la sidebar si on clique un lien à l'intérieur */
    sidebar.addEventListener('click', function (e) {
      if (e.target.closest('.hg-nav-item')) _closeSidebar();
    });

    _watchConnectivity();
  }

  /* ---- POINT D'ENTRÉE ---- */
  function _init() {
    _ensureModal();
    
    /* Enregistrement du Service Worker pour la PWA */
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', function() {
        navigator.serviceWorker.register('/app/sw.js').then(function(registration) {
          console.log('ServiceWorker registration successful with scope: ', registration.scope);
        }, function(err) {
          console.log('ServiceWorker registration failed: ', err);
        });
      });
    }

    if (_shouldSkipNav()) return;

    if (window.innerWidth >= DESKTOP_MIN) {
      _initDesktopLayout();
    } else {
      _initMobileNav();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _init);
  } else {
    _init();
  }

})();
