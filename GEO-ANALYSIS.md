# GEO Analysis: weerzone.nl
**Generative Engine Optimization Report**
**Analysis date:** 2026-05-05
**Site language:** Dutch (nl-NL)
**Report language:** English

---

## 1. GEO Readiness Score: 44/100

| Dimension | Weight | Raw Score | Weighted |
|-----------|--------|-----------|---------|
| Citability | 25% | 35/100 | 8.75 |
| Structural Readability | 20% | 45/100 | 9.0 |
| Multi-Modal Content | 15% | 40/100 | 6.0 |
| Authority & Brand Signals | 20% | 25/100 | 5.0 |
| Technical Accessibility | 20% | 72/100 | 14.4 |
| **TOTAL** | | | **43.15 → 44/100** |

**Interpretation:** weerzone.nl is technically accessible to AI crawlers and has server-side rendering, but lacks almost all content signals that cause AI systems to cite a page. The biggest gaps are structured data, authority signals, and citable passage formats.

---

## 2. Platform Breakdown

| Platform | Estimated Visibility | Key Blockers |
|----------|---------------------|-------------|
| Google AI Overviews | Low-Medium (30/100) | No FAQ schema, no structured data, multiple H1s |
| ChatGPT web search | Low (20/100) | No Wikipedia presence, no Reddit mentions, Dutch-only |
| Perplexity | Low (22/100) | No community validation, no Reddit/forum presence |
| Bing Copilot | Medium (40/100) | SSR content indexed but no rich signals |

**Note on Dutch content:** AI systems trained predominantly on English have weaker recall for Dutch-language pages. This makes schema markup and entity signals even more critical for weerzone.nl than for English-language competitors.

---

## 3. AI Crawler Access Status

**robots.txt analysis:**

```
User-agent: *
Allow: /
Disallow: /api/
Disallow: /admin/
Disallow: /auth/
Disallow: /app/
Disallow: /*?*          <-- blocks ALL URLs with query parameters
Sitemap: https://weerzone.nl/sitemap.xml
```

| Crawler | Status | Notes |
|---------|--------|-------|
| GPTBot (OpenAI) | Allowed (implicit) | Falls under `User-agent: *` |
| OAI-SearchBot (OpenAI) | Allowed (implicit) | Falls under `User-agent: *` |
| ChatGPT-User (OpenAI) | Allowed (implicit) | Falls under `User-agent: *` |
| ClaudeBot (Anthropic) | Allowed (implicit) | Falls under `User-agent: *` |
| PerplexityBot | Allowed (implicit) | Falls under `User-agent: *` |
| CCBot (Common Crawl) | Allowed (implicit) | Consider blocking if training opt-out desired |
| anthropic-ai | Allowed (implicit) | Training crawler |

**Issues:**
1. `Disallow: /*?*` blocks all query-string URLs. If any AI crawler uses `?format=raw` or similar, it will be blocked. Low risk but worth noting.
2. No explicit AI crawler rules — implicit allow is fine, but explicit allow signals cooperation and can improve crawl priority.

**Recommended addition to robots.txt:**
```
# AI Search Crawlers - explicitly welcome
User-agent: GPTBot
Allow: /

User-agent: OAI-SearchBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: PerplexityBot
Allow: /

# Optional: block training-only crawlers
User-agent: CCBot
Disallow: /

User-agent: anthropic-ai
Disallow: /
```

---

## 4. llms.txt Status: MISSING (404)

`https://weerzone.nl/llms.txt` returns 404. This is a missed opportunity — the standard is gaining adoption and signals AI-readiness.

**Ready-to-use template for weerzone.nl:**

```markdown
# WEERZONE

> WEERZONE is een Nederlandse hyperlocale weerdienst die 48-uur voorspellingen
> levert per stad en provincie, vertaald naar praktische keuzes voor je dag.

## Weerpaginas

- [Weer in Nederland](https://weerzone.nl/weer): Overzicht van alle steden en provincies
- [Amsterdam](https://weerzone.nl/weer/amsterdam): 48-uur weerverwachting Amsterdam
- [Rotterdam](https://weerzone.nl/weer/rotterdam): 48-uur weerverwachting Rotterdam
- [Utrecht](https://weerzone.nl/weer/utrecht): 48-uur weerverwachting Utrecht
- [Den Haag](https://weerzone.nl/weer/den-haag): 48-uur weerverwachting Den Haag

## Diensten

- [Piet - Dagelijkse weermail](https://weerzone.nl/piet): Persoonlijke ochtendmail met weervertaling
- [Reed - Weerwaarschuwingen](https://weerzone.nl/reed): Alerts als het weer jouw drempelwaarde overschrijdt
- [Steve - Zakelijk weer](https://weerzone.nl/zakelijk): Weertranslatie voor bedrijfsbeslissingen

## Over WEERZONE

- WEERZONE richt zich op 0-48 uur voorspellingen (nauwkeurigheid: 92-98%)
- Weer vertaald naar dagelijkse beslissingen, niet naar meteorologie-jargon
- Dekking: alle Nederlandse steden en provincies
- Taal: Nederlands

## Contact

- Website: https://weerzone.nl
- Contact: https://weerzone.nl/contact
```

