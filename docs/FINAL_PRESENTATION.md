# SearchSense: final presentation brief

**ABHIKALP 2026 · Team Outliers · Finals**
**A B2B SaaS:** an agentic AI search layer that any e-commerce platform or brand plugs into its own search bar. Shoppers describe what they need in their own words and get the right products in the right size; the platform gets more conversions and fewer returns.

This file is the source for the final deck. It follows the six areas every presentation must cover, in order. Each section has the slide content, then **"Say"** notes for a conversational delivery. A suggested slide list is at the end.

---

## 0. The one-liner (title slide)

> **Shoppers don't search in keywords. They describe a situation.**
> SearchSense is a team of AI agents that plugs into any e-commerce search bar as SaaS. They understand the situation, ask only when they must, find products that fit every need, recommend the right size, and catch returns before checkout.

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

### Target customer (who buys) and primary user (who uses it)
SearchSense is sold **business-to-business** and used by shoppers.

**Customer: e-commerce platforms and brands in India** (the buyer is the Head of Search, Product or Growth; the business case goes to the CXO):

| Segment | Typical situational query | Why they buy | What the agents do there |
|---|---|---|---|
| **E-commerce marketplaces** (horizontal and fashion) | "Pastel ethnic outfit for a daytime wedding under ₹6,000" | Search drives the most valuable sessions; returns cost them the most | Full flow: intent, context, clarifier, size, return-risk check |
| **Quick commerce** (10–30 minute delivery) | "Snacks for a movie night for 6", "everything for paneer butter masala", "something for a sore throat" | Tiny screens, impatient shoppers; basket size is the metric | Situation → a ready **basket** with quantities; substitutes when out of stock; dietary needs (Jain, vegan, sugar-free) |
| **Vertical platforms** (beauty, electronics, home, grocery) | "Phone under ₹20k for vlogging", "fragrance-free moisturiser for oily skin" | Category-specific needs that keyword search can't match | The fit agent becomes a **"right choice" agent**: compatibility, skin type, dimensions |
| **D2C brands and omnichannel retailers** | "Gift for my dad, 60, who likes linen" | Can't build an AI search team in-house; need it plug-and-play | Same agents through an API or plug-in; also in-store kiosks and assisted selling |
| **Social and value commerce** | Hinglish and voice-first queries from Tier 2 and 3 cities | New-to-online shoppers who don't know category names | Hinglish and vernacular understanding; one simple question instead of filters |

