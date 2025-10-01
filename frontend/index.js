const chatWindow = document.getElementById("chatWindow");
const messageForm = document.getElementById("messageForm");
const submitButton = messageForm.querySelector('button[type="submit"]');
const messageInput = document.getElementById("messageInput");
const locationLabel = document.getElementById("locationLabel");

locationLabel.textContent = "Demo Location";

const state = {
  messages: [
    {
      role: "assistant",
      content: "Hi there! What would you like to order today?",
    },
  ],
  typing: false,
};

renderMessages();

messageForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = messageInput.value.trim();
  if (!text) {
    return;
  }

  const history = [...state.messages];
  appendMessage({ role: "user", content: text });
  messageInput.value = "";
  toggleFormDisabled(true);
  state.typing = true;
  renderMessages();

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        history,
      }),
    });

    if (!response.ok) {
      throw new Error("Failed to reach assistant.");
    }

    const payload = await response.json();
    state.messages = payload.messages || state.messages;
    state.typing = false;

    renderMessages();
  } catch (error) {
    console.error(error);
  } finally {
    toggleFormDisabled(false);
    // Ensure the input regains focus so the user can immediately type again
    try {
      messageInput.focus();
    } catch (e) {
      // no-op if focus fails in some environments
    }
  }
});

function appendMessage(message) {
  state.messages.push(message);
  renderMessages();
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function renderMessages() {
  chatWindow.innerHTML = "";
  state.messages.forEach((message) => {
    const wrapper = document.createElement("div");
    wrapper.className =
      message.role === "user" ? "flex justify-end" : "flex justify-start";

    const bubble = document.createElement("div");
    bubble.className = `max-w-[85%] rounded-2xl px-4 py-2 text-sm leading-relaxed ${
      message.role === "user"
        ? "bg-gray-900 text-white rounded-br-none"
        : "bg-gray-100 text-gray-900 rounded-bl-none"
    }`;
    bubble.textContent = message.content;

    wrapper.appendChild(bubble);
    chatWindow.appendChild(wrapper);
  });
  if (state.typing) {
    const wrapper = document.createElement("div");
    wrapper.className = "flex justify-start";

    const bubble = document.createElement("div");
    bubble.className =
      "max-w-[85%] rounded-2xl px-4 py-2 text-sm leading-relaxed bg-gray-100 text-gray-900 rounded-bl-none";

    const dots = document.createElement("div");
    dots.className = "flex space-x-1";
    for (let i = 0; i < 3; i++) {
      const dot = document.createElement("div");
      dot.className = `w-2 h-2 bg-gray-400 rounded-full animate-pulse ${
        i === 1 ? "delay-75" : i === 2 ? "delay-150" : ""
      }`;
      dots.appendChild(dot);
    }
    bubble.appendChild(dots);

    wrapper.appendChild(bubble);
    chatWindow.appendChild(wrapper);
  }
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function toggleFormDisabled(disabled) {
  messageInput.disabled = disabled;
  submitButton.disabled = disabled;
}

// Set focus to the message input on page load
try {
  messageInput.focus();
} catch (e) {
  // no-op if focus fails in some environments
}