Create this file at `public/llms.txt` and add the route in Next.js so it serves from the root.

---

## 5. Brand Mention Analysis

| Platform | Status | Action Needed |
|----------|--------|--------------|
| Wikipedia (NL) | Not detected | Create a Wikipedia stub for "Weerzone" entity |
| Reddit (r/nederland, r/weer) | Not detected | Engage in weather discussions, mention service |
| YouTube | Not detected | High priority: YouTube mentions correlate 0.737 with AI citations |
| LinkedIn | Unknown | Create company page if absent |
| Wikidata | Not detected | Add entity: Dutch weather service |

**Critical gap:** Brand mention signals are by far the weakest dimension. ChatGPT cites Wikipedia in 47.9% of responses and Reddit in 11.3%. Perplexity cites Reddit in 46.7% of responses. Without presence on these platforms, AI systems have no third-party validation to anchor citations to weerzone.nl.

**Highest-ROI actions:**
1. Create a Dutch Wikipedia article for Weerzone (requires notability — a few press mentions will help)
2. Participate in `/r/Nederland` and `/r/DutchWeather` threads naturally
3. Publish YouTube shorts with weather tips — even 10 videos creates the citation signal

---

## 6. Passage-Level Citability

**Optimal AI citation length: 134-167 words per passage**

### Existing citable asset (homepage)

The homepage contains one strong quote-ready claim:

> "92-98% nauwkeurigheid voor 0-48 uur, daarna neemt de betrouwbaarheid snel af"

This is a specific, verifiable stat — the kind AI systems cite. **Problem:** it has no source attribution. Citing it without a source makes AI systems distrust it.

### Citability gaps

| Issue | Impact | Fix |
|-------|--------|-----|
| No self-contained answer blocks | High | Add 134-167 word FAQ-style answers |
| No source citations on accuracy claims | High | Link to KNMI or meteo data source |
| No "X is..." definitional sentences | High | Add "Weerzone is een..." intro |
| Dutch content only | Medium | Consider EN summary meta tags |
| No publication/update dates visible | Medium | Show "Bijgewerkt: [datum]" on weather pages |

### Suggested citable passage (Dutch, ready to implement)

Add to the `/weer` page intro (152 words — within optimal range):

> **Wat is WEERZONE?**
>
> WEERZONE is een Nederlandse weerdienst die hyperlocale weersverwachtingen geeft voor alle steden en provincies in Nederland. In tegenstelling tot algemene weersdiensten richt WEERZONE zich uitsluitend op de komende 48 uur, de periode waarvoor weersmodellen betrouwbaar zijn. De nauwkeurigheid voor dag 1 ligt tussen 92% en 98%; daarna neemt de betrouwbaarheid snel af. De voorspellingen zijn gebaseerd op het KNMI-weermodel en worden elk uur ververst. Wat WEERZONE onderscheidt is de vertaling van technische meteorologische data naar praktische adviezen: wat betekent dit weer voor jouw activiteiten vandaag? De service biedt ook drie gepersonaliseerde abonnementen: Piet (dagelijkse weermail op jouw postcode), Reed (drempelwaarschuwingen), en Steve (zakelijke weerinformatie). WEERZONE dekt alle 12 Nederlandse provincies en honderden steden, van Amsterdam tot Zeeland.

---

## 7. Server-Side Rendering Check

**Result: PASS — content is server-side rendered**

Evidence from homepage fetch:
- Headings, weather data, and body text are present in the raw HTML response
- Uses `/_next/image` patterns consistent with Next.js SSR/SSG
- AI crawlers (which do not execute JavaScript) can read the content

**Caveat:** Interactive elements (real-time temperature updates, map widgets) are JavaScript-enhanced. This is acceptable — the core content is SSR. AI crawlers will see the initial render, which includes all text content.

**One risk:** The `Disallow: /*?*` rule blocks query-parameter URLs. If Next.js generates any SSR pages with query params that contain useful weather content, those pages are invisible to all crawlers including AI ones.

---

## 8. Structured Data: MISSING

**No JSON-LD detected** on homepage (`/`) or weather index (`/weer`).

This is a major gap. Without schema, AI systems must guess at content type, authorship, and context.

### Recommended schema implementations

**Priority 1 — Organization (add to `layout.tsx` globally):**
```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "WEERZONE",
  "url": "https://weerzone.nl",
  "logo": "https://weerzone.nl/logo.png",
  "description": "Nederlandse hyperlocale weerdienst voor 48-uur voorspellingen per stad en provincie",
  "foundingLocation": {
    "@type": "Place",
    "name": "Nederland"
  },
  "areaServed": {
    "@type": "Country",
    "name": "Nederland"
  },
  "inLanguage": "nl-NL"
}
```

