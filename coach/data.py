
# =====================================================================
# DATA: original practice cases, behavioral bank, framework drills, rubrics
# All cases below are fictional and written for this project.
# Rubrics are study aids, not any firm's official criteria.
# =====================================================================

CASES = {
    "profitability": {
        "title": "Harbor & Pine Coffee: falling profit",
        "difficulty": "medium",
        "prompt": (
            "Our client is Harbor & Pine Coffee, a chain of 40 company-owned cafes in the US "
            "Southeast. Over the last two years its annual profit has fallen from $12M to $4.8M. "
            "The CEO has hired us to find out why and what to do about it."
        ),
        "clarifying": {
            "business model": "Company-owned cafes only, no franchises. Sells coffee, tea, pastries and packaged beans. All 40 stores existed in both years.",
            "revenue": "Average transaction value is flat at about $8. Customer traffic is down about 5 percent.",
            "competition": "A national chain opened about 15 new stores in the client's markets over the last two years.",
            "goal": "The board wants profit back to at least $10M within 18 months.",
        },
        "exhibit": (
            "Income summary ($M)         Year 1   Year 3\n"
            "Revenue                       80.0     76.0\n"
            "COGS (beans, dairy, pastry)   24.0     26.0\n"
            "Labor                         24.0     25.2\n"
            "Rent and other fixed          20.0     20.0\n"
            "Profit                        12.0      4.8"
        ),
        "math_question": (
            "Assume costs and traffic stay as in Year 3. What average price increase would restore "
            "profit to $12M, assuming no customers are lost because of the price change?"
        ),
        "math_answer": "About 9.5 percent (needs $7.2M more profit; 7.2 / 76 = 9.5%). A 6.8 percent increase reaches the board's $10M goal.",
        "key_insights": [
            "Profit fell $7.2M: about $4.0M from lower revenue (traffic), $2.0M from higher COGS, $1.2M from higher labor.",
            "Rent and other fixed costs did not flex when revenue fell.",
            "A price increase alone could restore profit but risks losing more traffic against a new competitor, so a mix of levers is more realistic.",
            "The traffic decline coincides with about 15 new competitor stores.",
        ],
        "strong_structure": [
            "Revenue: traffic x price, by store and daypart",
            "Costs: COGS, labor, fixed, compared year over year",
            "External: competitor entry, input prices",
            "Levers: price, menu mix, supplier terms, labor scheduling, weakest-store review",
        ],
        "recommendation_hint": "A strong answer combines a modest price increase (3 to 4 percent) with supplier renegotiation, labor scheduling and a review of the weakest stores, and names the traffic-loss risk.",
    },
    "market_entry": {
        "title": "NorthStar Telehealth: entering Canada",
        "difficulty": "medium",
        "prompt": (
            "Our client is NorthStar Telehealth, a US virtual-care company with $400M in annual "
            "revenue and a 20 percent operating margin. The CEO is considering entering Canada and "
            "wants to know whether it is worth it."
        ),
        "clarifying": {
            "target segment": "Adults in Canada with a chronic condition such as diabetes or hypertension: about 12 million people.",
            "adoption": "In the US about 15 percent of that segment uses digital care providers. Assume Canada reaches the same level by Year 3.",
            "share": "NorthStar expects to win 10 percent of digital users by Year 3.",
            "pricing": "Average revenue per member is $300 per year.",
            "investment": "Entry needs $60M upfront for licensing, provider network and marketing.",
            "margin": "Assume a 25 percent operating margin on Canadian revenue at maturity.",
            "competition": "Two local players hold about 50 percent of digital users together; the rest is fragmented.",
        },
        "exhibit": (
            "Share of Canadian population by province (licensing is province by province)\n"
            "Ontario 39%   Quebec 22%   British Columbia 14%   Alberta 11%   Other 14%"
        ),
        "math_question": (
            "Estimate NorthStar's Year 3 Canadian revenue, then the simple payback period on the "
            "$60M investment at a 25 percent operating margin."
        ),
        "math_answer": "Revenue = 12M x 15% x 10% x $300 = $54M. Operating profit = $13.5M. Payback = 60 / 13.5 = about 4.4 years.",
        "key_insights": [
            "Year 3 revenue is about $54M, small against the existing $400M business, so Canada is a modest near-term bet.",
            "The 4.4-year payback starts at Year 3 profit and ignores the ramp-up years, so true payback is longer.",
            "Biggest uncertainties: adoption rate, share against two local incumbents, provincial licensing.",
            "Alternative entry modes: partner with or acquire a local player instead of building from scratch.",
        ],
        "strong_structure": [
            "Market attractiveness: size, growth, adoption",
            "Ability to win: competition, differentiation, regulation",
            "Economics: revenue, costs, investment, payback",
            "Entry mode and risks: build, partner, acquire; phasing",
        ],
        "recommendation_hint": "A strong answer proposes a phased entry (for example Ontario first, about 39 percent of the population) or a partnership, with go/no-go checkpoints on adoption and share.",
    },
    "market_sizing": {
        "title": "Metro Atlanta: public EV chargers by 2030",
        "difficulty": "easy",
        "prompt": (
            "A state energy agency asks: how many public EV chargers (individual charging points) "
            "will metro Atlanta need by 2030? Walk me through your estimate."
        ),
        "clarifying": {
            "population": "Assume metro Atlanta has about 6 million people.",
            "households": "Assume 2.5 people per household and about 1.5 vehicles per household.",
            "ev share": "Assume electric vehicles are 10 percent of vehicles by 2030.",
            "home charging": "Assume 80 percent of EV owners can charge at home.",
            "utilization": "Assume one public charger can support about 15 EVs.",
        },
        "exhibit": "Assume there are about 1,200 public chargers in the metro area today.",
        "math_question": (
            "Using your own assumptions (or the ones I gave you), what is your final number, and "
            "how sensitive is it to the EV share assumption?"
        ),
        "math_answer": (
            "Reference path: 6M / 2.5 = 2.4M households; x 1.5 = 3.6M vehicles; x 10% = 360,000 EVs; "
            "x 20% needing public charging = 72,000; / 15 = about 4,800 chargers. "
            "Each 5-point change in EV share moves the answer by about 2,400. Any answer from 3,000 to 7,000 with clear logic is acceptable."
        ),
        "key_insights": [
            "Segmenting who actually needs public charging matters more than the total EV count.",
            "States assumptions explicitly and sanity-checks against today's 1,200 chargers (about 4x growth).",
            "Sensitivity: the answer scales linearly with EV share.",
        ],
        "strong_structure": [
            "Population to households to vehicles",
            "EV share by 2030",
            "Share needing public charging",
            "EVs per charger",
            "Sanity check against current supply",
        ],
        "recommendation_hint": "A strong answer ends with a number, a range, and the two assumptions that move it most.",
    },
    "operations": {
        "title": "Riverside Hospital: emergency room wait times",
        "difficulty": "medium",
        "prompt": (
            "Riverside Hospital's emergency department has an average patient time of 4 hours 20 "
            "minutes from arrival to discharge, and patient satisfaction is falling. The hospital "
            "wants to get under 3.5 hours. How would you approach this?"
        ),
        "clarifying": {
            "scope": "Focus on non-critical patients. Critical cases already go straight to treatment.",
            "capacity": "The ER has 30 beds. They are occupied by patients waiting for inpatient rooms about 35 percent of the time.",
            "staffing": "Staffing looks adequate on paper, but arrivals peak between 4 pm and 10 pm.",
            "constraints": "No budget for construction. Some process and IT spending is possible.",
            "target": "Under 210 minutes.",
        },
        "exhibit": (
            "Average patient journey (minutes)\n"
            "Triage 15 | Registration 25 | Wait for bed 120 | Doctor evaluation 30 | "
            "Labs and imaging 45 | Discharge paperwork 25 | Total 260"
        ),
        "math_question": (
            "Suppose registration moves to the bedside so it no longer adds time, and the wait for a "
            "bed falls by 40 percent. What is the new average time, and does it meet the target?"
        ),
        "math_answer": "260 - 25 - (0.40 x 120 = 48) = 187 minutes, about 3 hours 7 minutes. This meets the 210-minute target with margin.",
        "key_insights": [
            "Waiting for a bed is 120 of 260 minutes (46 percent) and is the bottleneck; inpatient boarding drives it.",
            "Fixes: faster inpatient discharge and bed turnover, a fast track for low-acuity patients, parallel steps.",
            "Peak-hour staffing (4 to 10 pm) does not match demand.",
            "187 minutes meets the target, but the numbers are averages, so peak hours still need checking.",
        ],
        "strong_structure": [
            "Map the patient journey step by step",
            "Find the bottleneck with data",
            "Root causes: capacity, process, staffing",
            "Levers: quick wins vs longer-term; metrics to track",
        ],
        "recommendation_hint": "A strong answer prioritizes bed flow (earlier inpatient discharges, boarding protocol), adds a fast track and bedside registration, and tracks door-to-discharge time by hour.",
    },
}

