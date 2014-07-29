## twitter-monday

Usage: `python monday.py [<date> ...]`

`monday.py` creates a blog entry containing one week's worth of tweets.

Without arguments, the period is the last week (Monday to Sunday). With
parameters, entries are generated for the week “surrounding” each date given
(again, Monday to Sunday).

The files are created under `tweets/<year>/short-<year>-<month>-<day>.txt`.

### Authentication

The first time you run `monday`, a browser window opens and you have to allow
access to your Twitter account. The resulting OAuth credentials are stored in
your home folder as `.twitter_monday_oauth`. Your Twitter password is not
saved.

## Dependencies

These tools require the Twitter library from https://github.com/sixohsix/twitter

## License

[MIT](LICENSE)

<!-- vim: set tw=78: -->
