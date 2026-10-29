# SearchSense: final presentation brief

**ABHIKALP 2026 · Team Outliers · Finals**
An agentic AI mode for the search bar of a multi-category e-commerce platform. Shoppers describe what they need in their own words and get the right products in the right size, with fewer returns.

This file is the source for the final deck. It follows the six areas every presentation must cover, in order. Each section has the slide content, then **"Say"** notes for a conversational delivery. A suggested slide list is at the end.

---

## 0. The one-liner (title slide)

> **Shoppers don't search in keywords. They describe a situation.**
> SearchSense is a team of AI agents inside the search bar. They understand the situation, ask only when they must, find products that fit every need, recommend the right size, and catch returns before checkout.

Live MVP: https://searchsense-e8rmkpxmrlrncputsvc6p2.streamlit.app/ (🎬 Demo tab = the finals walkthrough)

---

## 1. Problem statement & target customer

### The problem
The search bar is where buying intent starts, but it only understands keywords. Real shoppers type situations:

> *"I need a breathable, pastel ethnic outfit for a humid daytime wedding in Mumbai under ₹6,000 that pairs well with silver jewelry"* (the case brief)

A keyword engine can't work out that "humid daytime wedding in Mumbai" means breathable fabrics, light colours and daytime styles. It can't apply a budget, a colour family and an occasion together. When it fails, the shopper gets **no results** or **irrelevant results**, rephrases, gives up, or buys the wrong thing and returns it.

