#!/usr/bin/env python
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

def eprint(*args):
    print(*args, file=sys.stderr)

def run(cmd, cwd=None, env=None, check=True):
    eprint("+", " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd, env=env, check=check)

def capture(cmd, cwd=None, env=None):
    r = subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        return ""
    return r.stdout.strip()

def need_cmd(name: str):
    if shutil.which(name) is None:
        eprint(f"Missing required command: {name}")
        sys.exit(1)

def ask(prompt: str, default: str | None = None) -> str:
    if default is not None and default != "":
        raw = input(f"{prompt} [{default}]: ").strip()
        return raw if raw else default
    raw = input(f"{prompt}: ").strip()
    return raw

def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"^-+|-+$", "", s)
    return s

def config_paths():
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    cfg_dir = base / "gittaku"
    cfg_file = cfg_dir / "settings.json"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_file

def read_settings(cfg_file: Path) -> dict:
    if not cfg_file.exists():
        return {}
    try:
        return json.loads(cfg_file.read_text(encoding="utf-8"))
    except Exception:
        return {}

def write_settings(cfg_file: Path, settings: dict):
    cfg_file.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")

def ensure_louder_global(louder_dir: Path):
    # Create/update global louder wrapper around wouter.
    louder_dir.mkdir(parents=True, exist_ok=True)

    pkg = {
        "name": "louder",
        "version": "0.0.1",
        "private": True,
        "main": "index.js",
        "types": "index.d.ts",
        "dependencies": {
            "wouter": "^3.3.0"
        }
    }
    (louder_dir / "package.json").write_text(json.dumps(pkg, indent=2) + "\n", encoding="utf-8")

    (louder_dir / "index.js").write_text(
        'export * from "wouter";\nexport { default } from "wouter";\n',
        encoding="utf-8"
    )
    (louder_dir / "index.d.ts").write_text(
        'export * from "wouter";\nexport { default } from "wouter";\n',
        encoding="utf-8"
    )

    # Install deps in louder_dir if needed
    need_cmd("npm")
    run(["npm", "install"], cwd=str(louder_dir))

def patch_app_package_json(app_dir: Path, louder_path: Path, include_routes: list[str]):
    pj = app_dir / "package.json"
    data = json.loads(pj.read_text(encoding="utf-8"))

    deps = data.get("dependencies", {})
    # Louder as file dependency to your global path:
    deps["louder"] = f"file:{louder_path}"
    deps.setdefault("react-helmet-async", "^2.0.5")
    deps.setdefault("react-snap", "^1.23.0")
    data["dependencies"] = deps

    scripts = data.get("scripts", {})
    scripts["postbuild"] = "react-snap"
    data["scripts"] = scripts

    data["reactSnap"] = {
        "include": include_routes,
        "inlineCss": True,
        "minifyHtml": True
    }

    pj.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

def write_app_files(app_dir: Path):
    src = app_dir / "src"
    (src / "content").mkdir(parents=True, exist_ok=True)
    (src / "pages").mkdir(parents=True, exist_ok=True)

    (src / "content" / "lakes.json").write_text(
        json.dumps([
            {"id": "superior", "name": "Lake Superior", "tagline": "Cold. Huge. Legendary.", "description": "The largest of the Great Lakes by surface area."},
            {"id": "tahoe", "name": "Lake Tahoe", "tagline": "Blue glass in the mountains.", "description": "An alpine lake on the California–Nevada border."},
            {"id": "pontchartrain", "name": "Lake Pontchartrain", "tagline": "Wide water, big sky.", "description": "A brackish estuary in Louisiana."}
        ], indent=2) + "\n",
        encoding="utf-8"
    )

    (src / "index.js").write_text(
        """import React from "react";
import ReactDOM from "react-dom/client";
import { HelmetProvider } from "react-helmet-async";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <HelmetProvider>
      <App />
    </HelmetProvider>
  </React.StrictMode>
);
""",
        encoding="utf-8"
    )

    (src / "pages" / "Lakes.js").write_text(
        """import React from "react";
import { Link } from "louder";
import { Helmet } from "react-helmet-async";
import lakes from "../content/lakes.json";

export default function Lakes() {
  return (
    <div style={{ padding: 24, fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif" }}>
      <Helmet>
        <title>Lakes</title>
        <meta name="description" content="Browse lakes. Static HTML output with dynamic routes." />
      </Helmet>

      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontWeight: 800, letterSpacing: 0.3 }}>taku</div>
        <nav style={{ display: "flex", gap: 12 }}>
          <Link href="/lakes">Lakes</Link>
        </nav>
      </header>

      <h1 style={{ marginTop: 24 }}>Lakes</h1>
      <ul>
        {lakes.map((l) => (
          <li key={l.id}>
            <Link href={`/lake/${l.id}`}>{l.name}</Link> — {l.tagline}
          </li>
        ))}
      </ul>
    </div>
  );
}
""",
        encoding="utf-8"
    )

    (src / "pages" / "Lake.js").write_text(
        """import React from "react";
import { Link, Route } from "louder";
import { Helmet } from "react-helmet-async";
import lakes from "../content/lakes.json";

function LakePage({ lakeId }) {
  const lake = lakes.find((x) => x.id === lakeId);

  if (!lake) {
    return (
      <div style={{ padding: 24, fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif" }}>
        <Helmet>
          <title>Lake Not Found</title>
          <meta name="robots" content="noindex" />
        </Helmet>
        <h1>Not found</h1>
        <p>No lake named “{lakeId}”.</p>
        <p><Link href="/lakes">Back to Lakes</Link></p>
      </div>
    );
  }

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif" }}>
      <Helmet>
        <title>{lake.name}</title>
        <meta name="description" content={lake.tagline} />
        <meta property="og:title" content={lake.name} />
        <meta property="og:description" content={lake.tagline} />
      </Helmet>

      <p><Link href="/lakes">← All Lakes</Link></p>
      <h1 style={{ marginTop: 8 }}>{lake.name}</h1>
      <p style={{ fontSize: 18, opacity: 0.85 }}>{lake.tagline}</p>
      <p style={{ lineHeight: 1.6 }}>{lake.description}</p>
    </div>
  );
}

export default function Lake() {
  return (
    <Route path="/lake/:lakeId">
      {(params) => <LakePage lakeId={params.lakeId} />}
    </Route>
  );
}
""",
        encoding="utf-8"
    )

    (src / "App.js").write_text(
        """import React from "react";
import { Switch, Route } from "louder";
import Lakes from "./pages/Lakes";
import Lake from "./pages/Lake";

export default function App() {
  return (
    <Switch>
      <Route path="/" component={Lakes} />
      <Route path="/lakes" component={Lakes} />
      <Route path="/lake/:lakeId" component={Lake} />
      <Route>
        <Lakes />
      </Route>
    </Switch>
  );
}
""",
        encoding="utf-8"
    )

