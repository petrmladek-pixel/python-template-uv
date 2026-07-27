import sys
from pathlib import Path

# 1. Získání názvu projektu
project_name = sys.argv[1] if len(sys.argv) > 1 else "portfolio_assistant"
project_slug = project_name.lower().replace("-", "_")

template_file = Path("MASTER_TEMPLATE.md")
if not template_file.exists():
    print("❌ Soubor MASTER_TEMPLATE.md nenalezen v aktuální složce!")
    sys.exit(1)

content = template_file.read_text(encoding="utf-8")
content = content.replace("{{ project_name }}", project_slug)
content = content.replace("{{ project_description }}", f"Project {project_slug}")

lines = content.splitlines()

current_file = None
in_code_block = False
code_buffer = []
extracted_count = 0

print(f"📂 Čtu MASTER_TEMPLATE.md a generuji projekt: '{project_slug}'...\n")

for line in lines:
    # 1. Detekce nadpisu (## nebo ###) mimo kódový blok
    if (line.startswith("## ") or line.startswith("### ")) and not in_code_block:
        header_text = line.lstrip("#").strip()
        clean_path = header_text.replace("`", "").replace("'", "").replace('"', "").strip()
        
        # Extrakce cesty z nadpisu
        parts = clean_path.split()
        found_path = None
        for part in reversed(parts):
            if "." in part or "/" in part or "\\" in part or part.endswith(".md"):
                found_path = part
                break
        
        current_file = found_path if found_path else clean_path

    # 2. Detekce začátku nebo konce kódového bloku (```)
    elif line.startswith("```"):
        if not in_code_block:
            # Začátek kódového bloku
            in_code_block = True
            code_buffer = []
        else:
            # Konec kódového bloku -> Zápis souboru na disk
            in_code_block = False
            if current_file:
                file_path = Path(current_file)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_content = "\n".join(code_buffer) + "\n"
                file_path.write_text(file_content, encoding="utf-8")
                print(f"  ✓ Vytvořen: {current_file}")
                extracted_count += 1
                current_file = None
    elif in_code_block:
        code_buffer.append(line)

print(f"\n🎉 Hotovo! Celkem úspěšně vygenerováno {extracted_count} souborů pro '{project_slug}'.")