BEHAVIORAL = {
    "leadership": {
        "label": "Leadership and personal impact",
        "questions": [
            "Tell me about a time you led a group to achieve something that would not have happened without you.",
            "Describe a situation where you took charge without being asked.",
        ],
    },
    "teamwork_conflict": {
        "label": "Teamwork and conflict",
        "questions": [
            "Tell me about a time you disagreed with a teammate and how you resolved it.",
            "Describe working with someone whose style was very different from yours.",
        ],
    },
    "drive_resilience": {
        "label": "Drive and resilience",
        "questions": [
            "Tell me about the hardest goal you pursued and what it took to reach it.",
            "Describe a time you kept going when the odds were against you.",
        ],
    },
    "change_initiative": {
        "label": "Entrepreneurial drive and initiative",
        "questions": [
            "Tell me about a time you started or changed something that no one asked you to.",
            "Describe a time you challenged how things were done and what happened.",
        ],
    },
    "failure_learning": {
        "label": "Failure and learning",
        "questions": [
            "Tell me about a time you failed and what you did afterward.",
            "Describe a mistake that taught you something you still use.",
        ],
    },
}

BEHAVIORAL_PROBES = [
    "What exactly did YOU do, as opposed to the team?",
    "What was the result, in numbers if you can?",
    "What did the other person say or do in response?",
    "What would you do differently?",
    "Why did you choose that approach over the alternatives?",
]

