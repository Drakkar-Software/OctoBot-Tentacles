#  Drakkar-Software OctoBot-Tentacles
#  Copyright (c) Drakkar-Software, All rights reserved.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3.0 of the License, or (at your option) any later version.
#
#  This library is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library.
import asyncio
import json
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import octobot_services.constants as services_constants
import octobot_services.enums as services_enums
import octobot_services.services as services


@dataclass
class Tweet:
    """Represents a tweet from Bird CLI JSON output."""
    id: str
    text: str
    author: str
    created_at: str
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    url: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Tweet":
        """Create Tweet from Bird CLI JSON (author can be object {username, name} or string)."""
        author = data.get("author", "")
        if isinstance(author, dict):
            author = author.get("username", author.get("name", ""))
            if author and not author.startswith("@"):
                author = f"@{author}"
        elif not isinstance(author, str):
            author = str(author) if author else ""
        return cls(
            id=str(data.get("id", "")),
            text=data.get("text", ""),
            author=author,
            created_at=data.get("createdAt") or data.get("created_at", ""),
            likes=int(data.get("likeCount", data.get("likes", 0))),
            retweets=int(data.get("retweetCount", data.get("retweets", 0))),
            replies=int(data.get("replyCount", data.get("replies", 0))),
            url=data.get("url", ""),
        )


