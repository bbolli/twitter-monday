## twitter-monday

Usage: `python monday.py [ <date>|<from>..<to> ...]`

`monday.py` creates a blog entry containing one week's worth of tweets.

Without arguments, the period is the last week (Monday to Sunday). With
parameters, entries are generated for the week “surrounding” each date given
(again, Monday to Sunday). Ranges are allowed; start and end dates are
separated by two full stops (`..`).

The files are created under `tweets/<year>/short-<year>-<month>-<day>.txt`.

### Authentication

The first time you run `monday`, a browser window opens and you have to allow
access to your Twitter account. The resulting OAuth credentials are stored in
your home folder as `.twitter_monday_oauth`. Your Twitter password is not
saved.

## twitter-complete

`python complete.py [-f] [-r] [screen_name]`

`complete.py` creates a complete backup of your or `screen_name`'s tweets, as
far as they are returned by the Twitter API.

The output is a file called `@<screen_name>.json`. It contains the tweets in
their original JSON format.

Option `-f` returns the user's favorite tweets instead of their own. In this
case, the output file's name is `@<screen_name>-favs.json`.

With option `-r`, shortened `t.co` URLs are expanded.

## Dependencies

These tools require the Twitter library from https://github.com/sixohsix/twitter

## License

[MIT](LICENSE)

<!-- vim: set tw=78: -->
