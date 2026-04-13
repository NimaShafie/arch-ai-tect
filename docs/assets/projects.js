// docs/assets/projects.js
// Dynamic project listings for the MkDocs site:
// - On /projects/ index: fills #wb-projects with a simple list.
// - On the home page: fills #wb-latest-projects with nice "card" layout.
//
// Uses the Workbench API: GET /api/projects
// Falls back to a static list if the API can't be reached (e.g., CORS/403).

(function () {
  const cfg = window.__WB_CFG || {};
  const DEFAULT_API = "https://workbench.shafie.org";

  // Static fallback projects (used if the API call fails).
  // You can edit these slugs/names/summaries as your real projects evolve.
  const STATIC_PROJECTS = [
    {
      slug: "dev-kit",
      name: "Dev Kit",
      summary: "A C++ package management system hosted as a Python localhost server, supporting installation of pre-packaged tools, libraries, and plug-ins.",
      tagline: "Architecture workspace",
      created_at: "2026-04-12",
    },
    {
      slug: "hover-and-click",
      name: "Hover And Click",
      summary: "Architecture workspace managed by the ArchAiTect Workbench.",
      tagline: "Architecture workspace",
      created_at: "2025-12-02",
    },
    {
      slug: "v4-test",
      name: "V4 Test",
      summary: "Architecture workspace managed by the ArchAiTect Workbench.",
      tagline: "Architecture workspace",
      created_at: "2025-12-02",
    },
    {
      slug: "disney-ai-v3",
      name: "Disney+ AI Clone",
      summary: "End-to-end architecture for a Disney+ style streaming platform with AI-assisted workflows.",
      tagline: "Reference architecture",
      created_at: "2025-11-23",
      github_url: "https://github.com/SevDev21/disney-ai-plus",
    },
  ];

  // Always default to the Workbench API, unless explicitly overridden.
  const API_BASE =
    cfg.API_BASE ||
    window.__WB_API_BASE ||
    DEFAULT_API;

  async function fetchProjects() {
    const bust = Date.now().toString();
    const url =
      API_BASE.replace(/\/+$/, "") +
      "/api/projects?_bust=" +
      encodeURIComponent(bust);

    const resp = await fetch(url, {
      // Do NOT send cookies/credentials cross-origin. This avoids the
      // browser enforcing Access-Control-Allow-Credentials: true.
      credentials: "omit",
      cache: "no-store",
      mode: "cors",
    });

    if (!resp.ok) throw new Error("HTTP " + resp.status);
    return await resp.json();
  }

  function showErrorFor(hostId, msg) {
    const host = document.getElementById(hostId);
    if (!host) return;
    host.innerHTML =
      '<p style="color:#b00020">' +
      (msg || "Could not load projects from Workbench.") +
      "</p>";
  }

  // ---- Projects index: simple list ----------------------------------------

  function renderProjectsList(items) {
    const host = document.getElementById("wb-projects");
    if (!host) return;

    const ul = document.createElement("ul");
    ul.style.listStyle = "disc";
    ul.style.paddingLeft = "1.25rem";

    for (const p of items) {
      const li = document.createElement("li");
      const a = document.createElement("a");
      const name =
        p.name ||
        p.title ||
        p.nav_title ||
        p.project_name ||
        p.slug ||
        "Unnamed project";
      a.textContent = name;
      a.href = "/projects/" + encodeURIComponent(p.slug) + "/";
      li.appendChild(a);
      ul.appendChild(li);
    }

    host.innerHTML = "";
    host.appendChild(ul);
  }

  // ---- Home page: "Latest projects" cards ---------------------------------

  function pickIconForSlug(slug) {
    const s = (slug || "").toLowerCase();
    if (s.includes("disney")) return "🎬";
    if (s.includes("test")) return "🧪";
    if (s.includes("auth")) return "🔐";
    return "🧩";
  }

  function renderLatestProjects(items) {
    const host = document.getElementById("wb-latest-projects");
    if (!host) return;

    // How many cards to show on the home page
    const maxAttr = host.getAttribute("data-max");
    const max = maxAttr ? parseInt(maxAttr, 10) || 2 : 2;

    const latest = items.slice(0, max);

    if (!latest.length) {
      host.innerHTML = "<p>No projects available yet.</p>";
      return;
    }

    const container = document.createElement("div");
    container.className = "latest-projects-grid";

    latest.forEach((p) => {
      const slug = p.slug;
      const name =
        p.name ||
        p.title ||
        p.nav_title ||
        p.project_name ||
        slug ||
        "Unnamed project";
      const summary =
        p.summary ||
        p.description ||
        "Architecture workspace managed by the ArchAiTect Workbench.";

      const icon = pickIconForSlug(slug);

      const card = document.createElement("div");
      card.className = "project-card";

      const iconDiv = document.createElement("div");
      iconDiv.className = "project-icon";
      iconDiv.textContent = icon;

      const bodyDiv = document.createElement("div");
      bodyDiv.className = "project-body";

      const titleDiv = document.createElement("div");
      titleDiv.className = "project-title";
      titleDiv.textContent = name;

      const metaDiv = document.createElement("div");
      metaDiv.className = "project-meta";
      metaDiv.textContent =
        (p.tagline || "Architecture workspace").toUpperCase();

      const textP = document.createElement("p");
      textP.className = "project-text";
      textP.textContent = summary;

      const linksDiv = document.createElement("div");
      linksDiv.className = "project-links";

      const docsBtn = document.createElement("a");
      docsBtn.className = "md-button md-button--primary";
      docsBtn.href = "./projects/" + encodeURIComponent(slug) + "/";
      docsBtn.textContent = "Open project docs";

      linksDiv.appendChild(docsBtn);

      // Optional GitHub link if API provides it
      if (p.github_url) {
        const ghBtn = document.createElement("a");
        ghBtn.className = "md-button md-button--secondary";
        ghBtn.href = p.github_url;
        ghBtn.target = "_blank";
        ghBtn.rel = "noopener";
        ghBtn.textContent = "GitHub repo";
        linksDiv.appendChild(ghBtn);
      }

      bodyDiv.appendChild(titleDiv);
      bodyDiv.appendChild(metaDiv);
      bodyDiv.appendChild(textP);
      bodyDiv.appendChild(linksDiv);

      card.appendChild(iconDiv);
      card.appendChild(bodyDiv);

      container.appendChild(card);
    });

    host.innerHTML = "";
    host.appendChild(container);
  }

  // ---- Stats grid (home page "At a glance") --------------------------------

  function renderStats(items) {
    const n = items.length;
    const elProjects  = document.getElementById("wb-stat-projects");
    const elDiagrams  = document.getElementById("wb-stat-diagrams");
    const elDocs      = document.getElementById("wb-stat-docs");
    if (elProjects) elProjects.textContent = n;
    if (elDiagrams) elDiagrams.textContent = (n * 6) + "+";
    if (elDocs)     elDocs.textContent     = n * 4;
  }

  // ---- Wire everything up -------------------------------------------------

  document.addEventListener("DOMContentLoaded", async () => {
    const projectsHost = document.getElementById("wb-projects");
    const latestHost   = document.getElementById("wb-latest-projects");
    const hasStats     = !!document.getElementById("wb-stat-projects");

    // If nothing on this page needs data, skip the fetch.
    if (!projectsHost && !latestHost && !hasStats) return;

    let items = null;

    try {
      // Try live data first (will fail if Cloudflare blocks CORS).
      items = await fetchProjects();
    } catch (e) {
      console.warn("projects.js: live fetch failed, using static fallback", e);
    }

    // If the API call failed, fall back to the static list for dynamic sections.
    // For #wb-projects the static markdown is already correct — don't overwrite it.
    const liveFailed = !items || !items.length;
    if (liveFailed) {
      items = STATIC_PROJECTS.slice();
    }

    if (!items || !items.length) {
      if (latestHost)
        showErrorFor("wb-latest-projects", "Could not load latest projects from Workbench.");
      return;
    }

    // Sort newest first if created_at exists, otherwise by slug.
    items.sort((a, b) => {
      const ak = (a.created_at || "") + (a.slug || "");
      const bk = (b.created_at || "") + (b.slug || "");
      return bk.localeCompare(ak);
    });

    // Always render stats (works with live data or static fallback).
    renderStats(items);

    // Only overwrite the projects list if we got live data
    // (static markdown in #wb-projects is already correct as a fallback).
    if (projectsHost && !liveFailed) renderProjectsList(items);
    if (latestHost) renderLatestProjects(items);
  });
})();
