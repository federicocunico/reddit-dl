import os
import praw
from typing import List, Dict, Any
import time
import json


class RedditWrapper:
    """
    Simple but effective Reddit API wrapper using PRAW with rate limiting
    """

    def __init__(self, client_id: str, client_secret: str, user_agent: str, requests_per_minute: int = 50):
        """
        Initialize Reddit API wrapper

        Args:
            client_id: Reddit app client ID
            client_secret: Reddit app client secret
            user_agent: User agent string (e.g., "MyBot/1.0 by u/username")
            requests_per_minute: Custom rate limit (default 50 to be safe)
        """
        self.reddit = praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent)

        # Rate limiting
        self.min_delay = 60.0 / requests_per_minute  # Minimum delay between requests
        self.last_request_time = 0

    def _rate_limit(self):
        """Enforce rate limiting between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_delay:
            sleep_time = self.min_delay - time_since_last
            print(f"Rate limiting: sleeping for {sleep_time:.2f} seconds...")
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def search_subreddit_threads(
        self, subreddit_name: str, query: str = "", limit: int = 10, sort: str = "hot"
    ) -> List[Dict[str, Any]]:
        """
        Search for threads in a specific subreddit

        Args:
            subreddit_name: Name of the subreddit (without r/)
            query: Search query (empty string gets all posts)
            limit: Number of threads to retrieve
            sort: Sort method ("hot", "new", "top", "rising")

        Returns:
            List of thread dictionaries with relevant information
        """
        self._rate_limit()

        try:
            subreddit = self.reddit.subreddit(subreddit_name)

            # Get submissions based on sort method
            if query:
                submissions = subreddit.search(query, limit=limit)
            else:
                if sort == "hot":
                    submissions = subreddit.hot(limit=limit)
                elif sort == "new":
                    submissions = subreddit.new(limit=limit)
                elif sort == "top":
                    submissions = subreddit.top(limit=limit)
                elif sort == "rising":
                    submissions = subreddit.rising(limit=limit)
                else:
                    submissions = subreddit.hot(limit=limit)

            threads = []
            for submission in submissions:
                # Rate limit each submission fetch
                if len(threads) > 0:  # Don't rate limit the first one
                    self._rate_limit()

                thread_data = {
                    "id": submission.id,
                    "title": submission.title,
                    "author": str(submission.author) if submission.author else "[deleted]",
                    "score": submission.score,
                    "upvote_ratio": submission.upvote_ratio,
                    "num_comments": submission.num_comments,
                    "created_utc": submission.created_utc,
                    "url": submission.url,
                    "permalink": f"https://reddit.com{submission.permalink}",
                    "selftext": submission.selftext,
                    "is_self": submission.is_self,
                    "subreddit": submission.subreddit.display_name,
                    "flair": submission.link_flair_text,
                }
                threads.append(thread_data)

            return threads

        except Exception as e:
            print(f"Error searching subreddit {subreddit_name}: {e}")
            return []

    def get_thread_comments(self, thread_id: str, sort: str = "best") -> List[Dict[str, Any]]:
        """
        Get ALL comments from a specific thread with proper rate limiting

        Args:
            thread_id: Reddit thread ID (without prefix)
            sort: Comment sort method ("best", "top", "new", "controversial", "old", "qa")

        Returns:
            List of all comments in the thread (flattened structure)
        """
        self._rate_limit()

        try:
            submission = self.reddit.submission(id=thread_id)

            # Set comment sort
            submission.comment_sort = sort

            print(f"Fetching ALL comments for thread {thread_id}...")
            print("This may take a while for threads with many comments...")

            # Replace "MoreComments" objects to get ALL comments
            # This can make multiple API calls, so we need to be patient
            submission.comments.replace_more(limit=None)

            comments = []

            def extract_comment(comment, parent_id=None, depth=0):
                """Recursively extract comment data"""
                if hasattr(comment, "body"):  # It's a real comment
                    comment_data = {
                        "id": comment.id,
                        "author": str(comment.author) if comment.author else "[deleted]",
                        "body": comment.body,
                        "score": comment.score,
                        "created_utc": comment.created_utc,
                        "parent_id": parent_id,
                        "depth": depth,
                        "permalink": f"https://reddit.com{comment.permalink}",
                        "is_submitter": comment.is_submitter,
                        "edited": bool(comment.edited),
                        "gilded": comment.gilded,
                        "controversiality": comment.controversiality,
                    }
                    comments.append(comment_data)

                    # Process replies
                    for reply in comment.replies:
                        extract_comment(reply, comment.id, depth + 1)

            # Process all top-level comments
            for comment in submission.comments:
                extract_comment(comment)

            print(f"Successfully fetched {len(comments)} comments")
            return comments

        except Exception as e:
            print(f"Error getting comments for thread {thread_id}: {e}")
            return []

    def get_user_content(
        self, username: str, content_type: str = "both", limit: int = 100
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get comments and/or submissions from a specific user

        Args:
            username: Reddit username (without u/)
            content_type: "comments", "submissions", or "both"
            limit: Maximum number of items to retrieve per type

        Returns:
            Dictionary with 'comments' and/or 'submissions' keys
        """
        self._rate_limit()

        try:
            user = self.reddit.redditor(username)
            result = {}

            if content_type in ["comments", "both"]:
                comments = []
                print(f"Fetching up to {limit} comments from u/{username}...")

                for i, comment in enumerate(user.comments.new(limit=limit)):
                    if i > 0 and i % 10 == 0:  # Rate limit every 10 comments
                        self._rate_limit()

                    comment_data = {
                        "id": comment.id,
                        "body": comment.body,
                        "score": comment.score,
                        "created_utc": comment.created_utc,
                        "subreddit": comment.subreddit.display_name,
                        "permalink": f"https://reddit.com{comment.permalink}",
                        "parent_id": comment.parent_id,
                        "is_submitter": comment.is_submitter,
                        "edited": bool(comment.edited),
                    }
                    comments.append(comment_data)
                result["comments"] = comments
                print(f"Found {len(comments)} comments")

            if content_type in ["submissions", "both"]:
                submissions = []
                print(f"Fetching up to {limit} submissions from u/{username}...")

                for i, submission in enumerate(user.submissions.new(limit=limit)):
                    if i > 0 and i % 10 == 0:  # Rate limit every 10 submissions
                        self._rate_limit()

                    submission_data = {
                        "id": submission.id,
                        "title": submission.title,
                        "score": submission.score,
                        "upvote_ratio": submission.upvote_ratio,
                        "num_comments": submission.num_comments,
                        "created_utc": submission.created_utc,
                        "url": submission.url,
                        "permalink": f"https://reddit.com{submission.permalink}",
                        "selftext": submission.selftext,
                        "subreddit": submission.subreddit.display_name,
                        "is_self": submission.is_self,
                        "flair": submission.link_flair_text,
                    }
                    submissions.append(submission_data)
                result["submissions"] = submissions
                print(f"Found {len(submissions)} submissions")

            return result

        except Exception as e:
            print(f"Error getting content for user {username}: {e}")
            return {}


