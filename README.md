# finaccess

Exploring the FinAccess 2024 household survey (Kenya) to find where financial access and usage gaps are, for whom, and in which products.

> **Hypothetical case study.** This is an exercise in turning survey microdata into insight for fintech founders. The outputs are not market advice.

## Goal

Answer questions a fintech founder would ask when choosing where to build, using the latest FinAccess round (2024):

- Who is underserved, and where? (dimensions: county, sex, age group, education)
- Which products are used, and how does that vary across those dimensions? (savings, credit, insurance, pensions, mobile money, SACCOs, chamas)
- Why do adults not use a product: is it awareness, cost, trust, documents or distance? (the survey has no direct awareness question, so this is answered through the stated reasons for non-use)

The emphasis is on **gaps**: segments that lag the national picture, and how many adults that represents. A gap is only a niche if it is large enough to build for, so every gap is sized in adults.

## Pipeline

1. Download the raw xlsx (see below), which holds all 3,816 survey variables
2. `to_parquet.py` converts it to `finaccess_2024_optimized.parquet` (all columns stored as strings, label text for coded values)
3. `to_typed_parquet.py` builds `finaccess_2024_typed.parquet`: `#NULL!` becomes NULL and unlabelled numeric columns get real types (labelled and text columns stay strings); `finaccess_2024_typed_report.csv` lists every column's final type
4. Analyse the parquet with DuckDB (see `exp.py`)
5. `metrics.py` computes the weighted share of adults served by each product, overall and by segment; `gaps.py` ranks the lagging segments and products (results in `src/finaccess/results/`)
6. `barriers.py` groups the reasons adults give for not using six products into the report's barrier categories (`results/barriers.csv`)
7. `niches.py` combines the gaps and the barriers into a rule-based niche shortlist (`results/niches.csv`)
8. `build_site.py` turns the results into a single-page data story, `site/index.html`
9. `create_ddl.py` and `values.py` use the data dictionary to produce Postgres DDL and processed value labels


## Finding the gaps

```sh
uv run python -m finaccess.metrics   # results/metrics_by_segment.csv
uv run python -m finaccess.gaps      # results/segment_gaps.csv, results/product_gaps.csv
uv run pytest
```

**Method.** Eleven "served" metrics built on the survey's own derived indicators (any access, formal access, mobile money, bank, savings, loan, digital credit, app-based digital loans, insurance, pension, SACCO). Each is the share of adults (18+) served, weighted with `indWeight`, for all adults and for mobile money users, cut by county, sex, age group and education. `metrics.py` checks the national figures against the 2024 report (formal access 84.8%, excluded 9.9%, 14.8 million bank users, credit usage 64.0%, savings 68.1%) and fails if they drift.

- `gap_pp`: segment share minus national share
- `gap_adults`: adults who would be served if the segment matched the national share. This is the size of the opportunity.
- A segment is a gap if it lags by 5+ points or sits 25%+ below the national share (the relative rule covers low-prevalence products like app-based digital loans). Segments with fewer than 30 sampled adults are flagged and never ranked.

**Product gaps** (adults 18+, 28.1M):

| Product | Served | Unserved adults | Unserved mobile money users |
|---|---|---|---|
| App-based digital loans | 2.4% | 27.5M | 24.4M |
| SACCO | 11.7% | 24.9M | 21.9M |
| Pension | 11.8% | 24.8M | 21.8M |
| Insurance (incl. NHIF) | 22.0% | 22.0M | 19.0M |
| Digital credit (broad) | 29.6% | 19.8M | 16.9M |
| Bank | 52.5% | 13.4M | 10.7M |
| Loan | 64.0% | 10.1M | 8.0M |
| Savings | 68.1% | 9.0M | 6.9M |
| Mobile money access | 89.2% | 3.0M | 0 |

Mobile money is close to universal, yet most mobile money users have no insurance, pension or SACCO account, and about two in three have used no digital credit at all. That is the adjacent gap: the rail exists, the product does not.

**Two digital credit measures.** "Digital credit (broad)" is the survey's `Digital_credit_2`: Hustler Fund, mobile money and mobile banking loans. The report puts Hustler Fund usage alone at 28.9% of adults, and this indicator is close (29.6%) but I have not validated it exactly. "App-based digital loans" is `Digital_credit_usage`, which covers lending apps only. It is about 2% of adults, which matches the report's Figure 3.7 (roughly 0-4% across wealth quintiles), so app lending is a thin market, not a gap that mobile money or Hustler Fund users are missing out on. An earlier version of this README presented the 2.4% figure as digital credit overall; that overstated the gap.

