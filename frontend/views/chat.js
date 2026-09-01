import { el, getToken } from "../lib.js";

let socket = null;

export const ChatView = {
  render(container) {
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
      socket.close();
    }
    const chat = el(`
      <div class="chat">
        <div class="chat-head">
          <h2>Mentor chat</h2>
          <div class="chat-status" id="chat-status">connecting…</div>
          <button type="button" id="chat-new">New chat</button>
        </div>
        <div class="chat-messages" id="chat-messages"></div>
        <form class="chat-input" id="chat-form">
          <input id="chat-text" placeholder="Ask your mentor something…" autocomplete="off" />
          <button type="submit" class="primary">Send</button>
        </form>
      </div>`);

    container.appendChild(chat);

    const messages = chat.querySelector("#chat-messages");
    const status = chat.querySelector("#chat-status");
    const form = chat.querySelector("#chat-form");
    const text = chat.querySelector("#chat-text");
    let currentBubble = null;

    function append(msg, cls) {
      const bubble = el(`<div class="bubble ${cls}"></div>`);
      bubble.textContent = msg;
      messages.appendChild(bubble);
      messages.scrollTop = messages.scrollHeight;
      return bubble;
    }

    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${window.location.host}/api/chat/ws`);
    socket = ws;

    ws.addEventListener("open", () => {
      ws.send(JSON.stringify({ type: "auth", content: getToken() }));
      status.textContent = "connected";
      status.classList.add("ok");
    });
    ws.addEventListener("close", () => {
      status.textContent = "disconnected";
      status.classList.remove("ok");
    });
    ws.addEventListener("error", () => {
      status.textContent = "connection error";
      status.classList.remove("ok");
    });
    ws.addEventListener("message", (event) => {
      let msg;
      try {
        msg = JSON.parse(event.data);
      } catch {
        return;
      }
      if (msg.type === "token") {
        if (!currentBubble) currentBubble = append("", "mentor");
        currentBubble.textContent += msg.content || "";
        messages.scrollTop = messages.scrollHeight;
      } else if (msg.type === "done") {
        currentBubble = null;
      } else if (msg.type === "error") {
        currentBubble = null;
        append(msg.content || "Service error", "mentor error");
      }
    });

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const value = text.value.trim();
      if (!value) return;
      append(value, "user");
      text.value = "";
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ message: value }));
      } else {
        append("Connection lost. Please reload the page.", "mentor error");
      }
    });

    chat.querySelector("#chat-new").addEventListener("click", () => {
      messages.innerHTML = "";
    });
  },
};