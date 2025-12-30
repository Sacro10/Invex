const API_BASE = window.API_BASE || "";

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

forms.forEach((form) => {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const result = form.querySelector(".result");
    if (result) {
      result.textContent = "Running...";
      result.classList.remove("error");
    }
    // Hide table when submitting
    const tableContainer = document.getElementById('table-container');
    if (tableContainer) {
      tableContainer.style.display = 'none';
    }

    const payload = {};
    form.querySelectorAll("input, select, textarea").forEach((el) => {
      if (!el.name) return;
      payload[el.name] = parseValue(el);
    });

    try {
      const response = await fetch(`${API_BASE}${form.dataset.endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Request failed");
      }
      if (result) {
        displayTable([data]);
      }
    } catch (error) {
      if (result) {
        result.textContent = error.message;
        result.classList.add("error");
      }
    }
  });
});

// View All button
const viewAllBtn = document.getElementById('view-all');
if (viewAllBtn) {
  viewAllBtn.addEventListener('click', async () => {
    const form = document.querySelector("form[data-endpoint]");
    const endpoint = form ? form.dataset.viewEndpoint : null;
    if (!endpoint) return;
    try {
      const response = await fetch(endpoint);
      const data = await response.json();
      alert('Fetched data: ' + JSON.stringify(data));
      displayTable(data);
    } catch (e) {
      alert('Error fetching data: ' + e.message);
    }
  });
}

// Download CSV button
const downloadBtn = document.getElementById('download-csv');
if (downloadBtn) {
  downloadBtn.addEventListener('click', () => {
    const form = document.querySelector("form[data-endpoint]");
    const endpoint = form ? form.dataset.exportEndpoint : null;
    if (endpoint) {
      window.location = endpoint;
    }
  });
}

function displayTable(data) {
  const container = document.getElementById('table-container');
  if (!container || !data.length) return;
  container.style.display = 'block';
  // Hide the result
  const result = document.querySelector('.result');
  if (result) {
    result.style.display = 'none';
  }
  const keys = Object.keys(data[0]);
  let html = '<table border="1" style="width:100%; border-collapse:collapse;"><thead><tr>';
  html += keys.map(k => `<th style="padding:8px; background:#f0f0f0;">${k}</th>`).join('');
  // Add Actions column for maintenance
  const isMaintenance = document.querySelector("form[data-endpoint*='maintenance']");
  if (isMaintenance) {
    html += '<th style="padding:8px; background:#f0f0f0;">Actions</th>';
  }
  html += '</tr></thead><tbody>';
  html += data.map(row => {
    let rowHtml = '<tr>' + keys.map(k => `<td style="padding:8px;">${row[k]}</td>`).join('') + '';
    if (isMaintenance) {
      rowHtml += `<td style="padding:8px;"><button onclick="updateStatus(${row.id}, 'resolved')">Mark Resolved</button></td>`;
    }
    rowHtml += '</tr>';
    return rowHtml;
  }).join('');
  html += '</tbody></table>';
  container.innerHTML = html;
}

function updateStatus(id, status) {
  alert('Updating request ' + id + ' to ' + status);
  fetch(`/api/maintenance-requests/${id}`, { 
    method: 'PUT', 
    headers: { 'Content-Type': 'application/json' }, 
    body: JSON.stringify({ status: status }) 
  })
    .then(() => {
      // Refresh the table
      const viewAllBtn = document.getElementById('view-all');
      if (viewAllBtn) {
        viewAllBtn.click();
      }
    })
    .catch(err => alert('Error updating status: ' + err.message));
}
