from pathlib import Path

root = Path(__file__).resolve().parents[1]
for folder in ["src", "tests"]:
    files = list((root / folder).rglob("*.py"))
    count = sum(
        sum(
            bool(line.strip()) and not line.lstrip().startswith("#")
            for line in p.read_text(encoding="utf-8-sig").splitlines()
        )
        for p in files
    )
    print(f"{folder}: {len(files)} Python files, {count} nonblank noncomment lines")