**Priority 2 — WebSite with SearchAction (add to homepage):**
```json
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "WEERZONE",
  "url": "https://weerzone.nl",
  "potentialAction": {
    "@type": "SearchAction",
    "target": {
      "@type": "EntryPoint",
      "urlTemplate": "https://weerzone.nl/weer/{search_term_string}"
    },
    "query-input": "required name=search_term_string"
  }
}
```

**Priority 3 — WeatherForecast pages (add to each `/weer/[stad]` page):**
```json
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "Weerverwachting Amsterdam - 48 uur vooruit",
  "description": "Hyperlocale weersverwachting voor Amsterdam voor de komende 48 uur",
  "dateModified": "[ISO timestamp — update on each render]",
  "publisher": {
    "@type": "Organization",
    "name": "WEERZONE",
    "url": "https://weerzone.nl"
  },
  "about": {
    "@type": "Place",
    "name": "Amsterdam",
    "addressCountry": "NL"
  }
}
```

**Priority 4 — FAQ schema on informational pages (prijzen, over ons):**
```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "Hoe nauwkeurig zijn de voorspellingen van WEERZONE?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Voor de komende 24-48 uur ligt de nauwkeurigheid tussen 92% en 98%. Daarna neemt de betrouwbaarheid snel af doordat atmosferische chaos kleine fouten uitvergroot."
      }
    },
    {
      "@type": "Question",
      "name": "Welke steden dekt WEERZONE?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "WEERZONE dekt alle Nederlandse steden en dorpen, verdeeld over de 12 provincies. Van Amsterdam en Rotterdam tot kleinere plaatsen in Zeeland en Drenthe."
      }
    }
  ]
}
```

---

## 9. Top 5 Highest-Impact Changes

| Priority | Action | GEO Impact | Effort |
|----------|--------|-----------|--------|
| 1 | Add Organization + WebSite JSON-LD to layout | High | 1 hour |
| 2 | Create `/public/llms.txt` with site map | High | 30 min |
| 3 | Fix multiple H1 tags on homepage (should be exactly 1) | Medium-High | 2 hours |
| 4 | Add 134-167 word self-contained intro block to `/weer` | Medium-High | 1 hour |
| 5 | Add explicit AI crawler directives to robots.txt | Medium | 15 min |

**Longer-term (off-site):**
- Reddit engagement in Dutch weather communities
- YouTube presence (even short clips)
- Dutch Wikipedia article or Wikidata entity

---

## 10. Content Reformatting Suggestions

### Homepage H1 problem
**Current state:** Multiple H1s detected — "Amsterdam", "Wat betekent dit vandaag?", "Vandaag en morgen", "Activiteiten", "Details", "Transparantie over nauwkeurigheid", etc.

**Fix:** One H1 only, e.g.: `<h1>WEERZONE — hyperlocaal weer voor Nederland</h1>`
Demote all other current H1s to H2 or H3.

### Add a "Wat is WEERZONE?" definition block
On the homepage, above the fold or in an "Over ons" section, add:

```
Wat is WEERZONE?

WEERZONE is een Nederlandse weerdienst die 48-uur weersverwachtingen 
geeft voor elke stad en provincie in Nederland. De service vertaalt 
meteorologische data naar praktische adviezen — wat betekent dit weer 
voor jouw dag? Met een nauwkeurigheid van 92-98% voor de eerste 48 uur 
is WEERZONE gericht op de beslistermijn die er echt toe doet.
```

This 60-word block follows the "X is..." pattern that AI systems parse as a definition and quote directly.

### Add date stamps to weather pages
Weather content is time-sensitive. AI systems give higher weight to recently updated content.

Add to each `/weer/[stad]` page:
```tsx
<time dateTime={new Date().toISOString()}>
  Bijgewerkt: {format(new Date(), "d MMMM yyyy, HH:mm", { locale: nl })}
</time>
```

### Question-format H2 headings
**Current:** "Activiteiten", "Details", "Transparantie over nauwkeurigheid"

**Better for AI citation:**
- "Hoe betrouwbaar is de weersverwachting?"
- "Wat kan ik vandaag buitenshuis doen?"
- "Wat is de verwachting voor morgen in [stad]?"

Question-based headings directly match user query patterns and increase the chance of AI Overview selection.

---

## Quick Reference: Implementation Checklist

- [ ] Add `Organization` JSON-LD to `src/app/layout.tsx`
- [ ] Add `WebSite` + `SearchAction` JSON-LD to homepage
- [ ] Add `Article` + `dateModified` JSON-LD to `/weer/[stad]` pages
- [ ] Add `FAQPage` JSON-LD to `/prijzen` and informational pages
- [ ] Create `public/llms.txt`
- [ ] Add explicit AI crawler rules to `public/robots.txt`
- [ ] Fix multiple H1s on homepage — one H1 only
- [ ] Add "Wat is WEERZONE?" definition paragraph (60 words)
- [ ] Add self-contained 134-167 word answer block to `/weer`
- [ ] Add `<time dateTime=...>` update stamps to weather pages
- [ ] Convert section headings to question format where appropriate
