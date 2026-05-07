/* ============================================================
   SchoolMS — Enhanced App JS
   ============================================================ */

"use strict";

/* ── Dark Mode ─────────────────────────────────────────────── */
const ThemeManager = {
  init() {
    const stored = localStorage.getItem("theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const isDark = stored ? stored === "dark" : prefersDark;
    this.apply(isDark);

    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", e => {
      if (!localStorage.getItem("theme")) this.apply(e.matches);
    });
  },
  apply(isDark) {
    document.documentElement.classList.toggle("dark", isDark);
    document.querySelectorAll("[data-theme-toggle]").forEach(btn => {
      const icon = btn.querySelector("[data-theme-icon]");
      if (icon) icon.innerHTML = isDark ? SvgIcons.sun : SvgIcons.moon;
    });
  },
  toggle() {
    const isDark = document.documentElement.classList.toggle("dark");
    localStorage.setItem("theme", isDark ? "dark" : "light");
    document.querySelectorAll("[data-theme-toggle]").forEach(btn => {
      const icon = btn.querySelector("[data-theme-icon]");
      if (icon) icon.innerHTML = isDark ? SvgIcons.sun : SvgIcons.moon;
    });
  }
};

/* ── SVG Icons ──────────────────────────────────────────────── */
const SvgIcons = {
  eye: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.75" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>`,
  eyeOff: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.75" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88"/></svg>`,
  sun: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.75" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z"/></svg>`,
  moon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.75" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z"/></svg>`,
  check: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5"/></svg>`,
  x: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>`,
  info: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z"/></svg>`,
  warn: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"/></svg>`,
};

