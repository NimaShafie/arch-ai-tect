from server.services.mkdocs_nav import build_nav

print("Running build_nav() before starting mkdocs serve...")
build_nav()
print("Done.")

