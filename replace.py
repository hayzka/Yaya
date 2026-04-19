import os

replacements = {
    "client": "supabase",
    "userSession.id": "currentUser.id",
    "music_posts": "posts"
}

for root, dirs, files in os.walk("."):
    for file in files:
        if file.endswith(".js") or file.endswith(".html"):
            path = os.path.join(root, file)
            
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            for old, new in replacements.items():
                content = content.replace(old, new)

            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

print("Done replace all!")
