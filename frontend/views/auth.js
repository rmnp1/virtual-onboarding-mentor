import { api, el, go, setMe, setToken } from "../lib.js";

let authConfig = { invite_required: false };

async function loadConfig() {
  try {
    authConfig = await api("/api/auth/config");
  } catch {
    authConfig = { invite_required: false };
  }
}

function loginForm() {
  return `
    <label>Email
      <input name="email" type="email" required />
    </label>
    <label>Password
      <input name="password" type="password" required />
    </label>
    <button type="submit" class="primary" style="width: 100%">Login</button>`;
}

function registerForm() {
  const inviteField = authConfig.invite_required
    ? `
    <label>Invite code
      <input name="invite_code" required />
    </label>`
    : "";
  return `
    <label>Email
      <input name="email" type="email" required />
    </label>
    <label>Password
      <input name="password" type="password" minlength="8" required />
    </label>
    <div class="row">
      <label>Full name
        <input name="full_name" />
      </label>
      <label>Department
        <input name="department" />
      </label>
    </div>
    ${inviteField}
    <label>Language
      <select name="language">
        <option value="pl">Polski</option>
        <option value="en">English</option>
      </select>
    </label>
    <button type="submit" class="primary" style="width: 100%">Register</button>`;
}

async function login(email, password) {
  const res = await api("/api/auth/login", { method: "POST", body: { email, password } });
  setToken(res.access_token);
  const me = await api("/api/auth/me");
  setMe(me);
  go("/chat");
}

export const AuthView = {
  render(container) {
    const card = el(`
      <div class="auth-card">
        <h2>Welcome to Onboarding Mentor</h2>
        <div class="tabs">
          <button type="button" class="tab active" data-mode="login">Login</button>
          <button type="button" class="tab" data-mode="register">Register</button>
        </div>
        <form id="auth-form"></form>
      </div>`);

    const form = card.querySelector("#auth-form");
    const tabs = card.querySelectorAll(".tab");
    let mode = "login";

    function renderMode() {
      form.innerHTML = mode === "login" ? loginForm() : registerForm();
      tabs.forEach((t) => t.classList.toggle("active", t.dataset.mode === mode));
    }

    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        mode = tab.dataset.mode;
        renderMode();
      });
    });

    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const fd = new FormData(form);
      const submit = form.querySelector("button[type=submit]");
      submit.disabled = true;
      try {
        if (mode === "login") {
          await login(String(fd.get("email")).trim(), String(fd.get("password")));
        } else {
          await api("/api/auth/register", {
            method: "POST",
            body: {
              email: String(fd.get("email")).trim(),
              password: String(fd.get("password")),
              full_name: String(fd.get("full_name") || "").trim() || null,
              department: String(fd.get("department") || "").trim() || null,
              language: fd.get("language"),
              invite_code: String(fd.get("invite_code") || "").trim() || null,
            },
          });
          await login(
            String(fd.get("email")).trim(),
            String(fd.get("password")),
          );
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Request failed";
        const msgEl = form.querySelector(".form-error");
        if (msgEl) {
          msgEl.textContent = msg;
          return;
        }
        const p = document.createElement("p");
        p.className = "empty form-error";
        p.style.color = "#dc2626";
        p.textContent = msg;
        form.appendChild(p);
      } finally {
        submit.disabled = false;
      }
    });

    loadConfig().then(() => renderMode());
    container.appendChild(card);
  },
};
