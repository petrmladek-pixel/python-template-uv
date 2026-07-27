"""Review the current pull request diff with Gemini and post a GitHub comment."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from google import genai
from google.genai import errors, types

DEFAULT_MODEL = "gemini-3.1-flash-lite"
SYSTEM_PROMPT = """Jsi Senior Python Architekt. Tvým úkolem je revidovat kód v 
Pull Requestu.
ZÁKLADNÍ PRAVIDLA:
Ignoruj formátování, importy, mezery a PEP8. (To už vyřešil Ruff před tebou).
Soustřeď se na 'Big Picture': logické chyby, chybějící ošetření chyb (try-except), 
bezpečnostní rizika (API klíče v kódu), nebo zbytečně složitou implementaci.
Buď pragmatický freelancer: Nekritizuj věci, které jsou věcí vkusu. 
Kritizuj to, co může způsobit pád v produkci nebo budoucí technický dluh.
Priority: Pokud je chyba kritická, označ ji 🔴. Pokud je to jen doporučení, označ ho 💡.
Stručnost: Pokud je kód v pořádku, napiš jen: '✅ Kód je čistý a připraven k mergi.'
Tón: Konstruktivní, stručný, kolegiální."""
MAX_GITHUB_COMMENT_LENGTH = 60_000


def get_git_diff(base_branch: str = "main") -> str:
    """Return the merge-base diff between the base branch and HEAD."""
    base_revision = _resolve_base_revision(base_branch)
    result = subprocess.run(
        [
            "git",
            "diff",
            "--no-ext-diff",
            "--no-color",
            f"{base_revision}...HEAD",
            "--",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout


def review_diff(diff: str, api_key: str) -> str:
    """Send a git diff to Gemini and return its review text."""
    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(
            model=os.environ.get("GEMINI_REVIEW_MODEL", DEFAULT_MODEL),
            contents=diff,
            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
        )
    except errors.APIError as exc:
        message = " ".join(str(exc.message).split())[:500]
        raise RuntimeError(
            f"Gemini review failed with status {exc.code}: {message}"
        ) from exc
    if not response.text:
        raise RuntimeError("Gemini returned an empty review")
    return response.text.strip()


def get_pull_request_context() -> tuple[str, int]:
    """Read the repository and pull request number from the GitHub event payload."""
    event_path = Path(_required_environment("GITHUB_EVENT_PATH"))
    try:
        event: dict[str, Any] = json.loads(event_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read GitHub event payload: {exc}") from exc

    pull_request = event.get("pull_request")
    if not isinstance(pull_request, dict) or not isinstance(
        pull_request.get("number"), int
    ):
        raise RuntimeError("The GitHub event is not associated with a pull request")

    repository = os.environ.get("GITHUB_REPOSITORY")
    if not repository:
        repository_data = event.get("repository")
        if isinstance(repository_data, dict):
            repository = repository_data.get("full_name")
    if not isinstance(repository, str) or not repository:
        raise RuntimeError("Could not determine the GitHub repository")

    return repository, pull_request["number"]


def post_pull_request_comment(
    repository: str,
    pull_request_number: int,
    comment: str,
) -> None:
    """Post a pull request issue comment using the GitHub REST API."""
    github_token = os.environ["GITHUB_TOKEN"]
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    url = f"{api_url}/repos/{repository}/issues/{pull_request_number}/comments"
    body = comment[:MAX_GITHUB_COMMENT_LENGTH]
    if len(comment) > MAX_GITHUB_COMMENT_LENGTH:
        body += "\n\n_Review truncated to fit the GitHub comment limit._"

    request = Request(
        url,
        data=json.dumps({"body": body}).encode("utf-8"),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {github_token}",
            "Content-Type": "application/json",
            "User-Agent": "ai-engine-ai-reviewer",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            if response.status != 201:
                raise RuntimeError(
                    f"GitHub returned unexpected status {response.status}"
                )
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")[:1_000]
        raise RuntimeError(
            f"GitHub comment request failed with status {exc.code}: {error_body}"
        ) from exc


def main() -> None:
    """Run the AI review workflow for the current pull request."""
    _required_environment("GITHUB_TOKEN")
    gemini_api_key = _required_environment("GEMINI_API_KEY")
    base_branch = os.environ.get("GITHUB_BASE_REF", "main")

    diff = get_git_diff(base_branch)
    if not diff.strip():
        print("No changes found between the current branch and the base branch.")
        return

    repository, pull_request_number = get_pull_request_context()
    review = review_diff(diff, gemini_api_key)
    post_pull_request_comment(repository, pull_request_number, review)
    print(f"AI review posted to {repository}#{pull_request_number}.")


def _resolve_base_revision(base_branch: str) -> str:
    for revision in (f"origin/{base_branch}", base_branch):
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", revision],
            check=False,
            capture_output=True,
        )
        if result.returncode == 0:
            return revision
    raise RuntimeError(
        f"Base branch '{base_branch}' is unavailable. Check out the repository "
        "with full history before running the reviewer."
    )


def _required_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.SubprocessError) as exc:
        print(f"AI reviewer failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
