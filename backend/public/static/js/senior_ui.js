/* Senior UI enhancements: safe, progressive, no dependency on business logic. */
(function () {
  'use strict';

  function ready(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  /**
   * The project now runs on Bootstrap 5, while many older templates still call
   * Bootstrap 3/4 jQuery APIs such as $('.modal').modal('show') and use
   * data-toggle/data-target/data-dismiss. This small bridge keeps those pages
   * working without touching the database or rewriting every template.
   */
  function installBootstrap5JqueryBridge() {
    if (!window.jQuery || !window.bootstrap) return;
    var $ = window.jQuery;
    if ($.fn.schoolBootstrapBridge === true) return;

    function bridge(pluginName, BootstrapClass) {
      if (!BootstrapClass || $.fn[pluginName]) return;
      $.fn[pluginName] = function (commandOrOptions) {
        var args = Array.prototype.slice.call(arguments, 1);
        var returnValue = this;
        this.each(function () {
          var instance = BootstrapClass.getOrCreateInstance(this, typeof commandOrOptions === 'object' ? commandOrOptions : undefined);
          if (typeof commandOrOptions === 'string' && typeof instance[commandOrOptions] === 'function') {
            var result = instance[commandOrOptions].apply(instance, args);
            if (typeof result !== 'undefined') returnValue = result;
          }
        });
        return returnValue;
      };
    }

    bridge('modal', window.bootstrap.Modal);
    bridge('collapse', window.bootstrap.Collapse);
    bridge('dropdown', window.bootstrap.Dropdown);
    bridge('tab', window.bootstrap.Tab);
    bridge('tooltip', window.bootstrap.Tooltip);
    bridge('popover', window.bootstrap.Popover);
    $.fn.schoolBootstrapBridge = true;
  }

  function normalizeLegacyBootstrapAttributes(root) {
    root = root || document;
    if (!root.querySelectorAll) return;

    root.querySelectorAll('[data-toggle]').forEach(function (el) {
      if (!el.getAttribute('data-bs-toggle')) el.setAttribute('data-bs-toggle', el.getAttribute('data-toggle'));
    });
    root.querySelectorAll('[data-target]').forEach(function (el) {
      if (!el.getAttribute('data-bs-target')) el.setAttribute('data-bs-target', el.getAttribute('data-target'));
    });
    root.querySelectorAll('[data-dismiss]').forEach(function (el) {
      if (!el.getAttribute('data-bs-dismiss')) el.setAttribute('data-bs-dismiss', el.getAttribute('data-dismiss'));
    });
    root.querySelectorAll('[data-parent]').forEach(function (el) {
      if (!el.getAttribute('data-bs-parent')) el.setAttribute('data-bs-parent', el.getAttribute('data-parent'));
    });
    root.querySelectorAll('[data-placement]').forEach(function (el) {
      if (!el.getAttribute('data-bs-placement')) el.setAttribute('data-bs-placement', el.getAttribute('data-placement'));
    });
  }

  function getSelectorFromTrigger(trigger) {
    if (!trigger) return '';
    return trigger.getAttribute('data-bs-target') || trigger.getAttribute('data-target') || trigger.getAttribute('href') || '';
  }

  function safeQuerySelector(selector) {
    if (!selector || selector === '#') return null;
    try { return document.querySelector(selector); }
    catch (e) { return null; }
  }

  // Make the jQuery bridge available to page scripts that execute immediately.
  installBootstrap5JqueryBridge();

  ready(function () {
    installBootstrap5JqueryBridge();
    normalizeLegacyBootstrapAttributes(document);

    // Reliable delegated handler for legacy Bootstrap modal trigger attributes.
    document.addEventListener('click', function (event) {
      var trigger = event.target.closest('[data-toggle="modal"], [data-bs-toggle="modal"]');
      if (!trigger || !window.bootstrap || !window.bootstrap.Modal) return;
      var target = safeQuerySelector(getSelectorFromTrigger(trigger));
      if (!target || !target.classList.contains('modal')) return;
      event.preventDefault();
      window.bootstrap.Modal.getOrCreateInstance(target).show(trigger);
    }, false);

    var path = window.location.pathname.replace(/\/$/, '') || '/';

    // Mark active sidebar links so the user always knows where they are.
    document.querySelectorAll('.pc-sidebar a.pc-link[href]').forEach(function (link) {
      var href = link.getAttribute('href');
      if (!href || href === '#!' || href === '#') return;
      var linkPath;
      try { linkPath = new URL(href, window.location.origin).pathname.replace(/\/$/, '') || '/'; }
      catch (e) { return; }
      if (linkPath === path) {
        var item = link.closest('.pc-item');
        if (item) item.classList.add('ui-active');
        var parent = link.closest('.pc-hasmenu');
        if (parent) parent.classList.add('pc-trigger', 'ui-active');
      }
    });

    // Make ordinary tables responsive without editing every template.
    document.querySelectorAll('table.table, table.datatable, table.dataTable').forEach(function (table) {
      if (!table.closest('.table-responsive')) {
        var wrapper = document.createElement('div');
        wrapper.className = 'table-responsive ui-table-wrap';
        table.parentNode.insertBefore(wrapper, table);
        wrapper.appendChild(table);
      }
    });

    // Submission feedback is handled by production_ui.js at the document
    // bubble phase so page-level validation can cancel a submit first.

    // Lightweight confirmation for destructive links/buttons that do not already have a handler.
    document.querySelectorAll('a, button').forEach(function (el) {
      if (el.dataset.confirmBound || el.dataset.noConfirm === 'true') return;
      var label = (el.textContent || '').toLowerCase();
      var href = (el.getAttribute('href') || '').toLowerCase();
      var name = (el.getAttribute('name') || '').toLowerCase();
      var action = (el.getAttribute('formaction') || '').toLowerCase();
      var destructive = /delete|remove|trash/.test(label + ' ' + href + ' ' + name + ' ' + action);
      if (!destructive) return;
      el.dataset.confirmBound = 'true';
      el.addEventListener('click', function (event) {
        if (el.dataset.confirmed === 'true') return;
        var ok = window.confirm('Please confirm this action. It may affect saved school records.');
        if (!ok) {
          event.preventDefault();
          event.stopPropagation();
        }
      });
    });

    // Improve accessibility of icon-only buttons/links.
    document.querySelectorAll('a, button').forEach(function (el) {
      var hasText = (el.textContent || '').trim().length > 0;
      if (hasText || el.getAttribute('aria-label') || el.getAttribute('title')) return;
      var icon = el.querySelector('i');
      if (icon) el.setAttribute('aria-label', 'Action');
    });

    // Open table edit links in a shared modal instead of navigating away.
    var editModalEl = document.getElementById('tableEditModal');
    var editModalBody = document.getElementById('tableEditModalBody');
    var editModalTitle = document.getElementById('tableEditModalLabel');
    var editModal = editModalEl && window.bootstrap ? new bootstrap.Modal(editModalEl) : null;

    function getTableEditTriggerUrl(trigger) {
      if (!trigger || trigger.dataset.noEditModal === 'true' || !trigger.closest('table')) return '';
      if (trigger.target && trigger.target !== '_self') return '';

      // Production safety: AJAX edit is opt-in, never inferred from an "edit"
      // looking URL. Complex forms may require their own JavaScript, uploads, or
      // dependent fields and are safer on their normal full page.
      var explicitlyEnabled = trigger.dataset.editModal === 'true' || Boolean(trigger.dataset.modalUrl);
      if (!explicitlyEnabled) return '';

      // Do not hijack real Bootstrap modal buttons. Those usually have their own
      // row-specific form already in the page, e.g. Expense and Allocation modals.
      if ((trigger.getAttribute('data-toggle') || trigger.getAttribute('data-bs-toggle')) === 'modal') return '';

      return trigger.getAttribute('href') || trigger.dataset.url || trigger.dataset.href || trigger.dataset.editUrl || trigger.dataset.modalUrl || '';
    }

    function editUrlLooksSafe(rawHref) {
      if (!rawHref || rawHref === '#' || rawHref.indexOf('javascript:') === 0) return false;
      var path;
      try { path = new URL(rawHref, window.location.origin).pathname.toLowerCase(); }
      catch (e) { return false; }

      // Only true edit endpoints should open in the shared modal. This prevents
      // links like "Add or Edit Results" or timetable-center pages from loading a
      // large unrelated page into the edit popup.
      return (
        /(^|\/)edit([_\/-]|$)/.test(path) ||
        /(^|\/)[^\/]*[_-]edit([_\/-]|$)/.test(path) ||
        /\/edit\//.test(path) ||
        /\/edit_[^\/]+/.test(path) ||
        /_[Ee]dit/.test(path)
      );
    }

    function isTableEditTrigger(trigger) {
      var href = getTableEditTriggerUrl(trigger);
      if (!href) return false;
      var text = (trigger.textContent || '').trim().toLowerCase();
      var title = (trigger.getAttribute('title') || '').toLowerCase();
      var aria = (trigger.getAttribute('aria-label') || '').toLowerCase();
      var classes = String(trigger.className || '');
      var icon = trigger.querySelector('.fa-edit, .fa-pencil, .fa-pen, .ph-pencil, .ti-pencil');
      var explicitEditButton = Boolean(
        trigger.dataset.editUrl ||
        trigger.dataset.modalUrl ||
        classes.indexOf('open-edit-student-modal') !== -1
      );

      return editUrlLooksSafe(href) || Boolean(explicitEditButton && (icon || text.indexOf('edit') !== -1 || title.indexOf('edit') !== -1 || aria.indexOf('edit') !== -1));
    }

    function setEditModalLoading() {
      editModalBody.innerHTML = '<div class="text-center text-muted py-4"><span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>Loading the correct edit form...</div>';
      editModalTitle.innerHTML = '<i class="fa fa-edit me-2"></i>Edit record';
    }

    function normalizeLoadedModalContent(container) {
      normalizeLegacyBootstrapAttributes(container);
      container.querySelectorAll('.modal-footer [data-dismiss="modal"]').forEach(function (button) {
        if (!button.getAttribute('data-bs-dismiss')) button.setAttribute('data-bs-dismiss', 'modal');
      });
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, function (char) {
        return {
          '&': '&amp;',
          '<': '&lt;',
          '>': '&gt;',
          '"': '&quot;',
          "'": '&#39;'
        }[char];
      });
    }

    function appendModalQuery(url) {
      var parsed = new URL(url, window.location.origin);
      parsed.searchParams.set('modal', '1');
      parsed.searchParams.set('table_edit_modal', '1');
      return parsed.href;
    }

    function normalizedPath(url) {
      try { return new URL(url, window.location.origin).pathname.replace(/\/$/, '').toLowerCase(); }
      catch (e) { return ''; }
    }

    function formActionMatches(form, sourceUrl) {
      var action = form.getAttribute('action');
      if (!action) return true;
      return normalizedPath(action ? new URL(action, sourceUrl).href : sourceUrl) === normalizedPath(sourceUrl);
    }

    function isBadModalForm(form) {
      var idClass = ((form.id || '') + ' ' + (form.className || '')).toLowerCase();
      var action = (form.getAttribute('action') || '').toLowerCase();
      if (/filter|search|logout|switchrole|switch-role/.test(idClass + ' ' + action)) return true;
      var modal = form.closest('.modal');
      if (modal) {
        var modalName = ((modal.id || '') + ' ' + (modal.className || '')).toLowerCase();
        // Ignore utility/add modals embedded in the base template. The shared
        // modal should only use a modal form if it is clearly an edit modal.
        if (modalName.indexOf('edit') === -1) return true;
        if (modalName.indexOf('add') !== -1 && modalName.indexOf('edit') === -1) return true;
      }
      return false;
    }

    function chooseEditForm(doc, sourceUrl) {
      var sourcePath = normalizedPath(sourceUrl);
      var forms = Array.prototype.slice.call(doc.querySelectorAll('[data-table-edit-form="true"], .table-edit-modal-form, main form, .pc-content form, .x_content form, form'));
      forms = forms.filter(function (form) {
        var method = (form.getAttribute('method') || 'get').toLowerCase();
        if (method !== 'post') return false;
        if (isBadModalForm(form)) return false;
        return true;
      });
      if (!forms.length) return null;

      // 1) Explicit modal/edit forms from templates or future views.
      var explicit = forms.find(function (form) {
        return form.matches('[data-table-edit-form="true"], .table-edit-modal-form, [data-edit-form="true"]');
      });
      if (explicit) return explicit;

      // 2) A form whose action points to the clicked edit URL.
      var matchingAction = forms.find(function (form) {
        return formActionMatches(form, sourceUrl);
      });
      if (matchingAction) return matchingAction;

      // 3) A form inside the actual main content, not a hidden/modal utility form.
      var mainContent = doc.querySelector('#main-content, main, .pc-content');
      if (mainContent) {
        var mainForm = forms.find(function (form) { return mainContent.contains(form); });
        if (mainForm) return mainForm;
      }

      // 4) Last fallback: a form whose action/path still looks like an edit endpoint.
      return forms.find(function (form) {
        var action = form.getAttribute('action') || sourcePath;
        return editUrlLooksSafe(action);
      }) || forms[0];
    }

    function findTitleForForm(doc, form) {
      var panel = form.closest('.x_panel, .card, .modal-content, .container, .pc-content, main');
      var titleNode = null;
      if (panel) {
        titleNode = panel.querySelector('.x_title h2, .card-title, .modal-title, h1, h2, h3');
      }
      if (!titleNode) {
        var previous = form.previousElementSibling;
        while (previous && !titleNode) {
          if (/^H[1-6]$/.test(previous.tagName)) titleNode = previous;
          previous = previous.previousElementSibling;
        }
      }
      if (!titleNode) {
        titleNode = doc.querySelector('main h1, main h2, main h3, .pc-content h1, .pc-content h2, .pc-content h3, .x_title h2, .modal-title, title');
      }
      var title = titleNode ? (titleNode.textContent || '').replace(/\s+/g, ' ').trim() : '';
      if (!title || title.toLowerCase() === 'school mis') return 'Edit record';
      return title;
    }

    function prepareFormForSharedModal(form, sourceUrl) {
      var clonedForm = form.cloneNode(true);
      var originalAction = clonedForm.getAttribute('action');
      clonedForm.setAttribute('action', originalAction ? new URL(originalAction, sourceUrl).href : sourceUrl);
      clonedForm.setAttribute('method', clonedForm.getAttribute('method') || 'post');
      clonedForm.classList.add('table-edit-modal-form');
      clonedForm.dataset.tableEditForm = 'true';
      clonedForm.dataset.noLoading = 'true';

      clonedForm.querySelectorAll('script, style').forEach(function (el) { el.remove(); });
      clonedForm.querySelectorAll('input[type="submit"], button[type="submit"]').forEach(function (submit) { submit.remove(); });
      clonedForm.querySelectorAll('.container:empty, .row:empty, .clearfix:empty, .modal-footer:empty').forEach(function (emptyBlock) { emptyBlock.remove(); });

      var footer = document.createElement('div');
      footer.className = 'modal-footer table-edit-modal-footer';

      var cancel = document.createElement('button');
      cancel.type = 'button';
      cancel.className = 'btn btn-secondary';
      cancel.setAttribute('data-bs-dismiss', 'modal');
      cancel.textContent = 'Cancel';

      var save = document.createElement('button');
      save.type = 'submit';
      save.className = 'btn btn-primary';
      save.innerHTML = '<i class="fa fa-save me-1"></i> Save changes';

      footer.appendChild(cancel);
      footer.appendChild(save);
      clonedForm.appendChild(footer);
      return clonedForm;
    }

    function extractEditContent(html, sourceUrl) {
      var parser = new DOMParser();
      var doc = parser.parseFromString(html, 'text/html');

      // If a view returns a purpose-built modal partial, use it exactly.
      var explicitPartial = doc.querySelector('[data-modal-edit-content], [data-table-edit-content]');
      if (explicitPartial) {
        normalizeLoadedModalContent(explicitPartial);
        var partialTitle = explicitPartial.getAttribute('data-modal-title') || explicitPartial.getAttribute('data-title') || 'Edit record';
        return { title: partialTitle, html: explicitPartial.innerHTML };
      }

      var form = chooseEditForm(doc, sourceUrl);
      if (!form) return null;

      var wrapper = document.createElement('div');
      wrapper.appendChild(prepareFormForSharedModal(form, sourceUrl));
      normalizeLoadedModalContent(wrapper);
      return { title: findTitleForForm(doc, form), html: wrapper.innerHTML };
    }

    function renderEditContent(content) {
      editModalTitle.innerHTML = '<i class="fa fa-edit me-2"></i>' + escapeHtml(content.title);
      editModalBody.innerHTML = content.html;
      normalizeLoadedModalContent(editModalBody);
    }

    function openTableEditModal(url) {
      if (!editModal) {
        window.location.href = url;
        return;
      }
      setEditModalLoading();
      editModal.show();

      fetch(appendModalQuery(url), { headers: { 'X-Requested-With': 'XMLHttpRequest' }, credentials: 'same-origin' })
        .then(function (response) {
          if (!response.ok) throw new Error('Unable to load edit form.');
          return response.text();
        })
        .then(function (html) {
          var content = extractEditContent(html, url);
          if (!content) throw new Error('No editable form was found.');
          renderEditContent(content);
        })
        .catch(function () {
          editModalBody.innerHTML = '<div class="alert alert-danger mb-0">Failed to load the edit form. <a href="' + escapeHtml(url) + '">Open the edit page</a>.</div>';
        });
    }

    document.addEventListener('click', function (event) {
      var trigger = event.target.closest('a[href], button[data-url], button[data-href], button[data-edit-url], [data-edit-url], [data-modal-url]');
      if (!isTableEditTrigger(trigger)) return;
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      var rawUrl = getTableEditTriggerUrl(trigger);
      openTableEditModal(new URL(rawUrl, window.location.origin).href);
    }, true);

    if (editModalBody) {
      editModalBody.addEventListener('submit', function (event) {
        var form = event.target.closest('form[data-table-edit-form="true"]');
        if (!form) return;
        event.preventDefault();

        var button = form.querySelector('button[type="submit"], input[type="submit"]');
        if (button) button.disabled = true;

        fetch(form.action || window.location.href, {
          method: (form.method || 'POST').toUpperCase(),
          body: new FormData(form),
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
          credentials: 'same-origin',
          redirect: 'follow'
        })
          .then(function (response) {
            var contentType = response.headers.get('content-type') || '';
            if (contentType.indexOf('application/json') !== -1) {
              return response.json().then(function (data) {
                if (data.ok || data.success) {
                  window.location.reload();
                  return;
                }
                if (data.html || data.form_html) {
                  editModalBody.innerHTML = data.html || data.form_html;
                  normalizeLoadedModalContent(editModalBody);
                  return;
                }
                throw new Error('Save failed.');
              });
            }
            return response.text().then(function (html) {
              if (response.redirected || response.ok) {
                var content = extractEditContent(html, response.url || form.action);
                if (!content || response.redirected) {
                  window.location.reload();
                  return;
                }
                renderEditContent(content);
                var hasErrors = editModalBody.querySelector('.errorlist, .invalid-feedback, .is-invalid, .has-error');
                if (!hasErrors) window.location.reload();
              } else {
                var failedContent = extractEditContent(html, form.action);
                if (failedContent) renderEditContent(failedContent);
                else throw new Error('Save failed.');
              }
            });
          })
          .catch(function () {
            editModalBody.insertAdjacentHTML('afterbegin', '<div class="alert alert-danger">Could not save changes. Please check the form and try again.</div>');
          })
          .finally(function () {
            if (button) button.disabled = false;
          });
      });
    }
  });
})();
