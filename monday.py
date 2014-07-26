#! /usr/bin/env python

"""Run this during the week to write last week's short-form entry"""

from __future__ import print_function

from datetime import datetime, timedelta
import errno
import operator
import os
import sys


def sunday_after(dt, offset=1):
    """offset == 3 means 3rd Sunday from now, -2 means two Sundays back"""
    if offset == 0:
        raise ArgumentError("offset must be nonzero")
    if offset > 0:
        offset -= 1
    dt += timedelta(days=offset * 7)

    # 23:59:59 on next Sunday
    days = 6 - dt.weekday()
    hours = 23 - dt.hour
    mins = 59 - dt.minute
    sec = 59 - dt.second
    s = dt + timedelta(days=days, hours=hours, minutes=mins, seconds=sec)
    s = s.replace(microsecond=0)

    # Watch out for DST transition
    #s -= s.gmtoff - t.gmtoff
    return s


class Week:

    # Monday-to-Sunday week of tweets around mid_week
    def __init__(self, mid_week):
        latest = sunday_after(mid_week, 1)
        earliest = sunday_after(mid_week, -1)
        """r = Reader.new
        @tweets = []
        while true do
          tweet = r.next
          break if tweet.time <= earliest
          @tweets << tweet if tweet.time <= latest
        end"""
        class MockedTweet:
            def __init__(self, nr):
                self.time = latest - timedelta(days=nr, hours=nr * 2, minutes=nr * 3)
            def __repr__(self):
                return "\nMockedTweet from %s" % self.time
        self.tweets = [MockedTweet(1), MockedTweet(2), MockedTweet(3), MockedTweet(4)]
        self.tweets.sort(key=operator.attrgetter('time'))

    @property
    def sunday(self):
        return sunday_after(self.tweets[0].time)


def entry(tweets, sunday):
    return "blosxom entry for week ending %s:\n%r" % (sunday, tweets)

def main():
    w = Week(datetime.now() - timedelta(days=7))
    sunday = w.sunday
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