Three failures, one root cause (search doesn't understand intent):
1. **Complex intent is lost.** Multi-constraint, subjective or situational queries give zero or irrelevant results.
2. **No conversation.** A shopper can't say "same but in blue" or "#2 but cheaper". Every refinement starts from scratch.
3. **Wrong size, then a return.** Search ends at the product. Nothing connects the shopper's own size history to what they're about to buy, so size-related returns follow.

### Target customer and primary user
**Primary user:** the online shopper in India who starts at the search bar of a large multi-category platform (fashion, home, beauty, electronics, everyday goods). They're mobile-first, often shop for an occasion, a trip or for someone else, and write the way they speak, including Hinglish, short forms and typos.

**Personas** (from our solution doc; all three are live in the MVP as profiles):

| Persona | Situation | What fails today | What they need |
|---|---|---|---|
| **Priya**, 27, wedding guest | "Breathable pastel ethnic outfit for a humid daytime wedding in Mumbai under ₹6,000" | Zero or irrelevant results | Her whole situation understood in one go |
| **Rohan**, 24, quick shopper | "wite linnen shirt M": fast, typos | Typos give no results or the wrong items | Fixed silently, with a one-tap undo |
| **Ananya**, 31, fit-anxious | Returned jeans for being too small; unsure of her size | The size chart is generic | A size that learns from her own returns |

**Who else benefits:** the platform (conversion, fewer returns, lower reverse-logistics cost) and the catalog team (we flag listings missing key attributes such as fabric).

**Say:** "Every one of us has typed a full sentence into a shopping search bar and got nothing useful back. The case brief's own query gets zero results on Myntra today. We built for Priya, Rohan and Ananya: three shoppers, three different ways search fails them."

---

## 2. Competitor analysis & market research

### What we tested (October 2026, live sites, same queries)

| Query / ask | Myntra search | Amazon search | SearchSense |
|---|---|---|---|
| Case brief: *"I need a breathable, pastel ethnic outfit for a humid daytime wedding in Mumbai under ₹6,000 that pairs well with silver jewelry"* | **"No results"** | **3 results, all off-target:** western dresses (not ethnic); the top of the page is sponsored silver bracelets; an unrelated hair-straightener ad | Ethnic, pastel, breathable outfits under ₹6,000 that suit silver, with every constraint shown as a chip and a size on each card |
| *"tshirts for Manali"* (situational) | Ads and mixed men's/women's results; no idea Manali is cold | *to test* | Keeps the t-shirts, knows Manali is cold, warns the shopper and offers a warm layer in one tap |
| *"Return last order"*, *"Track my order"* | Treated as a product search | Treated as a product search | Recognised as a support request and handed to Customer Care, with no product results |
| Refine: *"same but in blue"*, *"#2 but cheaper"* | Not possible in the search bar (filters only) | Not possible in the search bar (filters only) | The conversation continues: only what you changed changes |
| Ambiguous: *"Marriage outfits"*, *"outfits for jaggu"* | *to test* | *to test* | Asks **one** question (Ethnic or western? Is Jaggu a man or a woman?) |
| Typos and Hinglish: *"vlue tops with flower under 700"*, *"shaadi ke liye kurta"* | *to test* | *to test* | Fixed and mapped (blue, floral print, under ₹700; shaadi → wedding) |
| Right size, inside search and before checkout | Size help on the product page | Size suggestions on some fashion products | A size on every result card with the reason (own orders, brands, returns), plus a pre-checkout size check |

*(Screenshots: Myntra "No results" for the case query; Amazon's 3 results for the case query; Myntra "tshirts for Manali". Put them on the slide, dated. Fill or drop the* to test *cells before the deck: only show what we actually tried.)*

### Existing AI assistants (be ready for this question)
- **Myntra** has **MyFashionGPT** (2023, built with Microsoft on Azure OpenAI) and **Maya**, a chat assistant that asks clarifying questions ([Business Today](https://www.businesstoday.in/amp/technology/news/story/myntra-collaborates-with-microsoft-to-unveil-ai-powered-online-shopping-with-myfashiongpt-410366-2023-12-21), [Apparel Resources](https://apparelresources.com/business-news/retail/myntra-launches-ai-powered-chatbot-maya-personalized-shopping-assistance)).
- **Amazon India** has **Rufus**, a chat assistant, in beta since August 2024, with over 1 crore users per Amazon India ([About Amazon India](https://aboutamazon.in/news/retail/rufus-ai-shopping-assistant-launch-in-india), [YourStory](https://yourstory.com/2024/08/amazon-genai-conversational-shopping-assistant-available-india)).

**The gap they leave:** these are **separate chat surfaces** that a shopper has to find and open. The **search bar**, where most shopping starts, still fails these queries (our tests above). And sizing sits on the product page, apart from search: nothing ties the query, the shopper's own size and returns history, and a pre-checkout return check into one flow.

**Our position:** we don't add another chatbot. We make **the search bar itself agentic**, keep the familiar grid of products, and carry the shopper through to the right size and a return-safe checkout.

### Market research: why search is worth fixing
- **Searchers are the best customers.** Shoppers who use site search convert at about **2.5×** the rate of those who don't (Algolia, via [Xictron](https://www.xictron.com/en/blog/site-search-analytics-onsite-search-2026/), [Algolia](https://www.algolia.com/blog/ecommerce/ecommerce-search-statistics/)).
- **Search often fails them.** About **10–15%** of searches on an average e-commerce site return **zero results** (Baymard, via [Findbar](https://findbar.io/?p=12510)). Benchmarks also find a large share of sites don't support common query types such as features, themes and use-cases (Baymard, via [Algolia](https://www.algolia.com/blog/ecommerce/ecommerce-search-statistics/)).
- **Returns are expensive.** In India, fashion return rates are reported at **25–40%** and electronics at **10–15%**; overall estimates range from about **15% to 30%** of orders ([Base.com](https://base.com/en-IN/blog/cod-return-rates-by-product-category-in-india-2026-report/), [IndiaRetailing / Return Prime](https://www.indiaretailing.com/2024/08/18/brands-could-lose-20-30-billion-in-revenue-to-returns-by-2025-report)). Return Prime estimated brands could lose **$20–30 billion** in revenue to returns by 2025. *(These are industry and vendor estimates; quote them as "reported".)*

### How we address each gap

| Gap | SearchSense |
|---|---|
| Keywords only; situations lost | Intent agent turns a sentence into hard and soft constraints; a context agent adds weather and occasion |
| Zero results | The verifier relaxes the weakest preference first and says so; it is never a dead end |
| No conversation | Refine bar with memory, plus one-tap refines |
| Guessing on ambiguity | The clarifier asks one question, only when the answer changes the results |
| Support questions shown products | Recognised and handed to Customer Care |
| Generic size charts, then returns | Fit agent per product, using the shopper's own orders, brands and returns; a return-risk check before checkout |
| AI hidden in a separate chat | AI mode lives in the search bar, with the reasoning shown: *You typed → I understood → So I'm showing* |

**Say:** "We tried the case query ourselves on Myntra and Amazon. Myntra: no results. Amazon: three western dresses under a row of silver bracelet ads. Both have chat assistants (Maya, Rufus), but the search bar, where most people actually start, still breaks. That's the gap we close."

---

## 3. Market potential

### Market size
India's online retail market was about **$65–66 billion GMV in 2025** and is projected to grow over 20% a year to **$170–180 billion by 2030** (Bain & Company, via [IANS](https://ianslive.in/india-eretail-sector-crosses-65-bn-likely-to-grow-over-20-pc-annually-till-2030--20260409130958)). Our solution applies to **every category** on a platform, not just fashion: fashion, home, beauty, electronics and everyday goods all have situational queries ("phone under ₹20k for vlogging", "lamp for a small reading corner, warm light", "fragrance-free moisturiser for oily skin").

### The share we can influence (illustrative, assumptions labelled)

| Step | Assumption | 2025 | 2030 |
|---|---|---|---|
| India e-retail GMV | Bain | $65–66B | $170–180B |
| GMV from shoppers who use search | **35%** *(assumption; searchers convert ~2.5×)* | ~$23B | ~$61B |
| Of that, descriptive or complex queries (sent to AI mode) | **35%** *(assumption, from our router design)* | **~$8B** | **~$21B** |
| Conversion lift on those queries | 5% conservative · 20% target | **$0.4–1.6B** a year | **$1.1–4.3B** a year |

### For one platform: per ₹10,000 crore of GMV

| Lever | Assumptions | Value a year |
|---|---|---|
| **More conversions** | 35% of GMV search-led × 35% via AI mode = ₹1,225 cr influenced; +5% to +20% conversion | **₹61–245 cr** more GMV |
| **Fewer size returns** | Average order ₹1,000 → 10 cr orders; 20% returned; 30% of returns are size/fit related *(assumption)*; −15% of those | **9 lakh fewer returns**; about **₹90 cr** of GMV kept, plus **~₹13.5 cr** of handling saved at ₹150 a return *(assumption)* |
| **Fewer dead ends** | Zero-result searches (10–15% today) turned into relevant results or closest matches | Shown in the KPI dashboard; not counted above |

### What it costs to run
Each AI-mode search is one call to a fast, low-cost model (we use Google's Gemini Flash family, with Cohere as a backup):
- **Per AI search:** about 8,200 input tokens (instructions, catalog vocabulary, the query) and about 350 output tokens.
- **At Gemini 2.5 Flash-Lite list prices** ($0.10 per million input tokens, $0.40 per million output; cached input $0.01 per million) ([pricing trackers](https://pricepertoken.com/pricing-page/model/google-gemini-2.5-flash-lite), [MorphLLM](https://www.morphllm.com/gemini-api-pricing)):
  - Without caching: **$0.00096 ≈ ₹0.08** per AI search.
  - With the standing instructions cached (they're identical on every call): **$0.00023 ≈ ₹0.02** per AI search.
- **Per 1,000 AI searches: ₹20–85.** *(₹88 = $1.)*

**Platform example: 1 crore (10 million) searches a day**

| | |
|---|---|
| Sent to AI mode | 35% → 35 lakh a day; simple queries skip the AI |
| Answered from cache (identical popular queries) | ~30% *(assumption)* → **~24.5 lakh model calls a day** |
| Model cost | **₹0.5–2.1 lakh a day ≈ ₹1.8–7.6 crore a year** |
| Photo reading and product questions | Small prompts; add about 10% → **≈ ₹2–8.5 crore a year** |
| **Per search across all traffic** | **≈ ₹0.005–0.02** (half a paisa to two paise) |

**ROI in one line:** about **₹2–8.5 crore a year** in AI cost for a platform at 1 crore searches a day, against **₹61–245 crore** of extra GMV and **9 lakh fewer returns** for every ₹10,000 crore of GMV. Production costs fall further with a fine-tuned small model and batching (see Next steps).

**Say:** "Searchers are already the best customers, converting about two and a half times better. We only need to fix the third of searches that are descriptive. Even at a conservative 5% lift, that's hundreds of crores for a large platform, for a running cost of about one paisa a search."

---

## 4. Solution & differentiation

### What SearchSense is
An **agentic AI mode for the search bar**. A team of specialised agents works together on every search, each doing one job, checking each other, and handing over to the next. The shopper sees one familiar search bar and a product grid, plus the reasoning.

### The agents

| Agent | What it does |
|---|---|
| **Router agent** | Reads every query: a simple search goes straight to fast results, a support request goes to Customer Care, and descriptive queries go to the intent agent |
| **Intent agent** | Turns the sentence into must-haves (category, gender, budget, item, style) and preferences (occasion, time, colours, fabric, fit, print, sleeves, neckline, pairing); fixes typos and Hinglish; spots out-of-catalog asks |
| **Context agent** | Brings in the world: weather for the place and month (Jaipur in January is cold; the Maldives is humid) and occasion rules (a daytime wedding means lighter colours) |
| **Clarifier agent** | Asks **one** question, only when the answer would change the results (Ethnic or western? Is Jaggu a man or a woman?) |
| **Search & verifier agent** | Finds candidates, checks each against every constraint, and relaxes the weakest preference first when too few match, saying what it relaxed |
| **Memory** | Keeps the conversation: a refine changes only what the shopper said |
| **Fit agent** | Recommends a size for every product with a confidence level and the reason, from the shopper's usual size, the brand that fits them, their own past returns and product fit signals. When unsure, it asks one fit question instead of guessing |
| **Vision agent** | Reads a photo of a size tag, a bill, a label or a garment: sets the shopper's size, or searches for the item |
| **Product Q&A agent** | Answers questions on the product page ("Is this see-through?") using only that listing, and says when the listing doesn't tell us |
| **Look agent** | Suggests what goes with a product when you view it or add it to the cart |
| **Return-risk agent** | Checks the cart before checkout: the wrong size ("you picked S, but it runs small: switch to L?"), two sizes of the same item, and honest notes |

**Why it's agentic, not just "AI in search":**
- **Several agents with different jobs** pass work along a plan.
- **It decides what to do next.** It answers, asks a question, relaxes a constraint, hands over to support, or suggests a warm layer.
- **It uses tools** such as weather, occasion rules, the catalog and the shopper's profile.
- **It checks its own work** with the verifier and validation, and falls back when a step fails.
- **It keeps memory** across the conversation.
- **It acts beyond search**, through to size, cart and support.

### The shopper journey (what the demo shows)
1. **Profile panel.** Several shoppers per account (you, Mom, a partner), each with their own usual size, waist, the brand that fits best (with brand size conversion, e.g. "Zara runs small: Zara M ≈ our S"), past orders ("Fits me: use size", "Shop similar"), returns that count, a size chart, and **a photo of a size tag** read by the vision agent.
2. **Search like you talk.**
   - *"Outfits for Jaipur"*: warm this month, so cotton and linen.
   - Refine *"tshirts & I am going in January"*: now cold, so fleece, wool, long sleeves, a heads-up, and **"Add a warm layer"**.
   - *"Maldives outfits"*, then *"vlue tops with flower under 700"*: typo fixed, floral print filter, budget, trip kept.
   - *"Marriage outfits"*: one question, Ethnic, then *"dark shades which go with gold"*.
   - *"outfits for jaggu"*: "Is Jaggu a man or a woman?"
   - The case-brief query, word for word.
3. **View a product.** *"M recommended: based on your usual size M; reviews say it runs large; you returned a kurta in S for being too small, so M."* Ask *"Is this see-through?"*, then see Complete the look.
4. **Add to cart.** It shows what goes with the item. Before checkout: *"you picked S, but it runs small, so size up to L. Switch to L?"*, one tap.

### Full feature list

**Search (AI mode in the search bar)**
- Natural-language search across categories (fashion, home, beauty)
- Situational understanding: weather by place and month, occasion and time of day
- Hard and soft constraints, with every filter shown as a removable chip: gender, item, style, budget, colour or colour family, fabric, fit, print, sleeves, neckline, occasion, time, pairs with (silver or gold)
- One clarifying question only when needed
- Typo correction with a one-tap "search instead for…"; Hinglish and Indian English (sari, kurthi, shaadi, "4k budget")
- Conversational refine with memory, plus one-tap refines ("#1 but cheaper", "Under ₹X", "Add a warm layer", "For men instead")
- Never a dead end: relaxes the weakest preference and says what it relaxed; shows the closest options when over budget
- Out-of-catalog requests get the closest alternative ("We don't sell footwear yet; here's running wear")
- Support requests (track, return, refund, cancel) handed to Customer Care; chit-chat redirected
- Transparent reasoning: *You typed → I understood → So I'm showing*, plus a "How I got here" strip of the agent steps
- Best match and top pick highlighted; a size badge on every card
- Fast path for simple queries ("white linen shirt M"), with no AI wait

**Profiles and fit**
- Several profiles per account, each with its own sizes, brand, orders, behaviour and "Picked for you" home page
- Brand-to-platform size conversion for any brand, typed or listed
- Size from your own returns ("you returned a kurta in S for being too small"), per product type
- Size confidence: High ("Take M"), Medium (size plus reason), Low (no guess: one fit question and the size chart)
- Photo of a size tag, bill, label or garment → use as my size, or search this

**Product and cart**
- Product Q&A grounded in the listing
- Complete the look on the product page and right after adding to the cart
- Pre-checkout return-risk check: switch to the right size, keep only one of two sizes, honest notes (sheer, runs small, heavy)

**Platform and trust**
- Works when the AI is busy: several models with automatic fallback (Gemini, with Cohere as a backup), cached answers, and normal search as the final safety net
- Admin observability: every search and model call, timings and errors
- KPI dashboard: search-to-checkout conversion, return proxy, zero-result rate, clarifying-question rate, accepted size rate, latency

### What makes it unique
1. **In the search bar, not a side chatbot.** It works where shopping already starts, with the familiar product grid.
2. **Situation → products.** The context agent reasons about weather, occasion and time; a keyword engine can't.
3. **Asks only when it matters.** One question, never an interrogation.
4. **Search through to the right size.** One flow from query to size to return-safe cart, using the shopper's own history.
5. **Honest by design.** It shows what it understood and what it relaxed, and says when a listing doesn't say.
6. **Category-agnostic and multilingual.** One agent team for every category, in the way Indians actually type.

**Say:** "Think of it as a team of shop assistants behind the search bar. One listens, one checks the weather, one asks a question if needed, one finds and checks every product, and one makes sure you pick the right size before you pay."

---

## 5. Next steps: roadmap & scalability

### Roadmap

| Phase | When | What |
|---|---|---|
| **1. Pilot** | 0–3 months | AI mode on 10% of search traffic in fashion (A/B against current search). Real fit signals from reviews and returns. Measure the KPIs below |
| **2. All categories** | 3–9 months | Electronics ("phone under ₹20k for vlogging"), home, beauty and grocery. The fit agent generalises into a **"right choice" agent**: compatibility for electronics, skin type for beauty, dimensions for home |
| **3. Languages and voice** | 6–12 months | Hindi and regional languages, typed and spoken; vernacular-first shoppers in Tier 2 and 3 cities |
| **4. Visual and social** | 9–15 months | Search by photo or screenshot ("find this look"), a look builder across categories, shared wishlists for occasions |
| **5. Proactive** | 12–18 months | Occasion and trip planning ("Goa trip next month": a packing list), size updates when your fit history changes |

### Pilot KPIs (already measured in the MVP's Metrics tab)

| KPI | Type | Target |
|---|---|---|
| Search-to-checkout conversion | North star | +20% vs keyword search |
| Size- and style-related return rate | North star | −15% |
| Zero- and low-result searches | Supporting | Down |
| Accepted size recommendation rate | Supporting | Up |
| Clarifying-question rate | Guardrail | Kept low |
| Search latency on simple queries | Guardrail | No change |

### Scalability
- **Cost:** about 1 paisa a search today. Caching, a fine-tuned small model and routing simple queries away from the AI keep cost flat as traffic grows.
- **Speed:** simple queries skip the AI entirely. Popular descriptive queries are answered from cache. Each model call has fallbacks.
- **Reliability:** several models from two providers, with normal search as the last resort. The shopper is never worse off than today.
- **Catalog:** the agents use the platform's own attributes. Gaps (for example, listings with no fabric) are flagged to the catalog team, so data quality improves over time.
- **Privacy:** profile data is used only to size and suggest, and the shopper controls it.

**Say:** "We pilot where returns hurt most, fashion, then take the same agent team to every category. For electronics, 'the right size' becomes 'the right compatibility'."

---

## 6. Key learnings

1. **Shoppers describe situations, not products.** "Outfits for Jaipur" or "Maldives outfits" carry weather, occasion and style. Understanding the situation mattered more than better keyword matching.
2. **Let the AI reason; don't hard-code the world.** Our first weather tool was a fixed table of 8 cities, and "clothes for Manali" broke. Letting the agent estimate weather and choose fabrics itself, with a validator as the guardrail, made it work for any place.
3. **Memory makes or breaks refinement.** Early on, "outfits for trekking" followed by "pink" showed pink sarees. A refine must keep everything the shopper didn't change.
4. **Ask once, and only when it matters.** One well-chosen question ("Ethnic or western?") beats guessing, and beats asking five.
5. **Never a dead end.** When nothing matches every constraint, relax the weakest one and say so. When the AI is slow or down, fall back to another model, then to normal search.
6. **Returns start at search.** The best size signal is the shopper's own history (a kurta returned in S beats "usual size M"), and it has to show at the moment of choice, not after delivery.
7. **Transparency builds trust.** Showing *"You typed → I understood → So I'm showing"*, with removable chips, lets shoppers correct the agent instead of abandoning the search.
8. **Speed is part of quality.** Free-tier models sometimes queued for minutes. Routing simple queries away from the AI, caching answers and model fallbacks were as important as the prompt.
9. **Data quality is the ceiling.** Most listings don't state a fabric. Agents can infer and flag, but structured catalog data lifts everything.
10. **Incumbents have chatbots, but the search bar is still the gap.** Our own tests on Myntra and Amazon showed the opportunity is where shoppers already type.

---

## Suggested slide list (about 14 slides)

| # | Slide | Section |
|---|---|---|
| 1 | Title + one-liner | 0 |
| 2 | The problem: the case query, with Myntra's "No results" | 1 |
| 3 | Who we build for: Priya, Rohan, Ananya | 1 |
| 4 | We tested it: Myntra vs Amazon vs SearchSense (table + screenshots) | 2 |
| 5 | Existing assistants (Maya, Rufus) and the gap: the search bar | 2 |
| 6 | Market research: searchers convert 2.5×, 10–15% zero results, returns 25–40% | 2 |
| 7 | Market potential: market size → share we influence → value per platform | 3 |
| 8 | Cost to run: about 1 paisa a search; ROI | 3 |
| 9 | The solution: a team of agents (agent diagram) | 4 |
| 10 | **Live demo** (🎬 Demo tab): profile → search → product → cart | 4 |
| 11 | What makes it unique (6 points) | 4 |
| 12 | Roadmap and pilot KPIs | 5 |
| 13 | Scalability: categories, languages, cost, reliability | 5 |
| 14 | Key learnings, then thank you and Q&A | 6 |

## Demo run-of-show (about 6–7 minutes)
Open the **🎬 Demo** tab → **▶ Start from step 1** → use **Next ▶**. The yellow box at the top shows what to say and what to point out.
1. **Profile panel** (1 min): profiles, fit profile, sample size-tag photo
2. **Search** (3 min): Jaipur → January t-shirts → warm layer · Maldives → "vlue tops with flower under 700" · Marriage outfits → Ethnic → dark with gold · outfits for jaggu → Men · the case-brief query
3. **Product** (1 min): Naari kurta: the size reason, "Is this see-through?", Complete the look
4. **Cart** (1 min): add the kurta → what goes with it · Alcis sweatshirt in S → "Switch to L?"

Before going on stage: open the app once (it wakes up), keep a screen recording of the demo as a backup, and keep a phone hotspot ready.

## Likely questions and answers
- **"Myntra has Maya and Amazon has Rufus. How are you different?"** They're chat assistants you have to open. We fix the search bar itself, where most shopping starts, and carry through to size and return-safe checkout. Our tests show the search bars still fail these queries.
- **"What does it cost at scale?"** About ₹0.02–0.08 per AI search, roughly half a paisa to two paise per search across all traffic. That's about ₹2–8.5 crore a year at 1 crore searches a day, against hundreds of crores of GMV impact.
- **"What if the AI is wrong?"** Every answer is checked against the catalog, the verifier checks each product, and the shopper sees and can remove every filter. If the AI is down, a backup model answers, and if that fails, normal search does.
- **"Is it only for fashion?"** No. The same agents work for home, beauty and electronics. The fit agent becomes a compatibility or suitability agent per category.
- **"Where does fit data come from?"** In production: reviews that mention fit, returns with reasons, and the shopper's own orders. In the MVP it's simulated, which is why the pilot starts by collecting it.
- **"How fast is it?"** Simple queries are instant (no AI). Descriptive queries take one model call, cached when popular.
- **"Hinglish and regional languages?"** Hinglish and Indian English work today (shaadi, sari, "4k budget"). Hindi and regional languages, including voice, are on the roadmap.

## Sources
- Bain & Company, India e-retail 2025 and 2030 (via IANS): https://ianslive.in/india-eretail-sector-crosses-65-bn-likely-to-grow-over-20-pc-annually-till-2030--20260409130958
- Search conversion and zero results (Algolia, Baymard, via secondary sources): https://www.algolia.com/blog/ecommerce/ecommerce-search-statistics/ · https://www.xictron.com/en/blog/site-search-analytics-onsite-search-2026/ · https://findbar.io/?p=12510
- Return rates in India (industry and vendor estimates): https://base.com/en-IN/blog/cod-return-rates-by-product-category-in-india-2026-report/ · https://www.indiaretailing.com/2024/08/18/brands-could-lose-20-30-billion-in-revenue-to-returns-by-2025-report
- Myntra MyFashionGPT and Maya: https://www.businesstoday.in/amp/technology/news/story/myntra-collaborates-with-microsoft-to-unveil-ai-powered-online-shopping-with-myfashiongpt-410366-2023-12-21 · https://apparelresources.com/business-news/retail/myntra-launches-ai-powered-chatbot-maya-personalized-shopping-assistance
- Amazon Rufus in India: https://aboutamazon.in/news/retail/rufus-ai-shopping-assistant-launch-in-india · https://yourstory.com/2024/08/amazon-genai-conversational-shopping-assistant-available-india
- Gemini 2.5 Flash-Lite pricing (third-party trackers citing Google's list price; confirm at ai.google.dev/pricing before quoting): https://pricepertoken.com/pricing-page/model/google-gemini-2.5-flash-lite · https://www.morphllm.com/gemini-api-pricing

**Assumptions to state on the slide:** the 35% search-led GMV share, 35% of searches being descriptive, the 5–20% lift, 30% of returns being size related, ₹150 per return, a ₹1,000 average order, 1 crore searches a day, a 30% cache-hit rate and ₹88 = $1 are our planning assumptions, not measured figures.
