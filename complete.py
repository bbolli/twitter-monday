#! /usr/bin/env python

import json

from monday import TwitterApi


api = TwitterApi()
tweets = list(api.get_tweets())
with open('all-tweets.json', 'w') as f:
    json.dump(tweets, f, indent=2, sort_keys=True, separators=(',', ': '))
