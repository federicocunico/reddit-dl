from reddit_wrapper import RedditWrapper
from reddit_comment_analyzer import RedditCommentAnalyzer


def main():
    
    # Get comments from Reddit
    reddit = RedditWrapper(client_id, client_secret, "TestApp/1.0 by u/federicocunico")

    threads = reddit.search_subreddit_threads(
        subreddit_name="psicologia",
        query="",  # Empty for all posts
        limit=15,
        sort="hot"
    )
    print(f"Found {len(threads)} threads")

    # from first thread, get all the comments
    print("Top threads:")
    if not threads:
        print("No threads found.")
        return

    # get the thread with most comments
    threads.sort(key=lambda x: x['num_comments'], reverse=True)

    # Display the top threads
    print(f"Top {len(threads)} threads in 'psicologia':")

    target_thread = threads[0]
    thread_id = target_thread['id']
    comments = reddit.get_thread_comments(thread_id)
    
    # remove moderator comments
    comments = [c for c in comments if not c['author'].startswith('AutoModerator')]
    if not comments:
        print("No comments found.")
        return

    # Analyze them
    analyzer = RedditCommentAnalyzer()
    results = analyzer.analyze_comments_batch(comments)

    # Get insights
    stats = analyzer.get_summary_stats(results)
    print(f"Positive: {stats['sentiment_distribution']['positive']}")
    print(f"Top topics: {stats['top_topics'][:5]}")


if __name__ == "__main__":
    with open("app.txt", "r") as f:
        # first line is client_id, second line is client_secret
        lines = f.readlines()
    client_id = lines[0].strip()
    client_secret = lines[1].strip()
    # Initialize the wrapper with custom rate limiting
    reddit_api = RedditWrapper(
        client_id=client_id,
        client_secret=client_secret, 
        user_agent="TestApp/1.0 by u/federicocunico",
        requests_per_minute=30  # Conservative rate limit
    )
    main()