class BirdService(services.AbstractService):
    BIRD_HELP_URL = "https://github.com/steipete/bird"

    def __init__(self):
        super().__init__()
        self._cli_path: str = "bird"
        self._account: Optional[str] = None
        self._startup_message: str = ""
        self._startup_healthy: bool = False

    def _run_command(self, args: List[str]) -> str:
        """Run a bird CLI command. Blocking."""
        cmd = [self._cli_path] + args
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            if self.logger:
                self.logger.error(f"Bird CLI command failed: {' '.join(cmd)}: {e.stderr}")
            raise
        except subprocess.TimeoutExpired:
            if self.logger:
                self.logger.error(f"Bird CLI command timed out: {' '.join(cmd)}")
            raise

    def _parse_tweets_output(self, output: str) -> List[Tweet]:
        """Parse CLI JSON output: either a list of tweets or { tweets, nextCursor }."""
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return []
        if isinstance(data, list):
            return [Tweet.from_dict(t) for t in data]
        tweets = data.get("tweets", data.get("tweet", []))
        if isinstance(tweets, dict):
            tweets = [tweets]
        return [Tweet.from_dict(t) for t in tweets] if tweets else []

    def _parse_single_tweet(self, output: str) -> Optional[Tweet]:
        """Parse single tweet JSON."""
        try:
            data = json.loads(output)
            return Tweet.from_dict(data) if data else None
        except json.JSONDecodeError:
            return None

    def get_type(self):
        return services_constants.CONFIG_BIRD

    def get_endpoint(self):
        return self

    @staticmethod
    def is_setup_correctly(config):
        return (
            services_constants.CONFIG_CATEGORY_SERVICES in config
            and services_constants.CONFIG_BIRD in config[services_constants.CONFIG_CATEGORY_SERVICES]
            and services_constants.CONFIG_SERVICE_INSTANCE
            in config[services_constants.CONFIG_CATEGORY_SERVICES][services_constants.CONFIG_BIRD]
        )

    def has_required_configuration(self):
        return (
            services_constants.CONFIG_CATEGORY_SERVICES in self.config
            and services_constants.CONFIG_BIRD in self.config[services_constants.CONFIG_CATEGORY_SERVICES]
        )

    async def prepare(self):
        bird_config = self.config.get(services_constants.CONFIG_CATEGORY_SERVICES, {}).get(
            services_constants.CONFIG_BIRD, {}
        )
        self._cli_path = bird_config.get(services_constants.CONFIG_BIRD_CLI_PATH, "bird") or "bird"
        account = bird_config.get(services_constants.CONFIG_BIRD_ACCOUNT, "")
        self._account = account.strip() or None

        def _do_whoami():
            try:
                return self._run_command(["whoami"]).strip()
            except Exception:
                try:
                    return self._run_command(["--version"]).strip()
                except Exception:
                    return ""

        loop = asyncio.get_event_loop()
        try:
            msg = await loop.run_in_executor(None, _do_whoami)
            self._startup_healthy = bool(msg)
            self._startup_message = f"Bird CLI ready: {msg}" if msg else "Bird CLI check completed."
        except Exception as e:
            self._startup_healthy = False
            self._startup_message = ""
            if self.logger:
                self.logger.error(f"Bird CLI startup check failed: {e}")

    def get_successful_startup_message(self):
        return self._startup_message, self._startup_healthy

    def get_fields_description(self):
        return {
            services_constants.CONFIG_BIRD_CLI_PATH: "Path to the Bird CLI binary (default: 'bird' from PATH).",
            services_constants.CONFIG_BIRD_ACCOUNT: "Optional Twitter/X handle for user-tweets, about, etc.",
        }

    def get_default_value(self):
        return {
            services_constants.CONFIG_BIRD_CLI_PATH: "bird",
            services_constants.CONFIG_BIRD_ACCOUNT: "",
        }

    def get_required_config(self):
        return []

    @classmethod
    def get_help_page(cls) -> str:
        return cls.BIRD_HELP_URL

    def get_website_url(self) -> str:
        return self.BIRD_HELP_URL

    def get_read_only_info(self) -> list:
        if not self._account:
            return []
        profile_url = f"https://x.com/{self._account.lstrip('@')}"
        return [
            services.ReadOnlyInfo(
                "Account",
                self._account,
                services_enums.ReadOnlyInfoType.CLICKABLE,
                path=profile_url,
            )
        ]

    @staticmethod
    def build_tweet_url(text: str) -> str:
        """
        Build a URL that opens Twitter/X compose form with pre-filled text.
        When the user clicks the link, the tweet form opens with the text filled in.
        """
        encoded = quote(text, safe="")
        return f"https://twitter.com/intent/tweet?text={encoded}"

    @staticmethod
    def build_reply_url(tweet_id: str, text: str = "") -> str:
        """
        Build a URL that opens Twitter/X reply form for the given tweet.
        When the user clicks the link, the reply form opens (optionally with pre-filled text).
        """
        tid = str(tweet_id).strip()
        if not tid:
            return BirdService.build_tweet_url(text) if text else "https://twitter.com/intent/tweet"
        base = f"https://twitter.com/intent/tweet?in_reply_to={tid}"
        if text:
            base += f"&text={quote(text, safe='')}"
        return base

    def whoami(self) -> str:
        """Return the logged-in Bird CLI account."""
        try:
            return self._run_command(["whoami"]).strip()
        except Exception as e:
            if self.logger:
                self.logger.error(f"Bird whoami failed: {e}")
            return ""

    def check(self) -> str:
        """Return credentials/source info from bird check."""
        try:
            return self._run_command(["check"]).strip()
        except Exception as e:
            if self.logger:
                self.logger.error(f"Bird check failed: {e}")
            return ""

    def read_tweet(self, tweet_id_or_url: str) -> Optional[Tweet]:
        """Read a single tweet by ID or URL."""
        try:
            out = self._run_command(["read", tweet_id_or_url, "--json"])
            return self._parse_single_tweet(out)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Bird read_tweet failed: {e}")
            return None

    def get_timeline(self, limit: int = 20, following_only: bool = False) -> List[Tweet]:
        """Fetch home timeline (bird home -n count [--following] --json)."""
        try:
            args = ["home", "-n", str(limit), "--json"]
            if following_only:
                args.insert(2, "--following")
            out = self._run_command(args)
            return self._parse_tweets_output(out)[:limit]
        except Exception as e:
            if self.logger:
                self.logger.error(f"Bird get_timeline failed: {e}")
            return []

    def get_thread(self, tweet_id: str, max_pages: Optional[int] = None) -> List[Tweet]:
        """Fetch tweet thread (bird thread <id> [--max-pages n] --json)."""
        try:
            args = ["thread", tweet_id, "--json"]
            if max_pages is not None:
                args.extend(["--max-pages", str(max_pages)])
            out = self._run_command(args)
            return self._parse_tweets_output(out)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Bird get_thread failed: {e}")
            return []

    def get_replies(self, tweet_id: str, limit: int = 20, max_pages: Optional[int] = None) -> List[Tweet]:
        """Fetch replies to a tweet (bird replies <id> -n count [--max-pages n] --json)."""
        try:
            args = ["replies", tweet_id, "-n", str(limit), "--json"]
            if max_pages is not None:
                args.extend(["--max-pages", str(max_pages)])
            out = self._run_command(args)
            return self._parse_tweets_output(out)[:limit]
        except Exception as e:
            if self.logger:
                self.logger.error(f"Bird get_replies failed: {e}")
            return []

    def search_tweets(self, query: str, limit: int = 20) -> List[Tweet]:
        """Search tweets (bird search '<query>' -n count --json)."""
        try:
            out = self._run_command(["search", query, "-n", str(limit), "--json"])
            return self._parse_tweets_output(out)[:limit]
        except Exception as e:
            if self.logger:
                self.logger.error(f"Bird search_tweets failed: {e}")
            return []

    def get_mentions(self, limit: int = 20, user: Optional[str] = None) -> List[Tweet]:
        """Fetch mentions (bird mentions -n count [--user @handle] --json)."""
        try:
            args = ["mentions", "-n", str(limit), "--json"]
            if user:
                args.extend(["--user", user])
            out = self._run_command(args)
            return self._parse_tweets_output(out)[:limit]
        except Exception as e:
            if self.logger:
                self.logger.error(f"Bird get_mentions failed: {e}")
            return []

    def get_user_posts(self, limit: int = 20) -> List[Tweet]:
        """Fetch user's tweets (bird user-tweets @handle -n count --json)."""
        handle = self._account or ""
        if not handle:
            if self.logger:
                self.logger.error("Account not set for get_user_posts")
            return []
        try:
            handle = handle if handle.startswith("@") else f"@{handle}"
            out = self._run_command(["user-tweets", handle, "-n", str(limit), "--json"])
            return self._parse_tweets_output(out)[:limit]
        except Exception as e:
            if self.logger:
                self.logger.error(f"Bird get_user_posts failed: {e}")
            return []

    def get_user_replies(self, limit: int = 20) -> List[Tweet]:
        """Fetch user's replies via search from:handle filter:replies."""
        handle = self._account or ""
        if not handle:
            if self.logger:
                self.logger.error("Account not set for get_user_replies")
            return []
        return self.search_tweets(f"from:{handle} filter:replies", limit=limit)

    def scroll_user_posts(
        self, cursor: Optional[str] = None, max_pages: int = 1
    ) -> Dict[str, Any]:
        """Scroll user tweets with pagination (bird user-tweets @handle [--cursor] [--max-pages] --json)."""
        handle = self._account or ""
        if not handle:
            if self.logger:
                self.logger.error("Account not set for scroll_user_posts")
            return {"tweets": [], "next_cursor": None}
        try:
            handle = handle if handle.startswith("@") else f"@{handle}"
            args = ["user-tweets", handle, "--json", "--max-pages", str(max_pages)]
            if cursor:
                args.extend(["--cursor", cursor])
            out = self._run_command(args)
            data = json.loads(out) if out.strip() else {}
            tweets = self._parse_tweets_output(out)
            next_cursor = data.get("nextCursor") or data.get("next_cursor")
            return {"tweets": tweets, "next_cursor": next_cursor}
        except Exception as e:
            if self.logger:
                self.logger.error(f"Bird scroll_user_posts failed: {e}")
            return {"tweets": [], "next_cursor": None}

    def scroll_timeline(self, cursor: Optional[str] = None, max_pages: int = 1) -> Dict[str, Any]:
        """Scroll home timeline; Bird home may not support cursor, return recent tweets."""
        try:
            out = self._run_command(["home", "-n", "20", "--json"])
            tweets = self._parse_tweets_output(out)
            return {"tweets": tweets, "next_cursor": None}
        except Exception as e:
            if self.logger:
                self.logger.error(f"Bird scroll_timeline failed: {e}")
            return {"tweets": [], "next_cursor": None}

    def scroll_search(
        self, query: str, cursor: Optional[str] = None, max_pages: int = 1
    ) -> Dict[str, Any]:
        """Scroll search results (bird search '<query>' [--cursor] [--max-pages] --json)."""
        try:
            args = ["search", query, "--json", "--max-pages", str(max_pages)]
            if cursor:
                args.extend(["--cursor", cursor])
            else:
                args.append("--all")
            out = self._run_command(args)
            data = json.loads(out) if out.strip() else {}
            tweets = self._parse_tweets_output(out)
            next_cursor = data.get("nextCursor") or data.get("next_cursor")
            return {"tweets": tweets, "next_cursor": next_cursor}
        except Exception as e:
            if self.logger:
                self.logger.error(f"Bird scroll_search failed: {e}")
            return {"tweets": [], "next_cursor": None}

    def get_bookmarks(
        self,
        limit: int = 20,
        folder_id: Optional[str] = None,
        max_pages: Optional[int] = None,
    ) -> List[Tweet]:
        """Fetch bookmarks (bird bookmarks -n count [--folder-id id] [--max-pages n] --json)."""
        try:
            args = ["bookmarks", "-n", str(limit), "--json"]
            if folder_id:
                args.extend(["--folder-id", folder_id])
            if max_pages is not None:
                args.extend(["--max-pages", str(max_pages)])
            out = self._run_command(args)
            return self._parse_tweets_output(out)[:limit]
        except Exception as e:
            if self.logger:
                self.logger.error(f"Bird get_bookmarks failed: {e}")
            return []

    def get_likes(self, limit: int = 20, max_pages: Optional[int] = None) -> List[Tweet]:
        """Fetch liked tweets (bird likes -n count [--max-pages n] --json)."""
        try:
            args = ["likes", "-n", str(limit), "--json"]
            if max_pages is not None:
                args.extend(["--max-pages", str(max_pages)])
            out = self._run_command(args)
            return self._parse_tweets_output(out)[:limit]
        except Exception as e:
            if self.logger:
                self.logger.error(f"Bird get_likes failed: {e}")
            return []

    def get_news(
        self,
        limit: int = 10,
        ai_only: bool = False,
        with_tweets: bool = False,
        tabs: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch news/trending (bird news -n count [--ai-only] [--with-tweets] [--for-you|--news-only|...] --json)."""
        try:
            args = ["news", "-n", str(limit), "--json"]
            if ai_only:
                args.append("--ai-only")
            if with_tweets:
                args.append("--with-tweets")
            if tabs:
                for t in tabs:
                    if t in ("for-you", "news-only", "sports", "entertainment", "trending-only"):
                        args.append(f"--{t}")
            out = self._run_command(args)
            data = json.loads(out) if out.strip() else []
            return data if isinstance(data, list) else data.get("news", data.get("items", []))
        except Exception as e:
            if self.logger:
                self.logger.error(f"Bird get_news failed: {e}")
            return []

    def get_list_timeline(
        self,
        list_id_or_url: str,
        limit: int = 20,
        max_pages: Optional[int] = None,
    ) -> List[Tweet]:
        """Fetch list timeline (bird list-timeline <id|url> -n count [--max-pages n] --json)."""
        try:
            args = ["list-timeline", list_id_or_url, "-n", str(limit), "--json"]
            if max_pages is not None:
                args.extend(["--max-pages", str(max_pages)])
            out = self._run_command(args)
            return self._parse_tweets_output(out)[:limit]
        except Exception as e:
            if self.logger:
                self.logger.error(f"Bird get_list_timeline failed: {e}")
            return []

    def get_following(
        self,
        user_id_or_handle: Optional[str] = None,
        limit: int = 20,
        max_pages: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch following list (bird following [--user id] -n count [--max-pages n] --json)."""
        try:
            args = ["following", "-n", str(limit), "--json"]
            if user_id_or_handle:
                args.extend(["--user", user_id_or_handle])
            if max_pages is not None:
                args.extend(["--max-pages", str(max_pages)])
            out = self._run_command(args)
            data = json.loads(out) if out.strip() else []
            return data if isinstance(data, list) else data.get("users", data.get("following", []))
        except Exception as e:
            if self.logger:
                self.logger.error(f"Bird get_following failed: {e}")
            return []

    def get_followers(
        self,
        user_id_or_handle: Optional[str] = None,
        limit: int = 20,
        max_pages: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch followers (bird followers [--user id] -n count [--max-pages n] --json)."""
        try:
            args = ["followers", "-n", str(limit), "--json"]
            if user_id_or_handle:
                args.extend(["--user", user_id_or_handle])
            if max_pages is not None:
                args.extend(["--max-pages", str(max_pages)])
            out = self._run_command(args)
            data = json.loads(out) if out.strip() else []
            return data if isinstance(data, list) else data.get("users", data.get("followers", []))
        except Exception as e:
            if self.logger:
                self.logger.error(f"Bird get_followers failed: {e}")
            return []

    def get_user_about(self, handle: str) -> Optional[Dict[str, Any]]:
        """Fetch user about/account info (bird about @handle --json)."""
        try:
            h = handle if handle.startswith("@") else f"@{handle}"
            out = self._run_command(["about", h, "--json"])
            data = json.loads(out) if out.strip() else {}
            return data.get("aboutProfile", data) if data else None
        except Exception as e:
            if self.logger:
                self.logger.error(f"Bird get_user_about failed: {e}")
            return None