/* ── Toast Notifications ────────────────────────────────────── */
const Toast = {
  container: null,
  init() {
    this.container = document.getElementById("toast-container") || this._createContainer();
  },
  _createContainer() {
    const c = document.createElement("div");
    c.id = "toast-container";
    c.className = "toast-container";
    document.body.appendChild(c);
    return c;
  },
  show(title, message = "", type = "info", duration = 4000) {
    if (!this.container) this.init();
    const iconMap = { success: SvgIcons.check, error: SvgIcons.warn, info: SvgIcons.info };
    const colorMap = { success: "#10b981", error: "#ef4444", info: "#6366f1" };

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
      <span class="toast-icon" style="color:${colorMap[type]}">${iconMap[type] || SvgIcons.info}</span>
      <div class="toast-content">
        <div class="toast-title">${title}</div>
        ${message ? `<div class="toast-message">${message}</div>` : ""}
        <div class="toast-progress"><div class="toast-progress-bar" style="width:100%"></div></div>
      </div>
      <button class="toast-close" aria-label="Dismiss">${SvgIcons.x}</button>`;

    this.container.appendChild(toast);

    const bar = toast.querySelector(".toast-progress-bar");
    bar.style.transition = `width ${duration}ms linear`;
    requestAnimationFrame(() => requestAnimationFrame(() => { bar.style.width = "0%"; }));

    const dismiss = () => {
      toast.classList.add("removing");
      toast.addEventListener("animationend", () => toast.remove(), { once: true });
    };
    toast.querySelector(".toast-close").addEventListener("click", dismiss);
    setTimeout(dismiss, duration);
    return toast;
  },
  success(title, msg) { return this.show(title, msg, "success"); },
  error(title, msg) { return this.show(title, msg, "error"); },
  info(title, msg) { return this.show(title, msg, "info"); },
};

/* ── Password Toggle ────────────────────────────────────────── */
const PasswordToggle = {
  init() {
    document.querySelectorAll("[data-password-toggle]").forEach(btn => {
      btn.addEventListener("click", () => {
        const target = document.getElementById(btn.dataset.passwordToggle) || btn.closest(".password-wrapper")?.querySelector("input");
        if (!target) return;
        const isText = target.type === "text";
        target.type = isText ? "password" : "text";
        btn.innerHTML = isText ? SvgIcons.eye : SvgIcons.eyeOff;
        btn.setAttribute("aria-label", isText ? "Show password" : "Hide password");
      });
    });

    // Auto-init: wrap all bare password inputs that aren't already wrapped
    document.querySelectorAll("input[type='password']:not(.pw-processed)").forEach(input => {
      input.classList.add("pw-processed");
      if (input.closest(".password-wrapper")) return;

      const wrapper = document.createElement("div");
      wrapper.className = "password-wrapper";
      input.parentNode.insertBefore(wrapper, input);
      wrapper.appendChild(input);

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "password-toggle";
      btn.setAttribute("aria-label", "Show password");
      btn.innerHTML = SvgIcons.eye;
      btn.addEventListener("click", () => {
        const isText = input.type === "text";
        input.type = isText ? "password" : "text";
        btn.innerHTML = isText ? SvgIcons.eye : SvgIcons.eyeOff;
        btn.setAttribute("aria-label", isText ? "Show password" : "Hide password");
      });
      wrapper.appendChild(btn);
    });
  }
};

/* ── Password Strength Meter ────────────────────────────────── */
const PasswordStrength = {
  init() {
    document.querySelectorAll("[data-strength-for]").forEach(meter => {
      const input = document.getElementById(meter.dataset.strengthFor);
      if (!input) return;
      input.addEventListener("input", () => this.update(meter, input.value));
    });

    document.querySelectorAll("input[data-show-strength]").forEach(input => {
      const meter = document.createElement("div");
      meter.className = "strength-meter mt-1";
      meter.innerHTML = `<div class="strength-bar"></div>`;
      const label = document.createElement("p");
      label.className = "text-xs mt-1";
      label.style.color = "var(--color-text-muted)";
      input.closest(".password-wrapper")?.after(meter) || input.after(meter);
      meter.after(label);
      input.addEventListener("input", () => this._update(meter.querySelector(".strength-bar"), label, input.value));
    });
  },
  _update(bar, label, val) {
    const score = this._score(val);
    const states = [
      { cls: "strength-weak",   text: "Weak",   color: "#ef4444" },
      { cls: "strength-fair",   text: "Fair",   color: "#f59e0b" },
      { cls: "strength-good",   text: "Good",   color: "#3b82f6" },
      { cls: "strength-strong", text: "Strong", color: "#10b981" },
    ];
    bar.className = `strength-bar ${states[score].cls}`;
    label.textContent = val ? `Password strength: ${states[score].text}` : "";
    label.style.color = val ? states[score].color : "var(--color-text-muted)";
  },
  _score(val) {
    let s = 0;
    if (val.length >= 8) s++;
    if (/[A-Z]/.test(val) && /[a-z]/.test(val)) s++;
    if (/\d/.test(val)) s++;
    if (/[^A-Za-z0-9]/.test(val)) s++;
    return Math.min(s, 3);
  }
};

/* ── Confirmation Modal ─────────────────────────────────────── */
const Modal = {
  _overlay: null,
  init() {
    // Replace all data-confirm links/buttons
    document.querySelectorAll("[data-confirm]").forEach(el => {
      el.addEventListener("click", e => {
        e.preventDefault();
        const msg = el.dataset.confirm || "Are you sure?";
        const title = el.dataset.confirmTitle || "Confirm Action";
        this.confirm(title, msg).then(ok => {
          if (!ok) return;
          if (el.tagName === "A") { window.location.href = el.href; }
          else if (el.form) { el.form.submit(); }
          else { el.closest("form")?.submit(); }
        });
      });
    });
  },
  confirm(title, message) {
    return new Promise(resolve => {
      const overlay = document.createElement("div");
      overlay.className = "modal-overlay";
      overlay.innerHTML = `
        <div class="modal-panel" role="dialog" aria-modal="true" aria-labelledby="modal-title">
          <div class="flex items-start gap-3 mb-4">
            <span style="color:#ef4444;flex-shrink:0;width:24px">${SvgIcons.warn}</span>
            <div>
              <h3 id="modal-title" class="font-semibold text-base" style="color:var(--color-text)">${title}</h3>
              <p class="text-sm mt-1" style="color:var(--color-text-secondary)">${message}</p>
            </div>
          </div>
          <div class="flex gap-3 justify-end">
            <button id="modal-cancel" class="px-4 py-2 rounded-lg text-sm font-medium border transition-all" style="border-color:var(--color-border);color:var(--color-text-secondary)" onmouseover="this.style.background='var(--color-bg)'" onmouseout="this.style.background='transparent'">Cancel</button>
            <button id="modal-confirm" class="px-4 py-2 rounded-lg text-sm font-semibold text-white bg-red-500 hover:bg-red-600 transition-all">Confirm</button>
          </div>
        </div>`;
      document.body.appendChild(overlay);
      requestAnimationFrame(() => overlay.classList.add("active"));

      const cleanup = (result) => {
        overlay.classList.remove("active");
        overlay.addEventListener("transitionend", () => overlay.remove(), { once: true });
        resolve(result);
      };

      overlay.querySelector("#modal-confirm").addEventListener("click", () => cleanup(true));
      overlay.querySelector("#modal-cancel").addEventListener("click", () => cleanup(false));
      overlay.addEventListener("click", e => { if (e.target === overlay) cleanup(false); });
      document.addEventListener("keydown", e => { if (e.key === "Escape") cleanup(false); }, { once: true });

      setTimeout(() => overlay.querySelector("#modal-cancel")?.focus(), 50);
    });
  }
};

/* ── Nav Link Helpers ───────────────────────────────────────── */
const Drawer = {
  init() {
    document.querySelectorAll("[data-nav-link]").forEach(link => {
      link.addEventListener("click", () => {
        document.querySelectorAll(".app-drawer, .mobile-more-sheet").forEach(panel => {
          panel.classList.add("hidden");
        });
      });
    });
  }
};

/* ── Compact Menus ──────────────────────────────────────────── */
const CompactMenu = {
  init() {
    document.querySelectorAll("[data-menu-toggle]").forEach(button => {
      button.addEventListener("click", () => {
        const target = document.getElementById(button.dataset.menuToggle);
        if (!target) return;
        target.classList.toggle("hidden");
      });
    });

    document.addEventListener("keydown", e => {
      if (e.key !== "Escape") return;
      document.querySelectorAll(".app-drawer, .mobile-more-sheet").forEach(panel => {
        panel.classList.add("hidden");
      });
    });
  }
};

/* ── Search / Filter Tables ─────────────────────────────────── */
const TableSearch = {
  init() {
    document.querySelectorAll("[data-search]").forEach(input => {
      const tableId = input.dataset.search;
      const table = document.getElementById(tableId);
      const emptyMsg = document.getElementById(`${tableId}-empty`);

      input.addEventListener("input", () => {
        const q = input.value.toLowerCase().trim();
        let visible = 0;
        table?.querySelectorAll("tbody tr").forEach(row => {
          const match = row.textContent.toLowerCase().includes(q);
          row.style.display = match ? "" : "none";
          if (match) visible++;
        });
        if (emptyMsg) emptyMsg.style.display = visible === 0 ? "" : "none";
      });
    });
  }
};

/* ── Form Loading States ────────────────────────────────────── */
const FormLoader = {
  init() {
    document.querySelectorAll("form[data-loading]").forEach(form => {
      form.addEventListener("submit", () => {
        const btn = form.querySelector("button[type='submit'], input[type='submit']");
        if (!btn) return;
        btn.disabled = true;
        const original = btn.innerHTML;
        btn.dataset.originalHtml = original;
        btn.innerHTML = `<span style="display:flex;align-items:center;gap:8px;justify-content:center"><span class="spinner"></span>${btn.dataset.loadingText || "Processing…"}</span>`;
        setTimeout(() => { btn.disabled = false; btn.innerHTML = original; }, 15000);
      });
    });
  }
};

/* ── Auto-dismiss Alerts ────────────────────────────────────── */
const Alerts = {
  init() {
    document.querySelectorAll("[data-auto-dismiss]").forEach(el => {
      const delay = parseInt(el.dataset.autoDismiss) || 5000;
      setTimeout(() => {
        el.style.transition = "opacity 0.4s ease";
        el.style.opacity = "0";
        setTimeout(() => el.remove(), 400);
      }, delay);
    });
  }
};

/* ── Active Nav Link ────────────────────────────────────────── */
const ActiveNav = {
  init() {
    const path = window.location.pathname;
    document.querySelectorAll("[data-nav-link]").forEach(link => {
      const href = link.getAttribute("href");
      if (!href) return;
      const isActive = path === href || (href !== "/" && path.startsWith(href));
      link.setAttribute("data-active", isActive ? "true" : "false");
    });
  }
};

/* ── Init All ───────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", () => {
  ThemeManager.init();
  Toast.init();
  PasswordToggle.init();
  PasswordStrength.init();
  Modal.init();
  Drawer.init();
  CompactMenu.init();
  TableSearch.init();
  FormLoader.init();
  Alerts.init();
  ActiveNav.init();
});

// Expose globally
window.Toast = Toast;
window.ThemeManager = ThemeManager;
window.Modal = Modal;
window.CompactMenu = CompactMenu;
