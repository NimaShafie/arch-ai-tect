# Projects

<div id="projects-root" aria-live="polite">
  <p class="muted">Loading projects from Workbench…</p>
</div>

<!-- Live list from Workbench: shows newest first, falls back if API unavailable -->
<script>
(function() {
  const API = 'https://workbench.shafie.org/api/projects';
  const root = document.getElementById('projects-root');

  function render(items) {
    if (!items || !items.length) {
      root.innerHTML = '<p class="muted">No projects yet.</p>';
      return;
    }
    // newest first (created_at desc), fallback by slug
    items.sort((a,b) => {
      const aa = (a.created_at || '') + (a.slug || '');
      const bb = (b.created_at || '') + (b.slug || '');
      return aa < bb ? 1 : aa > bb ? -1 : 0;
    });

    const ul = document.createElement('ul');
    ul.style.listStyle = 'disc';
    ul.style.paddingLeft = '1.25rem';

    for (const p of items) {
      const name = (p.name || p.slug || '').trim();
      const slug = (p.slug || '').trim();
      if (!slug) continue;

      const li = document.createElement('li');
      const a = document.createElement('a');
      a.textContent = name || slug;
      a.href = `/projects/${encodeURIComponent(slug)}/`;
      li.appendChild(a);
      ul.appendChild(li);
    }
    root.innerHTML = '';
    root.appendChild(ul);
  }

  fetch(API + '?t=' + Date.now(), { method: 'GET', mode: 'cors' })
    .then(r => {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(render)
    .catch(err => {
      console.warn('Workbench projects fetch failed:', err);
      root.innerHTML = '<p class="muted">Could not load projects from Workbench right now.</p>';
    });
})();
</script>
