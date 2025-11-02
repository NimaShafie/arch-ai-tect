Return this JSON unchanged to confirm you understand it; do not add commentary.

{
  "project_name": "<<<PROJECT_NAME>>>",
  "domain": "<<<BUSINESS_DOMAIN>>>",
  "stakeholders": ["End User", "Product Manager", "Engineering", "Ops/Sec"],
  "actors": ["Anonymous Visitor", "Authenticated User", "Admin"],
  "core_capabilities": ["<<<CAP1>>>","<<<CAP2>>>","<<<CAP3>>>"],
  "user_journeys": ["<<<JOURNEY1>>>","<<<JOURNEY2>>>"],
  "constraints": ["student-scale","limited budget","privacy-first"],
  "non_functional": {
    "availability": "target 99.5%",
    "latency_p95": "<<<e.g., <300ms page, <2s start>>>",
    "scalability": "modest burst tolerance",
    "security": ["JWT sessions","OWASP ASVS L1"],
    "observability": ["logs","metrics","traces"]
  },
  "tech_preferences": {
    "frontend": "<<<e.g., React static>>>",
    "backend": "<<<e.g., REST over HTTPS>>>",
    "data": "<<<e.g., KV + relational>>>",
    "media_or_streaming": "<<<if applicable>>>",
    "cloud": "<<<agnostic/AWS/GCP/Azure/on-prem>>>"
  }
}
