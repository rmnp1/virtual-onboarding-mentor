import { escapeHtml, getMe, getToken, currentPath, go, setMe, setToken } from "./lib.js";
import { AuthView } from "./views/auth.js";
import { ChatView } from "./views/chat.js";
import { ScenariosView } from "./views/scenarios.js";
import { ProfileView } from "./views/profile.js";
import { FeedbackView } from "./views/feedback.js";
import { MetricsView } from "./views/metrics.js";

const EXACT_ROUTES = {
  "/login": AuthView,
  "/chat": ChatView,
  "/scenarios": ScenariosView,
  "/profile": ProfileView,
  "/feedback": FeedbackView,
  "/metrics": MetricsView,
};

function match(path) {
  const scenarioMatch = path.match(/^\/scenario\/(.+)$/);
  if (scenarioMatch) return { view: ScenariosView, params: [undefined, scenarioMatch[1]] };
  const view = EXACT_ROUTES[path];
  if (view) return { view, params: [] };
  return null;
}

function renderNav() {
  const nav = document.getElementById("navbar");
  const me = getMe();
  const label = me ? me.full_name || me.email : "";
  nav.innerHTML = `
    <div class="brand">Onboarding Mentor</div>
    <div class="links">
      <a href="#/chat">Chat</a>
      <a href="#/scenarios">Scenarios</a>
      <a href="#/profile">Profile</a>
      <a href="#/feedback">Feedback</a>
      <a href="#/metrics">Metrics</a>
    </div>
    <div class="user">
      ${label ? `<span>${escapeHtml(label)}</span>` : ""}
      <button type="button" id="logout">Logout</button>
    </div>`;
  nav.querySelector("#logout").addEventListener("click", () => {
    setToken(null);
    setMe(null);
    render();
  });
}

function render() {
  const token = getToken();
  const nav = document.getElementById("navbar");
  let path = currentPath();
  const container = document.getElementById("view");

  if (!token) {
    nav.classList.add("hidden");
    if (path !== "/login") {
      go("/login");
      return;
    }
  } else {
    nav.classList.remove("hidden");
    renderNav();
    if (path === "/login" || path === "/") {
      go("/chat");
      return;
    }
  }

  const matched = match(path);
  container.innerHTML = "";
  if (!matched) {
    const p = document.createElement("p");
    p.className = "empty";
    p.textContent = "Page not found.";
    const link = document.createElement("a");
    link.href = "#/chat";
    link.textContent = " Go to chat";
    p.appendChild(link);
    container.appendChild(p);
    return;
  }

  matched.view.render(container, matched.params);
}

window.addEventListener("hashchange", render);
window.addEventListener("DOMContentLoaded", render);