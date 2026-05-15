# Schema Markup Report: weerzone.nl
**Analyse via broncode — 2026-05-05**

---

## Validation Results

| Pagina | Schema Type | Status | Probleem |
|--------|-------------|--------|---------|
| `/homepage` | WebSite + SearchAction | ⚠️ | SearchAction target `{city}` matcht niet met URL-structuur `/weer/[province]/[place]` |
| `/homepage` | Organization | ⚠️ | `sameAs: []` — lege array, verwijder of vul in |
| `/homepage` | **FAQPage** | ❌ | **RESTRICTED** — alleen voor overheid/zorg sinds aug 2023 |
| `/layout.tsx` (global) | Organization | ✅ | OK |
| `/weer` | Organization | ⚠️ | Duplicaat — al globaal in layout |
| `/weer` | **WebSite** | ❌ | Duplicaat — WebSite hoort alleen op homepage |
| `/weer` | BreadcrumbList | ✅ | OK |
| `/weer/[province]` | BreadcrumbList | ✅ | OK |
| `/weer/[province]` | ItemList | ✅ | OK |
| `/weer/[province]` | **FAQPage** | ❌ | **RESTRICTED** — op 12 provincies |
| `/weer/[province]/[place]` | **WeatherForecast** | ❌ | **Ongeldig @type** — bestaat niet in schema.org |
| `/weer/[province]/[place]` | **FAQPage** | ❌ | **RESTRICTED** — op ~9.000+ stedenpagina's |
| `/weer/[province]/[place]` | BreadcrumbList | ✅ | OK |
| `/prijzen` | — | ❌ | **Geen schema** — Product + Offer ontbreekt |

---

## Kritieke Issues

### 1. FAQPage op 9.000+ pagina's — SPAM-RISICO
**Locaties:** `homepage`, `[province]` (×12), `[place]` (×9.000+)

FAQPage is sinds augustus 2023 beperkt tot overheids- en gezondheidszorgsites. Google negeert het niet alleen — het kan als structured data spam worden gezien bij massaal gebruik op commerciële pagina's.

**Fix:** Verwijder FAQPage uit alle drie locaties.

### 2. WeatherForecast is geen geldig schema.org type
**Locatie:** `src/app/weer/[province]/[place]/page.tsx`

`@type: "WeatherForecast"` bestaat niet in de schema.org-hiërarchie. Google's parser negeert het volledig — alle rijke data erin (locatie, temperatuur, provider) wordt nooit verwerkt.

**Fix:** Vervang door `WebPage` met `about` (City), `dateModified`, en `publisher`.

### 3. Dubbele WebSite schema op /weer
`WebSite` schema hoort sitebreed één keer voor te komen — op de homepage. De dubbele op `/weer` kan conflicteren met Google's SearchAction-parsing.

---

## Verbeterkansen (niet kritiek)

### 4. Product + Offer ontbreekt op /prijzen
De prijzenpagina heeft geen structured data. Google kan de abonnementsprijzen niet tonen in rich results. Met `Product` + `Offer` per tier is prijs-markup mogelijk in Google Shopping en Knowledge Panel.

### 5. SearchAction URL-structuur inconsistent
Homepage target: `https://weerzone.nl/weer/{city}` — maar steden zitten op `/weer/[province]/[place]`. Dit werkt nooit als sitelinks-searchbox. Veiligste optie: verwijder de SearchAction of voeg een echte zoekroute toe.

---

## Fixes die worden doorgevoerd

- [x] FAQPage verwijderen uit homepage
- [x] FAQPage verwijderen uit province pagina's
- [x] WeatherForecast → WebPage op city pagina's + FAQPage verwijderen
- [x] Dubbele WebSite + Organization verwijderen van /weer
- [x] Product + Offer toevoegen aan /prijzen (server-rendered)
- [x] Lege sameAs verwijderen van homepage Organization
