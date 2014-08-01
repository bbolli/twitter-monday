#! /usr/bin/env python

import argparse
import json

from monday import TwitterApi, Tweet


parser = argparse.ArgumentParser(description="Make a complete Twitter backup")
parser.add_argument('-r', '--resolve', action='store_true',
    help="resolve t.co short URLs"
)
parser.add_argument('screen_name', type=str, nargs='?',
    help="screen name to backup"
)
options = parser.parse_args()

api = TwitterApi()
if options.screen_name:
    tweets = list(api.get_tweets(screen_name=options.screen_name))
else:
    tweets = list(api.get_tweets())

if options.resolve:
    munge = Tweet._munge
    for t in tweets:
        t['text'] = munge(t['text'], t['entities'])

with open('@%s.json' % api.screen_name, 'w') as f:
    json.dump(tweets, f, indent=2, sort_keys=True, separators=(',', ': '))
