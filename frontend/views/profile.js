import { api, el, escapeHtml, showToast } from "../lib.js";

export const ProfileView = {
  async render(container) {
    container.innerHTML = `<h2>Profile</h2><p class="empty">Loading…</p>`;

    let profile;
    try {
      profile = await api("/api/profile");
    } catch (err) {
      container.innerHTML = `<p class="empty">${escapeHtml(err instanceof Error ? err.message : "Failed to load")}</p>`;
      return;
    }

    const levels = ["junior", "mid", "senior"];
    const paces = ["slow", "normal", "fast"];
    const form = el(`
      <form class="card" id="profile-form">
        <label>
          Preferred name (how the mentor should call you)
          <input name="prefers_name" value="${escapeHtml(profile.prefers_name || "")}" />
        </label>
        <div class="row">
          <label>Experience level
            <select name="experience_level">
              ${levels
                .map(
                  (l) =>
                    `<option value="${l}" ${l === profile.experience_level ? "selected" : ""}>${l}</option>`,
                )
                .join("")}
            </select>
          </label>
          <label>Learning pace
            <select name="learning_pace">
              ${paces
                .map(
                  (p) =>
                    `<option value="${p}" ${p === profile.learning_pace ? "selected" : ""}>${p}</option>`,
                )
                .join("")}
            </select>
          </label>
        </div>
        <label>
          Interests (comma separated)
          <input name="interests" value="${escapeHtml(profile.interests.join(", "))}" />
        </label>
        <label>
          Additional context for the mentor
          <textarea name="custom_notes">${escapeHtml(profile.custom_notes || "")}</textarea>
        </label>
        <button type="submit" class="primary">Save</button>
      </form>`);

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const fd = new FormData(form);
      const interests = String(fd.get("interests") || "")
        .split(",")
        .map((i) => i.trim())
        .filter(Boolean);
      const submit = form.querySelector("button[type=submit]");
      submit.disabled = true;
      try {
        await api("/api/profile", {
          method: "PUT",
          body: {
            prefers_name: String(fd.get("prefers_name")).trim() || null,
            experience_level: fd.get("experience_level"),
            learning_pace: fd.get("learning_pace"),
            interests,
            custom_notes: String(fd.get("custom_notes")).trim() || null,
          },
        });
        showToast("Profile saved");
      } catch (err) {
        showToast(err instanceof Error ? err.message : "Save failed", true);
      } finally {
        submit.disabled = false;
      }
    });

    container.innerHTML = "";
    container.appendChild(form);
  },
};