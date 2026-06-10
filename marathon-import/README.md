# `marathon-import/`

Tooling for ingesting Marathon Hardware catalog data into
`southbrook_hardware_catalog`. Two scripts, one CSV.

## `run_full_crawl.sh`

Crawls all 10 Marathon top-level category pages via headed Chrome
(Marathon CF-challenges headless). Outputs one `marathon_<cat>.json`
+ `marathon_<cat>.csv` per category alongside this script.

```sh
./run_full_crawl.sh   # needs a display attached
```

Each category typically yields 50-400 products; full crawl is
10-30 min.

## `ingest.py`

Reads every `marathon_*.json` here, dedupes against templates already
shipping in `addons/southbrook_hardware_catalog/data/`, and emits a
single ingest XML at `data/marathon_ingest_<date>.xml`.

```sh
python3 ingest.py             # write the XML
python3 ingest.py --dry-run   # stats only, no file
python3 ingest.py --out X.xml # override path
```

Brand and category are inferred from each product's name + declared
fields using the rule tables at the top of the script. Per-finish
variants spawn only when the source data has a clean `finish` list
(crawler-quality, not browser_20-noisy).

The seed is idempotent — re-running after a new crawl emits ONLY the
delta (new SKUs + new finish values).

## `res.partner.marathon.csv`

Bootstrapping vendor master record. Imported by
`addons/southbrook_hardware_catalog/data/res_partner_marathon.xml`.

## Workflow

1. Run `./run_full_crawl.sh` — writes JSON per category
2. Run `python3 ingest.py` — produces XML
3. Add the new file to the addon's `__manifest__.py` data list
4. `./scripts/deploy_to_qnap.sh southbrook_hardware_catalog`
