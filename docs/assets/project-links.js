// docs/assets/project-links.js
// Frontend helpers for project pages (MkDocs site)
// - Intercept "Send to Pipeline" clicks
// - Show an in-page modal with real-time status from the API

(function () {
  // --- Modal helpers -------------------------------------------------------

  function ensurePipelineModal() {
    let overlay = document.getElementById("aw-pipeline-overlay");
    let modal = document.getElementById("aw-pipeline-modal");
    let titleEl = document.getElementById("aw-pipeline-title");
    let bodyEl = document.getElementById("aw-pipeline-body");
    let closeBtn = document.getElementById("aw-pipeline-close");

    if (overlay && modal && titleEl && bodyEl && closeBtn) {
      return { overlay, modal, titleEl, bodyEl, closeBtn };
    }

    // Create a simple overlay + card (matches existing visual style closely)
    overlay = document.createElement("div");
    overlay.id = "aw-pipeline-overlay";
    overlay.style.position = "fixed";
    overlay.style.inset = "0";
    overlay.style.background = "rgba(0,0,0,0.25)";
    overlay.style.display = "none";
    overlay.style.alignItems = "flex-start";
    overlay.style.justifyContent = "center";
    overlay.style.paddingTop = "80px";
    overlay.style.zIndex = "9999";

    modal = document.createElement("div");
    modal.id = "aw-pipeline-modal";
    modal.style.minWidth = "320px";
    modal.style.maxWidth = "480px";
    modal.style.background = "#f5f5f5";
    modal.style.borderRadius = "4px";
    modal.style.boxShadow = "0 8px 24px rgba(0,0,0,0.2)";
    modal.style.padding = "16px 20px";
    modal.style.fontFamily =
      'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';

    titleEl = document.createElement("div");
    titleEl.id = "aw-pipeline-title";
    titleEl.textContent = "Pipeline Status";
    titleEl.style.fontSize = "18px";
    titleEl.style.fontWeight = "600";
    titleEl.style.marginBottom = "8px";

    bodyEl = document.createElement("div");
    bodyEl.id = "aw-pipeline-body";
    bodyEl.style.fontSize = "14px";
    bodyEl.style.lineHeight = "1.5";
    bodyEl.style.marginBottom = "16px";

    closeBtn = document.createElement("button");
    closeBtn.id = "aw-pipeline-close";
    closeBtn.type = "button";
    closeBtn.textContent = "Close";
    closeBtn.style.border = "none";
    closeBtn.style.borderRadius = "4px";
    closeBtn.style.padding = "6px 14px";
    closeBtn.style.fontSize = "14px";
    closeBtn.style.cursor = "pointer";
    closeBtn.style.background = "#e0e0e0";
    closeBtn.style.color = "#333";

    closeBtn.addEventListener("click", function () {
      overlay.style.display = "none";
    });

    modal.appendChild(titleEl);
    modal.appendChild(bodyEl);
    modal.appendChild(closeBtn);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    return { overlay, modal, titleEl, bodyEl, closeBtn };
  }

  function openPipelineModal(initialHtml) {
    const { overlay, bodyEl } = ensurePipelineModal();
    bodyEl.innerHTML =
      initialHtml || "Triggering the pipeline for this project…";
    overlay.style.display = "flex";
  }

  function updatePipelineModal(html) {
    const { overlay, bodyEl } = ensurePipelineModal();
    bodyEl.innerHTML = html;
    overlay.style.display = "flex";
  }

  // --- Small helpers -------------------------------------------------------

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function encodeAttr(str) {
    return String(str).replace(/"/g, "&quot;");
  }

  function currentProjectSlug() {
    // Expect paths like /projects/test-2/... on docs.shafie.org
    var parts = (window.location.pathname || "").split("/");
    // ["", "projects", "test-2", ...]
    var idx = parts.indexOf("projects");
    if (idx >= 0 && parts.length > idx + 1) {
      return decodeURIComponent(parts[idx + 1]);
    }
    return null;
  }

  // --- API call + status wiring -------------------------------------------

  async function callPipeline(slug) {
    if (!slug) {
      updatePipelineModal(
        "<p><strong>Unable to determine project slug from URL.</strong></p>"
      );
      return;
    }

    const base =
      window.AW_WORKBENCH_BASE || "https://workbench.shafie.org";

    const url =
      base.replace(/\/$/, "") +
      "/api/projects/" +
      encodeURIComponent(slug) +
      "/pipeline";

    openPipelineModal("Triggering the pipeline for this project…");

    try {
      const resp = await fetch(url, {
        method: "POST",
        credentials: "omit",
        headers: {
          Accept: "application/json",
        },
      });

      let data = null;
      let text = null;

      try {
        data = await resp.json();
      } catch (e) {
        text = await resp.text();
      }

      if (!resp.ok) {
        const detail =
          (data && (data.detail || data.error)) ||
          (text && text.substring(0, 300)) ||
          "Unknown error";
        updatePipelineModal(
          [
            "<p><strong>Pipeline failed.</strong></p>",
            "<p>Status code: " + resp.status + "</p>",
            "<pre style='white-space:pre-wrap; font-size:12px;'>" +
              escapeHtml(detail) +
              "</pre>",
          ].join("")
        );
        return;
      }

      if (data && data.ok) {
        const files = []
          .concat(data.architecture_file || [])
          .concat(data.diagram_files || []);

        const commitShort = data.commit || "";
        const commitUrl = data.commit_url || "";

        const changedText = data.changed
          ? "Changes were committed and pushed to the Disney AI+ repo."
          : "No content changed, but the pipeline still recorded this run.";

        let html = "<p><strong>Pipeline run completed successfully.</strong></p>";

        html += "<p>" + escapeHtml(changedText) + "</p>";

        if (commitShort || commitUrl) {
          html += "<p>Commit: ";
          if (commitUrl) {
            html +=
              '<a href="' +
              encodeAttr(commitUrl) +
              '" target="_blank" rel="noopener">' +
              escapeHtml(commitShort) +
              "</a>";
          } else {
            html += escapeHtml(commitShort);
          }
          html += "</p>";
        }

        if (files.length > 0) {
          html += "<p>Updated files:</p><ul>";
          files.forEach(function (f) {
            html +=
              "<li><code style='font-size:12px;'>" +
              escapeHtml(f) +
              "</code></li>";
          });
          html += "</ul>";
        }

        html +=
          "<p style='margin-top:8px; font-size:12px; color:#555;'>You can confirm in GitHub under the <code>disney-ai-plus</code> repository.</p>";

        updatePipelineModal(html);
      } else {
        updatePipelineModal(
          "<p><strong>Pipeline finished.</strong></p>" +
            "<p>The server returned an unexpected response.</p>" +
            "<pre style='white-space:pre-wrap; font-size:12px;'>" +
            escapeHtml(JSON.stringify(data, null, 2)) +
            "</pre>"
        );
      }
    } catch (err) {
      updatePipelineModal(
        "<p><strong>Network error while calling the pipeline.</strong></p>" +
          "<pre style='white-space:pre-wrap; font-size:12px;'>" +
          escapeHtml(String(err)) +
          "</pre>"
      );
    }
  }

  // Expose a global so inline onclick can delegate if we wire it that way
  window.awSendToPipeline = function (slug) {
    callPipeline(slug || currentProjectSlug());
    // Returning false is helpful if used as onclick="return awSendToPipeline(...)"
    return false;
  };

  // --- Intercept clicks BEFORE inline handlers run -------------------------
  //
  // We use capture: true so this handler fires before any onclick attribute
  // attached to the button and can prevent navigation.

  document.addEventListener(
    "click",
    function (event) {
      var target = event.target;
      if (!target) return;

      // 1) Intercept the "Send to Pipeline" button
      var btn = target.closest && target.closest("button");
      if (btn && btn.textContent && btn.textContent.trim() === "Send to Pipeline") {
        event.preventDefault();
        event.stopImmediatePropagation();
        callPipeline(currentProjectSlug());
        return;
      }

      // 2) Intercept direct links to /api/projects/<slug>/pipeline
      var link = target.closest && target.closest("a[href]");
      if (!link) return;

      var href = link.getAttribute("href") || "";
      var match = href.match(/\/api\/projects\/([^/]+)\/pipeline\/?$/);
      if (!match) return;

      event.preventDefault();
      event.stopImmediatePropagation();

      var slug = decodeURIComponent(match[1]);
      callPipeline(slug);
    },
    true // <-- capture phase
  );
})();
