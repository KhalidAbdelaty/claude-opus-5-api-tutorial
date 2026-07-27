import subprocess

MSG = """Show the brand mark only when the sidebar is collapsed

The sidebar already carries the wordmark, so the mark in the main column was
redundant and left an empty paragraph block above the hero. It now lives inside
the hero div and is revealed via the sidebar's aria-expanded attribute.

Streamlit renders the sidebar expand button inside the toolbar, which the app
was hiding wholesale, so a collapsed sidebar could not be reopened. The toolbar
stays hidden but the button's visibility is restored on the child.
"""


def git(*args: str) -> str:
    out = subprocess.run(["git", *args], capture_output=True, text=True, check=True)
    return out.stdout.strip()


git("add", "-A")
tree = git("write-tree")
parent = git("rev-parse", "HEAD")
commit = git("commit-tree", tree, "-p", parent, "-m", MSG)
git("update-ref", "HEAD", commit)
print(git("log", "-1", "--format=%H%n%B"))
