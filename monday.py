#! /usr/bin/env python

"""Run this during the week to write last week's short-form entry"""

from __future__ import print_function

import codecs
from datetime import datetime, timedelta
from email.utils import parsedate_tz, mktime_tz
import errno
import locale
import operator
import os
import sys
import time

from twitter.api import Twitter, TwitterHTTPError
from twitter.oauth import OAuth, write_token_file, read_token_file
from twitter.oauth_dance import oauth_dance


# Registered by @swissbolli
CONSUMER_KEY = '2fLClfUjnO720IiTSZXwxiQM6'
CONSUMER_SECRET = 'uHLl38PJy1clObRCWHkjRy3nP3h0km7LLTXSiXMRF9ExBUjBVF'
OAUTH_FILENAME = os.environ.get('HOME', os.environ.get('USERPROFILE', '.')) + \
    os.sep + '.twitter_monday_oauth'

# ignore tweets originating from these sources
IGNORE_SOURCES = ('tumblr', 'instagram')


# ensure the right date/time format
try:
    locale.setlocale(locale.LC_TIME, '')
except locale.Error:
    pass
encoding = locale.getdefaultlocale()[1]
time_encoding = locale.getlocale(locale.LC_TIME)[1] or encoding

ONE_WEEK = timedelta(weeks=1)


def sunday_after(dt, offset=1):
    """offset == 3 means 3rd Sunday from now, -2 means two Sundays back"""
    if offset == 0:
        raise ArgumentError("offset must be nonzero")
    if offset > 0:
        offset -= 1
    dt += ONE_WEEK * offset

    # 23:59:59 on next Sunday
    s = dt + timedelta(days=6 - dt.weekday())
    s = s.replace(hour=23, minute=59, second=59, microsecond=0)

    # Watch out for DST transition
    # s -= s.gmtoff - t.gmtoff
    return s


def strftime(t, format):
    return t.strftime(format).decode(time_encoding)


class Tweet:

    def __init__(self, d):
        self.text = d['text']
        self.t_id = d['id']
        self.source = d.get('source', '')
        self.reply_person = d.get('in_reply_to_screen_name')
        self.reply_tweet = d.get('in_reply_to_status_id')
        self.entities = d['entities']
        self.ext_entities = d.get('extended_entities', {})
        self.screen_name = d['user']['screen_name']
        self.time = self._time(d)

    @staticmethod
    def _time(d):
        return datetime.fromtimestamp(
            mktime_tz(parsedate_tz(d['created_at']))
        )

    def __repr__(self):
        return u'%(time)s %(text)r' % self.__dict__

    def as_html(self, date_tag, text_tag, out):
        out('<%s id=\'p-%s\'>%s</%s>' % (
            date_tag, self.t_id, strftime(self.time, '%A, %H:%M'), date_tag
        ))
        out('<%s>%s' % (text_tag, self.text))
        attrib = ''
        if self.reply_person:
            who = 'http://twitter.com/%s' % self.reply_person
            if self.reply_tweet:
                who += '/status/%s' % self.reply_tweet
            attrib = "; Antwort an <a href='%s'>@%s</a>" % (who, self.reply_person)
        url = 'http://twitter.com/%s/status/%s' % (self.screen_name, self.t_id)
        out('[<a href=\'%s\'>%s</a>%s]</%s>' % (url, "Original", attrib, text_tag))

    def munge(self):
        self.text = self._munge(self.text, self.entities, self.ext_entities)

    @staticmethod
    def _munge(text, entities, ext_entities):
        text = text.replace('\n', '<br />\n')
        for u in entities.get('urls', []):
            text = text.replace(u['url'],
                '<a href=\'%(expanded_url)s\'>%(display_url)s</a>' % u
            )
        for m in ext_entities.get('media', []):
            text = text.replace(m['url'],
                '<a href=\'%(media_url_https)s\'>%(display_url)s</a>' % m
            )
            if m['type'] == 'photo':
                text += '<br />\n<img src=\'%(media_url_https)s\' alt=\'\' />' % m
        return text.replace('&amp;gt;', '&gt;').replace('&amp;lt;', '&lt;')