*(Marketplaces that build their own assistants in-house, such as Amazon's Rufus or Myntra's Maya, are competitors and also proof of demand. Most of the market can't build one.)*

**Where we start:** fashion e-commerce, where returns hurt most and where our MVP is deep. **Then:** quick commerce (fast growing, basket-led), vertical platforms, and D2C brands on self-serve.

**Primary user:** the online shopper in India who starts at the search bar of a large multi-category platform (fashion, home, beauty, electronics, everyday goods). They're mobile-first, often shop for an occasion, a trip or for someone else, and write the way they speak, including Hinglish, short forms and typos.

**Personas** (from our solution doc; all three are live in the MVP as profiles):

| Persona | Situation | What fails today | What they need |
|---|---|---|---|
| **Priya**, 27, wedding guest | "Breathable pastel ethnic outfit for a humid daytime wedding in Mumbai under ₹6,000" | Zero or irrelevant results | Her whole situation understood in one go |
| **Rohan**, 24, quick shopper | "wite linnen shirt M": fast, typos | Typos give no results or the wrong items | Fixed silently, with a one-tap undo |
| **Ananya**, 31, fit-anxious | Returned jeans for being too small; unsure of her size | The size chart is generic | A size that learns from her own returns |

**Inside the customer, who else uses it:** the search and merchandising team (client console: what shoppers ask for, what failed, KPIs), the catalog team (listings missing key attributes such as fabric are flagged), and finance (lower reverse-logistics cost).

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
- **Flipkart** launched **Flippi**, a GenAI shopping assistant, in October 2023, English-first at launch ([Inc42](https://inc42.com/buzz/flipkart-launches-chatgpt-powered-shopping-assistant-flippi), [Flippi paper](https://arxiv.org/html/2507.05788v2)).

**The gap they leave:** these are **separate chat surfaces** that a shopper has to find and open. The **search bar**, where most shopping starts, still fails these queries (our tests above). And sizing sits on the product page, apart from search: nothing ties the query, the shopper's own size and returns history, and a pre-checkout return check into one flow.

**Our position:** we don't add another chatbot. We make **the search bar itself agentic**, keep the familiar grid of products, and carry the shopper through to the right size and a return-safe checkout. And because these assistants are **built in-house and locked to one marketplace**, every other platform and brand needs a way to get the same capability: that's who we sell to.

### The wider landscape: four kinds of competitors

| Type | Players | What they offer | What's missing for an Indian platform |
|---|---|---|---|
| **1. In-house marketplace assistants** | Myntra Maya / MyFashionGPT, Amazon Rufus, Flipkart Flippi | Chat assistants inside their own apps | Not for sale to anyone else; separate from the search bar; the search bar itself still fails (our tests) |
| **2. Search & discovery SaaS (global)** | Algolia, Constructor, Bloomreach, Coveo | Keyword and semantic search, merchandising; newer AI shopping agents (Constructor's AI Shopping Agent, Bloomreach's Loomi, Algolia NeuralSearch on its top tier) | Built for Western catalogs and enterprise budgets; no size, return-risk or support routing in search; little India-specific context (occasions like haldi or sangeet, city weather, Hinglish) |
| **3. Search SaaS from India** | Netcore Unbxd (Indian-owned; named a Leader in Gartner's 2026 Magic Quadrant for Search and Product Discovery) | AI search, merchandising and recommendations for merchants and D2C brands | Search and merchandising focus; fit, return risk and support routing aren't part of the search flow |
| **4. Fit & size SaaS** | True Fit, Fit Analytics (Snap) | Size recommendation on the product page, from sales and returns data | Starts after search, on the product page; doesn't understand the query or the occasion; mostly global fashion retailers |
| *(Adjacent: chat-commerce platforms)* | WhatsApp and website chatbot builders | Scripted or LLM chatbots for support and sales | Not connected to search ranking, the catalog verifier or sizing |

Sources: Constructor ([eCommerceNews Asia](https://ecommercenews.asia/story/constructor-posts-surge-on-ai-retail-search-momentum)), Bloomreach and Coveo ([Coveo comparison](https://www.coveo.com/en/compare/coveo-vs-bloomreach)), Algolia ([support](https://support.algolia.com/hc/en-us/articles/15745996583441-How-am-I-charged-on-the-Grow-plan), [Meilisearch on Algolia tiers](https://www.meilisearch.com/blog/algolia-pricing)), Netcore Unbxd ([YourStory](https://yourstory.com/2022/07/in-line-with-an-ipo-100m-acquisition-unbxd-netcore/amp), [CustomerThink](https://customerthink.com/netcore-unbxd-named-a-leader-in-the-2026-gartner-magic-quadrant-for-search-and-product-discovery/)), True Fit ([truefit.com](https://truefit.com/reduce-returns-improve-margins)). Vendor capabilities are from their public material; check the latest before the slide.

### Compared on every aspect

✓ = yes · ◐ = partly, or a separate add-on · ✗ = no · *based on public material and our own tests*

| Aspect | Marketplace search bars (Myntra, Amazon) | In-house assistants (Maya, Rufus, Flippi) | Global search SaaS (Algolia, Constructor, Bloomreach, Coveo) | Search SaaS from India (Unbxd) | Fit SaaS (True Fit, Fit Analytics) | **SearchSense** |
|---|---|---|---|---|---|---|
| Where it lives | Search bar | Separate chat | Search bar | Search bar | Product page | **Search bar → product → cart** |
| Understands full sentences | ✗ (our tests) | ✓ | ◐ (semantic search; AI agents on higher tiers) | ◐ | ✗ | **✓** |
| Situational context (weather by city and month, occasion and time) | ✗ | ◐ | ✗ | ✗ | ✗ | **✓** |
| Asks one clarifying question only when needed | ✗ | ◐ (chat asks) | ◐ | ✗ | ✗ | **✓** |
| Conversational refine with memory | ✗ (filters only) | ✓ (in chat) | ◐ | ✗ | ✗ | **✓ in the search bar** |
| Never a dead end (relaxes and explains) | ✗ ("No results") | ◐ | ◐ | ◐ | ✗ | **✓** |
| Support requests (track, return) routed | ✗ (our tests) | ◐ | ✗ | ✗ | ✗ | **✓** |
| Size from the shopper's own orders, brands and returns | ◐ (product page) | ◐ | ✗ | ✗ | ✓ (product page) | **✓ on every result** |
| Pre-checkout return-risk check | ✗ | ✗ | ✗ | ✗ | ◐ (bracketing) | **✓** |
| Hinglish and Indian occasions | ◐ | ◐ | ✗ | ◐ | ✗ | **✓** |
| Shows its reasoning (You typed → I understood) | ✗ | ◐ | ✗ | ✗ | ◐ (why this size) | **✓** |
| Available to other platforms | ✗ | ✗ (in-house) | ✓ | ✓ | ✓ | **✓ (SaaS)** |
| Pricing model | — | — | Per search or records (Algolia Grow: about $0.50 per 1,000 searches; AI features on higher tiers) or enterprise contracts | Enterprise | Enterprise, per retailer | **Per AI search, with simple searches free** |

### Gaps we fill (the summary for the slide)
1. **Nobody does search → size → return-safe cart in one flow.** Search SaaS stops at results, and fit SaaS starts at the product page.
2. **The best assistants are locked in-house.** Rufus, Maya and Flippi aren't available to the rest of the market.
3. **Global tools miss India.** Hinglish, occasions such as haldi and sangeet, weather by city, and price sensitivity (budgets in ₹, "4k").
4. **Search bars still break.** Our tests: the case query gets no results on Myntra and off-target results on Amazon.

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
India's online retail market was about **$65–66 billion GMV in 2025** and is projected to grow over 20% a year to **$170–180 billion by 2030** (Bain & Company, via [IANS](https://ianslive.in/india-eretail-sector-crosses-65-bn-likely-to-grow-over-20-pc-annually-till-2030--20260409130958)). Within it, **quick commerce** has roughly doubled every year to **$10–11 billion in 2025** and is forecast at **$65–70 billion by 2030** (same report). Our solution applies to **every kind of commerce**: e-commerce, quick commerce, vertical platforms and D2C. It also applies to **every category**, not just fashion: fashion, home, beauty, electronics and everyday goods all have situational queries ("phone under ₹20k for vlogging", "lamp for a small reading corner, warm light", "fragrance-free moisturiser for oily skin").

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

### Business model (SaaS)

| Plan | For | Price *(proposed)* |
|---|---|---|
| **Enterprise** | Marketplaces and large platforms | Annual contract: **₹0.25 per AI-mode search**; simple searches that skip the AI are free; optional success fee on measured uplift in the A/B pilot |
| **Growth** | Vertical platforms, large D2C brands | Same usage price with a monthly minimum; fit and return-risk modules included |
| **Self-serve** *(future: "Search-as-a-service")* | Small D2C stores, Shopify-style plug-in | Monthly plan, e.g. **₹15,000 a month** including 1 lakh AI searches |

**Unit economics:**
- Our cost is ₹0.02–0.085 per AI search (above), so at ₹0.25 the **gross margin is about 66–92%**.
- For comparison, global search SaaS lists keyword search at about $0.50 (≈ ₹44) per 1,000 searches (Algolia Grow), with AI features on higher, enterprise-priced tiers. We charge more per search because we sell **outcomes** (conversion, returns), not queries.

**Example customer: a platform with 1 crore searches a day**

| | |
|---|---|
| AI-mode searches a year | 35 lakh a day × 365 ≈ **128 crore** |
| SearchSense revenue (ARR) | 128 crore × ₹0.25 ≈ **₹32 crore** |
| Our AI cost | ₹2–8.5 crore → **gross margin ~73–94%** |
| The customer's return | ₹61–245 crore more GMV and 9 lakh fewer returns per ₹10,000 crore GMV: **several times the fee** |

### Market size for SearchSense (TAM · SAM · SOM)

| | Definition | Size | Basis |
|---|---|---|---|
| **TAM** | Global e-commerce search software | **~$4–5.5 billion** (2024–25), growing ~11% a year | Market research reports; estimates vary widely by definition ([DataHorizzon](https://datahorizzonresearch.com/e-commerce-search-software-market-44365), [WiseGuy](https://www.wiseguyreports.com/reports/e-commerce-search-software-market)) |
| **SAM** | Search and discovery spend of e-commerce in India | **~$65 million (≈ ₹575 crore) in 2025 → ~$175 million by 2030** | *Assumption:* about 0.1% of India's e-retail GMV ($65–66B → $170–180B) goes to search and discovery software |
| **SOM (3 years)** | What we can win | **~₹100 crore ARR** | *Assumption:* 3 large platforms (≈ ₹32 crore each) + 50 D2C brands on self-serve |

India-first, then Southeast Asia and other emerging markets with the same pattern: mobile-first, mixed languages, price-sensitive and occasion-led.

**Say:** "Searchers are already the best customers, converting about two and a half times better. We only need to fix the third of searches that are descriptive. Even at a conservative 5% lift, that's hundreds of crores for a large platform. It costs us about one paisa a search to run, we charge 25 paise, and the customer still earns several times what they pay."

---

## 4. Solution & differentiation

### What SearchSense is
An **agentic AI mode for the search bar**, sold as **SaaS** to e-commerce and quick-commerce platforms and brands. A team of specialised agents works together on every search, each doing one job, checking each other, and handing over to the next. The shopper sees one familiar search bar and a product grid, plus the reasoning.

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
- Client console (Admin): every search and agent step, timings and errors, live
- KPI dashboard: search-to-checkout conversion, return proxy, zero-result rate, clarifying-question rate, accepted size rate, latency

### How it's delivered (SaaS)
| Piece | What the customer gets |
|---|---|
| **Search API** | Send the shopper's query (plus session and profile, with consent) and get ranked products, the applied filters, the clarifying question if any, and the reasoning |
| **UI kit** | Drop-in components for web and app: the reasoning bubble, filter chips, refine bar, size badge, product Q&A and the pre-checkout check. White-labelled in the platform's look |
| **Catalog connector** | A daily feed of the platform's own catalog and attributes; the agents use the platform's own values, and gaps are flagged to its catalog team |
| **Client console** | Live view of searches and agent steps, KPIs, an A/B switch, and the demand and catalog-gap reports |
| **Security and privacy** | Each customer's data kept separate; shopper data used only with consent and only to size and suggest |
| **Go-live** | About 4–6 weeks: catalog feed, UI kit, then an A/B pilot on a share of traffic |

*(The MVP already shows the shopper side and a first version of the console: the 🔐 Admin and 📊 Metrics tabs.)*

### What makes it unique
1. **In the search bar, not a side chatbot.** It works where shopping already starts, with the familiar product grid.
2. **Situation → products.** The context agent reasons about weather, occasion and time; a keyword engine can't.
3. **Asks only when it matters.** One question, never an interrogation.
4. **Search through to the right size.** One flow from query to size to return-safe cart, using the shopper's own history.
5. **Honest by design.** It shows what it understood and what it relaxed, and says when a listing doesn't say.
6. **Category-agnostic and multilingual.** One agent team for every category, in the way Indians actually type.
7. **Plug-and-play SaaS.** What only the largest marketplaces build in-house (Rufus, Maya, Flippi), every platform and brand can switch on in weeks.

**Say:** "Think of it as a team of shop assistants behind the search bar. One listens, one checks the weather, one asks a question if needed, one finds and checks every product, and one makes sure you pick the right size before you pay."

---

## 5. Next steps: roadmap & scalability

### Roadmap

| Phase | When | What |
|---|---|---|
| **1. Design partner pilot** | 0–3 months | One fashion e-commerce platform; AI mode on 10% of search traffic, A/B against current search; real fit signals from reviews and returns |
| **2. Enterprise launch** | 3–9 months | Search API, UI kit and client console; more categories (beauty, home, electronics) with the "right choice" agent; first quick-commerce customer (situation → basket) |
| **3. Languages and voice** | 6–12 months | Hindi and regional languages, typed and spoken, for Tier 2 and 3 shoppers |
| **4. Future products** | 9–24 months | The six products below, in order of customer demand |
| **5. New markets** | 18–36 months | Southeast Asia and other mobile-first, multilingual markets |

### Future products (planned)

| Product | What it does | Who pays for it |
|---|---|---|
| **Visual try-on** | The shopper uploads a photo and sees themselves wearing the product on the product page, using an image-generation model | Fashion and beauty platforms (fewer "looked different on me" returns) |
| **Look builder** | A complete outfit or set in one tap (kurta + dupatta + jhumkas + juttis), matched to budget, colour and occasion, across categories | Marketplaces (bigger baskets) |
| **Wardrobe memory** | "What goes with the blue kurta I bought in March?" The agents remember what the shopper owns and suggest pieces that complete it | Marketplaces and brands (repeat purchases) |
| **Catalog quality agent** | Finds listings with missing or wrong attributes (fabric, fit, size chart, colour) and drafts the fix for sellers | The platform's catalog and seller teams |
| **Demand insights** | What shoppers ask for that the catalog doesn't have ("pastel linen kurta under ₹2,000", searched 40,000 times) → buying and assortment signals | Category, buying and private-label teams (a new revenue line) |
| **Search-as-a-service (self-serve)** | A plug-and-play version for small D2C stores and Shopify-style websites: connect the catalog and go live the same day | D2C brands (the self-serve plan) |

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
- **Multi-customer SaaS:** one agent platform serves many customers, each with its own catalog, vocabulary and settings. A new customer is configuration, not a rebuild.

**Say:** "We pilot with one fashion platform, where returns hurt most, then take the same agents to every category and to quick commerce. For electronics, 'the right size' becomes 'the right compatibility'; for quick commerce, 'a situation' becomes 'a basket'. Next come try-on, the look builder and wardrobe memory for shoppers, plus catalog-quality and demand insights for the platform team."

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
11. **Sell to the platform, design for the shopper.** The shopper feels the magic, but the platform pays. Showing the reasoning, the KPIs and the client console matters as much as the answers.
12. **The same pattern holds everywhere.** A situation, a need and a constraint ("for a wedding", "for a movie night for 6", "for vlogging") is how people shop in fashion, quick commerce and electronics alike, so one agent platform can serve them all.

---

## Suggested slide list (about 16 slides)

| # | Slide | Section |
|---|---|---|
| 1 | Title + one-liner (agentic search, as SaaS) | 0 |
| 2 | The problem: the case query, with Myntra's "No results" | 1 |
| 3 | Who we build for: customers (e-commerce, quick commerce, vertical, D2C) and users (Priya, Rohan, Ananya) | 1 |
| 4 | We tested it: Myntra vs Amazon vs SearchSense (table + screenshots) | 2 |
| 5 | The landscape: 4 kinds of competitors | 2 |
| 6 | Compared on every aspect (the ✓ / ◐ / ✗ matrix) and the 4 gaps we fill | 2 |
| 7 | Market research: searchers convert 2.5×, 10–15% zero results, returns 25–40% | 2 |
| 8 | Market potential: e-retail $66B → $175B, q-commerce $10B → $65B; the share we influence | 3 |
| 9 | Business model: pricing, unit economics, TAM · SAM · SOM | 3 |
| 10 | The solution: a team of agents (agent diagram) + how it's delivered as SaaS | 4 |
| 11 | **Live demo** (🎬 Demo tab): profile → search → product → cart | 4 |
| 12 | What makes it unique (7 points) | 4 |
| 13 | Roadmap and pilot KPIs | 5 |
| 14 | Future products: try-on, look builder, wardrobe memory, catalog quality, demand insights, self-serve | 5 |
| 15 | Key learnings | 6 |
| 16 | Thank you + Q&A | — |

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
- **"Is it only for fashion?"** No. The same agents work for home, beauty and electronics, and for quick commerce (situation → basket). The fit agent becomes a compatibility or suitability agent per category.
- **"Algolia, Constructor and Unbxd already sell AI search. Why you?"** They sell search; fit tools sell sizing. Nobody sells search → size → return-safe cart as one agent flow, and the global tools aren't built for Indian queries (Hinglish, haldi, city weather, ₹ budgets). We're priced on outcomes and plug into their search too if a customer already has one.
- **"How do you make money?"** SaaS, about ₹0.25 per AI-mode search (simple searches free), against our cost of about ₹0.02–0.085: a 66–92% gross margin. A self-serve plan for small brands comes later.
- **"How does a platform integrate?"** A catalog feed, our Search API and UI kit, then an A/B pilot on a share of traffic: about 4–6 weeks.
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
- Quick commerce GMV 2025 and 2030 (Bain, via IANS): same link as e-retail above
- Flipkart Flippi: https://inc42.com/buzz/flipkart-launches-chatgpt-powered-shopping-assistant-flippi · https://arxiv.org/html/2507.05788v2
- Search SaaS: Algolia pricing https://support.algolia.com/hc/en-us/articles/15745996583441-How-am-I-charged-on-the-Grow-plan · Constructor https://ecommercenews.asia/story/constructor-posts-surge-on-ai-retail-search-momentum · Coveo vs Bloomreach https://www.coveo.com/en/compare/coveo-vs-bloomreach · Netcore Unbxd https://yourstory.com/2022/07/in-line-with-an-ipo-100m-acquisition-unbxd-netcore/amp · https://customerthink.com/netcore-unbxd-named-a-leader-in-the-2026-gartner-magic-quadrant-for-search-and-product-discovery/
- Fit SaaS: True Fit https://truefit.com/reduce-returns-improve-margins
- E-commerce search software market size (estimates vary by source and definition): https://datahorizzonresearch.com/e-commerce-search-software-market-44365 · https://www.wiseguyreports.com/reports/e-commerce-search-software-market

**Assumptions to state on the slide:** these are our planning assumptions, not measured figures:
- 35% search-led GMV share, 35% of searches being descriptive, and a 5–20% lift
- 30% of returns being size related, ₹150 per return, a ₹1,000 average order
- 1 crore searches a day and a 30% cache-hit rate
- ₹0.25 per AI search pricing, search software spend at 0.1% of GMV (SAM), and the SOM customer mix
- ₹88 = $1
