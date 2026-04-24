# Research Methodology

Evidence-first protocol for marketing decisions. Use this reference whenever the problem requires structured research, hypothesis design, or validation planning.

---

## Confidence Classification

Assign one of these levels before making any claim or recommendation:

| Level | Meaning | Requirement before proceeding |
|---|---|---|
| **Confirmed** | Directly observed data, primary source | Cite source and date |
| **High** | Strong indirect evidence from multiple sources | Cite sources, note alignment |
| **Medium** | Plausible based on analogy or partial data | Label as hypothesis, state assumptions |
| **Low** | Reasoned inference, limited evidence | State explicitly, do not present as fact |
| **Needs research** | Insufficient basis to form a view | Stop and research before continuing |

Never proceed past "Needs research" without either finding the data or surfacing the gap to the user.

---

## Hypothesis Formation

A well-formed marketing hypothesis has three parts:

```
If [we do X],
then [we will see Y],
because [mechanism Z].
```

**Examples:**

- If we optimize the App Store title to lead with the primary use case keyword, then conversion rate from search will increase by 10-15%, because searchers with high intent will see an exact match to their query.
- If we lower the entry-tier price from $29 to $19, then trial-to-paid conversion will increase without proportionally reducing revenue, because current price point exceeds the psychological threshold for the target segment (Medium confidence — needs Van Westendorp validation).

**Embedded assumptions checklist:**
- What does this assume about user behavior?
- What does this assume about the competitive context?
- What does this assume about our own product or capacity?
- What would have to be true for this hypothesis to fail?

State all assumptions explicitly. Hidden assumptions are the most common source of failed marketing bets.

---

## Research Sequencing

Run research in this order to avoid wasted effort:

1. **Desk research first** — What is already publicly known? Use web search for: market reports, competitor public data, academic studies, industry benchmarks, case studies.
2. **Proxy data** — When primary data is unavailable, use proxies: app store review sentiment as a proxy for churn reasons; keyword search volume as a proxy for demand; LinkedIn job postings as a proxy for competitor investment areas.
3. **Qualitative before quantitative** — When the question is "why," talk to users (even 5 interviews surface patterns). Do not run a survey before you understand what to ask.
4. **Quantitative to measure, not discover** — Surveys and A/B tests confirm or size something you already understand directionally. They rarely generate insight on their own.

---

## Validation Methods by Question Type

| Question | Validation method |
|---|---|
| Is there demand for this product/feature? | Keyword search volume, waitlist conversion, landing page test |
| What is the right price? | Van Westendorp Price Sensitivity Meter, Gabor-Granger, pricing page A/B test |
| Why are users churning? | Exit surveys, churn cohort analysis, support ticket clustering |
| Which message resonates? | Ad creative A/B test, email subject line test, 5-second test |
| Which channel acquires best? | CAC by channel, LTV:CAC by cohort, payback period |
| Does this SEO strategy work? | Keyword ranking movement, organic traffic, click-through rate |
| Does this ASO change work? | Conversion rate by traffic source (search vs. browse), keyword rank |
| Is this positioning differentiated? | Competitive message mapping, customer perception survey |

---

## Using Web Search Effectively

Before searching, form a specific question. Vague searches return vague results.

**High-signal search patterns:**
- `[competitor] pricing site:[competitor.com]` — find published pricing
- `[keyword] "market size" OR "TAM" filetype:pdf` — find market reports
- `[app name] reviews site:reddit.com` — find unfiltered user sentiment
- `"[job title]" site:linkedin.com/jobs [company]` — infer competitor investment areas
- `[keyword] trend site:trends.google.com` — check demand trajectory

Always note: source name, publication date, sample size (if survey), and geographic scope. A US benchmark applied to a European market is a hypothesis, not a fact.

---

## Using `/find-skills`

Before attempting any specialized data task manually, run `/find-skills` with a description of what you need. Common cases:

- Need to scrape or interact with a web page → find a browser/scraping skill
- Need to analyze a dataset → find a data analysis skill
- Need to process a document or PDF → find a document skill
- Need to generate or edit visuals → find an image/design skill

Do not manually attempt what a specialized tool handles better. The `/find-skills` call takes seconds; a manual workaround may take much longer and produce lower quality results.

---

## Common Research Failure Modes

Avoid these:

- **Confirmation bias** — searching for evidence that supports a pre-formed conclusion instead of testing it. Counter: write down what would prove you wrong, then look for that evidence first.
- **Recency bias** — assuming current trends continue indefinitely. Counter: check historical cycles, seasonality, and category maturity signals.
- **Survivorship bias** — studying successful brands without studying failures. Counter: for every "X worked for [famous brand]," ask "how many tried X and failed?"
- **Small sample extrapolation** — citing one study or one competitor as representative. Counter: require at least two independent sources before treating something as a benchmark.
- **Precision theater** — presenting numbers with false precision (e.g., "37.4% of users will convert") when the data cannot support that precision. Counter: use ranges and state the basis.
