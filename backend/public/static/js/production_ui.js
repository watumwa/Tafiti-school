/* Production-safe interaction refinements. No API, URL, model or field changes. */
(function () {
  'use strict';

  function ready(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  function normalisePath(value) {
    try {
      var path = new URL(value, window.location.origin).pathname.replace(/\/+$/, '');
      return path || '/';
    } catch (e) {
      return '';
    }
  }

  ready(function () {
    /* Prefix-aware navigation state. Exact links still win, while deeper pages
       keep their parent module visibly active. */
    var current = normalisePath(window.location.href);
    var best = null;
    var bestLength = -1;
    document.querySelectorAll('.pc-sidebar a.pc-link[href]').forEach(function (link) {
      var href = link.getAttribute('href');
      if (!href || href === '#' || href === '#!') return;
      var path = normalisePath(href);
      if (!path || path === '/') {
        if (current === '/' && path.length > bestLength) { best = link; bestLength = path.length; }
        return;
      }
      if (current === path || current.indexOf(path + '/') === 0) {
        if (path.length > bestLength) { best = link; bestLength = path.length; }
      }
    });
    if (best) {
      var item = best.closest('.pc-item');
      if (item) item.classList.add('ui-active');
      var menu = best.closest('.pc-hasmenu');
      if (menu) menu.classList.add('pc-trigger', 'ui-active');
    }

    /* Unsaved-work protection is deliberately opt-in. Search/filter forms are
       not affected. Delegation also covers forms loaded later inside modals. */
    var dirtyForms = new Set();
    var indicator = null;

    function ensureIndicator() {
      if (indicator) return indicator;
      indicator = document.createElement('div');
      indicator.className = 'production-unsaved-indicator';
      indicator.setAttribute('role', 'status');
      indicator.innerHTML = '<i class="ph ph-warning-circle"></i><span>Unsaved changes</span>';
      document.body.appendChild(indicator);
      return indicator;
    }

    function refreshIndicator() {
      var el = ensureIndicator();
      el.classList.toggle('is-visible', dirtyForms.size > 0);
    }

    function protectedFormFromEvent(event) {
      var target = event.target;
      if (!target) return null;
      if (target.matches && target.matches('form[data-protect-unsaved="true"]')) return target;
      return target.closest ? target.closest('form[data-protect-unsaved="true"]') : null;
    }

    function markDirty(event) {
      var form = protectedFormFromEvent(event);
      if (!form || form.dataset.submitting === 'true') return;
      dirtyForms.add(form);
      refreshIndicator();
    }

    document.addEventListener('input', markDirty, true);
    document.addEventListener('change', markDirty, true);
    document.addEventListener('submit', function (event) {
      /* This runs in the bubble phase, after normal form-level validation
         handlers. If a page cancels the submit, keep the form dirty and do not
         show a false Processing state. */
      if (event.defaultPrevented) return;
      var form = event.target && event.target.matches && event.target.matches('form') ? event.target : null;
      if (!form) return;

      if (form.matches('form[data-protect-unsaved="true"]')) {
        form.dataset.submitting = 'true';
        dirtyForms.delete(form);
        refreshIndicator();
      }

      if (form.matches('form:not([data-no-loading])')) {
        var button = event.submitter;
        if (button && !button.disabled && button.dataset.noLoading !== 'true') {
          var text = button.tagName === 'INPUT' ? button.value : button.textContent;
          button.setAttribute('data-original-text', text || 'Submit');
          button.setAttribute('aria-busy', 'true');
          button.dataset.productionLoading = 'true';
          button.style.pointerEvents = 'none';
          form.setAttribute('aria-busy', 'true');
          /* Never alter an input submit value and never disable a named submitter:
             Django workflows may depend on its name/value in request.POST. */
          if (button.tagName !== 'INPUT') {
            button.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span><span>Processing...</span>';
          }
        }
      }
    }, false);

    /* AJAX modal forms need the same protection as full pages. Bootstrap's
       hide event is cancelable, so users get one clear chance to keep editing. */
    document.addEventListener('hide.bs.modal', function (event) {
      var modal = event.target;
      if (!modal || !modal.querySelectorAll) return;
      var hasDirtyForm = Array.from(modal.querySelectorAll('form[data-protect-unsaved="true"]')).some(function (form) {
        return dirtyForms.has(form) && form.dataset.submitting !== 'true';
      });
      if (hasDirtyForm && !window.confirm('Discard the unsaved changes in this form?')) {
        event.preventDefault();
      }
    });

    /* When an AJAX modal is removed after confirmation/submission, forget its
       discarded form so a stale reference cannot keep the page dirty. */
    document.addEventListener('hidden.bs.modal', function (event) {
      var modal = event.target;
      if (!modal || !modal.querySelectorAll) return;
      modal.querySelectorAll('form[data-protect-unsaved="true"]').forEach(function (form) {
        dirtyForms.delete(form);
      });
      refreshIndicator();
    });

    window.addEventListener('beforeunload', function (event) {
      var shouldWarn = Array.from(dirtyForms).some(function (form) {
        return form.isConnected && form.dataset.submitting !== 'true';
      });
      if (!shouldWarn) return;
      event.preventDefault();
      event.returnValue = '';
    });

    /* Declarative confirmation for consequential but valid existing actions. */
    document.addEventListener('click', function (event) {
      var target = event.target.closest('[data-confirm-message]');
      if (!target) return;
      var message = target.getAttribute('data-confirm-message') || 'Please confirm this action.';
      if (!window.confirm(message)) {
        event.preventDefault();
        event.stopPropagation();
      }
    }, true);

    /* Add useful labels to icon-only controls where the page supplied a title. */
    document.querySelectorAll('a[title], button[title]').forEach(function (el) {
      if (!el.getAttribute('aria-label') && !(el.textContent || '').trim()) {
        el.setAttribute('aria-label', el.getAttribute('title'));
      }
    });
  });
})();