**Largest lagging segments** (all adults, by `gap_adults`):

- Ages 18-25: formal access 69.0% (about 1.2M adults short of the national share), loans 50.3%, insurance 10.6%
- Adults with no formal education: bank 18.5%, savings 38.3% (about 0.9M and 0.8M short)
- Women: bank 46.5%, insurance 16.1%, pension 7.7% (0.6-0.9M short each)
- Counties: formal access in West Pokot (48.5%) and Turkana (65.9%); insurance in Kitui (8.6%) and Kakamega (13.8%)
- Digital credit (broad): adults over 55 (11.6%, about 0.7M short) and adults with no formal education (7.7%, about 0.6M short)

Read `segment_gaps.csv` for the full ranking, including the mobile-money-user cut.

**Limits.**
- Descriptive, not causal. Young adults lag on loans and insurance partly because of life stage, so a gap is not automatically an opportunity.
- No design-based standard errors: weights are applied but survey strata and clusters are not. County estimates rest on roughly 350-550 interviews each, so treat small differences between counties with caution.
- No urban/rural variable in the public data.
- One survey round, so no trends. The "served" definitions are the survey's derived indicators, not ours.

## Why the gaps exist: barriers

```sh
uv run python -m finaccess.barriers   # results/barriers.csv
```

The survey asks adults who do not use a product why not (insurance, credit, savings, bank account, mobile money, mobile banking). `barriers.py` groups the individual reasons into the six categories the 2024 report uses in Figure 3.9 (affordability, awareness, relevance, trust, eligibility, physical access) plus "other". **The grouping of individual reasons is my judgement**; the mapping is the `BARRIERS` table in the code.

Each row gives two measures. `share_citing` is the weighted share of the adults who were asked that cite the barrier (people can cite several, so shares do not sum to 100). `share_of_mentions` is the barrier's share of all reasons given, which is how the report draws its figure. The base is adults who were asked the question, not the derived non-usage flag, because the two differ (the bank question was also asked of some mobile-banking users).

**Share of non-users citing each barrier** (adults 18+):

| Product | Affordability | Awareness | Relevance | Trust | Eligibility | Physical access |
|---|---|---|---|---|---|---|
| Savings | 87.5% | 19.5% | 5.9% | 1.0% | 12.5% | n/a |
| Bank account | 82.1% | 6.1% | 10.1% | 1.4% | 8.7% | 6.6% |
| Insurance | 76.2% | 23.4% | 7.9% | 1.6% | 8.4% | n/a |
| Credit | 54.7% | 10.4% | 52.3% | 4.9% | 13.7% | n/a |
| Mobile banking | 47.7% | 21.0% | 23.9% | 1.5% | 10.5% | 16.9% |
| Mobile money | 32.0% | 7.0% | 5.2% | 0.6% | 46.1% | 51.0% |

How to read it:
- **Affordability dominates** for savings, banks and insurance, so a product for those has to be cheap or income-linked before anything else matters.
- **Awareness is real but secondary.** About 4.3M insurance non-users and 3.3M mobile banking non-users cite not knowing or understanding the product. That is a reach and education problem a fintech can address.
- **Credit is a relevance problem as much as a cost one** (52% do not want or see a use for loans), so more credit supply alone will not close that gap.
- **Mobile money is blocked by phones, network and ID**, not by cost or awareness.

**Where awareness is the barrier** (largest gaps against the national share; read with the sample size in mind): insurance in Trans Nzoia, Mandera, Turkana and Marsabit; savings in Turkana, Mandera; mobile banking among adults with no formal education (42%) and in Marsabit and Samburu. Several of these counties have only 35-100 respondents asked, so treat them as leads, not findings.

**Check against the report.** Insurance matches Figure 3.9 closely (affordability 63.3% vs 63.2%, awareness 19.5% vs 19.4% as share of reasons), and `barriers.py` fails if it drifts. Bank is within about 4 points but not exact, probably because of a different base or grouping, so it is not asserted. The report's narrative also agrees: affordability leads for savings, banks and insurance, relevance for mobile banking and credit, and phones for mobile money.

