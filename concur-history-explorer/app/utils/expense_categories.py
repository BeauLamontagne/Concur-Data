"""ICW Group internal expense category taxonomy."""

ICW_CATEGORIES: list[dict] = [
    # ── Agent/Insured Group ───────────────────────────────────────────────
    {
        "group_name": "Agent/Insured",
        "category_name": "Agent/Insured Relations",
        "description": "Retreats, tournaments, sporting events, theatre, spa",
        "instructions": "Requires attendees listed on expense entry.",
    },
    {
        "group_name": "Agent/Insured",
        "category_name": "Gifts - Agent/Insured",
        "description": "Flowers, gifts for agents and non-employees",
        "instructions": "Requires PO and PVMS for gift cards. Requires attendees listed.",
    },
    {
        "group_name": "Agent/Insured",
        "category_name": "Meals - Agent/Insured",
        "description": "Restaurant meals, conferences, catered events, gift baskets",
        "instructions": "Requires attendees listed on expense entry.",
    },
    # ── Business Travel Group ─────────────────────────────────────────────
    {
        "group_name": "Business Travel",
        "category_name": "Air Travel - Airfare",
        "description": "Airfare, check-in fees, baggage fees",
        "instructions": "2nd checked bag allowed only if needed for business or trips 14+ days.",
    },
    {
        "group_name": "Business Travel",
        "category_name": "Bus/Taxi/Train",
        "description": "Bus, metro, taxi, train, rideshare",
        "instructions": "",
    },
    {
        "group_name": "Business Travel",
        "category_name": "Car Rental",
        "description": "Daily rate, taxes, gas",
        "instructions": "Decline rental insurance. Refuel before return.",
    },
    {
        "group_name": "Business Travel",
        "category_name": "Hotel",
        "description": "Room, Wi-Fi, deposit",
        "instructions": "Itemize food, parking, and meals separately.",
    },
    {
        "group_name": "Business Travel",
        "category_name": "Laundry",
        "description": "Laundry/dry-cleaning, tablecloths for conventions",
        "instructions": "Allowed on trips 7+ days only.",
    },
    {
        "group_name": "Business Travel",
        "category_name": "Meals - Travel",
        "description": "Breakfast, lunch, dinner while traveling",
        "instructions": "$100/day allowance.",
    },
    {
        "group_name": "Business Travel",
        "category_name": "Mileage - Personal Vehicle",
        "description": "Manual mileage entry",
        "instructions": "Exclude commuting miles.",
    },
    {
        "group_name": "Business Travel",
        "category_name": "Parking",
        "description": "Business parking",
        "instructions": "",
    },
    {
        "group_name": "Business Travel",
        "category_name": "Tips",
        "description": "Skycap/porter, bell service, housekeeping",
        "instructions": "",
    },
    {
        "group_name": "Business Travel",
        "category_name": "Tolls",
        "description": "Toll fees",
        "instructions": "",
    },
    {
        "group_name": "Business Travel",
        "category_name": "Travel Documents",
        "description": "COVID testing, immunization, translation services",
        "instructions": "",
    },
    # ── Company Car Group ─────────────────────────────────────────────────
    {
        "group_name": "Company Car",
        "category_name": "Company Car - Car Wash",
        "description": "Car wash for company vehicle",
        "instructions": "",
    },
    {
        "group_name": "Company Car",
        "category_name": "Company Car - Expense",
        "description": "Tire rotation, oil changes, wipers",
        "instructions": "",
    },
    {
        "group_name": "Company Car",
        "category_name": "Company Car - Gasoline",
        "description": "Fuel for company vehicle",
        "instructions": "",
    },
    # ── Employee Relations Group ──────────────────────────────────────────
    {
        "group_name": "Employee Relations",
        "category_name": "Employee Relations",
        "description": "Party supplies, celebrations, team building",
        "instructions": "Requires attendees listed on expense entry.",
    },
    {
        "group_name": "Employee Relations",
        "category_name": "Meals - Employee Relations",
        "description": "Department team building meals",
        "instructions": "Requires attendees listed on expense entry.",
    },
    # ── Learning and Development Group ───────────────────────────────────
    {
        "group_name": "Learning and Development",
        "category_name": "Conferences & Industry Events",
        "description": "External conferences, networking, industry trends",
        "instructions": "",
    },
    {
        "group_name": "Learning and Development",
        "category_name": "Continuing Education / Certifications",
        "description": "CEUs, credentials, professional licenses",
        "instructions": "",
    },
    {
        "group_name": "Learning and Development",
        "category_name": "Leadership & Development Programs",
        "description": "Cohort programs, ASCEND, external academies",
        "instructions": "",
    },
    {
        "group_name": "Learning and Development",
        "category_name": "Professional Skills Training",
        "description": "Workshops, required training, practical skills",
        "instructions": "",
    },
    # ── Marketing/Recruiting Group ────────────────────────────────────────
    {
        "group_name": "Marketing/Recruiting",
        "category_name": "Advertising",
        "description": "Newspapers, billboards, promotional items, souvenirs, signs, medals",
        "instructions": "",
    },
    {
        "group_name": "Marketing/Recruiting",
        "category_name": "Corporate Marketing",
        "description": "Convention sponsorship, tradeshow booths, event fees, conference room rental",
        "instructions": "",
    },
    {
        "group_name": "Marketing/Recruiting",
        "category_name": "Recruiting",
        "description": "Job postings, interview space",
        "instructions": "",
    },
    # ── Other Group ───────────────────────────────────────────────────────
    {
        "group_name": "Other",
        "category_name": "Dues/Subscriptions",
        "description": "Membership fees, license fees, annual dues",
        "instructions": "",
    },
    {
        "group_name": "Other",
        "category_name": "Office Supplies",
        "description": "Office/field supplies, safety gear, training supplies",
        "instructions": "",
    },
    {
        "group_name": "Other",
        "category_name": "Postage/Freight",
        "description": "Postage, shipping",
        "instructions": "",
    },
    {
        "group_name": "Other",
        "category_name": "Printing",
        "description": "Convention/tradeshow printing",
        "instructions": "",
    },
]

# Quick lookups
GROUPS: list[str] = sorted({c["group_name"] for c in ICW_CATEGORIES})
CATEGORIES_BY_GROUP: dict[str, list[str]] = {}
for _cat in ICW_CATEGORIES:
    CATEGORIES_BY_GROUP.setdefault(_cat["group_name"], []).append(_cat["category_name"])
