(function () {
  "use strict";

  const API_BASE = (window.CAMPUSFIND_API_BASE || "http://127.0.0.1:8000/api")
    .replace(/\/$/, "");
  const ACCESS_KEY = "campusFindAccess";
  const REFRESH_KEY = "campusFindRefresh";
  const ROLE_KEY = "campusFindRole";
  let currentUser = null;

  class ApiError extends Error {
    constructor(message, statusCode, data) {
      super(message);
      this.status = statusCode;
      this.data = data;
    }
  }

  function getElement(id) {
    return document.getElementById(id);
  }

  function setMessage(id, message, isError) {
    const element = getElement(id);
    if (!element) return;
    element.textContent = message || "";
    element.classList.toggle("error-message", Boolean(isError && message));
    element.classList.toggle("success-message", Boolean(!isError && message));
  }

  function clearSession(preserveRole) {
    sessionStorage.removeItem(ACCESS_KEY);
    sessionStorage.removeItem(REFRESH_KEY);
    if (!preserveRole) sessionStorage.removeItem(ROLE_KEY);
    currentUser = null;
  }

  function responseMessage(payload, statusCode) {
    if (payload && typeof payload.detail === "string") return payload.detail;
    if (payload && typeof payload === "object") {
      const messages = Object.values(payload)
        .flat(Infinity)
        .filter(value => typeof value === "string");
      if (messages.length) return messages.join(" ");
    }
    return `Request failed (${statusCode}). Please try again.`;
  }

  async function readResponse(response) {
    const text = await response.text();
    if (!text) return null;
    try {
      return JSON.parse(text);
    } catch {
      return { detail: "The server returned an unexpected response." };
    }
  }

  async function refreshAccessToken() {
    const refresh = sessionStorage.getItem(REFRESH_KEY);
    if (!refresh) return false;
    try {
      const response = await fetch(`${API_BASE}/auth/token/refresh/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ refresh })
      });
      const payload = await readResponse(response);
      if (!response.ok || !payload || !payload.access) return false;
      sessionStorage.setItem(ACCESS_KEY, payload.access);
      if (payload.refresh) sessionStorage.setItem(REFRESH_KEY, payload.refresh);
      return true;
    } catch {
      return false;
    }
  }

  async function apiRequest(path, options) {
    const settings = Object.assign({
      method: "GET",
      body: undefined,
      authenticated: true,
      refreshOnUnauthorized: true,
      redirectOnUnauthorized: true
    }, options || {});

    const send = async function () {
      const headers = { Accept: "application/json" };
      let body = settings.body;
      if (body !== undefined && !(body instanceof FormData)) {
        headers["Content-Type"] = "application/json";
        body = JSON.stringify(body);
      }
      if (settings.authenticated) {
        const access = sessionStorage.getItem(ACCESS_KEY);
        if (access) headers.Authorization = `Bearer ${access}`;
      }
      return fetch(`${API_BASE}${path}`, {
        method: settings.method,
        headers,
        body
      });
    };

    let response;
    try {
      response = await send();
      if (response.status === 401 && settings.refreshOnUnauthorized) {
        if (await refreshAccessToken()) response = await send();
      }
    } catch {
      throw new ApiError("Could not reach CampusFind. Check that the backend is running.", 0);
    }

    const payload = await readResponse(response);
    if (response.status === 401 && settings.redirectOnUnauthorized) {
      clearSession(true);
      window.location.assign("login.html?session=expired");
    }
    if (!response.ok) {
      throw new ApiError(responseMessage(payload, response.status), response.status, payload);
    }
    return payload;
  }

  function makeElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function addButton(parent, text, className, action) {
    const button = makeElement("button", className || "outline-light-btn", text);
    button.type = "button";
    button.addEventListener("click", action);
    parent.append(button);
    return button;
  }

  function formatType(type) {
    return type === "FOUND" ? "Found" : "Lost";
  }

  function formatStatus(status) {
    return String(status || "OPEN").toLowerCase().replaceAll("_", " ");
  }

  function mediaUrl(url) {
    if (!url) return "";
    if (/^https?:\/\//i.test(url)) return url;
    return `${new URL(API_BASE).origin}${url.startsWith("/") ? "" : "/"}${url}`;
  }

  function setBusy(button, busy, busyText) {
    if (!button) return;
    if (busy) {
      button.dataset.originalText = button.textContent;
      button.disabled = true;
      button.textContent = busyText || "Working…";
    } else {
      button.disabled = false;
      if (button.dataset.originalText) button.textContent = button.dataset.originalText;
    }
  }

  function setUserBadges(user) {
    document.querySelectorAll("#userBadge").forEach(function (badge) {
      badge.textContent = `${user.name} · ${user.role.toLowerCase().replaceAll("_", " ")}`;
    });
  }

  function logout() {
    clearSession();
    window.location.assign("index.html");
  }

  async function requireUser() {
    if (!sessionStorage.getItem(ACCESS_KEY) && !sessionStorage.getItem(REFRESH_KEY)) {
      window.location.replace("login.html");
      return null;
    }
    try {
      currentUser = await apiRequest("/auth/me/");
      setUserBadges(currentUser);
      return currentUser;
    } catch {
      return null;
    }
  }

  function initHome() {
    const roleButtons = Array.from(document.querySelectorAll("[data-role]"));
    const savedRole = sessionStorage.getItem(ROLE_KEY);
    let selectedRole = savedRole || "";
    roleButtons.forEach(function (button) {
      if (button.dataset.role === selectedRole) button.classList.add("selected");
      button.addEventListener("click", function () {
        selectedRole = button.dataset.role;
        roleButtons.forEach(item => item.classList.toggle("selected", item === button));
        setMessage("roleMessage", `Selected role: ${formatRole(selectedRole)}`, false);
      });
    });
    const continueButton = getElement("roleContinue");
    continueButton.addEventListener("click", function () {
      if (!selectedRole) {
        setMessage("roleMessage", "Please select your campus role first.", true);
        return;
      }
      sessionStorage.setItem(ROLE_KEY, selectedRole);
      window.location.assign("login.html");
    });

    if (sessionStorage.getItem(ACCESS_KEY) || sessionStorage.getItem(REFRESH_KEY)) {
      apiRequest("/auth/me/", { redirectOnUnauthorized: false })
        .then(() => window.location.replace("dashboard.html"))
        .catch(() => clearSession(true));
    }
  }

  function formatRole(role) {
    return String(role || "").toLowerCase().replaceAll("_", " ");
  }

  function initAuth() {
    const role = sessionStorage.getItem(ROLE_KEY);
    if (!role) {
      window.location.replace("index.html");
      return;
    }
    getElement("loginTitle").textContent = `${formatRole(role)} account`;
    getElement("registerRole").textContent = formatRole(role);

    const loginForm = getElement("loginForm");
    const registerForm = getElement("registerForm");
    const loginModeButton = getElement("loginModeButton");
    const registerModeButton = getElement("registerModeButton");

    function showMode(mode) {
      const registering = mode === "register";
      loginForm.hidden = registering;
      registerForm.hidden = !registering;
      getElement("authSubtitle").textContent = registering
        ? "Create your account with your campus email."
        : "Sign in to your campus account.";
      loginModeButton.classList.toggle("active", !registering);
      registerModeButton.classList.toggle("active", registering);
      loginModeButton.setAttribute("aria-selected", String(!registering));
      registerModeButton.setAttribute("aria-selected", String(registering));
    }

    loginModeButton.addEventListener("click", () => showMode("login"));
    registerModeButton.addEventListener("click", () => showMode("register"));
    if (new URLSearchParams(window.location.search).get("session") === "expired") {
      setMessage("loginMessage", "Your session expired. Please sign in again.", true);
    }

    loginForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      setMessage("loginMessage", "", false);
      if (!loginForm.reportValidity()) return;
      const button = loginForm.querySelector("button[type='submit']");
      setBusy(button, true, "Signing in…");
      try {
        const result = await apiRequest("/auth/login/", {
          method: "POST",
          authenticated: false,
          refreshOnUnauthorized: false,
          redirectOnUnauthorized: false,
          body: {
            email: getElement("loginEmail").value.trim(),
            password: getElement("loginPassword").value
          }
        });
        sessionStorage.setItem(ACCESS_KEY, result.access);
        sessionStorage.setItem(REFRESH_KEY, result.refresh);
        window.location.assign("dashboard.html");
      } catch (error) {
        setMessage("loginMessage", error.message, true);
      } finally {
        setBusy(button, false);
      }
    });

    registerForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      setMessage("registerMessage", "", false);
      if (!registerForm.reportValidity()) return;
      const password = getElement("registerPassword").value;
      if (password !== getElement("registerPasswordConfirm").value) {
        setMessage("registerMessage", "Passwords do not match.", true);
        return;
      }
      const button = registerForm.querySelector("button[type='submit']");
      setBusy(button, true, "Creating account…");
      try {
        const email = getElement("registerEmail").value.trim();
        await apiRequest("/auth/register/", {
          method: "POST",
          authenticated: false,
          refreshOnUnauthorized: false,
          redirectOnUnauthorized: false,
          body: {
            name: getElement("registerName").value.trim(),
            email,
            password,
            role
          }
        });
        const tokens = await apiRequest("/auth/login/", {
          method: "POST",
          authenticated: false,
          refreshOnUnauthorized: false,
          redirectOnUnauthorized: false,
          body: { email, password }
        });
        sessionStorage.setItem(ACCESS_KEY, tokens.access);
        sessionStorage.setItem(REFRESH_KEY, tokens.refresh);
        window.location.assign("dashboard.html");
      } catch (error) {
        setMessage("registerMessage", error.message, true);
      } finally {
        setBusy(button, false);
      }
    });
  }

  function itemCard(item) {
    const card = makeElement("article", "report-card");
    if (item.image) {
      const image = makeElement("img", "report-image");
      image.src = mediaUrl(item.image);
      image.alt = `Photo of ${item.title}`;
      image.loading = "lazy";
      card.append(image);
    }
    const badge = makeElement("span", `report-type ${item.type === "LOST" ? "lost" : ""}`, `${formatType(item.type)} item`);
    const title = makeElement("h3", "", item.title);
    const category = makeElement("p", "", `Category: ${item.category}`);
    const location = makeElement("p", "", `Location: ${item.location}`);
    const date = makeElement("p", "", `Date: ${item.date}`);
    const status = makeElement("span", "status-pill", formatStatus(item.status));
    const link = makeElement("a", "text-link", "View details →");
    link.href = `item.html?item=${encodeURIComponent(item.id)}`;
    card.append(badge, title, category, location, date, status, link);
    if (item.description) card.append(makeElement("p", "report-description", item.description));
    return card;
  }

  async function initDashboard() {
    getElement("welcomeTitle").textContent = `Welcome, ${currentUser.name}!`;
    const list = getElement("reportList");
    let searchTimer;

    async function loadReports() {
      list.replaceChildren();
      getElement("reportError").textContent = "";
      getElement("emptyMessage").hidden = true;
      getElement("reportLoading").hidden = false;
      const params = new URLSearchParams();
      const filters = [
        ["name", getElement("dashboardSearch").value.trim()],
        ["type", getElement("typeFilter").value],
        ["category", getElement("categoryFilter").value],
        ["location", getElement("locationFilter").value.trim()],
        ["date", getElement("dateFilter").value]
      ];
      filters.forEach(([key, value]) => { if (value) params.set(key, value); });
      try {
        const reports = await apiRequest(`/items/${params.size ? `?${params}` : ""}`);
        const items = Array.isArray(reports) ? reports : reports.results || [];
        getElement("totalCount").textContent = items.length;
        getElement("lostCount").textContent = items.filter(item => item.type === "LOST").length;
        getElement("foundCount").textContent = items.filter(item => item.type === "FOUND").length;
        items.forEach(item => list.append(itemCard(item)));
        getElement("emptyMessage").hidden = items.length > 0;
        if (items.length === 0) {
          getElement("emptyMessage").textContent = params.size
            ? "No reports match these filters."
            : "No reports yet. Be the first to add one!";
        }
      } catch (error) {
        setMessage("reportError", error.message, true);
      } finally {
        getElement("reportLoading").hidden = true;
      }
    }

    function scheduleReportLoad() {
      window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(loadReports, 250);
    }

    ["dashboardSearch", "locationFilter"].forEach(id =>
      getElement(id).addEventListener("input", scheduleReportLoad));
    ["typeFilter", "categoryFilter", "dateFilter"].forEach(id =>
      getElement(id).addEventListener("change", loadReports));
    getElement("clearFilters").addEventListener("click", function () {
      ["dashboardSearch", "typeFilter", "categoryFilter", "locationFilter", "dateFilter"]
        .forEach(id => { getElement(id).value = ""; });
      loadReports();
    });
    getElement("logoutBtn").addEventListener("click", logout);
    getElement("notificationsButton").addEventListener("click", toggleNotifications);
    getElement("markAllReadButton").addEventListener("click", markAllNotificationsRead);
    getElement("refreshClaimsButton").addEventListener("click", loadClaims);

    await Promise.allSettled([loadReports(), refreshUnreadCount(), loadClaims()]);
  }

  async function refreshUnreadCount() {
    try {
      const result = await apiRequest("/notifications/unread-count/");
      getElement("unreadCount").textContent = result.unread_count;
    } catch (error) {
      setMessage("notificationError", error.message, true);
    }
  }

  async function toggleNotifications() {
    const panel = getElement("notificationPanel");
    const button = getElement("notificationsButton");
    panel.hidden = !panel.hidden;
    button.setAttribute("aria-expanded", String(!panel.hidden));
    if (!panel.hidden) await loadNotifications();
  }

  async function loadNotifications() {
    const list = getElement("notificationList");
    list.replaceChildren();
    getElement("notificationEmpty").hidden = true;
    setMessage("notificationError", "", false);
    try {
      const response = await apiRequest("/notifications/?page_size=100");
      const notifications = response.results || [];
      notifications.forEach(notification => {
        const row = makeElement("article", `activity-row ${notification.is_read ? "read" : "unread"}`);
        const copy = makeElement("div", "activity-copy");
        copy.append(
          makeElement("strong", "", notification.notification_type.replaceAll("_", " ").toLowerCase()),
          makeElement("p", "", notification.message),
          makeElement("time", "small-note", new Date(notification.created_at).toLocaleString())
        );
        row.append(copy);
        if (notification.related_item) {
          const open = makeElement("a", "text-link", "Open item →");
          const query = new URLSearchParams({ item: notification.related_item.id });
          if (notification.related_claim_id) query.set("claim", notification.related_claim_id);
          open.href = `item.html?${query}`;
          row.append(open);
        }
        if (!notification.is_read) {
          addButton(row, "Mark read", "text-button", async function () {
            try {
              await apiRequest(`/notifications/${notification.id}/read/`, { method: "PATCH", body: {} });
              await Promise.all([loadNotifications(), refreshUnreadCount()]);
            } catch (error) {
              setMessage("notificationError", error.message, true);
            }
          });
        }
        list.append(row);
      });
      getElement("notificationEmpty").hidden = notifications.length > 0;
    } catch (error) {
      setMessage("notificationError", error.message, true);
    }
  }

  async function markAllNotificationsRead() {
    const button = getElement("markAllReadButton");
    setBusy(button, true, "Updating…");
    try {
      await apiRequest("/notifications/read-all/", { method: "POST", body: {} });
      await Promise.all([loadNotifications(), refreshUnreadCount()]);
    } catch (error) {
      setMessage("notificationError", error.message, true);
    } finally {
      setBusy(button, false);
    }
  }

  async function loadClaims() {
    const list = getElement("claimList");
    if (!list) return;
    list.replaceChildren();
    getElement("claimsEmpty").hidden = true;
    setMessage("claimsError", "", false);
    try {
      const claims = await apiRequest("/recovery/claims/");
      claims.forEach(function (claim) {
        const row = makeElement("article", "activity-row");
        const copy = makeElement("div", "activity-copy");
        const role = claim.claimant.id === currentUser.id ? "Your claim" : "Claim on your report";
        copy.append(
          makeElement("strong", "", `${role} · ${formatStatus(claim.status)}`),
          makeElement("p", "", claim.item.title),
          makeElement("p", "", claim.reason)
        );
        const link = makeElement("a", "text-link", "Open claim →");
        link.href = `item.html?item=${claim.item.id}&claim=${claim.id}`;
        row.append(copy, link);
        list.append(row);
      });
      getElement("claimsEmpty").hidden = claims.length > 0;
    } catch (error) {
      setMessage("claimsError", error.message, true);
    }
  }

  function initChoice() {
    document.querySelectorAll("[data-type]").forEach(function (button) {
      button.addEventListener("click", function () {
        sessionStorage.setItem("campusFindType", button.dataset.type);
        window.location.assign("details.html");
      });
    });
  }

  async function initDetails() {
    const form = getElement("detailsForm");
    const params = new URLSearchParams(window.location.search);
    const itemId = params.get("id");
    const typeSelect = getElement("itemType");
    const fileInput = getElement("itemPhoto");
    const preview = getElement("photoPreview");
    const submitButton = getElement("submitReportButton");
    let existingImage = "";

    if (itemId) {
      getElement("detailsTitle").textContent = "Edit item report";
      getElement("detailsSubtitle").textContent = "Update your report details.";
      submitButton.textContent = "Save changes →";
      try {
        const item = await apiRequest(`/items/${encodeURIComponent(itemId)}/`);
        if (item.reporter.id !== currentUser.id && !currentUser.is_staff) {
          setMessage("detailsMessage", "Only the report owner can edit this item.", true);
          window.setTimeout(() => window.location.replace(`item.html?item=${item.id}`), 900);
          return;
        }
        typeSelect.value = item.type;
        getElement("itemName").value = item.title;
        getElement("category").value = item.category;
        getElement("location").value = item.location;
        getElement("itemDate").value = item.date;
        getElement("description").value = item.description || "";
        existingImage = item.image || "";
        if (existingImage) {
          preview.src = mediaUrl(existingImage);
          preview.hidden = false;
        }
      } catch (error) {
        setMessage("detailsMessage", error.message, true);
        return;
      }
    } else {
      const selectedType = sessionStorage.getItem("campusFindType");
      if (!selectedType) {
        window.location.replace("choice.html");
        return;
      }
      typeSelect.value = selectedType;
    }

    fileInput.addEventListener("change", function () {
      const file = fileInput.files[0];
      if (!file) {
        preview.hidden = !existingImage;
        if (existingImage) preview.src = mediaUrl(existingImage);
        return;
      }
      if (!file.type.startsWith("image/")) {
        fileInput.value = "";
        setMessage("detailsMessage", "Choose a valid image file.", true);
        return;
      }
      if (file.size > 5 * 1024 * 1024) {
        fileInput.value = "";
        setMessage("detailsMessage", "Images must be 5 MB or smaller.", true);
        return;
      }
      setMessage("detailsMessage", "", false);
      const reader = new FileReader();
      reader.onload = () => { preview.src = reader.result; preview.hidden = false; };
      reader.readAsDataURL(file);
    });

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      setMessage("detailsMessage", "", false);
      if (!form.reportValidity()) return;
      const body = new FormData();
      body.append("title", getElement("itemName").value.trim());
      body.append("description", getElement("description").value.trim());
      body.append("category", getElement("category").value);
      body.append("type", typeSelect.value);
      body.append("date", getElement("itemDate").value);
      body.append("location", getElement("location").value.trim());
      if (fileInput.files[0]) body.append("image", fileInput.files[0]);

      setBusy(submitButton, true, "Saving report…");
      try {
        const saved = await apiRequest(itemId ? `/items/${itemId}/` : "/items/", {
          method: itemId ? "PUT" : "POST",
          body
        });
        window.location.assign(`item.html?item=${saved.id}`);
      } catch (error) {
        setMessage("detailsMessage", error.message, true);
      } finally {
        setBusy(submitButton, false);
      }
    });
  }

  function renderMatch(match) {
    const item = match.item;
    const card = itemCard(item);
    const score = makeElement("strong", "similarity-score", `${match.similarity_score.toFixed(1)}% similarity`);
    card.insertBefore(score, card.firstChild);
    const details = match.matching_details || {};
    const explanation = makeElement("ul", "feature-list");
    explanation.append(makeElement("li", "", `Text: ${Number(details.text_similarity || 0) * 100}%`));
    if (details.category_match !== null) {
      explanation.append(makeElement("li", "", `Category: ${details.category_match ? "same" : "different"}`));
    }
    explanation.append(makeElement("li", "", `Colour overlap: ${(details.colour_matches || []).join(", ") || "not detected"}`));
    if (details.location_similarity !== null) {
      explanation.append(makeElement("li", "", `Location overlap: ${(details.location_similarity * 100).toFixed(0)}%`));
    }
    if (details.date_difference_days !== null) {
      explanation.append(makeElement("li", "", `Dates differ by ${details.date_difference_days} day(s)`));
    }
    card.append(explanation);
    return card;
  }

  async function loadMatches(itemId) {
    const button = getElement("loadMatchesButton");
    const list = getElement("matchesList");
    list.replaceChildren();
    getElement("matchesEmpty").hidden = true;
    setMessage("matchesError", "", false);
    setBusy(button, true, "Finding…");
    try {
      const response = await apiRequest(`/matching/items/${itemId}/suggestions/?limit=10`);
      response.matches.forEach(match => list.append(renderMatch(match)));
      getElement("matchesEmpty").hidden = response.matches.length > 0;
    } catch (error) {
      setMessage("matchesError", error.message, true);
    } finally {
      setBusy(button, false);
    }
  }

  function renderClaim(claim, item, reload) {
    const row = makeElement("article", "activity-row claim-row");
    const copy = makeElement("div", "activity-copy");
    const heading = makeElement("strong", "", `${claim.claimant.name} · ${formatStatus(claim.status)}`);
    copy.append(heading, makeElement("p", "", claim.reason));
    if (claim.rejection_note) copy.append(makeElement("p", "small-note", `Note: ${claim.rejection_note}`));
    copy.append(makeElement("p", "small-note", `Claimed ${new Date(claim.created_at).toLocaleString()}`));

    const isClaimant = claim.claimant.id === currentUser.id;
    const isReporter = item.reporter.id === currentUser.id;
    const isStaff = Boolean(currentUser.is_staff);
    const actions = makeElement("div", "action-row compact-actions");
    if (claim.status === "PENDING" && (isReporter || isStaff)) {
      addButton(actions, "Approve", "small-action-btn", () => updateClaim(claim.id, "approve", {}, reload));
      addButton(actions, "Reject", "small-action-btn secondary-action", function () {
        const note = window.prompt("Optional reason for rejection:") || "";
        updateClaim(claim.id, "reject", { note }, reload);
      });
    }
    if (claim.status === "PENDING" && isClaimant) {
      addButton(actions, "Cancel claim", "small-action-btn secondary-action", () => updateClaim(claim.id, "cancel", {}, reload));
    }
    if (claim.status === "APPROVED" && (isClaimant || isReporter)) {
      const confirmed = isClaimant ? claim.claimant_confirmed_at : claim.reporter_confirmed_at;
      const otherConfirmed = isClaimant ? claim.reporter_confirmed_at : claim.claimant_confirmed_at;
      copy.append(makeElement("p", "small-note", `Your confirmation: ${confirmed ? "complete" : "pending"}; other party: ${otherConfirmed ? "complete" : "pending"}.`));
      if (!confirmed) {
        addButton(actions, "Confirm handover", "small-action-btn", () => updateClaim(claim.id, "confirm-recovery", {}, reload));
      }
    }
    row.append(copy);
    if (actions.childElementCount) row.append(actions);
    return row;
  }

  async function updateClaim(claimId, action, body, reload) {
    setMessage("claimActionMessage", "", false);
    try {
      await apiRequest(`/recovery/claims/${claimId}/${action}/`, { method: "POST", body });
      setMessage("claimActionMessage", "Claim updated.", false);
      await reload();
    } catch (error) {
      setMessage("claimActionMessage", error.message, true);
    }
  }

  async function initItemPage() {
    const itemId = new URLSearchParams(window.location.search).get("item");
    const targetClaimId = new URLSearchParams(window.location.search).get("claim");
    if (!itemId) {
      getElement("itemLoading").hidden = true;
      setMessage("itemError", "No item was selected.", true);
      return;
    }

    async function loadItem() {
      getElement("itemLoading").hidden = false;
      getElement("itemContent").hidden = true;
      try {
        const item = await apiRequest(`/items/${encodeURIComponent(itemId)}/`);
        getElement("itemLoading").hidden = true;
        getElement("itemContent").hidden = false;
        getElement("itemDetailBody").replaceChildren();
        const body = getElement("itemDetailBody");
        const heading = makeElement("div", "item-detail-heading");
        heading.append(
          makeElement("span", `report-type ${item.type === "LOST" ? "lost" : ""}`, `${formatType(item.type)} item`),
          makeElement("span", "status-pill", formatStatus(item.status))
        );
        body.append(heading, makeElement("h1", "", item.title));
        if (item.image) {
          const image = makeElement("img", "detail-image");
          image.src = mediaUrl(item.image);
          image.alt = `Photo of ${item.title}`;
          body.append(image);
        }
        const info = makeElement("dl", "detail-facts");
        [["Category", item.category], ["Location", item.location], ["Date", item.date], ["Reported by", item.reporter.name], ["Status", formatStatus(item.status)]]
          .forEach(([term, value]) => {
            info.append(makeElement("dt", "", term), makeElement("dd", "", value));
          });
        body.append(info);
        if (item.description) body.append(makeElement("p", "item-long-description", item.description));

        const actions = getElement("itemActions");
        actions.replaceChildren();
        const isOwner = item.reporter.id === currentUser.id;
        const canManage = isOwner || currentUser.is_staff;
        if (canManage) {
          const editLink = makeElement("a", "primary-btn", "Edit report");
          editLink.href = `details.html?id=${item.id}`;
          actions.append(editLink);
          addButton(actions, "Delete report", "danger-btn", async function () {
            if (!window.confirm("Delete this item report?")) return;
            try {
              await apiRequest(`/items/${item.id}/`, { method: "DELETE" });
              window.location.assign("dashboard.html");
            } catch (error) {
              setMessage("itemError", error.message, true);
            }
          });
          getElement("matchesSection").hidden = item.status !== "OPEN";
          getElement("loadMatchesButton").onclick = () => loadMatches(item.id);
        } else {
          getElement("matchesSection").hidden = true;
        }

        getElement("claimSection").hidden = !(
          item.type === "FOUND" && item.status === "OPEN" && !isOwner
        );
        getElement("claimsSection").hidden = item.type !== "FOUND";
        getElement("itemRecoveryStatus").textContent = formatStatus(item.status);
        getElement("claimForm").onsubmit = async function (event) {
          event.preventDefault();
          const form = event.currentTarget;
          if (!form.reportValidity()) return;
          const button = getElement("submitClaimButton");
          setBusy(button, true, "Submitting…");
          try {
            await apiRequest("/recovery/claims/", {
              method: "POST",
              body: { item_id: item.id, reason: getElement("claimReason").value.trim() }
            });
            getElement("claimReason").value = "";
            setMessage("claimActionMessage", "Claim submitted to the report owner.", false);
            await reloadClaims();
          } catch (error) {
            setMessage("claimActionMessage", error.message, true);
          } finally {
            setBusy(button, false);
          }
        };
        if (item.type === "FOUND") await reloadClaims(item);
        return item;
      } catch (error) {
        getElement("itemLoading").hidden = true;
        setMessage("itemError", error.message, true);
        return null;
      }
    }

    async function reloadClaims(itemOverride) {
      const item = itemOverride || await apiRequest(`/items/${encodeURIComponent(itemId)}/`);
      const list = getElement("itemClaimsList");
      list.replaceChildren();
      getElement("itemClaimsEmpty").hidden = true;
      try {
        const claims = await apiRequest("/recovery/claims/");
        const relevant = claims.filter(claim => claim.item.id === item.id);
        relevant.forEach(claim => {
          const row = renderClaim(claim, item, () => loadItem());
          if (String(claim.id) === targetClaimId) row.classList.add("highlight-row");
          list.append(row);
        });
        getElement("itemClaimsEmpty").hidden = relevant.length > 0;
        if (targetClaimId) {
          const selected = list.querySelector(".highlight-row");
          if (selected) selected.scrollIntoView({ block: "center", behavior: "smooth" });
        }
      } catch (error) {
        setMessage("claimActionMessage", error.message, true);
      }
    }

    await loadItem();
  }

  async function boot() {
    document.querySelectorAll(".logout-button").forEach(button => button.addEventListener("click", logout));
    const page = document.body.dataset.page;
    if (page === "home") return initHome();
    if (page === "auth") return initAuth();
    document.body.classList.add("auth-pending");
    const user = await requireUser();
    document.body.classList.remove("auth-pending");
    if (!user) return;
    if (page === "dashboard") return initDashboard();
    if (page === "choice") return initChoice();
    if (page === "details") return initDetails();
    if (page === "item") return initItemPage();
  }

  document.addEventListener("DOMContentLoaded", boot);
})();