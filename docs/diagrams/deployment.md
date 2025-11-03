# High-Level Deployment

```plantuml
@startuml
title SMT Deployment (High-Level)

node "User Device" {
  component "Browser" as Browser
  component "iOS App" as IOS
}

node "Edge" {
  artifact "Cloudflare Tunnel / Proxy\nTLS" as Edge
}

node "App Server" {
  component "Frontend (Next.js)" as FE
  component "Backend (Node/Express)" as BE
}

node "Data" {
  database "MySQL" as DB
  component "Redis (cache)" as Cache
}

Browser --> Edge : HTTPS
IOS --> Edge     : HTTPS
Edge --> FE      : HTTP (internal)
FE --> BE        : HTTP (internal)
BE --> DB        : TCP 3306
BE --> Cache     : TCP 6379
@enduml
```
