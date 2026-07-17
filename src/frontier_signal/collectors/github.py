from __future__ import annotations

import httpx

from .base import Collector
from frontier_signal.schemas import RawItem, SourceConfig
from frontier_signal.settings import settings


class GitHubClient:
    def __init__(self) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "frontier-signal-v1",
        }
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"
        self.client = httpx.Client(base_url="https://api.github.com", headers=headers, timeout=30)

    def get(self, path: str, params: dict | None = None):
        response = self.client.get(path, params=params)
        response.raise_for_status()
        return response.json()


class GitHubRepoCollector(Collector):
    def collect(self, source: SourceConfig) -> list[RawItem]:
        gh = GitHubClient()
        repo = source.config["repo"]
        items: list[RawItem] = []

        if source.config.get("include_releases", True):
            releases = gh.get(f"/repos/{repo}/releases", {"per_page": 10})
            for release in releases:
                body = release.get("body") or ""
                items.append(RawItem(
                    source_id=source.id,
                    source_type=source.type,
                    external_id=f"release:{release['id']}",
                    url=release["html_url"],
                    title=f"{repo} release: {release.get('name') or release.get('tag_name')}",
                    content=body,
                    author_name=(release.get("author") or {}).get("login"),
                    language=source.language,
                    region=source.region,
                    published_at=release.get("published_at"),
                    metadata={
                        "repo": repo,
                        "kind": "release",
                        "tag": release.get("tag_name"),
                        "prerelease": release.get("prerelease", False),
                    },
                ))

        if source.config.get("include_issues", True):
            limit = int(source.config.get("issue_limit", 20))
            issues = gh.get(
                f"/repos/{repo}/issues",
                {
                    "state": source.config.get("issue_state", "open"),
                    "sort": "created",
                    "direction": "desc",
                    "per_page": limit,
                },
            )
            for issue in issues:
                if "pull_request" in issue:
                    continue
                items.append(RawItem(
                    source_id=source.id,
                    source_type=source.type,
                    external_id=f"issue:{issue['id']}",
                    url=issue["html_url"],
                    title=f"{repo} issue: {issue['title']}",
                    content=issue.get("body") or "",
                    author_name=(issue.get("user") or {}).get("login"),
                    language=source.language,
                    region=source.region,
                    published_at=issue.get("created_at"),
                    metadata={
                        "repo": repo,
                        "kind": "issue",
                        "comments": issue.get("comments", 0),
                        "labels": [x["name"] for x in issue.get("labels", [])],
                    },
                ))
        return items


class GitHubOrgCollector(Collector):
    def collect(self, source: SourceConfig) -> list[RawItem]:
        gh = GitHubClient()
        org = source.config["org"]
        repos = gh.get(
            f"/orgs/{org}/repos",
            {"sort": "updated", "direction": "desc", "per_page": source.config.get("repo_limit", 30)},
        )
        items: list[RawItem] = []
        for repo in repos:
            items.append(RawItem(
                source_id=source.id,
                source_type=source.type,
                external_id=f"repo:{repo['id']}:{repo.get('pushed_at')}",
                url=repo["html_url"],
                title=f"{org} repository activity: {repo['name']}",
                content=repo.get("description") or "",
                author_name=org,
                language=source.language,
                region=source.region,
                published_at=repo.get("pushed_at"),
                metadata={
                    "kind": "repository_activity",
                    "stars": repo.get("stargazers_count", 0),
                    "forks": repo.get("forks_count", 0),
                    "language": repo.get("language"),
                    "topics": repo.get("topics", []),
                },
            ))
        return items
