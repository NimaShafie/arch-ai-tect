// docs/assets/projects.js
(function () {
  const cfg = (window.__WB_CFG || {});
  // Prefer env-like globals injected by mkdocs extra_javascript or a small inline script
  const DEFAULT_API = 'https://workbench.shafie.org';
  const API_BASE =
    cfg.API_BASE ||
    window.__WB_API_BASE ||
    (typeof window !== 'undefined' ? new URL('/', window.location.origin).href : DEFAULT_API);

  async function fetchProjects() {
    const bust = Date.now().toString();
    const url = (API_BASE.replace(/\/+$/, '')) + '/api/projects?_bust=' + bust;
    const resp = await fetch(url, { credentials: 'omit', cache: 'no-store', mode: 'cors' });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
  }

  function renderProjects(items) {
    const host = document.getElementById('wb-projects');
    if (!host) return;
    const ul = document.createElement('ul');
    ul.style.listStyle = 'disc';
    ul.style.paddingLeft = '1.25rem';

    for (const p of items) {
      const li = document.createElement('li');
      const a = document.createElement('a');
      a.textContent = p.name || p.slug || 'Unnamed';
      // Point to the project page inside docs (relative)
      a.href = `../projects/${p.slug}/`;
      li.appendChild(a);
      ul.appendChild(li);
    }
    host.innerHTML = '';
    host.appendChild(ul);
  }

  function showError(msg) {
    const host = document.getElementById('wb-projects');
    if (host) {
      host.innerHTML = `<p style="color:#b00020">${msg}</p>`;
    }
  }

  document.addEventListener('DOMContentLoaded', async () => {
    const host = document.getElementById('wb-projects');
    if (!host) return;
    try {
      const items = await fetchProjects();
      // newest first if created_at exists
      items.sort((a, b) => ((b.created_at || '') + (b.slug || ''))
                          .localeCompare((a.created_at || '') + (a.slug || '')));
      renderProjects(items);
    } catch (e) {
      console.error('projects.js:', e);
      showError('Could not load projects from Workbench right now.');
    }
  });
})();
