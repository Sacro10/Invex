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
        result.textContent = JSON.stringify(data, null, 2);
      }
    } catch (error) {
      if (result) {
        result.textContent = error.message;
        result.classList.add("error");
      }
    }
  });
});
