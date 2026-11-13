"""Map market guard: every map belongs to the GitHub account that first published it (its "owner" in catalog.json; maps
from before owners belong to the repository's owner). A push that adds a map under someone else's name, or changes or
removes a map its pusher doesn't own, is undone: this script reverts the pushed commits and fails the run.

Runs on every push to the default branch (.github/workflows/guard.yml); GITHUB_ACTOR is the account that pushed."""
import json
import os
import subprocess
import sys


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def catalog_at(commit):
    try:
        return {m["name"]: m for m in json.loads(git("show", f"{commit}:catalog.json")).get("maps", [])}
    except (subprocess.CalledProcessError, ValueError):
        return {}


def map_of(path):
    """The map a file belongs to: maps/<Name>.rtsmap, previews/<Name>.png."""
    for folder, ext in (("maps/", ".rtsmap"), ("previews/", ".png")):
        if path.startswith(folder) and path.endswith(ext):
            return path[len(folder):-len(ext)]
    return None


def main():
    before, after = os.environ["BEFORE"], os.environ["AFTER"]
    actor = os.environ["GITHUB_ACTOR"]
    repo_owner = os.environ["GITHUB_REPOSITORY"].split("/")[0]
    if set(before) == {"0"}:
        print("First push: nothing to check.")
        return 0
    old, new = catalog_at(before), catalog_at(after)
    owner = lambda entry: entry.get("owner") or repo_owner
    touched = set()
    for path in git("diff", "--name-only", before, after).split():
        name = map_of(path)
        if name:
            touched.add(name)
    for name in set(old) | set(new):
        if old.get(name) != new.get(name):
            touched.add(name)
    problems = []
    for name in sorted(touched):
        if name in old:
            if owner(old[name]) != actor:
                problems.append(f"{name} belongs to {owner(old[name])}, not {actor}")
            elif name in new and owner(new[name]) != actor:
                problems.append(f"{name}: its owner can't be handed to {owner(new[name])} by a push")
        elif name in new and owner(new[name]) != actor:
            problems.append(f"{name} is new but names {owner(new[name])} as its owner, not {actor}")
    if not problems:
        print(f"OK: {actor} changed only their own maps ({', '.join(sorted(touched)) or 'none'}).")
        return 0
    print("Undoing this push:\n  " + "\n  ".join(problems))
    git("config", "user.name", "map-market-guard")
    git("config", "user.email", "map-market-guard@users.noreply.github.com")
    git("revert", "--no-edit", f"{before}..{after}")
    git("push", "origin", "HEAD")
    return 1


if __name__ == "__main__":
    sys.exit(main())
