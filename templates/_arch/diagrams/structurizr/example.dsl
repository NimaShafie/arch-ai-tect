workspace "{{TITLE}}" "{{TITLE}} Architecture" {
  model {
    user = person "User"
    system = softwareSystem "{{TITLE}} Core Service" "High-level responsibility"
    user -> system "Uses"
  }
  views {
    systemContext system "Context" {
      include *
      autoLayout lr
    }
  }
}
