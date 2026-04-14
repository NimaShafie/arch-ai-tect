// docs/assets/projects.js
// Dynamic project listings for the MkDocs site:
// - On /projects/ index: fills #wb-projects with project cards.
// - On the home page: fills #wb-latest-projects with nice "card" layout.
//
// Uses the Workbench API: GET /api/projects
// Falls back to a static list if the API can't be reached.

(function () {
  const cfg = window.__WB_CFG || {};
  const DEFAULT_API = "https://workbench.shafie.org";
  const WB_BASE = DEFAULT_API;

  // Static fallback projects (used if the API call fails).
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
      credentials: "omit",
      cache: "no-store",
      mode: "cors",
    });

    if (!resp.ok) throw new Error("HTTP " + resp.status);
    return await resp.json();
  }

  // ---- Icon picker --------------------------------------------------------

  function pickIconForSlug(slug) {
    const s = (slug || "").toLowerCase();
    if (s.includes("disney")) return "🎬";
    if (s.includes("test")) return "🧪";
    if (s.includes("auth")) return "🔐";
    if (s.includes("hover") || s.includes("click")) return "🖱️";
    if (s.includes("dev") || s.includes("kit")) return "🛠️";
    return "🧩";
  }

  // ---- Projects index: chip row -------------------------------------------

  function renderProjectsList(items) {
    const host = document.getElementById("wb-projects");
    if (!host) return;

    const row = document.createElement("div");
    row.className = "wb-project-chips";

    for (const p of items) {
      const name =
        p.name ||
        p.title ||
        p.nav_title ||
        p.project_name ||
        p.slug ||
        "Unnamed project";

      const a = document.createElement("a");
      a.className = "wb-chip";
      a.href = "/projects/" + encodeURIComponent(p.slug) + "/";
      a.innerHTML =
        '<span class="wb-chip-icon">' + pickIconForSlug(p.slug) + "</span>" +
        '<span class="wb-chip-label">' + name + "</span>";
      row.appendChild(a);
    }

    host.innerHTML = "";
    host.appendChild(row);
  }

  // ---- Home page: "Latest projects" cards ---------------------------------

  function renderLatestProjects(items) {
    const host = document.getElementById("wb-latest-projects");
    if (!host) return;

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
      const name = p.name || p.title || p.nav_title || p.project_name || slug || "Unnamed project";
      const summary = p.summary || p.description || "Architecture workspace managed by the ArchAiTect Workbench.";
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
      metaDiv.textContent = (p.tagline || "Architecture workspace").toUpperCase();

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

      const wbBtn = document.createElement("a");
      wbBtn.className = "md-button";
      wbBtn.href = WB_BASE + "/ui/" + encodeURIComponent(slug);
      wbBtn.target = "_blank";
      wbBtn.rel = "noopener";
      wbBtn.textContent = "Open in Workbench ↗";
      linksDiv.appendChild(wbBtn);

      if (p.github_url) {
        const ghBtn = document.createElement("a");
        ghBtn.className = "md-button";
        ghBtn.href = p.github_url;
        ghBtn.target = "_blank";
        ghBtn.rel = "noopener";
        ghBtn.textContent = "GitHub ↗";
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

  // ---- Wire everything up -------------------------------------------------

  document.addEventListener("DOMContentLoaded", async () => {
    const projectsHost = document.getElementById("wb-projects");
    const latestHost = document.getElementById("wb-latest-projects");
    const statCount = document.getElementById("wb-stat-project-count");

    if (!projectsHost && !latestHost && !statCount) return;

    let items = null;

    try {
      items = await fetchProjects();
    } catch (e) {
      console.warn("projects.js: live fetch failed, using static fallback", e);
    }

    // Always fall back to static list if API failed or returned nothing.
    if (!items || !items.length) {
      items = STATIC_PROJECTS.slice();
    }

    if (!items.length) return;

    // Sort newest first.
    items.sort((a, b) => {
      const ak = (a.created_at || "") + (a.slug || "");
      const bk = (b.created_at || "") + (b.slug || "");
      return bk.localeCompare(ak);
    });

    if (statCount) {
      statCount.textContent = items.length;
    }

    if (projectsHost) renderProjectsList(items);
    if (latestHost) renderLatestProjects(items);
  });
})();
