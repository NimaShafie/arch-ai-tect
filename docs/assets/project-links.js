// docs/assets/project-links.js
// Make project titles on /projects/ clickable, based on the "Slug:" field below each title.

document.addEventListener("DOMContentLoaded", () => {
  // Only run on the Projects index page (not on individual project pages)
  if (!window.location.pathname.endsWith("/projects/")) {
    return;
  }

  const content = document.querySelector(".md-content__inner");
  if (!content) return;

  const children = Array.from(content.children);

  for (let i = 0; i < children.length; i++) {
    const node = children[i];
    if (node.tagName !== "H2") continue;

    const heading = node;
    let slug = null;

    // Walk forward until the next H2 to find the "Slug:" paragraph
    for (let j = i + 1; j < children.length; j++) {
      const sib = children[j];
      if (sib.tagName === "H2") break; // next project

      if (sib.tagName === "P") {
        const strong = sib.querySelector("strong");
        if (strong && strong.textContent.trim().startsWith("Slug")) {
          const codeEl = sib.querySelector("code");
          if (codeEl) {
            slug = codeEl.textContent.trim();
            break;
          }
        }
      }
    }

    if (!slug) continue;

    // Wrap the existing heading text in a link to the project page
    const titleText = heading.textContent.trim();
    if (!titleText) continue;

    const link = document.createElement("a");
    link.href = `/projects/${slug}/`;
    link.textContent = titleText;

    // Clear the heading and insert the link
    heading.textContent = "";
    heading.appendChild(link);
  }
});
