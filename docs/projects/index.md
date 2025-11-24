# Projects

> This page auto-loads the current projects from **Workbench**.  
> If JavaScript is disabled, you’ll see whatever was last published.

<ul id="projects-list">
  <!-- Fallback content (kept for SEO and offline) -->
  <!-- The build step will overwrite this with the latest list.
       Then the script below will refresh it live at runtime. -->
  <li><a href="../projects/">(loading…)</a></li>
</ul>

<script>
(async () => {
  const list = document.getElementById('projects-list');
  function render(items){
    list.innerHTML = '';
    if (!items.length){
      list.innerHTML = '<li><em>No projects yet.</em></li>';
      return;
    }
    for (const p of items){
      const name = (p.name || p.slug || '').trim();
      const slug = p.slug || '';
      if (!name) continue;
      const li = document.createElement('li');
      const a  = document.createElement('a');
      a.textContent = name;
      a.href = slug ? `../${slug}/` : '#';
      li.appendChild(a);
      list.appendChild(li);
    }
  }

  try {
    // Always fetch fresh from Workbench (bypass intermediary caches)
    const url = `https://workbench.shafie.org/api/projects?t=${Date.now()}`;
    const res = await fetch(url, { cache: 'no-store', mode: 'cors' });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const items = await res.json();
    // newest first if created_at exists
    items.sort((a,b) => String(b.created_at||'').localeCompare(String(a.created_at||'')));
    render(items);
  } catch (e) {
    // On any error, keep whatever was baked at build time
    console.warn('Live projects fetch failed:', e);
  }
})();
</script>
