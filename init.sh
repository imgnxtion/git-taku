#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/gittaku"
CONFIG_FILE="$CONFIG_DIR/settings.json"
mkdir -p "$CONFIG_DIR"
owner="$(load_owner)"

load_owner() {
	[[ -f "$CONFIG_FILE" ]] || return 0
	python - <<PY
import json, pathlib
p = pathlib.Path("$CONFIG_FILE")
try:
  d = json.loads(p.read_text(encoding="utf-8"))
  v = d.get("github_owner", "")
  if isinstance(v, str):
    print(v)
except Exception:
  pass
PY
}

save_owner() {
	local owner="$1"
	python - <<PY
import json, pathlib
p = pathlib.Path("$CONFIG_FILE")
data = {}
if p.exists():
  try:
    data = json.loads(p.read_text(encoding="utf-8"))
  except Exception:
    data = {}
data["github_owner"] = "$owner"
p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
}

ask() {
	local prompt="$1"
	local def="${2-}"
	local out
	if [[ -n "$def" ]]; then
		printf "%s [%s]: " "$prompt" "$def" >&2
	else
		printf "%s: " "$prompt" >&2
	fi
	IFS= read -r out || true
	if [[ -z "${out}" && -n "${def}" ]]; then
		out="$def"
	fi
	printf "%s" "$out"
}

slugify() {
	printf "%s" "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//'
}

need_cmd() {
	command -v "$1" >/dev/null 2>&1 || {
		echo "Missing required command: $1" >&2
		exit 1
	}
}

need_cmd git

echo "taku (react-scripts scaffold)" >&2

raw_app="${1-}"
if [[ -z "$raw_app" ]]; then
	raw_app="$(ask "App name (human-friendly)" "my-app")"
fi

app_slug="$(slugify "$raw_app")"
if [[ -z "$app_slug" ]]; then
	echo "App name slugified to empty string. Try a different name." >&2
	exit 1
fi

dir_default="$app_slug"
dir="$(ask "Folder to create" "$dir_default")"
dir="${dir:-$dir_default}"

if [[ -e "$dir" ]]; then
	echo "Path already exists: $dir" >&2
	exit 1
fi

use_ts="$(ask "Use TypeScript? (y/n)" "y")"
case "$(printf "%s" "$use_ts" | tr '[:upper:]' '[:lower:]')" in
y | yes) ts=1 ;;
*) ts=0 ;;
esac

owner="$(ask "GitHub owner (user or org)" "")"
repo_default="$app_slug"
repo="$(ask "GitHub repo name" "$repo_default")"
repo="$(slugify "$repo")"
if [[ -z "$repo" ]]; then
	echo "Repo name invalid." >&2
	exit 1
fi

visibility="$(ask "Repo visibility (private/public)" "private")"
visibility="$(printf "%s" "$visibility" | tr '[:upper:]' '[:lower:]')"
case "$visibility" in
private | public) ;;
*)
	echo "Visibility must be 'private' or 'public'." >&2
	exit 1
	;;
esac

desc="$(ask "Repo description" "")"

need_cmd node
need_cmd npm

if command -v gh >/dev/null 2>&1; then
	:
else
	echo "Missing required command: gh (GitHub CLI). Install it to auto-create/push repos." >&2
	exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
	echo "GitHub CLI is not authenticated. Run: gh auth login" >&2
	exit 1
fi

template_arg=()
if [[ "$ts" -eq 1 ]]; then
	template_arg=(--template typescript)
fi

if [[ "$ts" -eq 1 ]]; then
	npx --yes create-react-app "$dir" --template typescript
else
	npx --yes create-react-app "$dir"
fi

cd "$dir"

if [[ -n "$desc" ]]; then
	if command -v python >/dev/null 2>&1; then
		python - <<'PY'
import json, pathlib, os
p = pathlib.Path("package.json")
d = json.loads(p.read_text(encoding="utf-8"))
desc = os.environ.get("TAKU_DESC","")
if desc:
  d["description"] = desc
p.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
PY
	else
		:
	fi
fi

if [[ -n "$desc" ]]; then
	export TAKU_DESC="$desc"
fi

git init
git add -A
git commit -m "chore(taku): initial commit" >/dev/null 2>&1 || git commit -m "chore(taku): initial commit"

default_branch="$(git config --get init.defaultBranch || true)"
if [[ -z "$default_branch" ]]; then
	default_branch="main"
fi
git branch -M "$default_branch"

full_repo="$repo"
if [[ -n "$owner" ]]; then
	full_repo="$owner/$repo"
fi

gh_args=(repo create "$full_repo" "--$visibility" --source=. --remote=origin --push)
if [[ -n "$desc" ]]; then
	gh_args+=(--description "$desc")
fi
gh "${gh_args[@]}"

echo "Done." >&2
echo "Repo: $full_repo" >&2
