<picture>
  <source srcset="/unfurl/static/unfurl_dark.png" media="(prefers-color-scheme: dark)">
  <img src="/unfurl/static/unfurl.png" alt="Unfurl Logo">
</picture>

# Extract and Visualize Data from URLs using Unfurl
Unfurl takes a URL and expands ("unfurls") it into a directed graph, extracting every bit of information from the URL and 
exposing the obscured. It does this by breaking up a URL into components, extracting as much information as it can from 
each piece, and presenting it all visually. This “show your work” approach (along with embedded references and documentation) 
makes the analysis transparent to the user and helps them learn about (and discover) semantic and syntactical URL structures.

Unfurl has parsers for URLs, search engines, chat applications, social media sites, and more. It also has more generic parsers 
(timestamps, UUIDs, etc) helpful for exploring new URLs or reverse engineering. It’s also easy to build new parsers, since 
Unfurl is open source (Python 3) and has an extensible plugin system.

No matter if you extracted a URL from a memory image, carved it from slack space, or pulled it from a browser’s history file, 
Unfurl can help you get the most out of it.

<img src="docs/unfurl-demo.gif"/>

## How to use Unfurl

### Online Version

1. There is an online version at **https://dfir.blog/unfurl**. Visit that page, enter the URL in the form, and 
click 'Unfurl!'. 
2. You can also access the online version using a bookmarklet - create a new bookmark and paste 
`javascript:window.location.href='https://dfir.blog/unfurl/?url='+window.location.href;` as the location. Then when on any
page with an interesting URL, you can click the bookmarklet and see the URL "unfurled".

### Local Python Install

Unfurl requires Python 3.11 or newer.

1. Install via pip: `pip install dfir-unfurl[all]`

After Unfurl is installed, you can run use it via the web app or command-line:

1. Run `unfurl_app`
1. Browse to localhost:5000/ (editable via config file)
1. Enter the URL to unfurl in the form, and 'Unfurl!'

OR

1. Run `unfurl https://twitter.com/_RyanBenson/status/1205161015177961473`
1. Output: 
```
[1] https://twitter.com/_RyanBenson/status/1205161015177961473
 ├─(u)─[2] Scheme: https
 ├─(u)─[3] twitter.com
 |  ├─(u)─[5] Domain Name: twitter.com
 |  └─(u)─[6] TLD: com
 └─(u)─[4] /_RyanBenson/status/1205161015177961473
    ├─(u)─[7] 1: _RyanBenson
    ├─(u)─[8] 2: status
    └─(u)─[9] 3: 1205161015177961473
       ├─(❄)─[10] Timestamp: 1576167751484
       |  └─(🕓)─[13] 2019-12-12 16:22:31.484
       ├─(❄)─[11] Machine ID: 334
       └─(❄)─[12] Sequence: 1 
```

If the URL has special characters (like "&") that your shell might interpret as a command, put the URL in quotes. 
Example: `unfurl "https://www.google.com/search?&ei=yTLGXeyKN_2y0PEP2smVuAg&q=dfir.blog&oq=dfir.blog&ved=0ahUKEwisk-WjmNzlAhV9GTQIHdpkBYcQ4dUDCAg"`

`unfurl` has a number of command line options to modify its behavior:
```
positional arguments:
  what_to_unfurl        what to unfurl. typically this is a URL, but it also
                        supports integers (timestamps), encoded protobufs, and
                        more. if this is instead a file path, unfurl will open
                        that file and process each line in it as a separate
                        input.

options:
  -h, --help            show this help message and exit
  -d, --detailed        show more detailed explanations.
  -f, --filter FILTER   only output lines that match this filter.
  -l, --lookups         allow remote lookups to enhance results.
  -o, --output OUTPUT   file to save output (as CSV) to. if omitted, output is
                        sent to stdout (typically this means displayed in the
                        console).
  -t, --type {tree,json}
                        Type of output to produce
  -v, -V, --version     show program's version number and exit
```

