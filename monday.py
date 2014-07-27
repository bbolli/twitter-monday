#! /usr/bin/env python

"""Run this during the week to write last week's short-form entry"""

from __future__ import print_function

from datetime import datetime, timedelta
from email.utils import parsedate_tz, mktime_tz
import errno
import operator
import os
import sys
import time

from twitter.api import Twitter, TwitterError
from twitter.oauth import OAuth, write_token_file, read_token_file
from twitter.oauth_dance import oauth_dance


# Registered by @swissbolli
CONSUMER_KEY = '2fLClfUjnO720IiTSZXwxiQM6'
CONSUMER_SECRET = 'uHLl38PJy1clObRCWHkjRy3nP3h0km7LLTXSiXMRF9ExBUjBVF'
OAUTH_FILENAME = os.environ.get('HOME', os.environ.get('USERPROFILE', '.')) + os.sep + '.twitter_monday_oauth'

### date handling ###

def sunday_after(dt, offset=1):
    """offset == 3 means 3rd Sunday from now, -2 means two Sundays back"""
    if offset == 0:
        raise ArgumentError("offset must be nonzero")
    if offset > 0:
        offset -= 1
    dt += timedelta(days=offset * 7)

    # 23:59:59 on next Sunday
    s = dt + timedelta(days=6 - dt.weekday())
    s = s.replace(hour=23, minute=59, second=59, microsecond=0)

    # Watch out for DST transition
    #s -= s.gmtoff - t.gmtoff
    return s


### Twitter API ###

def get_twitter_api():
    """If the user is not authorized yet, do the OAuth dance and save the
    credentials in her home folder for future incovations.
    Then read the credentials and return the authorized Twitter API object."""
    if not os.path.exists(OAUTH_FILENAME):
        oauth_dance("@swissbolli's Monday Twitter Backup",
            CONSUMER_KEY, CONSUMER_SECRET, OAUTH_FILENAME
        )
    oauth_token, oauth_token_secret = read_token_file(OAUTH_FILENAME)
    return Twitter(
        auth=OAuth(oauth_token, oauth_token_secret, CONSUMER_KEY, CONSUMER_SECRET),
        domain='api.twitter.com'
    )

def get_tweets(twitter, **args):
    """Read tweets from the authenticated user's timeline one at a time,
    starting with the most recent one."""
    kwargs = {'count': 500}
    kwargs.update(args)
    exc_count = 0
    while True:
        try:
            tweets = twitter.statuses.user_timeline(**kwargs)
        except TwitterError as e:
            print(e, file=sys.stderr)
            exc_count += 1
            if exc_count >= 10:
                break
            time.sleep(3)
            continue
        if not tweets:
            break
        for tweet in tweets:
            yield tweet
            kwargs['max_id'] = tweet['id'] - 1


### getting a week's worth of tweets ###

class Week:

    # Monday-to-Sunday week of tweets around mid_week
    def __init__(self, mid_week):
        latest = sunday_after(mid_week, 1)
        earliest = sunday_after(mid_week, -1)
        twitter = get_twitter_api()
        user = twitter.account.settings(_method='GET')
        self.tweets = []
        for tweet in get_tweets(twitter, screen_name=user['screen_name']):
            tm = tweet['_time'] = datetime.fromtimestamp(
                mktime_tz(parsedate_tz(tweet['created_at']))
            )
            if tm <= earliest:
                break
            if tm <= latest:
                self.tweets.append(tweet)
        self.tweets.sort(key=operator.itemgetter('_time'))

    @property
    def sunday(self):
        if self.tweets:
            return sunday_after(self.tweets[0]['_time'])


### formatting the tweets ###

def entry(tweets, sunday):
    return "blosxom entry for week ending %s:\n%r" % (sunday, tweets)


### main ###

def main():
    w = Week(datetime.now() - timedelta(days=7))
    sunday = w.sunday
    if not sunday:  # no tweets last week
        return
    year = '%04d' % sunday.year
    path = os.path.join('tweets', year[:-1] + 'x', year)
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
    path = os.path.join(path, '%02d-%02d.txt' % (sunday.month, sunday.day))
    with open(path, 'w') as f:
        f.write(entry(w.tweets, sunday))
    print("Wrote", path)

if __name__ == '__main__':
    main()
