from .arxiv import ArxivCollector
from .bluesky import BlueskyCollector
from .github import GitHubRepoCollector, GitHubOrgCollector
from .hackernews import HackerNewsCollector
from .openreview import OpenReviewCollector
from .rss import RSSCollector
from .youtube import YouTubeCollector
from .x import XCollector

COLLECTORS = {
    "arxiv": ArxivCollector,
    "rss": RSSCollector,
    "github_repo": GitHubRepoCollector,
    "github_org": GitHubOrgCollector,
    "hackernews": HackerNewsCollector,
    "openreview": OpenReviewCollector,
    "youtube": YouTubeCollector,
    "x": XCollector,
    "bluesky": BlueskyCollector,
}
