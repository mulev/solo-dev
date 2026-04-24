# Strategy Frameworks

Reference for go-to-market strategy, brand positioning, pricing decisions, and messaging architecture. Use when developing strategy documents, positioning work, or pricing recommendations.

**These are decision frameworks, not answers.** Each framework embeds assumptions about market structure, buyer behavior, and competitive dynamics. Before applying any framework:

1. Verify the framework's assumptions hold for the specific product and market — a B2C mobile app in a mature category has different dynamics than a B2B tool in an emerging one
2. Treat each framework output as a hypothesis, not a conclusion — apply the confidence classification from `references/research-methodology.md`
3. Name the evidence that supports or contradicts the framework's applicability
4. If the product or market doesn't fit the framework's assumptions, say so and adapt

A framework that fits poorly is worse than no framework at all.

---

## Contents

1. [Go-to-Market (GTM) Framework](#go-to-market-gtm-framework)
2. [Positioning](#positioning)
3. [Pricing Strategy](#pricing-strategy)
4. [Messaging Architecture](#messaging-architecture)
5. [Brand Strategy Foundations](#brand-strategy-foundations)

---

## Go-to-Market (GTM) Framework

A GTM strategy answers six questions in this order. Sequence matters — each answer constrains the next.

### 1. Market selection
- Which segment is experiencing this problem most acutely right now?
- Where do you have the highest probability of winning? (Consider: competition intensity, buyer accessibility, purchase frequency, deal size)
- Initial market is not final market — land where you can win, then expand

**Research required:** market size (addressable, not theoretical), competitor presence per segment, buyer behavior differences across segments

### 2. Ideal Customer Profile (ICP)
- Firmographic (B2B): company size, industry, geography, tech stack, org structure
- Demographic/psychographic (B2C): who they are, what they value, what triggers the purchase
- Behavioral: what they are doing when the problem surfaces, what alternatives they currently use, what would make them switch

**ICP test:** if you described this person to your sales team or a paid acquisition channel, could they find them? If not, the ICP is too vague.

### 3. Positioning
See the Positioning section below.

### 4. Channel strategy
Match channel to ICP buying behavior:

| Channel | Best for | When it does not work |
|---|---|---|
| SEO / content | Long purchase cycles, research-driven buyers, high search volume category | Emerging categories with no search behavior yet |
| Paid search | High-intent buyers actively searching | Low-volume categories, very high CPC relative to LTV |
| Paid social | Awareness, demand generation, interest-based targeting | Pure intent-based purchases where search captures demand |
| Product-led growth | Self-serve products, viral loops, bottoms-up enterprise | Complex products requiring sales assistance to start |
| Sales-led | High ACV, complex evaluation, procurement involvement | Low-margin or self-serve products where sales cost exceeds LTV |
| Partnerships | Category adjacencies, distribution leverage, trust transfer | When partner incentives are misaligned |
| App store (ASO) | Mobile-first products, discovery-driven categories | When users search for solutions on the web first |

### 5. Launch sequence
- Soft launch → closed beta → open beta / public launch → growth phase
- At each stage: define the success criteria before launch, not after
- Identify the leading indicators that predict downstream success (e.g., activation rate predicts retention; retention predicts LTV)

### 6. Metrics and feedback loops
- Define: one primary north star metric + 2-3 leading indicators per quarter
- Distinguish between lag metrics (revenue, churn) and lead metrics (activation, engagement, NPS)
- Frequency: weekly review of lead metrics, monthly review of lag metrics

---

## Positioning

Positioning is the strategic choice of what you are, for whom, and why — made before any messaging is written.

### The positioning statement (internal tool, not customer copy)

```
For [ICP],
[Product name] is the [category frame]
that [primary differentiator / key benefit]
unlike [main alternative],
because [proof / reason to believe].
```

### Category framing decision

How you frame your category determines who you compete against and what comparison set customers use when evaluating you. Options:

- **Own the category** — define yourself as the only thing in a new category you name (high reward, high difficulty; requires significant market education investment)
- **Reframe an existing category** — "the [adjective] [category]" — positions within an existing mental frame with a modifier (e.g., "the modern CRM")
- **Replace an alternative** — position directly against what customers currently use (risky if alternative is beloved; effective if alternative is a pain point)

### Differentiation criteria

A valid differentiator must be:
1. **True** — provable with evidence or product demonstration
2. **Relevant** — ICP actually cares about this, confirmed by research
3. **Distinctive** — competitors are not saying the same thing

Audit competitor messaging before writing yours. If your differentiator appears on three competitors' homepages, it is table stakes, not differentiation.

---

## Pricing Strategy

This section covers pricing frameworks and theory. For the full pricing research pipeline (competitive pricing scraping, price sensitivity analysis, tier design, revenue modeling, A/B test plans), see `references/pricing-playbook.md`.

### Pricing model selection

| Model | Best fit | Avoid when |
|---|---|---|
| Flat rate | Simple product, single ICP segment, low support overhead | Product has widely varying value delivery across customer segments |
| Per-seat / per-user | Collaboration tools, value scales with users, easy to audit | Solo use cases, or when seats create adoption friction |
| Usage-based | Value scales with usage, low-ACV self-serve motion | Hard to predict spend (creates anxiety), enterprise buyers need predictable costs |
| Tiered (feature-gated) | Broad ICP, upsell path exists, clear value ladder | When the differences between tiers are not meaningful to customers |
| Freemium | High viral coefficient, low marginal cost per user, large addressable market | When free users generate significant support cost without converting |

### Pricing research methods

**Van Westendorp Price Sensitivity Meter** — four questions asked to target customers:
1. At what price would this be too cheap to trust?
2. At what price would this be a bargain?
3. At what price is this getting expensive, but still worth considering?
4. At what price is this too expensive?

Plot the intersections to find acceptable price range and optimal price point. Minimum n=50 for directional insight; n=200 for reliable data.

**Gabor-Granger** — present a set of prices, ask purchase likelihood at each. Plot demand curve. Identify the price that maximizes revenue (not volume — these differ).

**Conjoint analysis** — quantifies willingness to pay for specific features by forcing trade-offs between feature bundles at different prices. Most rigorous but requires survey software (Qualtrics, Conjoint.ly).

**Competitive pricing anchor** — position relative to the nearest alternative: 10-30% below signals "accessible," parity signals "comparable quality," premium signals "worth more." Premium positioning requires proof.

### Pricing page principles
- Lead with the recommended plan (visual hierarchy, pre-selected, labeled "Most Popular")
- Make the annual discount visible and the savings concrete ("Save $120/year")
- Show 3-4 tiers maximum — more creates decision paralysis
- Put the pricing table on a standalone `/pricing` page — it signals confidence and is expected by buyers
- Enterprise: "Contact us" is acceptable only if the product genuinely requires custom scoping; use it to avoid publishing prices competitors can undercut

---

## Messaging Architecture

Messaging flows from positioning. Build it in this order:

### Core message (one sentence)
The single most important thing a target customer should believe after any interaction with the brand. Not a tagline — the strategic claim the brand must own.

### Audience variations
The core message adapted for each segment of the ICP. The underlying claim stays constant; the framing and emphasis shift to match each audience's specific context and pain.

### Channel adaptations
Each channel has different format constraints and audience mindset:

| Channel | Mindset | Constraint | Priority |
|---|---|---|---|
| Paid social | Passive, not looking | 3 seconds to earn attention | Disrupt first, value second |
| Search ad | Active intent, comparing | 30-character headline limit | Match the query, deliver the promise |
| Landing page | Evaluating | Time to read if interested | Credibility and specificity |
| Email (cold) | Interrupted, skeptical | 6-word subject line | Relevance to their world, not your product |
| In-product | Already a user | Context-aware | Reinforce value already experienced |
| PR / earned | Reading about a topic | Must be newsworthy | Angle that fits the story, not the ad |

### Message testing
Before scaling spend, test messages with small audiences:
- Paid social: $500-1,000 across 3-5 creative/copy variations; optimize for click-through rate as a proxy for resonance
- Email: subject line A/B test with 20% of list before full send
- Landing page: headline A/B test with 50/50 traffic split for minimum 2 weeks

---

## Brand Strategy Foundations

Brand strategy decisions that affect all downstream executions:

### Brand architecture
- **Monolithic (branded house):** one brand, all products under it. Builds equity fast, requires consistent quality across everything. Example: Apple.
- **Endorsed:** sub-brands with parent visible. Parent brand lends credibility. Example: Marriott/Courtyard by Marriott.
- **House of brands:** independent brands, parent invisible to consumer. Allows differentiated positioning but dilutes investment. Example: P&G.

For most startups: monolithic until there is a genuine reason to diverge.

### Tone of voice
Define along two axes: formal ↔ casual, and earnest ↔ irreverent. Pick a position on each axis. Apply consistently across all customer touchpoints.

**Common failure mode:** casual in social content, formal in legal copy, technical in documentation, friendly in support — four different voices that create a fragmented brand experience. Consistency across touchpoints is more important than optimizing any single touchpoint.
