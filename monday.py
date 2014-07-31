#! /usr/bin/env python

"""Run this during the week to write last week's short-form entry"""

from __future__ import print_function

import codecs
from datetime import datetime, timedelta
from email.utils import parsedate_tz, mktime_tz
import errno
import httplib
import locale
import operator
import os
import re
import sys
import time
import urlparse

from twitter.api import Twitter, TwitterError
from twitter.oauth import OAuth, write_token_file, read_token_file
from twitter.oauth_dance import oauth_dance


# Registered by @swissbolli
CONSUMER_KEY = '2fLClfUjnO720IiTSZXwxiQM6'
CONSUMER_SECRET = 'uHLl38PJy1clObRCWHkjRy3nP3h0km7LLTXSiXMRF9ExBUjBVF'
OAUTH_FILENAME = os.environ.get('HOME', os.environ.get('USERPROFILE', '.')) + os.sep + '.twitter_monday_oauth'

# ignore tweets originating from these sources
IGNORE_SOURCES = ('tumblr', 'instagram')


# ensure the right date/time format
try:
    locale.setlocale(locale.LC_TIME, '')
except locale.Error:
    pass
encoding = locale.getdefaultlocale()[1]
time_encoding = locale.getlocale(locale.LC_TIME)[1] or encoding


def sunday_after(dt, offset=1):
    """offset == 3 means 3rd Sunday from now, -2 means two Sundays back"""
    if offset == 0:
        raise ArgumentError("offset must be nonzero")
    if offset > 0:
        offset -= 1
    dt += timedelta(weeks=offset)

    # 23:59:59 on next Sunday
    s = dt + timedelta(days=6 - dt.weekday())
    s = s.replace(hour=23, minute=59, second=59, microsecond=0)

    # Watch out for DST transition
    #s -= s.gmtoff - t.gmtoff
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
        self.time = datetime.fromtimestamp(
            mktime_tz(parsedate_tz(d['created_at']))
        )

    def __repr__(self):
        return u'%(time)s %(text)r' % self.__dict__

    def munge(self):
        self.text = self._munge(self.text)

    @classmethod
    def _munge(cls, text):
        m = re.match(r'^(.*\()(http://[^)]*)(\).*$)', text, re.M)
        if m:
            return cls._munge(m.group(1)) + cls._check_url(m.group(2)) + cls._munge(m.group(3))
        m = re.match(r'^(.*)(http://[!-~]+)(.*)$', text, re.M)
        if m:
            return cls._munge(m.group(1)) + cls._check_url(m.group(2)) + cls._munge(m.group(3))
        return text.replace('&amp;gt;', '&gt;').replace('&amp;lt;', '&lt;')

    @classmethod
    def _check_url(cls, u):
        trailer = ''
        m = re.match(r'([,\)])$', u)
        if m:
            trailer = m.group()
            u = u[:-1]
        try:
            url = urlparse.urlsplit(u)
            conn = httplib.HTTPConnection(url.netloc)
            path = url.path + ('?' + url.query if url.query else '')
            conn.request('HEAD', path)
            resp = conn.getresponse()
            if resp.status in (301, 302, 303) and resp.getheader('Location'):
                u = resp.getheader('Location').replace('&', '&amp;')
        except Exception as e:
            print("Blew up on %s: %s" % (u, e), file=sys.stderr)
        m = re.match(r'http://(.*)', u)
        label = m.group(1) if m else u
        return '<a href="%s">%s</a>%s' % (u, label, trailer)


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
            auth=OAuth(oauth_token, oauth_token_secret, CONSUMER_KEY, CONSUMER_SECRET),
            domain='api.twitter.com'
        )
        user = self.api.account.settings(_method='GET')
        self.screen_name = user['screen_name']

    def get_tweets(self, **args):
        """Read tweets from the authenticated user's timeline one at a time,
        starting with the most recent one."""
        kwargs = {'count': 500, 'screen_name': self.screen_name}
        kwargs.update(args)
        exc_count = 0
        while True:
            try:
                tweets = self.api.statuses.user_timeline(**kwargs)
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


class Week:

    # Monday-to-Sunday week of tweets around mid_week
    def __init__(self, mid_week, twitter):
        latest = sunday_after(mid_week, 1)
        earliest = sunday_after(mid_week, -1)
        self.screen_name = twitter.screen_name
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
        self.sunday = sunday_after(self.tweets[0].time) if self.tweets else None

    def entry(self):
        e = ["Die Kurzmeldungen letzter Woche", '', '<dl>']
        _e = e.append

        for i, tweet in enumerate(self.tweets):
            _e('<dt id=\'p-%d\'>%s</dt>' % (i + 1, strftime(tweet.time, '%A, %H:%M')))
            _e('<dd>%s' % tweet.text)
            attrib = ''
            if tweet.reply_person:
                who = 'http://twitter.com/%s' % tweet.reply_person
                if tweet.reply_tweet:
                    who += '/status/%s' % tweet.reply_tweet
                attrib = "; Antwort auf <a href='%s'>@%s</a>" % (who, tweet.reply_person)
            url = 'http://twitter.com/%s/status/%s' % (self.screen_name, tweet.t_id)
            _e('[<a href=\'%s\'>Original</a>%s]</dd>' % (url, attrib))
        _e('</dl>')
        return '\n'.join(e) + '\n'


def main(mid_week, touch=False):
    w = Week(mid_week, TwitterApi())
    if not w.sunday:  # no tweets in this week
        return
    path = os.path.join('tweets', w.sunday.strftime('%Y'))
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
    path = os.path.join(path, w.sunday.strftime('short-%Y-%m-%d.txt'))
    with codecs.open(path, 'w', encoding) as f:
        f.write(w.entry())
    if touch:
        mtime = time.mktime(w.sunday.timetuple())
        os.utime(path, (mtime, mtime))
    print("Wrote", path)

if __name__ == '__main__':
    args = sys.argv[1:]
    if args:
        for day in args:
            main(datetime.strptime(day, '%Y-%m-%d'), True)
    else:
        main(datetime.now() - timedelta(weeks=1))
