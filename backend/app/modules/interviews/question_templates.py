"""The Colton Group's question bank, as templates a job can start from (docs/08_DECISIONS.md, item
41; docs/16_COLTON_BRIEF.md, Section 5).

The question wording and the optional probes are the client's, word for word from Appendix A of
"Colton_Group_Complete_AI_Candidate_Assessment_Pack.pdf" (one probe per sentence of the client's
"Optional probes" line). What the client's pack does NOT give, and was added here:

* the competency each question tests (``competency``): chosen from the question's heading and
  content, so that every weighted competency of the role has at least one question. The client
  can change a tag in the editor.
* the time to answer each question (``seconds``): a suggestion that keeps the whole list inside
  the interview's 20 minutes with a little room left for follow-ups. The employer can change
  every time.

The codes are the same as the scoring-profile templates in ``scoring_profile.py``: applying a
question template also puts that role's scoring profile on the job, so the tags are valid.
"""

from __future__ import annotations

ROLE_CODES = ("national_sales_manager", "commercial_director", "senior_marketing_manager")

QUESTION_TEMPLATES: dict[str, dict] = {
    "national_sales_manager": {
        "title": "National Sales Manager",
        "questions": [
            {
                "text": "You are preparing to launch Seasonings, Snacks and Breakfast products across Nigeria. How would you build a phased national route-to-market plan for the first 90 days?",
                "seconds": 150,
                "competency": "Route-to-market and distributor development",
                "probes": [
                    "Which markets and channels would you prioritise, and why?",
                    "How would you select and activate distributors?",
                    "Which milestones and measures would show progress?",
                ],
            },
            {
                "text": "Tell me about a time you built, expanded or improved a distributor network. What was the starting position, what did you personally do, and what changed?",
                "seconds": 120,
                "competency": "Route-to-market and distributor development",
                "probes": [
                    "How many distributors, territories or outlets were involved?",
                    "What measurable results did you achieve?",
                    "What did not work, and what did you change?",
                ],
            },
            {
                "text": "Describe the largest or most complex sales team you have managed. How was it structured, and how did you drive target achievement across territories?",
                "seconds": 120,
                "competency": "Sales-force leadership",
                "probes": [
                    "What routines did you use to review performance?",
                    "How did you address a weak territory or team member?",
                    "What evidence shows your approach worked?",
                ],
            },
            {
                "text": "Describe a product or category launch you led or supported. How did you build distribution, outlet coverage and sales momentum?",
                "seconds": 120,
                "competency": "Sales execution and territory management",
                "probes": [
                    "What were the targets and actual results?",
                    "How did you coordinate with Marketing, Trade Marketing and Supply Chain?",
                    "What would you do differently now?",
                ],
            },
            {
                "text": "Which metrics do you review weekly and monthly, and how do they influence your decisions?",
                "seconds": 120,
                "competency": "Reporting and performance analytics",
                "probes": [
                    "How do you track sell-in versus sell-out, active outlets, stock cover, returns and forecast accuracy?",
                    "How do you correct a territory that is falling behind?",
                    "Give an example of a decision driven by these metrics.",
                ],
            },
            {
                "text": "Tell me about a situation where you grew sales while protecting margins and managing distributor credit or overdue collections.",
                "seconds": 120,
                "competency": "Revenue, margin and collections management",
                "probes": [
                    "What trade-offs did you consider?",
                    "How did you enforce discount or credit discipline?",
                    "What happened to revenue, margin and cash collection?",
                ],
            },
            {
                "text": "How have you worked with Supply Chain, Operations or Finance to address stock-outs, excess inventory or forecast inaccuracies?",
                "seconds": 120,
                "competency": "Forecasting and supply coordination",
                "probes": [
                    "What information improved your forecasts?",
                    "How did you prioritise allocation when supply was constrained?",
                    "What measurable improvement followed?",
                ],
            },
            {
                "text": "Assume you join and must build distribution for three product categories with limited infrastructure. What would you prioritise in your first 30, 60 and 90 days?",
                "seconds": 180,
                "competency": "Sales execution and territory management",
                "probes": [
                    "What information would you request?",
                    "Which KPIs would you report weekly?",
                    "What are the main risks and mitigations?",
                ],
            },
        ],
    },
    "commercial_director": {
        "title": "Commercial Director",
        "questions": [
            {
                "text": "How would you translate a growth ambition into a commercial strategy for launching and scaling Seasonings, Snacks and Breakfast in Nigeria?",
                "seconds": 150,
                "competency": "Commercial strategy and profitable growth",
                "probes": [
                    "What would you prioritise across consumers, channels, markets and resources?",
                    "How would you sequence the launches?",
                    "Which assumptions would you validate first?",
                ],
            },
            {
                "text": "Describe a business or portfolio for which you held direct commercial or P&L accountability. What were the revenue, profitability and working-capital priorities, and what results did you deliver?",
                "seconds": 120,
                "competency": "P&L, pricing and financial management",
                "probes": [
                    "What authority did you hold over pricing, trade spend and budget?",
                    "How did you balance growth with margin and cash?",
                    "Which results can be quantified?",
                ],
            },
            {
                "text": "How would you design a national route-to-market across distributors, wholesalers, general trade, open markets, modern trade and key accounts?",
                "seconds": 120,
                "competency": "Route-to-market and distribution strategy",
                "probes": [
                    "How would you compare channel economics?",
                    "How would you identify coverage gaps and avoid channel conflict?",
                    "What would determine market-entry priorities?",
                ],
            },
            {
                "text": "Describe a product launch, brand repositioning or portfolio decision you led. How did consumer insight shape the proposition, pack, price and marketing investment?",
                "seconds": 120,
                "competency": "Brand and portfolio management",
                "probes": [
                    "What was your personal decision-making role?",
                    "How did Sales and Marketing work together?",
                    "What were the outcomes for penetration, sales or profitability?",
                ],
            },
            {
                "text": "Give an example of a pricing, promotion or trade-investment decision you made to improve profitable growth.",
                "seconds": 90,
                "competency": "P&L, pricing and financial management",
                "probes": [
                    "What alternatives did you consider?",
                    "How did you evaluate volume, net revenue, margin and ROI?",
                    "What happened after implementation?",
                ],
            },
            {
                "text": "How would you align Sales, Marketing, Supply Chain, Operations, Finance and Product/R&D around a three-category launch?",
                "seconds": 120,
                "competency": "Cross-functional execution",
                "probes": [
                    "What governance meetings, dashboards or decision rights would you establish?",
                    "How would you resolve conflict between demand generation and supply readiness?",
                    "How would you escalate risks?",
                ],
            },
            {
                "text": "Describe a commercial organisation you built, restructured or significantly improved.",
                "seconds": 90,
                "competency": "Leadership and organisational development",
                "probes": [
                    "How did you define roles, targets and accountability?",
                    "How did you develop managers and address underperformance?",
                    "What changed in business performance?",
                ],
            },
            {
                "text": "You have been appointed Commercial Director for a business launching Seasonings, Snacks and Breakfast. Walk me through your first 90 days.",
                "seconds": 180,
                "competency": "Commercial strategy and profitable growth",
                "probes": [
                    "What would you assess in the first two weeks?",
                    "How would you prioritise markets, distributors, people and budget?",
                    "Which metrics and risks would you present to leadership?",
                ],
            },
        ],
    },
    "senior_marketing_manager": {
        "title": "Senior Marketing Manager",
        "questions": [
            {
                "text": "How would you translate the Commercial Director’s strategy into distinct brand plans and consumer propositions for Seasonings, Snacks and Breakfast in Nigeria?",
                "seconds": 120,
                "competency": "Brand strategy and positioning",
                "probes": [
                    "How would you differentiate each category?",
                    "How would you maintain brand consistency across packaging, advertising, digital and trade materials?",
                    "What evidence would you need before recommending pack, price or portfolio changes?",
                ],
            },
            {
                "text": "How would you research consumer preferences, affordability, regional tastes, shopping behaviour and media habits across Nigerian markets, including open markets and rural communities?",
                "seconds": 120,
                "competency": "Consumer insights and market research",
                "probes": [
                    "How would you choose markets and research methods?",
                    "How would you turn findings into a specific decision?",
                    "How would you compare regions or consumer segments?",
                ],
            },
            {
                "text": "What would your 90-day pre-launch plan cover for Seasonings, Snacks and Breakfast?",
                "seconds": 150,
                "competency": "Product launches and integrated campaigns",
                "probes": [
                    "What are the milestones, owners, budgets and dependencies?",
                    "How would you sequence activities with limited resources?",
                    "What would you track on a launch-readiness dashboard?",
                ],
            },
            {
                "text": "Describe your experience working with Innovation or R&D on consumer briefs, concept tests, taste tests, packaging usability or product acceptance.",
                "seconds": 90,
                "competency": "Consumer insights and market research",
                "probes": [
                    "How did findings affect your recommendation?",
                    "How would you distinguish consumer preference from technical or regulatory feasibility?",
                    "How would you protect research integrity?",
                ],
            },
            {
                "text": "Tell me about a product launch or integrated campaign you led across advertising, digital, sampling, demonstrations, launch events or trade materials.",
                "seconds": 120,
                "competency": "Product launches and integrated campaigns",
                "probes": [
                    "What was your contribution and budget responsibility?",
                    "How did you connect consumer activity to sales and distribution?",
                    "What were the measurable results?",
                ],
            },
            {
                "text": "How would you ensure consumer campaigns are connected to available stock, distributor readiness, outlet visibility and replenishment?",
                "seconds": 90,
                "competency": "Sales alignment and launch readiness",
                "probes": [
                    "What if an activation were planned but stock was unavailable?",
                    "How would you work with the National Sales Manager and Trade Marketing?",
                    "Which conditions must be met before campaign release?",
                ],
            },
            {
                "text": "Describe a marketing budget you managed and explain how you evaluated campaign or activation effectiveness.",
                "seconds": 90,
                "competency": "Marketing budget and ROI",
                "probes": [
                    "How did you allocate or reallocate spend?",
                    "How did you verify agency and supplier deliverables?",
                    "What evidence showed whether the investment was effective?",
                ],
            },
            {
                "text": "How do you brief and manage creative, research, media, digital and activation agencies against deliverables, timelines, evaluation criteria and approved fees?",
                "seconds": 90,
                "competency": "Agency and stakeholder management",
                "probes": [
                    "How do you manage quality and delays?",
                    "How would you coordinate with Regulatory, Manufacturing, Supply Chain and Finance?",
                    "How do you escalate dependencies to the Commercial Director?",
                ],
            },
            {
                "text": "What would you include in a launch-readiness tracker before packaging, advertising or activation materials are released?",
                "seconds": 90,
                "competency": "Sales alignment and launch readiness",
                "probes": [
                    "Which technical, regulatory and management approvals are required?",
                    "How would you manage artwork versions and sign-offs?",
                    "What would trigger a launch delay or change in plan?",
                ],
            },
            {
                "text": "Which indicators would you use to assess awareness, consumer trial, activation effectiveness, sales contribution and repeat purchase?",
                "seconds": 90,
                "competency": "Marketing budget and ROI",
                "probes": [
                    "How would you distinguish reach and engagement from actual consumer behaviour?",
                    "How would you measure campaign contribution while accounting for distribution and stock availability?",
                    "How would you use findings to change future activity?",
                ],
            },
        ],
    },
}


def template_items(code: str) -> list[dict] | None:
    """The template's questions as the questions service saves them (a new list each time), or
    None for an unknown code. Probes are joined one per line, the form they are stored in."""
    template = QUESTION_TEMPLATES.get(code)
    if template is None:
        return None
    return [
        {
            "text": question["text"],
            "time_limit_seconds": question["seconds"],
            "source": "EMPLOYER",
            "competency": question["competency"],
            "probes": "\n".join(question["probes"]),
            "follow_up_seconds": None,
        }
        for question in template["questions"]
    ]


def template_summaries() -> list[dict]:
    """What the editor lists: the code, the role, how many questions and their total answer time."""
    return [
        {
            "code": code,
            "title": QUESTION_TEMPLATES[code]["title"],
            "question_count": len(QUESTION_TEMPLATES[code]["questions"]),
            "total_seconds": sum(question["seconds"] for question in QUESTION_TEMPLATES[code]["questions"]),
        }
        for code in ROLE_CODES
    ]
