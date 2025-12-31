
const API_BASE = window.API_BASE || "";

// Helper: fetch with auth token for /api/* except /api/auth/* and /api/health
async function apiFetch(url, options = {}) {
  const isApi = url.startsWith("/api/") || url.startsWith(API_BASE + "/api/");
  const isAuth = url.includes("/api/auth/") || url.endsWith("/api/health");
  const token = localStorage.getItem("access_token");
  if (isApi && !isAuth && token) {
    options.headers = options.headers || {};
    options.headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(url, options);
  if (res.status === 401) {
    localStorage.removeItem("access_token");
    window.location.href = "auth.html";
    throw new Error("Unauthorized");
  }
  return res;
}

const forms = document.querySelectorAll("form[data-endpoint]");

const parseValue = (el) => {
  if (el.type === "checkbox") {
    return el.checked;
  }

  const dataType = el.dataset.type;
  if (dataType === "number") {
    return Number(el.value);
  }
  if (dataType === "int") {
    return parseInt(el.value, 10);
  }
  if (dataType === "boolean") {
    return el.value === "true";
  }

  return el.value;
};

const formatDate = (isoString) => {
  if (!isoString) return "";
  const date = new Date(isoString);
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true
  });
};

const displayResultAsTable = (data, element) => {
  if (!data || typeof data !== 'object') {
    element.textContent = JSON.stringify(data, null, 2);
    return;
  }

  let table = '<table class="result-table"><thead><tr><th>Field</th><th>Value</th></tr></thead><tbody>';
  Object.entries(data).forEach(([key, value]) => {
    // Format dates
    if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(value)) {
      value = formatDate(value);
    }
    table += `<tr><td>${key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</td><td>${value}</td></tr>`;
  });
  table += '</tbody></table>';
  element.innerHTML = table;
};

forms.forEach((form) => {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const result = form.querySelector(".result");
    if (result) {
      result.textContent = "Running...";
      result.classList.remove("error");
    }

    const payload = {};
    form.querySelectorAll("input, select, textarea").forEach((el) => {
      if (!el.name) return;
      payload[el.name] = parseValue(el);
    });

    try {
      const response = await apiFetch(`${API_BASE}${form.dataset.endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Request failed");
      }
      if (result) {
        displayResultAsTable(data, result);
      }
    } catch (error) {
      if (result) {
        result.textContent = error.message;
        result.classList.add("error");
      }
    }
  });
});

// Function to display data in a table
function displayTable(data, containerId, columns) {
  const container = document.getElementById(containerId);
  if (!container) return;

  if (!data || data.length === 0) {
    container.innerHTML = "<p>No data available.</p>";
    return;
  }

  let table = "<table><thead><tr>";
  columns.forEach(col => {
    table += `<th>${col.label}</th>`;
  });
  table += "</tr></thead><tbody>";

  data.forEach(row => {
    table += "<tr>";
    columns.forEach(col => {
      let value = row[col.key];
      // Format dates
      if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(value)) {
        value = formatDate(value);
      }
      if (col.key === "status" && containerId === "maintenance-table") {
        // Add status select
        value = `<select class="status-select" data-id="${row.id}">
          <option value="open" ${value === 'open' ? 'selected' : ''}>Pending</option>
          <option value="resolved" ${value === 'resolved' ? 'selected' : ''}>Completed</option>
        </select>`;
      }
      table += `<td>${value}</td>`;
    });
    table += "</tr>";
  });

  table += "</tbody></table>";
  container.innerHTML = table;

  // Add event listeners for status selects
  if (containerId === "maintenance-table") {
    document.querySelectorAll(".status-select").forEach(select => {
      select.addEventListener("change", (e) => {
        const id = e.target.dataset.id;
        const status = e.target.value;
        updateStatus(id, status);
      });
    });
  }
}

// Function to update maintenance request status
async function updateStatus(requestId, status) {
  try {
    const response = await apiFetch(`${API_BASE}/api/maintenance-requests/${requestId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    if (response.ok) {
      // Refresh the table
      document.getElementById("view-all-maintenance").click();
    } else {
      alert("Failed to update status");
    }
  } catch (error) {
    alert("Error updating status: " + error.message);
  }
}

// Handle View All buttons
document.addEventListener("DOMContentLoaded", () => {
  const viewAllButtons = document.querySelectorAll(".view-all");
  viewAllButtons.forEach(btn => {
    btn.addEventListener("click", async (e) => {
      const endpoint = e.target.dataset.endpoint;
      const tableId = e.target.dataset.table;
      const columns = JSON.parse(e.target.dataset.columns);

      try {
        const response = await apiFetch(`${API_BASE}${endpoint}`);
        const data = await response.json();
        displayTable(data, tableId, columns);
      } catch (error) {
        console.error("Error fetching data:", error);
      }
    });
  });

  // Handle Export buttons
  const exportButtons = document.querySelectorAll(".export-csv");
  exportButtons.forEach(btn => {
    btn.addEventListener("click", (e) => {
      const endpoint = e.target.dataset.endpoint;
      const link = document.createElement("a");
      link.href = `${API_BASE}${endpoint}`;
      link.download = "";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    });
  });
});
