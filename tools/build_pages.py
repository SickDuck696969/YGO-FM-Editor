"""Assemble the public site from an explicit allowlist. Never copy local game files."""
import ast
import concurrent.futures
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "dist" / "pages"
RUNTIME = "https://cdn.jsdelivr.net/pyodide/v0.27.7/full/"
CORE = "canonical_card_names card_data cards cdrom fusions card_graphics card_list_icons legacy_frame_patch engine_patches duel_rewards".split()
EDITOR = "disc bps memory_card save_data portraits".split()


RUNTIME_HASHES = {
    "pyodide-lock.json": "9c45b916001a750f4102fc287494f3eab215909c7535c626a20db80fd6333e2c",
    "pyodide.asm.js": "6b4c90de5b7172873f04f21884d0e9d2274e305fe32116558fe3e4fbe3618d51",
    "pyodide.asm.wasm": "a50dd1843f805a0b7c45b61037ee0d7b26dfe85efe0e18ef95a34ad24e401f5f",
    "pyodide.js": "b4cb23a53aba19c221659b9fb40a2f18281d685691dc06647fb0afd0681baf98",
    "python_stdlib.zip": "16611534726e5d8ac2bd8f926410b2dcb8d6f49aa24913463533b457a2115c16"
}


def fetch(name, digest):
    target = SITE / "runtime" / name
    if not target.exists() or (digest and hashlib.sha256(target.read_bytes()).hexdigest() != digest):
        with urllib.request.urlopen(RUNTIME + name, timeout=90) as response:
            data = response.read()
        if digest and hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f"Checksum mismatch for {name}")
        target.write_bytes(data)


def build():
    (SITE / "runtime").mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "studio.css", "app.js", "recipes-drops.js", "saves-export.js", "worker.js", "disc-output.js"):
        shutil.copyfile(ROOT / "web" / name, SITE / name)
    shutil.copyfile(ROOT / "THIRD_PARTY_LICENSE.txt", SITE / "THIRD_PARTY_LICENSE.txt")
    with zipfile.ZipFile(SITE / "editor.zip", "w", zipfile.ZIP_DEFLATED) as bundle:
        for package, modules in (("core", CORE), ("fm_editor", EDITOR)):
            bundle.writestr(f"{package}/__init__.py", "")
            for module in modules:
                path = f"{package}/{module}.py"
                bundle.write(ROOT / path, path)
        bundle.write(ROOT / "web" / "bridge.py", "bridge.py")
    appearance = ast.parse((ROOT / "fm_editor/appearance.py").read_text(encoding="utf-8-sig"))
    palettes = next(n.value for n in appearance.body if isinstance(n, ast.Assign) and n.targets[0].id == "THEMES")
    themes = {k.value: [arg.value for arg in v.args] for k, v in zip(palettes.keys, palettes.values)}
    (SITE / "themes.json").write_text(json.dumps(themes), encoding="utf-8")
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(fetch, RUNTIME_HASHES, RUNTIME_HASHES.values()))
    lock = json.loads((SITE / "runtime/pyodide-lock.json").read_text())["packages"]
    needed = set()
    def include(name):
        if name not in needed:
            needed.add(name)
            for dependency in lock[name]["depends"]:
                include(dependency)
    include("pillow")
    for name in sorted(needed):
        fetch(lock[name]["file_name"], lock[name]["sha256"])
    print(SITE)


if __name__ == "__main__":
    build()
