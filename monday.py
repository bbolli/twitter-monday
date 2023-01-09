#! /usr/bin/env python

"""Run this at midnight to write the last day's short-form entry"""

from __future__ import print_function

import codecs
from datetime import datetime, timedelta
from email.utils import parsedate_tz, mktime_tz
import itertools
import locale
import operator
import os
import sys
import time

from twitter.api import Twitter
from twitter.oauth import OAuth, read_token_file
from twitter.oauth_dance import oauth_dance

# Config
POST_TITLE = ""
POST_HEADER = '<div class=\'tweets\'>\n'
POST_FOOTER = '</div>\n'
DATE_TAG = 'span'
TEXT_TAG = 'span'
TWEET_DATE_FMT = '%H:%M'
IGNORE_SOURCES = ('tumblr', 'instagram')
PERIOD_LENGTH = 1   # days

# Registered by @swissbolli
CONSUMER_KEY = '2fLClfUjnO720IiTSZXwxiQM6'
CONSUMER_SECRET = 'uHLl38PJy1clObRCWHkjRy3nP3h0km7LLTXSiXMRF9ExBUjBVF'
OAUTH_FILENAME = os.environ.get('HOME', os.environ.get('USERPROFILE', '.')) + \
    os.sep + '.twitter_monday_oauth'


# ensure the right date/time format
try:
    locale.setlocale(locale.LC_TIME, '')
except locale.Error:
    pass
encoding = locale.getdefaultlocale()[1]
time_encoding = locale.getlocale(locale.LC_TIME)[1] or encoding

PERIOD = timedelta(days=PERIOD_LENGTH)


def period_end(dt, offset=1):
    """offset == 3 means 3rd midnight from now, -2 means two periods back"""
    if offset == 0:
        raise ValueError("offset must be nonzero")
    if offset > 0:
        offset -= 1
    dt += PERIOD * offset

    if PERIOD_LENGTH == 7:
        dt += timedelta(days=PERIOD_LENGTH - 1 - dt.weekday())
    s = dt.replace(hour=23, minute=59, second=59, microsecond=0)

    # Watch out for DST transition
    # s -= s.gmtoff - t.gmtoff
    return s


def strftime(t, format):
    return t.strftime(format).decode(time_encoding)


class Tweet:

    def __init__(self, d):
        self.t_id = d['id']
        self.reply_person = d.get('in_reply_to_screen_name')
        self.reply_tweet = d.get('in_reply_to_status_id')
        self.screen_name = d['user']['screen_name']
        self.time = self.created(d)
        if 'retweeted_status' in d:
            original = Tweet(d['retweeted_status'])
            self.text = "RT @%s: %s" % (original.screen_name, original.text)
            # original.text is already munged
        else:
            self.munge_text(d)
            self.text = d['text']

    @staticmethod
    def ignore(d):
        return any(s in d.get('source', '') for s in IGNORE_SOURCES)

    @staticmethod
    def created(d):
        return datetime.fromtimestamp(
            mktime_tz(parsedate_tz(d['created_at']))
        )

    @staticmethod
    def munge_text(d):
        text = d['text'].replace('\n', '<br />\n')
        for u in d['entities'].get('urls', []):
            text = text.replace(u['url'],
                '<a href=\'%(expanded_url)s\'>%(display_url)s</a>' % u
            )
        for m in d.get('extended_entities', {}).get('media', []):
            text = text.replace(m['url'],
                '<a href=\'%(media_url_https)s\'>%(display_url)s</a>' % m
            )
            if m['type'] == 'photo':
                text += '<br />\n<img src=\'%(media_url_https)s\' alt=\'\' />' % m
        d['text'] = text.replace('&amp;gt;', '&gt;').replace('&amp;lt;', '&lt;')

    def __repr__(self):
        return u'%(time)s %(text)r' % self.__dict__

    def as_html(self):
        head = '<p class=\'tweet\'><%s id=\'%s\'>%s</%s>\n' % (
            DATE_TAG,
            'p-%s' % self.t_id, strftime(self.time, TWEET_DATE_FMT),
            DATE_TAG,
        )
        attrib = ''
        if self.reply_person:
            who = 'http://twitter.com/%s' % self.reply_person
            if self.reply_tweet:
                who += '/status/%s' % self.reply_tweet
            attrib = "; Antwort an <a href='%s'>@%s</a>" % (who, self.reply_person)
        url = 'http://twitter.com/%s/status/%s' % (self.screen_name, self.t_id)
        body = '<%s>%s\n[<a href=\'%s\'>%s</a>%s]</%s>\n' % (
            TEXT_TAG, self.text, url, "Original", attrib, TEXT_TAG
        )
        return head + body + '</p>\n'


