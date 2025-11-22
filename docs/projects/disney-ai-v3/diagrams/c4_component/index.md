# Disney+Ai+ V3 · C4 Component

> Source is embedded below and rendered via Kroki/PlantUML.

```plantuml
@startuml
!includeurl https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Component.puml
LAYOUT_WITH_LEGEND()

title {{TITLE}} — Component (Service internals)

Container_Boundary(svc, "Service") {
  Component(controller, "Controller")
  Component(domain, "Domain")
  Component(adapter, "Adapter")
}
Rel(controller, domain, "Orchestrates")
Rel(domain, adapter, "Uses")

SHOW_LEGEND()
@enduml
```
