(function () {
  "use strict";

  function one(root, selector) { return root.querySelector(selector); }
  function all(root, selector) { return Array.from(root.querySelectorAll(selector)); }
  function setText(root, selector, value) {
    const element = one(root, selector);
    if (element) element.textContent = value == null || value === "" ? "—" : value;
  }
  function money(value) {
    const amount = Number(value || 0);
    return "UGX " + new Intl.NumberFormat("en-UG", { maximumFractionDigits: 0 }).format(amount);
  }
  function debounce(callback, delay) {
    let timer;
    return function () {
      const args = arguments;
      window.clearTimeout(timer);
      timer = window.setTimeout(function () { callback.apply(null, args); }, delay);
    };
  }
  async function getJSON(url, params) {
    const query = new URLSearchParams(params);
    const response = await fetch(url + "?" + query.toString(), {
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin"
    });
    if (!response.ok) throw new Error("Lookup failed");
    return response.json();
  }
  function clearResults(container) {
    if (container) container.replaceChildren();
  }
  function emptyResult(container, message) {
    clearResults(container);
    const item = document.createElement("div");
    item.className = "lib-result-empty";
    item.textContent = message;
    container.appendChild(item);
  }
  function resultButton(icon, title, meta, tail) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "lib-result";
    button.setAttribute("role", "option");
    const iconWrap = document.createElement("span");
    iconWrap.className = "lib-result-icon";
    const iconElement = document.createElement("i");
    iconElement.className = icon;
    iconWrap.appendChild(iconElement);
    const content = document.createElement("span");
    const strong = document.createElement("strong");
    strong.textContent = title;
    const small = document.createElement("small");
    small.textContent = meta;
    content.append(strong, small);
    const end = document.createElement("span");
    end.className = "lib-result-tail";
    end.textContent = tail || "Select";
    button.append(iconWrap, content, end);
    return button;
  }

  function initIssue(form) {
    const borrowerURL = form.dataset.borrowerUrl;
    const copyURL = form.dataset.copyUrl;
    const borrowerSearch = one(form, "#borrower-search");
    const bookSearch = one(form, "#book-search");
    const borrowerResults = one(form, "[data-borrower-results]");
    const copyResults = one(form, "[data-copy-results]");
    const studentInput = one(form, "#id_student");
    const staffInput = one(form, "#id_staff");
    const copyInput = one(form, "#id_copy");
    const confirmButton = one(form, "[data-confirm-issue]");
    const bookStep = one(form, "[data-book-step]");
    const confirmStep = one(form, "[data-confirm-step]");
    let borrowerFilter = "all";
    let borrower = null;
    let copy = null;
    let borrowerSequence = 0;
    let copySequence = 0;

    function updateSteps() {
      const steps = all(document, ".lib-steps [data-step]");
      steps.forEach(function (step) { step.classList.remove("is-active", "is-done"); });
      const borrowerStep = steps.find(function (step) { return step.dataset.step === "borrower"; });
      const navBook = steps.find(function (step) { return step.dataset.step === "book"; });
      const navConfirm = steps.find(function (step) { return step.dataset.step === "confirm"; });
      if (!borrower) borrowerStep.classList.add("is-active");
      else {
        borrowerStep.classList.add("is-done");
        if (!copy) navBook.classList.add("is-active");
        else {
          navBook.classList.add("is-done");
          navConfirm.classList.add("is-active");
        }
      }
    }

    function resetCopy() {
      copy = null;
      copyInput.value = "";
      bookSearch.value = "";
      one(form, "[data-selected-copy]").hidden = true;
      one(form, "[data-issue-summary]").hidden = true;
      clearResults(copyResults);
      confirmButton.disabled = true;
      confirmStep.classList.add("is-muted");
      updateSteps();
    }

    function renderStatus(data) {
      one(form, ".lib-status-empty").hidden = true;
      one(form, "[data-status-content]").hidden = false;
      setText(form, "[data-status-name]", data.name);
      setText(form, "[data-status-meta]", data.meta);
      const eligibility = one(form, "[data-eligibility]");
      eligibility.classList.toggle("is-blocked", !data.eligible);
      eligibility.textContent = (data.eligible ? "✓ " : "⚠ ") + data.eligibility_message;
      setText(form, "[data-active-loans]", data.active_loans + " / " + data.maximum_books);
      setText(form, "[data-overdue-loans]", data.overdue_loans);
      setText(form, "[data-outstanding-fine]", money(data.outstanding_fine));
      const currentLoans = one(form, "[data-current-loans]");
      currentLoans.replaceChildren();
      if (!data.recent_loans.length) {
        const empty = document.createElement("div");
        empty.className = "lib-result-empty";
        empty.textContent = "No books currently on loan.";
        currentLoans.appendChild(empty);
      } else {
        data.recent_loans.forEach(function (loan) {
          const row = document.createElement("div");
          row.className = "lib-mini-loan" + (loan.overdue ? " is-overdue" : "");
          const title = document.createElement("strong");
          title.textContent = loan.title;
          const detail = document.createElement("small");
          detail.textContent = loan.copy + " · Due " + loan.due;
          row.append(title, detail);
          currentLoans.appendChild(row);
        });
      }
    }

    async function selectBorrower(kind, id) {
      const sequence = ++borrowerSequence;
      try {
        const payload = await getJSON(borrowerURL, { kind: kind, id: id });
        if (sequence !== borrowerSequence) return;
        borrower = payload.borrower;
        studentInput.value = borrower.kind === "student" ? borrower.id : "";
        staffInput.value = borrower.kind === "staff" ? borrower.id : "";
        setText(form, "[data-borrower-name]", borrower.name);
        setText(form, "[data-borrower-meta]", borrower.meta);
        one(form, "[data-selected-borrower]").hidden = false;
        borrowerSearch.hidden = true;
        one(form, "[data-borrower-step] .lib-search-row").hidden = true;
        one(form, ".lib-segmented").hidden = true;
        clearResults(borrowerResults);
        renderStatus(borrower);
        setText(form, "[data-loan-days]", borrower.loan_days + " days");
        setText(form, "[data-due-date]", borrower.due_label);
        resetCopy();
        const canContinue = borrower.eligible;
        bookSearch.disabled = !canContinue;
        all(bookStep, "[data-scan-target]").forEach(function (button) { button.disabled = !canContinue; });
        bookStep.classList.toggle("is-muted", !canContinue);
        if (canContinue) window.setTimeout(function () { bookSearch.focus(); }, 0);
        updateSteps();
      } catch (error) {
        emptyResult(borrowerResults, "This member is no longer available. Search again.");
      }
    }

    async function searchBorrowers(autoSelect) {
      const query = borrowerSearch.value.trim();
      if (!query) { clearResults(borrowerResults); return; }
      const sequence = ++borrowerSequence;
      borrowerResults.setAttribute("aria-busy", "true");
      try {
        const payload = await getJSON(borrowerURL, { q: query, filter: borrowerFilter });
        if (sequence !== borrowerSequence) return;
        clearResults(borrowerResults);
        if (!payload.results.length) {
          emptyResult(borrowerResults, "No active student or staff member found.");
          return;
        }
        const exact = payload.results.filter(function (item) { return item.exact; });
        if (autoSelect && (exact.length === 1 || payload.results.length === 1)) {
          const item = exact[0] || payload.results[0];
          selectBorrower(item.kind, item.id);
          return;
        }
        payload.results.forEach(function (item) {
          const button = resultButton(item.kind === "student" ? "ph ph-student" : "ph ph-identification-badge", item.name, item.meta, item.kind === "student" ? "Student" : "Staff");
          button.addEventListener("click", function () { selectBorrower(item.kind, item.id); });
          borrowerResults.appendChild(button);
        });
      } catch (error) {
        if (sequence === borrowerSequence) emptyResult(borrowerResults, "Member lookup is temporarily unavailable.");
      } finally {
        borrowerResults.removeAttribute("aria-busy");
      }
    }

    function selectCopy(item) {
      copy = item;
      copyInput.value = item.id;
      setText(form, "[data-copy-title]", item.title);
      setText(form, "[data-copy-meta]", [item.author, item.isbn, item.available_copies + " available"].filter(Boolean).join(" · "));
      setText(form, "[data-copy-accession]", item.accession);
      setText(form, "[data-copy-shelf]", item.shelf || "Not assigned");
      setText(form, "[data-copy-condition]", item.condition);
      one(form, "[data-selected-copy]").hidden = false;
      bookSearch.hidden = true;
      one(form, "[data-book-step] .lib-search-row").hidden = true;
      clearResults(copyResults);
      setText(form, "[data-summary-borrower]", borrower.name);
      setText(form, "[data-summary-book]", item.title);
      setText(form, "[data-summary-copy]", item.accession);
      one(form, "[data-issue-summary]").hidden = false;
      confirmButton.disabled = !borrower.eligible;
      confirmStep.classList.toggle("is-muted", !borrower.eligible);
      updateSteps();
      if (!confirmButton.disabled) confirmButton.focus();
    }

    async function selectCopyById(id) {
      try {
        const payload = await getJSON(copyURL, { id: id });
        if (payload.results.length) selectCopy(payload.results[0]);
      } catch (error) {
        emptyResult(copyResults, "This copy is no longer available. Scan another copy.");
      }
    }

    async function searchCopies(autoSelect) {
      const query = bookSearch.value.trim();
      if (!query || !borrower || !borrower.eligible) { clearResults(copyResults); return; }
      const sequence = ++copySequence;
      copyResults.setAttribute("aria-busy", "true");
      try {
        const payload = await getJSON(copyURL, { q: query });
        if (sequence !== copySequence) return;
        clearResults(copyResults);
        if (!payload.results.length) {
          emptyResult(copyResults, "No available copy matches this search.");
          return;
        }
        const exact = payload.results.filter(function (item) { return item.exact; });
        if (autoSelect && (exact.length === 1 || payload.results.length === 1)) {
          selectCopy(exact[0] || payload.results[0]);
          return;
        }
        payload.results.forEach(function (item) {
          const meta = [item.author, item.isbn, item.accession + " · " + (item.shelf || "No shelf")].filter(Boolean).join(" · ");
          const button = resultButton("ph ph-book-open", item.title, meta, item.available_copies + " available");
          button.addEventListener("click", function () { selectCopy(item); });
          copyResults.appendChild(button);
        });
      } catch (error) {
        if (sequence === copySequence) emptyResult(copyResults, "Book lookup is temporarily unavailable.");
      } finally {
        copyResults.removeAttribute("aria-busy");
      }
    }

    borrowerSearch.addEventListener("input", debounce(function () { searchBorrowers(false); }, 180));
    borrowerSearch.addEventListener("keydown", function (event) {
      if (event.key === "Enter") { event.preventDefault(); searchBorrowers(true); }
    });
    borrowerSearch.addEventListener("circulation:scan", function () { searchBorrowers(true); });
    bookSearch.addEventListener("input", debounce(function () { searchCopies(false); }, 180));
    bookSearch.addEventListener("keydown", function (event) {
      if (event.key === "Enter") { event.preventDefault(); searchCopies(true); }
    });
    bookSearch.addEventListener("circulation:scan", function () { searchCopies(true); });
    all(form, "[data-borrower-filter]").forEach(function (button) {
      button.addEventListener("click", function () {
        borrowerFilter = button.dataset.borrowerFilter;
        all(form, "[data-borrower-filter]").forEach(function (item) { item.classList.toggle("is-active", item === button); });
        searchBorrowers(false);
      });
    });
    one(form, "[data-change-borrower]").addEventListener("click", function () {
      borrower = null;
      studentInput.value = "";
      staffInput.value = "";
      one(form, "[data-selected-borrower]").hidden = true;
      borrowerSearch.hidden = false;
      borrowerSearch.value = "";
      one(form, "[data-borrower-step] .lib-search-row").hidden = false;
      one(form, ".lib-segmented").hidden = false;
      one(form, ".lib-status-empty").hidden = false;
      one(form, "[data-status-content]").hidden = true;
      bookSearch.disabled = true;
      all(bookStep, "[data-scan-target]").forEach(function (button) { button.disabled = true; });
      bookStep.classList.add("is-muted");
      resetCopy();
      borrowerSearch.focus();
      updateSteps();
    });
    one(form, "[data-change-copy]").addEventListener("click", function () {
      resetCopy();
      bookSearch.hidden = false;
      one(form, "[data-book-step] .lib-search-row").hidden = false;
      bookSearch.focus();
    });
    form.addEventListener("submit", function (event) {
      if (!borrower || !copy || !borrower.eligible) event.preventDefault();
      else confirmButton.disabled = true;
    });

    updateSteps();
    const initialKind = form.dataset.initialBorrowerKind;
    const initialId = form.dataset.initialBorrowerId;
    if (initialKind && initialId) {
      selectBorrower(initialKind, initialId).then(function () {
        if (form.dataset.initialCopyId) selectCopyById(form.dataset.initialCopyId);
      });
    }
  }

  function initReturn(form) {
    const loanURL = form.dataset.loanUrl;
    const search = one(form, "#return-search");
    const results = one(form, "[data-loan-results]");
    const loanInput = one(form, "#id_loan");
    const details = one(form, "[data-return-details]");
    const confirm = one(form, "[data-confirm-return]");
    const condition = one(form, "[data-condition-fields]");
    const damageFields = one(form, "[data-damage-fields]");
    let selectedLoan = null;
    let sequence = 0;

    function toggleDamage() {
      const damaged = one(form, "input[name='condition']:checked").value === "damaged";
      damageFields.hidden = !damaged;
      one(form, "#id_damage_amount").required = damaged;
    }

    function selectLoan(loan) {
      selectedLoan = loan;
      loanInput.value = loan.id;
      search.hidden = true;
      one(form, ".lib-search-row").hidden = true;
      clearResults(results);
      one(form, "[data-return-book]").hidden = false;
      one(form, "[data-return-facts]").hidden = false;
      setText(form, "[data-return-title]", loan.title);
      setText(form, "[data-return-copy]", loan.accession + " · " + loan.barcode + (loan.shelf ? " · Shelf " + loan.shelf : ""));
      setText(form, "[data-return-borrower]", loan.borrower);
      setText(form, "[data-return-borrower-meta]", loan.borrower_meta);
      setText(form, "[data-return-due]", loan.due);
      setText(form, "[data-return-issued]", "Issued " + loan.issued);
      const status = one(form, "[data-return-status]");
      const note = one(form, "[data-return-status-note]");
      status.classList.toggle("is-overdue", loan.overdue_days > 0);
      status.classList.toggle("is-on-time", loan.overdue_days === 0);
      status.textContent = loan.overdue_days ? "⚠ " + loan.overdue_days + " day" + (loan.overdue_days === 1 ? "" : "s") + " overdue" : "✓ On time";
      note.textContent = loan.overdue_days ? "Fine will be recorded when returned" : "No overdue charge";
      setText(form, "[data-return-fine]", money(loan.calculated_fine));
      setText(form, "[data-return-rate]", loan.overdue_days ? money(loan.daily_fine) + " per overdue day" : "No fine due");
      details.classList.remove("is-muted");
      condition.disabled = false;
      confirm.disabled = false;
      one(confirm, "span").textContent = loan.overdue_days ? "Return book & record fine" : "Confirm return";
      confirm.focus();
    }

    async function selectLoanById(id) {
      try {
        const payload = await getJSON(loanURL, { id: id });
        if (payload.results.length) selectLoan(payload.results[0]);
      } catch (error) {
        emptyResult(results, "This active loan could not be loaded.");
      }
    }

    async function findLoans(autoSelect) {
      const query = search.value.trim();
      if (!query) { clearResults(results); return; }
      const current = ++sequence;
      results.setAttribute("aria-busy", "true");
      try {
        const payload = await getJSON(loanURL, { q: query });
        if (current !== sequence) return;
        clearResults(results);
        if (!payload.results.length) {
          emptyResult(results, "No active loan matches this barcode or search.");
          return;
        }
        const exact = payload.results.filter(function (item) { return item.exact; });
        if (autoSelect && (exact.length === 1 || payload.results.length === 1)) {
          selectLoan(exact[0] || payload.results[0]);
          return;
        }
        payload.results.forEach(function (loan) {
          const tail = loan.overdue_days ? loan.overdue_days + "d overdue" : "Due " + loan.due;
          const button = resultButton("ph ph-book-open", loan.title, loan.accession + " · " + loan.borrower, tail);
          button.addEventListener("click", function () { selectLoan(loan); });
          results.appendChild(button);
        });
      } catch (error) {
        if (current === sequence) emptyResult(results, "Loan lookup is temporarily unavailable.");
      } finally {
        results.removeAttribute("aria-busy");
      }
    }

    search.addEventListener("input", debounce(function () { findLoans(false); }, 160));
    search.addEventListener("keydown", function (event) {
      if (event.key === "Enter") { event.preventDefault(); findLoans(true); }
    });
    search.addEventListener("circulation:scan", function () { findLoans(true); });
    one(form, "[data-change-loan]").addEventListener("click", function () {
      selectedLoan = null;
      loanInput.value = "";
      search.hidden = false;
      search.value = "";
      one(form, ".lib-search-row").hidden = false;
      one(form, "[data-return-book]").hidden = true;
      one(form, "[data-return-facts]").hidden = true;
      details.classList.add("is-muted");
      condition.disabled = true;
      confirm.disabled = true;
      search.focus();
    });
    all(form, "input[name='condition']").forEach(function (radio) { radio.addEventListener("change", toggleDamage); });
    form.addEventListener("submit", function (event) {
      if (!selectedLoan) event.preventDefault();
      else confirm.disabled = true;
    });
    toggleDamage();
    if (form.dataset.initialLoanId) selectLoanById(form.dataset.initialLoanId);
  }

  function initScanner() {
    const overlay = document.querySelector("[data-scanner]");
    if (!overlay) return;
    const video = one(overlay, "video");
    const status = one(overlay, "[data-scanner-status]");
    let stream = null;
    let scanning = false;
    let target = null;
    let detector = null;

    async function stop() {
      scanning = false;
      if (stream) stream.getTracks().forEach(function (track) { track.stop(); });
      stream = null;
      video.srcObject = null;
      overlay.hidden = true;
    }

    async function detectLoop() {
      if (!scanning || !detector) return;
      try {
        const codes = await detector.detect(video);
        if (codes.length) {
          const rawValue = codes[0].rawValue || "";
          await stop();
          target.value = rawValue;
          target.dispatchEvent(new CustomEvent("circulation:scan", { bubbles: true }));
          return;
        }
      } catch (error) {
        status.textContent = "Keep the code steady inside the frame.";
      }
      window.setTimeout(detectLoop, 220);
    }

    async function openScanner(input) {
      target = input;
      overlay.hidden = false;
      status.textContent = "Starting camera…";
      if (!("BarcodeDetector" in window) || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        status.textContent = "Camera scanning is not supported in this browser. Use a USB scanner or type the code.";
        return;
      }
      try {
        const desiredFormats = ["qr_code", "code_128", "code_39", "ean_13", "ean_8", "upc_a", "upc_e"];
        const supportedFormats = await window.BarcodeDetector.getSupportedFormats();
        detector = new window.BarcodeDetector({ formats: desiredFormats.filter(function (format) { return supportedFormats.includes(format); }) });
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false });
        video.srcObject = stream;
        await video.play();
        scanning = true;
        status.textContent = "Scanning…";
        detectLoop();
      } catch (error) {
        status.textContent = "Camera access was unavailable. Check browser permission or use a USB scanner.";
      }
    }

    all(document, "[data-scan-target]").forEach(function (button) {
      button.addEventListener("click", function () {
        const input = document.getElementById(button.dataset.scanTarget);
        if (input && !button.disabled) openScanner(input);
      });
    });
    one(overlay, "[data-scanner-close]").addEventListener("click", stop);
    overlay.addEventListener("click", function (event) { if (event.target === overlay) stop(); });
    document.addEventListener("keydown", function (event) { if (event.key === "Escape" && !overlay.hidden) stop(); });
  }

  const issueForm = document.querySelector("[data-circulation-issue]");
  const returnForm = document.querySelector("[data-circulation-return]");
  if (issueForm) initIssue(issueForm);
  if (returnForm) initReturn(returnForm);
  if (issueForm || returnForm) initScanner();
})();