class TwitterApi:

    def __init__(self):
        """If the user is not authorized yet, do the OAuth dance and save the
        credentials in their home folder for future invocations.
        Then read the credentials and return the authorized Twitter API object."""
        if not os.path.exists(OAUTH_FILENAME):
            oauth_dance("@swissbolli's Monday Twitter Backup",
                CONSUMER_KEY, CONSUMER_SECRET, OAUTH_FILENAME
            )
        oauth_token, oauth_token_secret = read_token_file(OAUTH_FILENAME)
        self.api = Twitter(
            auth=OAuth(oauth_token, oauth_token_secret, CONSUMER_KEY, CONSUMER_SECRET),
            retry=5
        )
        user = self.api.account.settings(_method='GET')
        self.screen_name = user['screen_name']

    def get_tweets(self, **args):
        """Read tweets from the authenticated user's timeline one at a time,
        starting with the most recent one."""
        kwargs = {'count': 500, 'screen_name': self.screen_name}
        kwargs.update(args)
        self.screen_name = kwargs['screen_name']    # in case it was overridden
        for t in self.get_all(self.api.statuses.user_timeline, kwargs):
            yield t

    @staticmethod
    def get_all(api_fn, kwargs):
        while True:
            tweets = api_fn(**kwargs)
            if not tweets:
                break
            for tweet in tweets:
                yield tweet
                kwargs['max_id'] = tweet['id'] - 1


class TweetPeriod:

    # One period's worth of tweets
    def __init__(self, end, tweets):
        self.tweets = sorted((
            Tweet(t) for t in tweets if not Tweet.ignore(t)
        ), key=operator.attrgetter('time'))
        self.end = end

    def entry(self, f):
        f.write(POST_TITLE + '\n\n' + POST_HEADER)
        for tweet in self.tweets:
            f.write(tweet.as_html())
        f.write(POST_FOOTER)

    def write(self):
        if not self.tweets:  # no tweets in this period
            return 0
        path = os.path.join('tweets', self.end.strftime('%Y'))
        if not os.path.isdir(path):
            os.makedirs(path)
        path = os.path.join(path, self.end.strftime('short-%Y-%m-%d.txt'))
        with codecs.open(path, 'w', encoding) as f:
            self.entry(f)
        mtime = time.mktime(self.end.timetuple())
        os.utime(path, (mtime, mtime))
        print("Wrote", path)
        return len(self.tweets)


def all_periods(days):
    # set(...) removes duplicate dates
    days = sorted(set(period_end(d) for d in days))
    if not days:
        return 0
    twitter = TwitterApi()
    count = 0
    for end, tweets in itertools.groupby(twitter.get_tweets(),
        key=lambda t: period_end(Tweet.created(t))
    ):
        if end < days[0]:
            break
        if end in days:
            count += TweetPeriod(end, tweets).write()
    return count


if __name__ == '__main__':

    def parse_date_ranges(args):
        for a in args:
            try:
                r = [datetime.strptime(d, '%Y-%m-%d') for d in a.split('..')]
            except ValueError:
                r = []
            if len(r) == 1:
                yield r[0]
            elif len(r) == 2:
                while r[0] <= r[1]:
                    yield r[0]
                    r[0] += PERIOD
            else:
                print("Ignoring unparseable argument '%s'" % a, file=sys.stderr)

    args = sys.argv[1:]
    dates = parse_date_ranges(args) if args else [period_end(datetime.now(), -1)]

    count = all_periods(dates)

    sys.exit(0 if count else 1)
