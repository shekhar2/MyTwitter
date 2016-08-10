#!/usr/bin/python
import warnings
warnings.simplefilter('ignore', DeprecationWarning)

import httplib2, urllib, time, re
try:
    import json
except ImportError:
    import simplejson as json

from config import USERNAME, PASSWORD

USER_TIMELINE = "http://twitter.com/statuses/user_timeline.json"
FILE = "my_tweets.json"

h = httplib2.Http()
h.add_credentials(USERNAME, PASSWORD, 'twitter.com')

def load_all():
    try:
        return json.load(open(FILE))
    except IOError:
        return []

def normalize_url(url):
    # Simple length heuristic
    if len(url) < 10: return None

    # Make sure we have some sort of protocol
    if not re.search('://', url):
        url = 'http://' + url

    return url

def lookup_short_urls(tweet):
    # If short_urls are already there, skip
    if 'short_urls' in tweet: return

    # (Start of line or word)
    # (Maybe something like http://)
    # (A vaguely domain-like section, at least one dot which is not a double dot)
    # (Whatever else follows, liberally via non-whitespace)
    url_regex = '(\A|\\b)([\w-]+://)?\S+[.][^\s.]\S*'

    redir = httplib2.Http(timeout=10)
    redir.follow_redirects = False
    redir.force_exception_to_status_code = True

    short_urls = {}

    new_text = tweet['text']
    for sub in tweet['text'].split():
        orig_url_match = re.search(url_regex, sub)
        if not orig_url_match:
            continue
        orig_url = normalize_url(orig_url_match.group(0))
        if not orig_url: continue

        try:
            response = redir.request(orig_url)[0]
            if 'status' in response and response['status'] == '301':
                short_urls[response['location']] = orig_url
                new_text = new_text.replace(orig_url, response['location'])
        except:
            pass

    tweet['short_urls'] = short_urls
    tweet['text'] = new_text

def fetch_and_save_new_tweets():
    tweets = load_all()
    old_tweet_ids = set(t['id'] for t in tweets)
    if tweets:
        since_id = max(t['id'] for t in tweets)
    else:
        since_id = None
    new_tweets = fetch_all(since_id)
    num_new_saved = 0
    for tweet in new_tweets:
        if tweet['id'] not in old_tweet_ids:
            tweets.append(tweet)
            num_new_saved += 1
    tweets.sort(key = lambda t: t['id'], reverse=True)
    # Delete the 'user' key, lookup short URLs
    for t in tweets:
        if 'user' in t:
            del t['user']
        lookup_short_urls(t)
    # Save back to disk
    json.dump(tweets, open(FILE, 'w'), indent = 2)
    print "Saved %s new tweets" % num_new_saved

def fetch_all(since_id = None):
    all_tweets = []
    seen_ids = set()
    page = 0
    args = {'count': 200}
    if since_id is not None:
        args['since_id'] = since_id

    all_tweets_len = len(all_tweets)

    while True:
        args['page'] = page
        headers, body = h.request(
            USER_TIMELINE + '?' + urllib.urlencode(args), method='GET'
        )
        page += 1
        tweets = json.loads(body)
        if 'error' in tweets:
            raise ValueError, tweets
        if not tweets:
            break
        for tweet in tweets:
            if tweet['id'] not in seen_ids:
                seen_ids.add(tweet['id'])
                all_tweets.append(tweet)
        #print "Fetched another %s" % (len(all_tweets) - all_tweets_len)
        all_tweets_len = len(all_tweets)
        time.sleep(2)

    all_tweets.sort(key = lambda t: t['id'], reverse=True)
    return all_tweets

if __name__ == '__main__':
    fetch_and_save_new_tweets()