class TwitterApi:

    def __init__(self):
        """If the user is not authorized yet, do the OAuth dance and save the
        credentials in her home folder for future incovations.
        Then read the credentials and return the authorized Twitter API object."""
        if not os.path.exists(OAUTH_FILENAME):
            oauth_dance("@swissbolli's Monday Twitter Backup",
                CONSUMER_KEY, CONSUMER_SECRET, OAUTH_FILENAME
            )
        oauth_token, oauth_token_secret = read_token_file(OAUTH_FILENAME)
        self.api = Twitter(
            auth=OAuth(oauth_token, oauth_token_secret, CONSUMER_KEY, CONSUMER_SECRET)
        )
        user = self._call_with_retry(self.api.account.settings, _method='GET')
        self.screen_name = user['screen_name']

    def get_tweets(self, **args):
        """Read tweets from the authenticated user's timeline one at a time,
        starting with the most recent one."""
        kwargs = {'count': 500, 'screen_name': self.screen_name}
        kwargs.update(args)
        self.screen_name = kwargs['screen_name']    # in case it was overridden
        for t in self._get_all(self.api.statuses.user_timeline, kwargs):
            yield t

    def _get_all(self, api_fn, kwargs):
        while True:
            tweets = self._call_with_retry(api_fn, **kwargs)
            if not tweets:
                break
            for tweet in tweets:
                yield tweet
                kwargs['max_id'] = tweet['id'] - 1

    def _call_with_retry(self, api_fn, **kwargs):
        while True:
            try:
                return api_fn(**kwargs)
            except TwitterHTTPError as te:
                if te.e.code == 429:
                    # API rate limit reached
                    reset = int(te.e.headers.get('X-Rate-Limit-Reset', time.time() + 30))
                    delay = int(reset - time.time()) + 2
                    print("API rate limit reached; waiting for %ds..." % delay, file=sys.stderr)
                elif te.e.code in (502, 503, 504):
                    delay = 30
                    print("Service unavailable; waiting for %ds..." % delay, file=sys.stderr)
                else:
                    print(te, file=sys.stderr)
                    sys.exit(1)
                time.sleep(delay)


class Week:

    # Monday-to-Sunday week of tweets around mid_week
    def __init__(self, mid_week, twitter):
        latest = sunday_after(mid_week, 1)
        earliest = sunday_after(mid_week, -1)
        self.tweets = []
        for tweet in twitter.get_tweets():
            tweet = Tweet(tweet)
            if tweet.time <= earliest:
                break
            if any(i in tweet.source for i in IGNORE_SOURCES):
                continue
            if tweet.time <= latest:
                tweet.munge()
                self.tweets.append(tweet)
        self.tweets.sort(key=operator.attrgetter('time'))
        self.sunday = latest

    def entry(self):
        e = ["Die Kurzmeldungen letzter Woche", '']
        _e = e.append

        _e('<dl class=\'tweet\'>')
        for tweet in self.tweets:
            tweet.as_html('dt', 'dd', _e)
        _e('</dl>')
        return '\n'.join(e) + '\n'

    def write(self):
        if not self.tweets:  # no tweets in this week
            return 0
        sun = self.sunday
        path = os.path.join('tweets', sun.strftime('%Y'))
        if not os.path.isdir(path):
            os.makedirs(path)
        path = os.path.join(path, sun.strftime('short-%Y-%m-%d.txt'))
        with codecs.open(path, 'w', encoding) as f:
            f.write(self.entry())
        mtime = time.mktime(sun.timetuple())
        os.utime(path, (mtime, mtime))
        print("Wrote", path)
        return len(self.tweets)


def one_week(mid_week):
    return Week(mid_week, TwitterApi()).write()


def all_weeks(mid_weeks):
    return sum(one_week(day) for day in mid_weeks)


if __name__ == '__main__':

    def parse_date_ranges(args):
        for a in args:
            try:
                r = [datetime.strptime(d, '%Y-%m-%d') for d in a.split('..')]
            except ValueError as e:
                r = []
            if len(r) == 1:
                yield r[0]
            elif len(r) == 2:
                while r[0] <= r[1]:
                    yield r[0]
                    r[0] += ONE_WEEK
            else:
                print("Ignoring unparseable argument '%s'" % a, file=sys.stderr)

    args = sys.argv[1:]
    if args:
        dates = [day for day in parse_date_ranges(args)]
    else:
        dates = [datetime.now() - ONE_WEEK]

    count = all_weeks(dates)
    sys.exit(0 if count else 1)