def ensure_git(app_dir: Path):
    need_cmd("git")
    run(["git", "init"], cwd=str(app_dir))
    run(["git", "add", "-A"], cwd=str(app_dir))
    # commit may fail if nothing changed; that's fine
    subprocess.run(["git", "commit", "-m", "chore(taku): initial commit"], cwd=str(app_dir))

    default_branch = capture(["git", "config", "--get", "init.defaultBranch"], cwd=str(app_dir)) or "main"
    run(["git", "branch", "-M", default_branch], cwd=str(app_dir))

def gh_repo_create_and_push(app_dir: Path, full_repo: str, visibility: str, desc: str):
    need_cmd("gh")
    if subprocess.run(["gh", "auth", "status"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        eprint("GitHub CLI is not authenticated. Run: gh auth login")
        sys.exit(1)

    args = ["gh", "repo", "create", full_repo, f"--{visibility}", "--source=.", "--remote=origin", "--push"]
    if desc.strip():
        args += ["--description", desc.strip()]
    run(args, cwd=str(app_dir))

def main():
    need_cmd("node")
    need_cmd("npm")
    need_cmd("npx")
    need_cmd("git")
    need_cmd("gh")

    eprint("taku (react-scripts scaffold)")

    cfg_file = config_paths()
    settings = read_settings(cfg_file)
    cached_owner = settings.get("github_owner", "")

    raw_app = sys.argv[1] if len(sys.argv) > 1 else ""
    if not raw_app:
        raw_app = ask("App name (human-friendly)", "my-app")

    app_slug = slugify(raw_app)
    if not app_slug:
        eprint("App name slugified to empty string. Try a different name.")
        sys.exit(1)

    dir_default = app_slug
    dir_name = ask("Folder to create", dir_default) or dir_default
    app_dir = (Path.cwd() / dir_name).resolve()

    if app_dir.exists():
        eprint(f"Path already exists: {app_dir}")
        sys.exit(1)

    owner = ask("GitHub owner (user or org)", cached_owner).strip()
    repo = slugify(ask("GitHub repo name", app_slug))
    if not repo:
        eprint("Repo name invalid.")
        sys.exit(1)

    visibility = ask("Repo visibility (private/public)", "private").strip().lower()
    if visibility not in ("private", "public"):
        eprint("Visibility must be 'private' or 'public'.")
        sys.exit(1)

    desc = ask("Repo description", "").strip()

    # Ensure global louder wrapper exists at ~/test/louder
    louder_path = (Path.home() / "test" / "louder").resolve()
    ensure_louder_global(louder_path)

    # CRA scaffold (JS)
    run(["npx", "--yes", "create-react-app", str(app_dir)])

    # Patch app package.json to use louder + react-snap + helmet
    include_routes = ["/", "/lakes", "/lake/superior", "/lake/tahoe", "/lake/pontchartrain"]
    patch_app_package_json(app_dir, louder_path, include_routes)

    # Write app files for lakes + louder routing + helmet
    write_app_files(app_dir)

    # Install deps after package.json changes
    run(["npm", "install"], cwd=str(app_dir))

    # Git + GH
    ensure_git(app_dir)
    full_repo = f"{owner}/{repo}" if owner else repo
    gh_repo_create_and_push(app_dir, full_repo, visibility, desc)

    # Save owner to config
    if owner:
        settings["github_owner"] = owner
        write_settings(cfg_file, settings)

    eprint("Done.")
    eprint(f"Repo: {full_repo}")

if __name__ == "__main__":
    main()
