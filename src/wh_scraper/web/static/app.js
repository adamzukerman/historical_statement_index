const MAX_SIMILARITY_PERCENT = 100;

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatDate(value) {
  if (!value) {
    return "Unknown date";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatSimilarity(score) {
  if (typeof score !== "number" || Number.isNaN(score)) {
    return "–";
  }
  const percent = Math.min(Math.max(score * 100, 0), MAX_SIMILARITY_PERCENT);
  return `${percent.toFixed(1)}%`;
}

function renderDocumentDetail(data) {
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
      ${published} · Status: ${escapeHtml(data.scrape_status)} · Admin: ${escapeHtml(data.admin)}
    </p>
    ${location}
    <h3>Transcript</h3>
    <div class="detail-text">${(data.clean_text || "No text captured yet.")
      .split("\n")
      .map((line) => `<p>${escapeHtml(line)}</p>`)
      .join("")}</div>
    <p><a href="${escapeHtml(data.url)}" target="_blank" rel="noreferrer">View original source ↗</a></p>
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
    renderDocumentDetail(data);

    const documentsList = document.getElementById("documents-list");
    if (documentsList) {
      documentsList.querySelectorAll(".document-link.active").forEach((el) => el.classList.remove("active"));
    }
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

function showErrorPopup(message) {
  const popup = document.getElementById("error-popup");
  const text = document.getElementById("error-popup-message");
  if (!popup || !text) return;
  text.textContent = message || "Something went wrong. Please try again.";
  popup.hidden = false;
}

function initErrorPopup() {
  const popup = document.getElementById("error-popup");
  const closeButton = document.getElementById("error-popup-close");
  if (!popup || !closeButton) return;

  function hidePopup() {
    popup.hidden = true;
  }

  closeButton.addEventListener("click", hidePopup);
  popup.addEventListener("click", (event) => {
    if (event.target === popup) {
      hidePopup();
    }
  });
}

function renderSearchDetail(result, triggerEl) {
  const detailPane = document.getElementById("search-detail");
  if (!detailPane || !result) return;

  const summary = [
    escapeHtml(result.admin),
    formatDate(result.publish_date),
    `Chunk #${result.chunk_index}`,
  ].join(" · ");

  const verdictPill = result.verdict
    ? `<span class="llm-pill ${result.rejected ? "no" : "yes"}">LLM ${escapeHtml(result.verdict)}</span>`
    : "";
  const verdictReason =
    result.verdict_reason && result.verdict
      ? `<p><strong>LLM reason:</strong> ${escapeHtml(result.verdict_reason)}</p>`
      : "";

  const chunkHtml = (result.chunk || "No chunk text available.")
    .split("\n")
    .map((line) => `<p>${escapeHtml(line)}</p>`)
    .join("");

  detailPane.innerHTML = `
    <h2>${escapeHtml(result.title)}</h2>
    <p class="detail-meta">${summary}</p>
    <p class="detail-meta">Similarity: ${formatSimilarity(result.cosine_score)}</p>
    ${verdictPill ? `<p>${verdictPill}</p>` : ""}
    ${verdictReason}
    <div class="chunk-preview">${chunkHtml}</div>
    <p><a href="${escapeHtml(result.source_url)}" target="_blank" rel="noreferrer">View full document ↗</a></p>
  `;

  const resultsList = document.getElementById("search-results");
  if (resultsList) {
    resultsList.querySelectorAll(".document-link.active").forEach((el) => el.classList.remove("active"));
  }
  if (triggerEl) {
    triggerEl.classList.add("active");
  }
}

function initDocumentList() {
  const documentsList = document.getElementById("documents-list");
  if (!documentsList) return;
  documentsList.querySelectorAll(".document-link").forEach((button) => {
    button.addEventListener("click", () => {
      const documentId = button.getAttribute("data-document-id");
      if (documentId) {
        fetchDocument(documentId, button);
      }
    });
  });
}

function initSearchPage() {
  const form = document.getElementById("search-form");
  if (!form) return;

  const queryInput = document.getElementById("search-query");
  const sortSelect = document.getElementById("sort-select");
  const includeRejectedInput = document.getElementById("include-rejected");
  const resetButton = document.getElementById("search-reset");
  const summary = document.getElementById("search-summary");
  const emptyState = document.getElementById("search-results-empty");
  const resultsList = document.getElementById("search-results");
  const pagination = document.getElementById("search-pagination");
  const prevButton = document.getElementById("search-prev");
  const nextButton = document.getElementById("search-next");
  const pageInfo = document.getElementById("search-page-info");
  const submitButton = form.querySelector("button[type='submit']");

  const state = {
    pageSize: Number(form.dataset.pageSize) || 25,
    page: 1,
    totalPages: 0,
    results: [],
    hasSearched: false,
  };

  function collectAdminFilters() {
    return Array.from(form.querySelectorAll('input[name="admin_filter"]:checked')).map(
      (input) => input.value,
    );
  }

  function setLoading(isLoading) {
    if (submitButton) {
      submitButton.disabled = isLoading;
    }
    if (prevButton) {
      prevButton.disabled = isLoading || state.page <= 1;
    }
    if (nextButton) {
      nextButton.disabled = isLoading || state.page >= state.totalPages || state.totalPages === 0;
    }
    if (isLoading && emptyState) {
      emptyState.textContent = "Searching…";
      emptyState.hidden = false;
      if (resultsList) {
        resultsList.hidden = true;
      }
      if (summary) {
        summary.hidden = true;
      }
    }
  }

  function resetResults() {
    state.results = [];
    state.totalPages = 0;
    state.page = 1;
    state.hasSearched = false;
    if (resultsList) {
      resultsList.innerHTML = "";
      resultsList.hidden = true;
    }
    if (summary) {
      summary.hidden = true;
      summary.textContent = "";
    }
    if (pagination) {
      pagination.hidden = true;
    }
    if (emptyState) {
      emptyState.textContent = "Enter a query to view relevant transcript chunks.";
      emptyState.hidden = false;
    }
    const detailPane = document.getElementById("search-detail");
    if (detailPane) {
      detailPane.innerHTML = "<p>Run a search to load transcript chunks and details here.</p>";
    }
  }

  function buildPayload() {
    const payload = {
      query: queryInput.value.trim(),
      mode: form.querySelector('input[name="mode"]:checked')?.value || "simple",
      admin_filter: collectAdminFilters(),
      sort: sortSelect ? sortSelect.value : "relevance",
      page: state.page,
      page_size: state.pageSize,
      include_rejected: includeRejectedInput ? includeRejectedInput.checked : false,
    };
    if (!payload.admin_filter || payload.admin_filter.length === 0) {
      delete payload.admin_filter;
    }
    return payload;
  }

  function renderResults(data) {
    state.page = data.pagination.page;
    state.totalPages = data.pagination.total_pages || 0;
    state.results = data.results || [];
    state.hasSearched = true;

    if (summary) {
      if (data.pagination.total_results > 0) {
        summary.hidden = false;
        summary.textContent = `Showing ${state.results.length} of ${
          data.pagination.total_results
        } results · Page ${state.page} of ${Math.max(state.totalPages, 1)}`;
      } else {
        summary.hidden = false;
        summary.textContent = "No results found.";
      }
    }

    if (state.results.length === 0) {
      if (resultsList) {
        resultsList.hidden = true;
        resultsList.innerHTML = "";
      }
      if (emptyState) {
        emptyState.hidden = false;
        emptyState.textContent = "No results match that query.";
      }
      if (pagination) {
        pagination.hidden = true;
      }
      const detailPane = document.getElementById("search-detail");
      if (detailPane) {
        detailPane.innerHTML = "<p>No results to display. Adjust your filters and try again.</p>";
      }
      return;
    }

    if (emptyState) {
      emptyState.hidden = true;
    }
    if (resultsList) {
      resultsList.hidden = false;
      resultsList.innerHTML = state.results
        .map((result, index) => {
          const dateText = formatDate(result.publish_date);
          const scoreText = formatSimilarity(result.cosine_score);
          const verdictTag = result.verdict
            ? `<span class="llm-pill ${result.rejected ? "no" : "yes"}">LLM ${escapeHtml(
                result.verdict,
              )}</span>`
            : "";
          return `
            <li>
              <button type="button" class="document-link" data-result-index="${index}">
                <span class="doc-title">${escapeHtml(result.title)}</span>
                <span class="search-result-meta">
                  <span>${dateText}</span>
                  <span>· ${escapeHtml(result.admin)}</span>
                  <span class="score-badge">${scoreText}</span>
                  ${verdictTag}
                </span>
              </button>
            </li>
          `;
        })
        .join("");

      resultsList.querySelectorAll(".document-link").forEach((button) => {
        button.addEventListener("click", () => {
          const idx = Number(button.getAttribute("data-result-index"));
          const result = Number.isInteger(idx) ? state.results[idx] : null;
          if (result) {
            renderSearchDetail(result, button);
          }
        });
        });
    }

    const detailPane = document.getElementById("search-detail");
    if (detailPane) {
      detailPane.innerHTML = "<p>Select a result to view its chunk.</p>";
    }

    if (pagination && pageInfo && prevButton && nextButton) {
      pagination.hidden = false;
      pageInfo.textContent = `Page ${state.page} of ${Math.max(state.totalPages, 1)}`;
      prevButton.disabled = state.page <= 1;
      nextButton.disabled = state.page >= state.totalPages || state.totalPages === 0;
    }
  }

  async function executeSearch() {
    const payload = buildPayload();
    if (!payload.query) {
      showErrorPopup("Please enter a query before searching.");
      return;
    }
    setLoading(true);
    try {
      const response = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) {
        showErrorPopup(data.error || "Search failed. Please try again.");
        return;
      }
      renderResults(data);
    } catch (error) {
      console.error(error);
      showErrorPopup("We couldn't run that search. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    state.page = 1;
    executeSearch();
  });

  if (sortSelect) {
    sortSelect.addEventListener("change", () => {
      if (!state.hasSearched) return;
      state.page = 1;
      executeSearch();
    });
  }

  if (prevButton) {
    prevButton.addEventListener("click", () => {
      if (state.page <= 1) return;
      state.page -= 1;
      executeSearch();
    });
  }

  if (nextButton) {
    nextButton.addEventListener("click", () => {
      if (state.page >= state.totalPages) return;
      state.page += 1;
      executeSearch();
    });
  }

  if (resetButton) {
    resetButton.addEventListener("click", () => {
      form.reset();
      resetResults();
    });
  }

  resetResults();
}

document.addEventListener("DOMContentLoaded", () => {
  initErrorPopup();
  initDocumentList();
  initSearchPage();
});
