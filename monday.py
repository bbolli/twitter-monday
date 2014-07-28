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


### date handling ###

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


### Tweet class ###

class Tweet:

    def __init__(self, d):
        self.text = self._munge(d['text'])
        self.t_id = d['id']
        self.source = d.get('source', '')
        self.reply_person = d.get('in_reply_to_screen_name')
        self.reply_tweet = d.get('in_reply_to_status_id')
        self.time = datetime.fromtimestamp(
            mktime_tz(parsedate_tz(d['created_at']))
        )

    def __repr__(self):
        return u'%(time)s %(text)r' % self.__dict__

    def _munge(self, text):
        m = re.match(r'^(.*\()(http:\/\/[^)]*)(\).*$)', text, re.M)
        if m:
            return self._munge(m.group(1)) + self._check_url(m.group(2)) + self._munge(m.group(3))
        m = re.match(r'^(.*)(http:\/\/\S+)(.*)$', text, re.M)
        if m:
            return self._munge(m.group(1)) + self._check_url(m.group(2)) + self._munge(m.group(3))
        return text.replace('&amp;gt;', '&gt;').replace('&amp;lt;', '&lt;')

    def _check_url(self, u):
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
            tweet = Tweet(tweet)
            if tweet.time <= earliest:
                break
            if any(i in tweet.source for i in IGNORE_SOURCES):
                continue
            if tweet.time <= latest:
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
            url = 'http://twitter.com/swissbolli/status/%s' % tweet.t_id
            _e('[<a href=\'%s\'>Original</a>%s]</dd>' % (url, attrib))
        _e('</dl>')
        return '\n'.join(e) + '\n'


### main ###

def main():
    w = Week(datetime.now() - timedelta(weeks=1))
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
    path = os.path.join(path, sunday.strftime('short-%Y-%m-%d.txt'))
    with codecs.open(path, 'w', encoding) as f:
        f.write(w.entry())
    print("Wrote", path)

if __name__ == '__main__':
    main()
