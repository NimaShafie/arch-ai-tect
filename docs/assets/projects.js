(function () {
  function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
    children.forEach(c => node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c));
    return node;
  }

  async function load() {
    const mount = document.getElementById('projects-list');
    if (!mount) return;

    const base = (window.ARCHWB && window.ARCHWB.WORKBENCH_BASE) || 'https://workbench.shafie.org';
    const url = base.replace(/\/+$/, '') + '/api/projects';

    try {
      const resp = await fetch(url, { credentials: 'omit' });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const items = await resp.json();

      mount.innerHTML = '';
      if (!items || !items.length) {
        mount.appendChild(el('p', {}, ['No projects yet.']));
        return;
      }

      const ul = el('ul');
      for (const p of items) {
        const name = (p.name || p.slug || '').trim();
        const slug = p.slug || '';
        if (!slug) continue;

        // Link to docs page under /projects/<slug>/ if it exists; otherwise just show text
        const link = el('a', { href: `/projects/${slug}/` }, [name || slug]);
        ul.appendChild(el('li', {}, [link]));
      }
      mount.appendChild(ul);
    } catch (e) {
      console.error('Failed to load projects', e);
      mount.innerHTML = '';
      mount.appendChild(
        el('p', { style: 'color:#b00020' }, [
          'Could not load projects from Workbench. ',
          'Please check API/CORS and try again.'
        ])
      );
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', load);
  } else {
    load();
  }
})();
