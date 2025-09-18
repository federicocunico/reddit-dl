import os
import praw
from typing import List, Dict, Any, Optional
import time
import json
from datetime import datetime


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

    def get_hot_topics_with_filters(
        self, 
        subreddit_name: str, 
        min_upvotes: int = 100,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        filter: str = "year",
        max_posts: int = 1000,
        sort: str = "top"
    ) -> List[Dict[str, Any]]:
        """
        Get hot topics from a subreddit with upvote and date filtering, handling pagination
        
        Args:
            subreddit_name: Name of the subreddit (without r/)
            min_upvotes: Minimum number of upvotes required
            start_date: Start date in format "YYYY-MM-DD" (e.g., "2025-01-01"). If None, no start limit
            end_date: End date in format "YYYY-MM-DD" (e.g., "2025-12-31"). If None, no end limit
            max_posts: Maximum number of posts to retrieve (handles pagination)
            sort: Sort method ("hot", "new", "top", "rising") - "top" is recommended for date ranges
            
        Returns:
            List of filtered thread dictionaries
        """
        print(f"Fetching topics from r/{subreddit_name} with {min_upvotes}+ upvotes...")
        
        # Parse date filters
        start_timestamp = None
        end_timestamp = None
        
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                start_timestamp = start_dt.timestamp()
                print(f"Start date: {start_date}")
            except ValueError:
                raise ValueError(f"Invalid start_date format. Use YYYY-MM-DD, got: {start_date}")
        
        if end_date:
            try:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                # Set to end of day (23:59:59)
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
                end_timestamp = end_dt.timestamp()
                print(f"End date: {end_date}")
            except ValueError:
                raise ValueError(f"Invalid end_date format. Use YYYY-MM-DD, got: {end_date}")
        
        if start_timestamp and end_timestamp and start_timestamp > end_timestamp:
            raise ValueError("start_date cannot be after end_date")
        
        # Determine the most efficient Reddit time filter
        # reddit_time_filter = self._get_optimal_time_filter(start_timestamp, end_timestamp)
        reddit_time_filter = filter
        
        print(f"Sort: {sort}, Reddit time filter: {reddit_time_filter}, Max posts to scan: {max_posts}")
        
        self._rate_limit()
        
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            all_posts = []
            fetched_count = 0
            
            # Get submissions based on sort method with optimal time filter
            if sort == "top":
                submissions = subreddit.top(time_filter=reddit_time_filter, limit=None)
                print(f"Using Reddit's built-in time filter '{reddit_time_filter}' for efficient top sorting")
            elif sort == "hot":
                submissions = subreddit.hot(limit=None)
                print("Warning: 'hot' sort doesn't support time filters - will manually filter results")
            elif sort == "new":
                submissions = subreddit.new(limit=None)
                print("Using 'new' sort - will stop early when reaching old posts")
            elif sort == "rising":
                submissions = subreddit.rising(limit=None)
                print("Warning: 'rising' sort doesn't support time filters - will manually filter results")
            else:
                submissions = subreddit.top(time_filter=reddit_time_filter, limit=None)
                print(f"Invalid sort '{sort}', defaulting to 'top' with time filter '{reddit_time_filter}'")
            
            print("Processing submissions with pagination and filtering...")
            posts_outside_range = 0
            max_consecutive_outside = 100  # Stop if we hit too many consecutive posts outside range
            
            for submission in submissions:
                # Rate limit every 10 submissions to be respectful
                if fetched_count > 0 and fetched_count % 10 == 0:
                    self._rate_limit()
                
                fetched_count += 1
                
                # Check if we've reached our scanning limit
                if fetched_count > max_posts:
                    print(f"Reached maximum posts scanning limit ({max_posts})")
                    break
                
                # Apply date filters first (most efficient)
                post_timestamp = submission.created_utc
                post_dt = datetime.fromtimestamp(post_timestamp)  # for logging if needed
                post_in_range = True
                
                # Check if post is within date range
                if start_timestamp and post_timestamp < start_timestamp:
                    post_in_range = False
                    posts_outside_range += 1
                    
                    # For 'new' sort, if we hit posts older than start_date, we can break
                    if sort == "new":
                        print(f"Breaking early: reached posts older than start_date ({posts_outside_range} posts checked)")
                        break
                
                if end_timestamp and post_timestamp > end_timestamp:
                    post_in_range = False
                    posts_outside_range += 1
                
                # If too many consecutive posts are outside range, probably no more good ones
                if posts_outside_range > max_consecutive_outside:
                    print(f"Breaking early: {max_consecutive_outside} consecutive posts outside date range")
                    break
                
                if not post_in_range:
                    continue
                
                # Reset counter since we found a post in range
                posts_outside_range = 0
                
                # Apply upvote filter
                if submission.score < min_upvotes:
                    # For 'top' sort, if we're getting posts with low scores,
                    # we can break early as they're sorted by score
                    if sort == "top":
                        print(f"Breaking early: post score {submission.score} below minimum {min_upvotes}")
                        break
                    else:
                        continue
                
                thread_data = {
                    "id": submission.id,
                    "title": submission.title,
                    "author": str(submission.author) if submission.author else "[deleted]",
                    "score": submission.score,
                    "upvote_ratio": submission.upvote_ratio,
                    "num_comments": submission.num_comments,
                    "created_utc": submission.created_utc,
                    "created_date": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(submission.created_utc)),
                    "url": submission.url,
                    "permalink": f"https://reddit.com{submission.permalink}",
                    "selftext": submission.selftext,
                    "is_self": submission.is_self,
                    "subreddit": submission.subreddit.display_name,
                    "flair": submission.link_flair_text,
                    "domain": submission.domain,
                    "gilded": submission.gilded,
                    "over_18": submission.over_18,
                    "spoiler": submission.spoiler,
                    "stickied": submission.stickied,
                }
                all_posts.append(thread_data)
                
                # Progress update
                if len(all_posts) % 25 == 0:
                    print(f"Found {len(all_posts)} qualifying posts so far... (scanned {fetched_count} total)")
            
            # Sort by score descending for final results
            all_posts.sort(key=lambda x: x['score'], reverse=True)
            
            print(f"✓ Found {len(all_posts)} topics with {min_upvotes}+ upvotes (scanned {fetched_count} posts)")
            if all_posts:
                print(f"  Top post: {all_posts[0]['score']} upvotes - '{all_posts[0]['title'][:60]}...'")
                print(f"  Date range in results: {min(p['created_date'] for p in all_posts)} to {max(p['created_date'] for p in all_posts)}")
            else:
                print("  No posts found matching criteria")
            
            return all_posts
            
        except Exception as e:
            print(f"Error getting topics from r/{subreddit_name}: {e}")
            return []

    def _get_optimal_time_filter(self, start_timestamp: Optional[float], end_timestamp: Optional[float]) -> str:
        """
        Determine the optimal Reddit time filter based on the date range
        
        Returns:
            Reddit time filter: "hour", "day", "week", "month", "year", or "all"
        """
        if not start_timestamp and not end_timestamp:
            return "all"
        
        now = time.time()
        
        # If we have an end date, use that as reference, otherwise use now
        reference_time = end_timestamp if end_timestamp else now
        
        # If we have a start date, calculate how far back it goes
        if start_timestamp:
            days_back = (reference_time - start_timestamp) / 86400
            
            # Choose the smallest time filter that covers our range
            if days_back <= 1:
                return "day"
            elif days_back <= 7:
                return "week"
            elif days_back <= 30:
                return "month"
            elif days_back <= 365:
                return "year"
            else:
                return "all"
        else:
            # Only end date specified, determine based on how recent it is
            days_ago = (now - reference_time) / 86400
            
            if days_ago <= 1:
                return "day"
            elif days_ago <= 7:
                return "week"
            elif days_ago <= 30:
                return "month"
            elif days_ago <= 365:
                return "year"
            else:
                return "all"

    def get_trending_topics_batch(
        self, 
        subreddit_names: List[str], 
        min_upvotes: int = 100,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_posts_per_sub: int = 100
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get trending topics from multiple subreddits with batch processing
        
        Args:
            subreddit_names: List of subreddit names (without r/)
            min_upvotes: Minimum number of upvotes required
            start_date: Start date in format "YYYY-MM-DD" (e.g., "2025-01-01"). If None, no start limit
            end_date: End date in format "YYYY-MM-DD" (e.g., "2025-12-31"). If None, no end limit
            max_posts_per_sub: Maximum number of posts per subreddit
            
        Returns:
            Dictionary with subreddit names as keys and lists of posts as values
        """
        results = {}
        
        print(f"Processing {len(subreddit_names)} subreddits...")
        if start_date or end_date:
            print(f"Date range: {start_date or 'earliest'} to {end_date or 'latest'}")
        
        for i, subreddit_name in enumerate(subreddit_names, 1):
            print(f"\n[{i}/{len(subreddit_names)}] Processing r/{subreddit_name}...")
            
            posts = self.get_hot_topics_with_filters(
                subreddit_name=subreddit_name,
                min_upvotes=min_upvotes,
                start_date=start_date,
                end_date=end_date,
                max_posts=max_posts_per_sub,
                sort="top"  # Use "top" for better efficiency with time filters
            )
            
            results[subreddit_name] = posts
            
            # Rate limit between subreddits
            if i < len(subreddit_names):
                self._rate_limit()
        
        total_posts = sum(len(posts) for posts in results.values())
        print(f"\n✓ Batch processing complete! Found {total_posts} total posts across {len(subreddit_names)} subreddits")
        
        return results


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
