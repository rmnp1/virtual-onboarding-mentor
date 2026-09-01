const TOKEN_KEY = "om_token";
const ME_KEY = "om_me";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function getMe() {
  try {
    return JSON.parse(localStorage.getItem(ME_KEY) || "null");
  } catch {
    return null;
  }
}

export function setMe(user) {
  if (user) localStorage.setItem(ME_KEY, JSON.stringify(user));
  else localStorage.removeItem(ME_KEY);
}

function apiError(data, status) {
  if (data && typeof data.detail === "string") return data.detail;
  if (data && Array.isArray(data.detail)) {
    return data.detail.map((d) => d.msg || d.message).join("; ");
  }
  return `Request failed (${status})`;
}

export async function api(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(path, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error("Network error");
  }

  if (res.status === 401 && getToken()) {
    go("/login");
    throw new Error("Session expired");
  }

  let data = null;
  try {
    data = await res.json();
  } catch {
    // empty body
  }

  if (!res.ok) throw new Error(apiError(data, res.status));
  return data;
}

export function go(path) {
  window.location.hash = path;
}

export function currentPath() {
  return window.location.hash.replace(/^#/, "") || "/chat";
}

export function el(html) {
  const template = document.createElement("template");
  template.innerHTML = html.trim();
  return template.content.firstElementChild;
}

export function escapeHtml(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
}

export function showToast(message, isError = false) {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.add("visible");
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => toast.classList.remove("visible"), 3500);
}