## From gaps to niches

```sh
uv run python -m finaccess.niches   # results/niches.csv
```

The shortlist is picked by a rule, not by hand. For each product (mobile money, bank, savings, loans, digital credit, insurance, pension, SACCO), take the segment with the largest `gap_adults` among segments that already pass the gap rules, then attach the two barriers non-users in that segment cite most, and what a product would have to do about them.

| # | Product | Segment | Served (national) | Adults short | Main barrier, then second | Awareness |
|---|---|---|---|---|---|---|
| 1 | Loans | Ages 18-25 | 50.3% (64.0%) | 1.07M | Affordability 56%, relevance 48% | 10% |
| 2 | Bank account | No formal education | 18.5% (52.5%) | 0.93M | Affordability 80%, awareness 19% | 19% |
| 3 | Insurance | Ages 18-25 | 10.6% (22.0%) | 0.89M | Affordability 74%, awareness 21% | 21% |
| 4 | Savings | No formal education | 38.3% (68.1%) | 0.82M | Affordability 85%, awareness 34% | 34% |
| 5 | Digital credit | Over 55 | 11.6% (29.6%) | 0.72M | not measured | |
| 6 | SACCO | Ages 18-25 | 3.4% (11.7%) | 0.65M | not measured | |
| 7 | Pension | Women | 7.7% (11.8%) | 0.59M | not measured | |
| 8 | Mobile money | Ages 18-25 | 82.6% (89.2%) | 0.52M | Eligibility (ID) 65%, physical access 42% | 4% |

What it says:
- **Young adults (18-25) and adults with no formal education recur** across products, so these are the two groups to design for.
- **For savings, the barrier is price first and awareness second:** one in three non-saving adults with no education cites not knowing how or where to save.
- **Loans for young adults are as much a relevance problem as a price one** (48% do not see a use for a loan as offered).
- **Mobile money for young adults is held back by ID and phone access**, not cost.
- Digital credit, SACCO and pension have no reasons-for-non-use questions in the survey, so the "why" is not measured for them.

**Limits.** Segments overlap: the same 18-25 year olds appear in four of the eight niches, so the "adults short" figures describe each niche on its own and must not be added up. Gap size is measured against the national share, not against a target. A barrier is what non-users in the segment say, and a segment with few respondents falls back to the national barrier for that product (flagged in `barrier_basis`). Everything is descriptive, one survey round, and a hypothetical case study.

## The data story page

```sh
uv run python -m finaccess.build_site   # writes site/index.html
```

`site/index.html` is one self-contained file (no framework, no build step, no external requests): the headline, the product gaps, a segment explorer, the barriers, the niche cards, and a "how far to trust it" table comparing the national figures with the 2024 report. It is generated from `results/*.csv`, so every number comes from the analysis. Edit `src/finaccess/site_template.html` (structure, styling, chart code) and rebuild; do not edit `site/index.html` by hand.

It follows light and dark mode, works at phone width, and every chart has a keyboard-focusable mark and a table view. The categorical colours were checked with the dataviz palette validator in both modes.

**Viewing it:** open `site/index.html` in a browser.

**Hosting it** (the page is static, so any static host works):
- *Render:* New > Static Site, connect this repository, leave the build command empty and set the publish directory to `site`.
- *GitHub Pages:* serve the `site` folder from the repository settings, or copy `site/index.html` to a `gh-pages` branch.

Rebuild and commit `site/index.html` whenever the results change.

## Getting the data

The raw survey xlsx (294 MB) is not stored in the repo. Download it from Google Drive:

```sh
uv sync
uv run python scripts/download_data.py
```

This saves `src/finaccess/2024_Finaccess_Publicdata.xlsx`. Manual link: https://drive.google.com/file/d/1NGPFK6IGwDpLLQJnrBRyMHiXzUypuZHn/view?usp=sharing

## Notes

The project uses polars (and DuckDB) rather than pandas; pandas is not a dependency.

1. preprocess values
2. use variables and preprocessed values to create sql


polars used insead of pandas

ask finaccess to release the data as a parquet file too


show the finaccess questionnaire too: paste the link

identify key metrics and key dimensions relevant to fintech startup founders. look at finaccess dashboard