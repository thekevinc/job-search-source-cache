# Job Search Source Cache

This repository is a public, non-personal cache of canonical employer job-board
sources discovered by an automated job search.

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

## Retention

A relevant listing resets the source's 90-day retention window. Recommended
polling frequency is daily for days 0-14, weekly for days 15-45, and every two
weeks for days 46-90. Broad discovery remains responsible for rediscovering a
source after it expires.

## Security boundary

Everything in this repository is public. Keep personal job-search state in a
separate private repository.
