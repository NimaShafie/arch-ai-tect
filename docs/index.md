# ArchAiTect Workbench

<div class="hero">

<span class="hero-kicker">AI-assisted architecture → living documentation</span>

<h2>Design systems once. Watch the docs, diagrams, and code stay in sync.</h2>

<p>
Start in the <strong>Workbench UI</strong>, generate architecture docs &amp; diagrams,
and consume them here in a clean, versioned documentation hub — backed by GitHub for real development work.
</p>

<div class="hero-cta-row">
  <a class="md-button hero-primary" href="https://workbench.shafie.org/" target="_blank" rel="noopener">
    Open Workbench
  </a>
  <a class="md-button hero-secondary" href="./projects/">
    View projects
  </a>
</div>

</div>

---

## At a glance

<div id="wb-stats-grid" class="stats-grid">

<div class="stat-card">
  <div class="stat-value" id="wb-stat-projects">—</div>
  <div class="stat-label">Active projects</div>
</div>

<div class="stat-card">
  <div class="stat-value" id="wb-stat-diagrams">—</div>
  <div class="stat-label">Generated diagrams</div>
</div>

<div class="stat-card">
  <div class="stat-value" id="wb-stat-docs">—</div>
  <div class="stat-label">Core architecture docs</div>
</div>

<div class="stat-card">
  <div class="stat-value">1</div>
  <div class="stat-label">Unified AI workbench</div>
</div>

</div>

---

## Start here

### 1. Create or open a project in the Workbench
Go to [https://workbench.shafie.org/](https://workbench.shafie.org/){ target="_blank" rel="noopener" } and create a project (or open an existing one).
Use AI-assisted briefs to describe the product, constraints, and quality attributes.

### 2. Generate architecture docs & diagrams
From the Workbench, trigger generation of:

&nbsp;&nbsp;&nbsp;&nbsp;Spec &amp; SRS  
&nbsp;&nbsp;&nbsp;&nbsp;Reference Architecture  
&nbsp;&nbsp;&nbsp;&nbsp;Implementation Guide  
&nbsp;&nbsp;&nbsp;&nbsp;C4, sequence, and deployment diagrams  

### 3. Consume the artifacts in two places

&nbsp;&nbsp;&nbsp;&nbsp;**Docs (this site)** – for browsable, internal documentation  
&nbsp;&nbsp;&nbsp;&nbsp;→ See **Projects** in the left nav to jump into a project.  

&nbsp;&nbsp;&nbsp;&nbsp;**GitHub** – for code-centric collaboration  
&nbsp;&nbsp;&nbsp;&nbsp;→ [`SevDev21/disney-ai-plus`](https://github.com/SevDev21/disney-ai-plus)

---

## Architecture → Stories → Code

The Workbench is designed around a simple pipeline:

### 1. Architect
&nbsp;&nbsp;&nbsp;&nbsp;Defines the system using briefs, requirements, and diagrams.  
&nbsp;&nbsp;&nbsp;&nbsp;Publishes architecture artifacts to MkDocs and to the GitHub repo.

### 2. Product Owner
&nbsp;&nbsp;&nbsp;&nbsp;Uses the specs and diagrams to derive user stories and backlog items.  
&nbsp;&nbsp;&nbsp;&nbsp;Stores and manages those stories alongside the repo.

### 3. Developer
&nbsp;&nbsp;&nbsp;&nbsp;Implements features and tests based on those stories.  
&nbsp;&nbsp;&nbsp;&nbsp;Uses the docs &amp; diagrams here as the source of truth for behavior and design.

---

## Visual pipeline

<div class="pipeline-row">

  <div class="pipeline-step">
    <div class="pipeline-badge">1</div>
    <div class="pipeline-title">Workbench</div>
    <div class="pipeline-text">
      Create or refine a project brief, capture requirements, and choose which diagrams to generate.
    </div>
  </div>

  <div class="pipeline-arrow">→</div>

  <div class="pipeline-step">
    <div class="pipeline-badge">2</div>
    <div class="pipeline-title">Generators</div>
    <div class="pipeline-text">
      Produce specs, SRS, reference architecture, implementation guides, and C4/sequence/deployment diagrams.
    </div>
  </div>

  <div class="pipeline-arrow">→</div>

  <div class="pipeline-step">
    <div class="pipeline-badge">3</div>
    <div class="pipeline-title">Docs &amp; GitHub</div>
    <div class="pipeline-text">
      Publish to this MkDocs site for human-friendly browsing, and to GitHub for code-centric collaboration.
    </div>
  </div>

  <div class="pipeline-arrow">→</div>

  <div class="pipeline-step">
    <div class="pipeline-badge">4</div>
    <div class="pipeline-title">Stories &amp; Code</div>
    <div class="pipeline-text">
      Product owners derive stories, developers implement and test, all backed by the same canonical architecture.
    </div>
  </div>

</div>

---

## Latest projects

A quick snapshot of what’s currently flowing through the Workbench.

<div id="wb-latest-projects" class="latest-projects-grid" data-max="2">
  <p>Loading latest projects…</p>
</div>

---

## Live system endpoints

These components make up the self-hosted stack:

- **Workbench UI:** <https://workbench.shafie.org/>  
- **Open WebUI (chat frontend):** {{ config.extra.endpoints.openwebui }}  
- **Kroki (diagram as a service):** {{ config.extra.endpoints.kroki }}  
- **PlantUML server:** {{ config.extra.endpoints.plantuml }}  
- **MkDocs (this site):** <https://docs.shafie.org/>

---

## Where to go next

Create or open a project in the Workbench  

Browse an existing project under **Projects** in the left navigation  

Open the GitHub repo to see how architecture, stories, and code stay in sync
