# Reddit Wrapper

## Requirements
Python version 3.10 or higher

Packages:
- praw

Run as `pip install praw`

## Instructions

Go to [https://www.reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) and create a new application.

Fill in the required fields:
- **name**: A name for your application
- **App type**: Choose "script"
- **description**: A short description of your application
- **about url**: Leave this blank
- **permissions**: Leave this as "read"
- **redirect uri**: Set this to `http://localhost:8080`

After creating the application, make a note of the following:
- **client ID**: This is located just under the webapp
- **client secret**: This is located in the app settings

You will need these values to configure the Reddit API wrapper.

Store the infos in a "secret.json" file in the root directory.
Like the following:
```
{
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
}
```
