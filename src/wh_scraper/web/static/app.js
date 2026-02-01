function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderDetail(data) {
  const detailPane = document.getElementById("document-detail");
  if (!detailPane) return;

  const published = data.date_published
    ? `Published: ${escapeHtml(data.date_published)}`
    : "Published date unknown";

  const location = data.location
    ? `<p><strong>Location:</strong> ${escapeHtml(data.location)}</p>`
    : "";

  detailPane.innerHTML = `
    <h2>${escapeHtml(data.title || "Untitled briefing")}</h2>
    <p class="detail-meta">
      ${published} · Status: ${data.scrape_status} · Admin: ${data.admin}
    </p>
    ${location}
    <h3>Transcript</h3>
    <div class="detail-text">${(data.clean_text || "No text captured yet.")
      .split("\n")
      .map((line) => `<p>${escapeHtml(line)}</p>`)
      .join("")}</div>
    <p><a href="${data.url}" target="_blank" rel="noreferrer">View original source ↗</a></p>
  `;
}

async function fetchDocument(documentId, triggerEl) {
  const detailPane = document.getElementById("document-detail");
  if (detailPane) {
    detailPane.innerHTML = "<p>Loading…</p>";
  }

  try {
    const response = await fetch(`/api/documents/${documentId}`);
    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }
    const data = await response.json();
    renderDetail(data);

    document
      .querySelectorAll(".document-link.active")
      .forEach((el) => el.classList.remove("active"));
    if (triggerEl) {
      triggerEl.classList.add("active");
    }
  } catch (error) {
    if (detailPane) {
      detailPane.innerHTML =
        "<p class='error'>Sorry, we couldn't load that document. Please try again.</p>";
    }
    console.error(error);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".document-link").forEach((button) => {
    button.addEventListener("click", () => {
      const documentId = button.getAttribute("data-document-id");
      if (documentId) {
        fetchDocument(documentId, button);
      }
    });
  });
});