FRAMEWORKS = [
    {
        "id": "airline_route",
        "prompt": "A regional airline is considering adding a new route. Structure the key questions you would answer to decide whether to launch it.",
        "strong": ["Demand: market size, price, seasonality", "Competition: incumbents, response", "Economics: revenue per flight, costs, load factor, breakeven", "Operations: aircraft, crew, slots, airports", "Strategy and risk: fit with network, downside, alternatives"],
    },
    {
        "id": "grocery_online",
        "prompt": "A grocery chain wants to launch online delivery. What would you want to know before deciding?",
        "strong": ["Customer demand and willingness to pay", "Unit economics: basket size, picking, delivery cost", "Operations: fulfillment model, stores vs warehouse", "Competition and differentiation", "Risks, pilots and success metrics"],
    },
    {
        "id": "bank_fintech",
        "prompt": "A mid-sized bank sees customers leaving for fintech apps. Structure how you would diagnose and respond.",
        "strong": ["Who is leaving and why: segments, products, reasons", "Value at stake: revenue and profit lost", "Competitor offering vs the bank's", "Response options: product, pricing, experience, partnership", "Prioritization, cost and timeline"],
    },
    {
        "id": "pharma_launch",
        "prompt": "A pharmaceutical company has a new drug approved. How would you structure the launch strategy?",
        "strong": ["Market: patients, physicians, payers", "Positioning vs existing treatments", "Pricing and reimbursement", "Go-to-market: sales force, channels, education", "Risks and launch metrics"],
    },
]

RUBRICS = {
    "case": {
        "label": "Case interview",
        "dims": {
            "structure": "1 = no clear structure; 3 = reasonable but generic buckets; 5 = tailored, MECE, prioritized structure",
            "hypothesis_driven": "1 = asks random questions; 3 = some direction; 5 = states a hypothesis and tests it, drives the case",
            "quantitative": "1 = frequent errors, no setup; 3 = correct with prompting; 5 = fast, accurate, states the setup and sanity-checks",
            "insight": "1 = restates data; 3 = reads the data correctly; 5 = draws the so-what and connects exhibits to the problem",
            "communication": "1 = hard to follow; 3 = clear but rambling at times; 5 = concise, signposted, thinks aloud well",
            "recommendation": "1 = none; 3 = a recommendation without support; 5 = clear answer first, supported, with risks and next steps",
        },
    },
    "behavioral": {
        "label": "Behavioral interview",
        "dims": {
            "story_structure": "1 = rambling; 3 = situation and result present but muddled; 5 = clear context, action, result in under two minutes",
            "personal_ownership": "1 = only says 'we'; 3 = mixed; 5 = specific about what I did and decided",
            "action_depth": "1 = vague actions; 3 = some detail; 5 = concrete steps, reasoning and obstacles",
            "measurable_impact": "1 = no result; 3 = qualitative result; 5 = quantified or clearly evidenced result",
            "reflection": "1 = none; 3 = generic lesson; 5 = specific lesson that changed later behavior",
        },
    },
    "framework": {
        "label": "Framework drill",
        "dims": {
            "structure": "1 = list of unrelated ideas; 3 = reasonable buckets; 5 = clear, tailored top-level structure",
            "mece": "1 = overlaps and gaps; 3 = mostly distinct; 5 = mutually exclusive and collectively exhaustive",
            "prioritization": "1 = no priorities; 3 = some; 5 = says where to start and why",
        },
    },
}
