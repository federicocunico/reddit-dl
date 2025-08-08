from glob import glob
import json
import os
from datetime import datetime
import sys
from src.reddit_comment_analyzer import RedditCommentAnalyzer
from src.reddit_wrapper import create_wrapper


def get_data_from_subreddit(subreddit_name: str, num_threads: int = 10):
    # Step 1: get comments
    wrapper = create_wrapper()
    threads = wrapper.search_subreddit_threads(
        subreddit_name=subreddit_name, query="", limit=num_threads, sort="hot"  # Empty for all posts
    )
    print(f"Found {len(threads)} threads")

    # from first thread, get all the comments
    print("Top threads:")
    if not threads:
        print("No threads found.")
        return

    # get the thread with most comments
    threads.sort(key=lambda x: x["num_comments"], reverse=True)

    # Display the top threads
    print(f"Top {len(threads)} threads in 'psicologia':")

    final_data = {}

    for target_thread in threads:
        print(f"Thread '{target_thread['title']}' has {target_thread['num_comments']} comments")

        thread_id = target_thread["id"]
        comments = wrapper.get_thread_comments(thread_id)

        # remove moderator comments
        comments = [c for c in comments if not c["author"].startswith("AutoModerator")]
        if not comments:
            print("No comments found.")
            continue

        thread_id = target_thread["id"]
        thread_title = target_thread["title"]
        thread_content = target_thread["selftext"]
        thread_comments = comments

        final_data[thread_id] = {"title": thread_title, "content": thread_content, "comments": thread_comments, "full_thread_infos": target_thread}

    # save on disk
    DST = "data"
    os.makedirs(DST, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    with open(os.path.join(DST, f"{today}_{subreddit_name}.json"), "w") as f:
        json.dump(final_data, f)

    return final_data


def analyze_data_from_subreddit(thread_data: dict):

    # Analyze them
    analyzer = RedditCommentAnalyzer()

    for th_id, data in thread_data.items():
        title = data["title"]
        content = data["content"]
        comments = data["comments"]

        results = analyzer.analyze_comments_batch(comments)

        # Get insights
        stats = analyzer.get_summary_stats(results)
        print(f"Positive: {stats['sentiment_distribution']['positive']}")
        print(f"Top topics: {stats['top_topics'][:5]}")


if __name__ == "__main__":
    
    # Scrape a new one
    # data = get_data_from_subreddit("psicologia", 10)

    # Load an old one
    files = sorted(glob("data/*.json"))

    # sort by descending date
    files.sort(key=os.path.getmtime, reverse=True)
    if not files:
        print("No old data found.")
        sys.exit(0)

    # Get latest
    latest_file = files[0]
    with open(latest_file, "r") as f:
        data = json.load(f)
    analyze_data_from_subreddit(data)

    ## Loop all
    # for file in files:
    #     with open(file, "r") as f:
    #         data = json.load(f)
    #     analyze_data_from_subreddit(data)

