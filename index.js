const chatWindow = document.getElementById("chatWindow");
const messageForm = document.getElementById("messageForm");
const submitButton = messageForm.querySelector('button[type="submit"]');
const messageInput = document.getElementById("messageInput");
const locationLabel = document.getElementById("locationLabel");

locationLabel.textContent = "IAH - El Premio Tex Mex Bar and Grill - DEMO";

const state = {
  messages: [
    {
      role: "assistant",
      content: "Hi there! What would you like to order today?",
    },
  ],
  cart: [],
  typing: false,
};

renderMessages();

messageForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = messageInput.value.trim();
  if (!text || messageInput.disabled) {
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
        cart: state.cart,
      }),
    });

    if (!response.ok) {
      throw new Error("Failed to reach assistant.");
    }

    const payload = await response.json();
    state.messages = payload.messages || state.messages;
    state.cart = payload.cart || state.cart;
    state.typing = false;

    renderMessages();
  } catch (error) {
    console.error(error);
    state.typing = false;
    renderMessages();
  } finally {
    // Check if payment button exists before re-enabling
    const hasPayment = state.messages.some((m) => m.role === "payment");
    toggleFormDisabled(hasPayment);
    if (!hasPayment) {
      try {
        messageInput.focus();
      } catch (e) {
        // no-op
      }
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

  let hasPaymentButton = false;

  // Render messages
  state.messages.forEach((message) => {
    if (message.role === "cart") {
      // Render cart message
      const wrapper = document.createElement("div");
      wrapper.className = "flex justify-start";

      const bubble = document.createElement("div");
      bubble.className =
        "max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed bg-gray-100 text-gray-900 rounded-bl-none";

      const lines = message.content.split("\n");
      lines.forEach((line, idx) => {
        if (line.startsWith("**") && line.endsWith("**")) {
          const title = document.createElement("div");
          title.className = "font-semibold mb-2 text-gray-800";
          title.textContent = line.replace(/\*\*/g, "");
          bubble.appendChild(title);
        } else if (line.trim()) {
          const itemDiv = document.createElement("div");
          itemDiv.className = "mb-1 text-gray-800";
          itemDiv.textContent = line;
          bubble.appendChild(itemDiv);
        }
      });

      wrapper.appendChild(bubble);
      chatWindow.appendChild(wrapper);
    } else if (message.role === "payment") {
      hasPaymentButton = true;

      // Render payment button (no bubble)
      const wrapper = document.createElement("div");
      wrapper.className = "flex justify-start mt-2";

      const paymentButton = document.createElement("button");
      paymentButton.className =
        "bg-gray-900 hover:bg-black text-white font-medium px-6 py-3 rounded-xl transition text-sm shadow-sm";
      paymentButton.textContent = "Proceed to Payment";
      paymentButton.onclick = () => {
        window.open(message.content, "_blank");
      };

      wrapper.appendChild(paymentButton);
      chatWindow.appendChild(wrapper);
    } else {
      // Render regular user/assistant message
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
    }
  });

  // Render typing indicator
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

  // Disable form if payment button exists
  if (hasPaymentButton) {
    messageInput.disabled = true;
    submitButton.disabled = true;
    messageInput.placeholder = "Order completed - payment in progress";
    messageInput.classList.add("bg-gray-100", "text-gray-400");
    submitButton.classList.add("opacity-50", "cursor-not-allowed");
  } else if (!state.typing) {
    messageInput.disabled = false;
    submitButton.disabled = false;
    messageInput.placeholder = "e.g. Cheeseburger without onions";
    messageInput.classList.remove("bg-gray-100", "text-gray-400");
    submitButton.classList.remove("opacity-50", "cursor-not-allowed");
  }
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
