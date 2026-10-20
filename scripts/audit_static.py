"""Inventário estático de referências/duplicações, sem importar app ou acessar banco.

Candidatos sem referência textual não são considerados mortos: handlers HTML,
exports globais, URLs externas e carregamento manual podem ser consumidores.
"""
from collections import Counter, defaultdict
from html.parser import HTMLParser
import ast
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend/src"


class References(HTMLParser):
    """Coleta IDs e recursos locais cuja existência pode ser validada."""
    def __init__(self):
        super().__init__()
        self.ids = []
        self.assets = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"])
        if tag in {"script", "link", "img"}:
            self.assets.append(values.get("src") or values.get("href") or "")


def audit():
    """Retorna achados estruturais, sem supor equivalência entre regras CSS."""
    missing, duplicate_ids = [], []
    css_rules = defaultdict(list)
    globals_ = defaultdict(list)
    files = sorted(p for p in FRONTEND.rglob("*") if p.is_file())
    for path in files:
        if path.suffix not in {".html", ".css", ".js"}:
            continue
        source = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT).as_posix()
        if path.suffix == ".html":
            parser = References()
            parser.feed(source)
            for name, count in Counter(parser.ids).items():
                if count > 1:
                    duplicate_ids.append({"file": relative, "id": name, "count": count})
            for ref in parser.assets:
                url = urlparse(urljoin("http://local/" + path.relative_to(FRONTEND).as_posix(), ref))
                if url.netloc == "local" and not (FRONTEND / url.path.lstrip("/")).is_file():
                    missing.append({"file": relative, "asset": ref})
        elif path.suffix == ".css":
            clean = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
            # Inventário textual de blocos sem aninhamento; não é um parser CSS.
            for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", clean):
                rule = re.sub(r"\s+", " ", match.group(0)).strip()
                css_rules[rule].append(relative)
        elif "/pages/sistema/" in relative:
            for name in re.findall(r"^\s*(?:async\s+)?function\s+(\w+)\s*\(", source, re.M):
                globals_[name].append(relative)
    source = (ROOT / "backend/app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    uses = Counter(node.id for node in ast.walk(tree) if isinstance(node, ast.Name))
    unused_imports = sorted({alias.asname or alias.name for node in ast.walk(tree)
                             if isinstance(node, (ast.Import, ast.ImportFrom))
                             for alias in node.names if not uses[(alias.asname or alias.name).split(".")[0]]})
    duplicates = [{"selector": rule.split("{")[0].strip(), "occurrences": len(paths), "files": sorted(set(paths))}
                  for rule, paths in css_rules.items() if len(set(paths)) > 1]
    return {"html_files": sum(p.suffix == ".html" for p in files),
            "missing_assets": missing, "duplicate_html_ids": duplicate_ids,
            "unused_backend_imports": unused_imports,
            "shared_css_blocks": len(duplicates),
            "shared_css_examples": sorted(duplicates, key=lambda r: -r["occurrences"])[:15],
            "repeated_page_function_names": {name: paths for name, paths in globals_.items() if len(paths) > 1}}


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