`-l` enables remote lookups for a single run; see [Configuration](#configuration) to turn
them on persistently.

### Docker 

1. `git clone https://github.com/RyanDFIR/unfurl`
1. `cd unfurl`
1. `docker compose up -d`

`docker-compose.yaml` mounts the repo's `unfurl.ini` into the container read-only.
`unfurl.local.ini` is *not* mounted, and `.dockerignore` keeps it out of the image, so
your API keys are never baked into an image layer. Pass them — and the remote-lookups
switch, which is off by default — to the container as environment variables instead, via
the `environment:` block in `docker-compose.yaml`:

```yaml
    environment:
      - PYTHONUNBUFFERED=1
      - UNFURL_REMOTE_LOOKUPS=true
      - UNFURL_VIRUSTOTAL_API_KEY=<your key>
```

## Configuration

Unfurl reads its settings from `unfurl.ini`:

```ini
[UNFURL_APP]
host = localhost
port = 5000
remote_lookups = false
debug = false

[API_KEYS]
bitly =
virustotal =
google_kg =
```

`remote_lookups` controls whether Unfurl may send data from the URL being analyzed to
external destinations, including third-party APIs (VirusTotal, Bitly, and Google Knowledge 
Graph). It is `false` by default, and the API keys are only used when it is enabled.

### Setting your own values

`unfurl.ini` is tracked in git as a template, so it ships with empty API keys. Rather
than editing it — which risks committing your keys — put your values in
**`unfurl.local.ini`** next to it. That file is gitignored, and anything in it overrides
`unfurl.ini`:

```ini
[UNFURL_APP]
remote_lookups = true

[API_KEYS]
virustotal = <your key>
```

Only the values you want to change need to appear; anything omitted falls back to
`unfurl.ini`. Both files are looked for alongside the installed package and in the
current working directory.

### Environment variables

Settings can also be supplied as environment variables, which is usually the most
convenient way to configure a container:

| Config key | Environment variable | |
|---|---|---|
| `bitly` | `UNFURL_BITLY_API_KEY` | used when neither config file sets that key |
| `virustotal` | `UNFURL_VIRUSTOTAL_API_KEY` | " |
| `google_kg` | `UNFURL_GOOGLE_KG_API_KEY` | " |
| `remote_lookups` | `UNFURL_REMOTE_LOOKUPS` | **overrides** both config files |

`UNFURL_REMOTE_LOOKUPS` takes the same values as the config file (`true`/`yes`/`on`/`1`
and their negatives). Unlike the API keys, it *overrides* the config files rather than
falling back to them — otherwise it would be useless in a container, where `unfurl.ini`
is mounted from the host. Because enabling it means data from the input gets sent to
third parties, Unfurl logs a warning when the environment turns it on, and any value it
can't interpret leaves lookups disabled rather than falling through to the config file.
The CLI's `-l` still wins over both.

Older versions read a bare lowercase variable instead (`virustotal`, `bitly`,
`google_kg`). Those still work, but are deprecated and log a warning — rename them to the
`UNFURL_*_API_KEY` form above. The bare names are easy to collide with, and because
environment variables are case-sensitive on Linux and macOS but not on Windows, they can
work on one platform and silently do nothing on another.

## Testing 

1. All tests are run automatically on each PR by GitHub Actions. Tests need to pass before merging. 
1. While not required, it is strongly encouraged to add tests that cover any new features in a PR. 
1. To manually run all tests (units and integration): ``python -m unittest discover -s unfurl/tests``

If using Docker as above, run: 
``docker exec unfurl python -m unittest discover -s unfurl/tests``

### Validating an installed copy

The tests ship with the package, so you can run them against the exact copy you have
installed rather than against a fresh checkout. That is useful for validating the tool in
the environment you'll actually use it in:

```
python -m unittest discover -s unfurl.tests.unit
```

This works from any directory. Use `-s unfurl.tests` to include the integration tests as
well; those exercise the web API and need the `ui` extra (`pip install dfir-unfurl[ui]`)
for Flask. Neither set requires network access.
