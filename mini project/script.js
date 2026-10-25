
const STORAGE_KEY = "campusFindReports";

function getReports() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
  } catch {
    return [];
  }
}

function saveReports(reports) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(reports));
}

function getRole() {
  return localStorage.getItem("campusFindRole") || "";
}

function requireLogin() {
  if (!getRole()) {
    window.location.href = "index.html";
    return false;
  }
  return true;
}

// PAGE 1: Choose role
const roleButtons = document.querySelectorAll("[data-role]");
const roleContinue = document.getElementById("roleContinue");
let selectedRole = "";

roleButtons.forEach(function (button) {
  button.addEventListener("click", function () {
    selectedRole = button.dataset.role;

    roleButtons.forEach(function (item) {
      item.classList.remove("selected");
    });

    button.classList.add("selected");

    const message = document.getElementById("roleMessage");
    if (message) {
      message.textContent = "Selected role: " + selectedRole;
    }
  });
});

if (roleContinue) {
  roleContinue.addEventListener("click", function () {
    if (!selectedRole) {
      document.getElementById("roleMessage").textContent =
        "Please select your role first.";
      return;
    }

    localStorage.setItem("campusFindRole", selectedRole);
    window.location.href = "login.html";
  });
}

// PAGE 2: Demo login
const loginTitle = document.getElementById("loginTitle");
const loginForm = document.getElementById("loginForm");

if (loginTitle) {
  const role = getRole();

  if (!role) {
    window.location.href = "index.html";
  } else {
    loginTitle.textContent = role + " Login";
  }
}

if (loginForm) {
  loginForm.addEventListener("submit", function (event) {
    event.preventDefault();

    const name = document.getElementById("fullName").value.trim();
    const campusId = document.getElementById("campusId").value.trim();
    const password = document.getElementById("password").value;

    if (!getRole()) {
      window.location.href = "index.html";
      return;
    }

    if (!name || !campusId || !password) {
      document.getElementById("loginMessage").textContent =
        "Please fill in all fields.";
      return;
    }

    // Demo only: this does not verify real credentials.
    localStorage.setItem("campusFindName", name);
    window.location.href = "dashboard.html";
  });
}

// PAGE 3: Dashboard
const reportList = document.getElementById("reportList");

if (reportList) {
  if (!requireLogin()) {
    // Redirect to the role selection page.
  } else {
    const role = getRole();
    const name = localStorage.getItem("campusFindName") || "Campus Member";

    document.getElementById("welcomeTitle").textContent =
      "Welcome, " + name + "!";
    document.getElementById("userBadge").textContent = role;

    function renderReports() {
      const reports = getReports();
      const query = document.getElementById("dashboardSearch")
        .value.toLowerCase().trim();

      const filteredReports = reports.filter(function (report) {
        const searchableText = [
          report.name,
          report.category,
          report.location,
          report.description,
          report.type
        ].join(" ").toLowerCase();

        return searchableText.includes(query);
      });

      document.getElementById("totalCount").textContent = reports.length;
      document.getElementById("lostCount").textContent =
        reports.filter(item => item.type === "Lost").length;
      document.getElementById("foundCount").textContent =
        reports.filter(item => item.type === "Found").length;

      reportList.replaceChildren();

      const emptyMessage = document.getElementById("emptyMessage");

      if (filteredReports.length === 0) {
        emptyMessage.hidden = false;
        emptyMessage.textContent = reports.length === 0
          ? "No reports yet. Be the first to add one!"
          : "No reports match your search.";
        return;
      }

      emptyMessage.hidden = true;

      filteredReports.slice().reverse().forEach(function (report) {
        const card = document.createElement("article");
        card.className = "report-card";

        const badge = document.createElement("span");
        badge.className = "report-type " +
          (report.type === "Lost" ? "lost" : "");
        badge.textContent = report.type + " Item";

        const title = document.createElement("h3");
        title.textContent = report.name;

        const category = document.createElement("p");
        category.textContent = "Category: " + report.category;

        const location = document.createElement("p");
        location.textContent = "Location: " + report.location;

        const date = document.createElement("p");
        date.textContent = "Date: " + report.date;

        card.append(badge, title, category, location, date);

        if (report.description) {
          const description = document.createElement("p");
          description.textContent = report.description;
          card.append(description);
        }

        reportList.append(card);
      });
    }

    renderReports();

    document.getElementById("dashboardSearch")
      .addEventListener("input", renderReports);

    document.getElementById("logoutBtn").addEventListener("click", function () {
      localStorage.removeItem("campusFindRole");
      localStorage.removeItem("campusFindName");
      window.location.href = "index.html";
    });
  }
}

// PAGE 4: Choose Lost or Found
const choiceButtons = document.querySelectorAll("[data-type]");

if (choiceButtons.length > 0 && !requireLogin()) {
  // Login is required to access this page.
}

choiceButtons.forEach(function (button) {
  button.addEventListener("click", function () {
    localStorage.setItem("campusFindType", button.dataset.type);
    window.location.href = "details.html";
  });
});

// PAGE 5: Item details
const detailsForm = document.getElementById("detailsForm");

if (detailsForm && !requireLogin()) {
  // Login is required to access this page.
}

const detailsTitle = document.getElementById("detailsTitle");
const detailsSubtitle = document.getElementById("detailsSubtitle");
const itemType = localStorage.getItem("campusFindType") || "Lost";

if (detailsTitle) {
  detailsTitle.textContent = itemType === "Lost"
    ? "Report a Lost Item"
    : "Report a Found Item";

  detailsSubtitle.textContent = itemType === "Lost"
    ? "Tell us what you lost and where you last saw it."
    : "Share details about the item you found to help its owner.";
}

const itemPhoto = document.getElementById("itemPhoto");
const photoPreview = document.getElementById("photoPreview");

if (itemPhoto && photoPreview) {
  itemPhoto.addEventListener("change", function () {
    const file = itemPhoto.files[0];

    if (!file) {
      photoPreview.hidden = true;
      photoPreview.removeAttribute("src");
      return;
    }

    if (!file.type.startsWith("image/")) {
      alert("Please select an image file.");
      itemPhoto.value = "";
      photoPreview.hidden = true;
      return;
    }

    const reader = new FileReader();

    reader.onload = function () {
      photoPreview.src = reader.result;
      photoPreview.hidden = false;
    };

    reader.readAsDataURL(file);
  });
}

if (detailsForm) {
  detailsForm.addEventListener("submit", function (event) {
    event.preventDefault();

    if (!getRole()) {
      window.location.href = "index.html";
      return;
    }

    const report = {
      id: Date.now(),
      type: localStorage.getItem("campusFindType") || "Lost",
      name: document.getElementById("itemName").value.trim(),
      category: document.getElementById("category").value,
      location: document.getElementById("location").value.trim(),
      date: document.getElementById("itemDate").value,
      description: document.getElementById("description").value.trim(),
      contact: document.getElementById("contact").value.trim(),
      role: getRole()
    };

    if (!report.name || !report.category ||
        !report.location || !report.date) {
      document.getElementById("detailsMessage").textContent =
        "Please complete all required fields.";
      return;
    }

    const reports = getReports();
    reports.push(report);
    saveReports(reports);

    alert("Your report has been saved in this browser!");
    window.location.href = "dashboard.html";
  });
}
