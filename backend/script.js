const reveals = document.querySelectorAll(".reveal");

const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("in-view");
        observer.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.2 }
);

reveals.forEach((el) => observer.observe(el));

// Dashboard pulse updater
(function () {
  const occEl = document.querySelector("#metric-occupancy");
  const rentEl = document.querySelector("#metric-rent");
  const reqEl = document.querySelector("#metric-requests");
  const maintEl = document.querySelector("#timeline-maintenance");
  const renewalEl = document.querySelector("#timeline-renewal");
  const screeningEl = document.querySelector("#timeline-screening");
  if (!occEl || !rentEl || !reqEl) return;

  const API_BASE = window.API_BASE || "";

  // Auth-aware fetch for pulse
  async function pulseFetch() {
    const token = localStorage.getItem("access_token");
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    try {
      const res = await fetch(`${API_BASE}/api/pulse`, { headers });
      if (res.status === 401) {
        localStorage.removeItem("access_token");
        window.location.href = "auth.html";
        return;
      }
      const data = await res.json();
      if (typeof data.occupancy === "number") {
        occEl.textContent = `${data.occupancy.toFixed(1)}%`;
      }
      if (typeof data.rent_collected === "number") {
        const formatted =
          data.rent_collected >= 1_000_000
            ? `$${(data.rent_collected / 1_000_000).toFixed(2)}M`
            : `$${Math.round(data.rent_collected).toLocaleString()}`;
        rentEl.textContent = formatted;
      }
      if (typeof data.open_requests === "number") {
        reqEl.textContent = data.open_requests;
      }
      if (data.timeline) {
        maintEl && (maintEl.textContent = data.timeline.maintenance);
        renewalEl && (renewalEl.textContent = data.timeline.renewal);
        screeningEl && (screeningEl.textContent = data.timeline.screening);
      }
    } catch {}
  }
  pulseFetch();
})();

// Nav dropdown toggle
(function () {
  const dropdown = document.querySelector(".nav-dropdown");
  if (!dropdown) return;
  const trigger = dropdown.querySelector(".nav-trigger");
  const menu = dropdown.querySelector(".nav-menu");

  const closeMenu = () => {
    dropdown.classList.remove("open");
    trigger.setAttribute("aria-expanded", "false");
  };

  trigger.addEventListener("click", (e) => {
    e.stopPropagation();
    const isOpen = dropdown.classList.contains("open");
    if (isOpen) {
      closeMenu();
    } else {
      dropdown.classList.add("open");
      trigger.setAttribute("aria-expanded", "true");
    }
  });

  document.addEventListener("click", (e) => {
    if (!dropdown.contains(e.target)) {
      closeMenu();
    }
  });

  menu.addEventListener("click", () => {
    closeMenu();
  });
})();
