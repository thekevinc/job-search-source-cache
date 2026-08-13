# Job Search Source Cache

This repository is a public, non-personal cache of canonical employer job-board
sources. A daily GitHub Action discovers ATS links in public GitHub content,
validates their public job feeds, and refreshes this file without third-party
hosting or API keys.

The cache is intentionally limited to public ATS metadata. It must not contain
applicant identity, search criteria, compensation requirements, job matches,
application history, reports, email addresses, credentials, or secrets.

## Data file

`employer_sources.json` is the machine-readable cache. Each source records:

- `company`: public employer name;
- `type`: supported ATS type (`greenhouse`, `lever`, or `ashby`);
- `board` or `site`: public ATS board identifier;
- `first_discovered_at`: UTC timestamp of initial discovery;
- `last_checked_at`: UTC timestamp of the last successful validation;
- `last_relevant_listing_at`: UTC timestamp of the last relevant listing;
- `active_until`: UTC timestamp 90 days after the last relevant listing; and
- `consecutive_failures`: validation failure count.

Consumers must validate the file against `employer_sources.schema.json`, ignore
expired entries, and treat a missing or invalid cache as an empty source list.

## Refresh workflow

`.github/workflows/refresh-sources.yml` runs daily and can also be dispatched
manually. It uses the repository-scoped `GITHUB_TOKEN` supplied automatically by
GitHub Actions. No personal access token, OpenAI API key, or hosted database is
required.

Discovery is intentionally broad and generic. Candidate Greenhouse, Lever, and
Ashby board identifiers are extracted from public GitHub code search results.
Only boards with a current software-engineering listing enter the cache. Existing
boards remain for 90 days after their last relevant listing.

## Retention

A relevant listing resets the source's 90-day retention window. Recommended
polling frequency is daily for days 0-14, weekly for days 15-45, and every two
weeks for days 46-90. Broad discovery remains responsible for rediscovering a
source after it expires.

## Security boundary

Everything in this repository is public. Keep personal job-search state in a
separate private repository.