def _load_secrets() -> Dict[str, str]:
    """
    Load Reddit API credentials from a secrets file.
    """
    user_id = os.environ.get("REDDIT_API_USER_ID", None)
    secret = os.environ.get("REDDIT_API_SECRET", None)
    if user_id is not None and secret is not None:
        return {"client_id": user_id, "client_secret": secret}
    else:
        print("[Warning]: Only one of REDDIT_API_USER_ID or REDDIT_API_SECRET is set. Both must be set to use environment variables. Trying with secret.json file...")

    json_file = "secret.json"
    if not os.path.isfile(json_file):
        raise FileNotFoundError(f"Secrets file '{json_file}' not found. Please create it with your Reddit API credentials.")
    with open(json_file, "r") as f:
        secrets = json.load(f)
    # sanity check
    if "client_id" not in secrets or "client_secret" not in secrets:
        raise KeyError(f"Secrets file '{json_file}' must contain 'client_id' and 'client_secret' keys.")
    if not secrets["client_id"] or not secrets["client_secret"]:
        raise ValueError(f"'client_id' and 'client_secret' in '{json_file}' cannot be empty.")
    if secrets["client_id"] == "YOUR_CLIENT_ID" or secrets["client_secret"] == "YOUR_CLIENT_SECRET":
        raise ValueError(f"'client_id' and 'client_secret' in '{json_file}' must be set to your actual Reddit API credentials, not the placeholder values.")
    return secrets


def create_wrapper(user_agent: str = "my_reddit_app"):
    secrets = _load_secrets()
    return RedditWrapper(
        client_id=secrets["client_id"],
        client_secret=secrets["client_secret"],
        user_agent=user_agent
    )
