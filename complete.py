#! /usr/bin/env python

import argparse
import json

from monday import TwitterApi, Tweet


parser = argparse.ArgumentParser(description="Make a complete Twitter backup")
parser.add_argument('-f', '--favorites', action='store_true',
    help="retrieve favorites instead of tweets"
)
parser.add_argument('-r', '--resolve', action='store_true',
    help="resolve t.co short URLs"
)
parser.add_argument('screen_name', type=str, nargs='?',
    help="screen name to backup"
)
options = parser.parse_args()

api = TwitterApi()
params = {'screen_name': options.screen_name} if options.screen_name else {}

if options.favorites:
    tweets = api._get_all(api.api.favorites.list, params)
else:
    tweets = api.get_tweets(**params)
tweets = list(tweets)

if options.resolve:
    munge = Tweet._munge
    for t in tweets:
        t['text'] = munge(t['text'], t['entities'])

with open('@%s.json' % api.screen_name, 'w') as f:
    json.dump(tweets, f, indent=2, sort_keys=True, separators=(',', ': '))
