from reddit_wrapper import RedditWrapper

def study(subreddit_name="psicologia", num_threads=5):
    # Example 1: Search for threads in a subreddit
    threads = reddit_api.search_subreddit_threads(
        subreddit_name=subreddit_name,
        query="",  # Empty for all posts
        limit=num_threads,
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
    print(f"Top {len(threads)} threads in '{subreddit_name}':")

    target_thread = threads[0]
    thread_id = target_thread['id']
    comments = reddit_api.get_thread_comments(thread_id)
    
    print(f"Thread '{target_thread['title']}' has {len(comments)} comments [sanity check: {target_thread['num_comments']}]")

    # filter out comments that are moderators or bots
    comments = [c for c in comments if not c['author'].startswith('AutoModerator')]

    # get first comment user; print its username, karma and recent activity
    if not comments:
        return

    first_comment = comments[0]
    first_comment_user = first_comment['author']
    print(f"First comment by {first_comment_user} has {first_comment['score']} karma")
    user_content = reddit_api.get_user_content(username=first_comment_user,  content_type="both", limit=5)
    print(f"Recent activity for {first_comment_user}: {user_content}")

    # # Example 3: Get user content
    # user_content = reddit_api.get_user_content(
    #     username="someusername",
    #     content_type="both",
    #     limit=10
    # )
    # print(f"\nUser has {len(user_content.get('comments', []))} recent comments")
    # print(f"User has {len(user_content.get('submissions', []))} recent submissions")




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
    
    study()