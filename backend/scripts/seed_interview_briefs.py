"""
One-off script: generate and write interview_brief for every job that lacks one.
Uses asyncpg (available in the API container) to connect to the database.
"""

import asyncio
import os

import asyncpg

BRIEFS_BY_TITLE: dict = {
    "backend engineer": (
        "Explore the candidate's hands-on backend development experience: languages, "
        "frameworks, and databases they rely on, how they design APIs and data models, "
        "and their approach to performance and reliability. Probe their experience with "
        "async processing, containerisation, and debugging production issues. "
        "Ask them to walk through a technically challenging backend project they led."
    ),
    "backend engineer (node.js)": (
        "Focus on the candidate's Node.js expertise: event-loop mechanics, async patterns, "
        "and their experience with frameworks such as Express or NestJS. Explore how they "
        "design REST or GraphQL APIs, handle auth, and manage database interactions. "
        "Ask about a production Node.js service they built and the challenges they solved."
    ),
    "senior backend engineer": (
        "Probe the candidate's experience leading backend architecture decisions: service "
        "decomposition, API design, scalability, and data modelling. Explore how they mentor "
        "junior engineers and ensure system reliability. Ask them to describe a significant "
        "backend challenge they owned end-to-end and the lessons they took from it."
    ),
    "senior backend engineer (python)": (
        "Explore the candidate's Python backend depth: frameworks like FastAPI or Django, "
        "async patterns, ORM usage, and background task processing. Probe their approach "
        "to API design, security best practices, and cloud deployment. Ask about a complex "
        "Python service they architected and the technical decisions they made."
    ),
    "senior software engineer": (
        "Explore the candidate's depth across the software engineering lifecycle: system "
        "design, code quality, testing strategies, and cross-functional collaboration. Ask "
        "how they approach ambiguous technical problems and influence architectural decisions. "
        "Have them walk through a project where their engineering judgement had real impact."
    ),
    "senior software engineer (js)": (
        "Probe the candidate's senior-level JavaScript/TypeScript expertise: runtime "
        "behaviour, performance optimisation, and experience across frontend and backend JS "
        "runtimes. Explore how they design scalable architectures and ensure code quality. "
        "Ask about a complex JS system they built and the tradeoffs they navigated."
    ),
    "senior software engineer (python)": (
        "Explore the candidate's senior Python experience: architecture patterns, performance "
        "optimisation, testing discipline, and mentoring. Probe async ecosystem comfort, "
        "type annotations, and packaging. Ask how they have led Python-based projects from "
        "design through production."
    ),
    "full stack developer": (
        "Cover the candidate's experience across the full stack: preferred frontend and "
        "backend technologies, state management, API design, and database decisions. "
        "Ask about a feature they owned end-to-end and the tradeoffs they made. Probe "
        "how they maintain quality and productivity across both sides of the stack."
    ),
    "full stack software engineer with ui/ux experience": (
        "Explore the candidate's ability to span frontend engineering, backend development, "
        "and UI/UX design. Ask how they translate business requirements into intuitive "
        "interfaces, their experience with Figma, and how they bridge design and "
        "implementation. Probe their approach to enterprise modules, API integrations, "
        "and multi-tenant architecture. Ask them to walk through a project that needed "
        "all three disciplines."
    ),
    "junior software developer": (
        "Assess the candidate's foundational programming knowledge and how they approach "
        "problem-solving. Ask about personal, academic, or internship projects they have "
        "built, how they handle feedback and code reviews, and what technologies they are "
        "actively developing skills in. Explore their understanding of version control, "
        "REST APIs, and basic database concepts."
    ),
    "frontend developer (react)": (
        "Explore the candidate's React experience: component design, state management "
        "approaches, performance optimisation, and accessibility. Ask how they work with "
        "designers, handle responsive layouts, and manage API interactions. Have them walk "
        "through a React application they built and the architectural choices they made."
    ),
    "mobile developer (flutter)": (
        "Probe the candidate's Flutter and Dart experience: widget architecture, state "
        "management patterns, platform channels, and publishing to app stores. Explore "
        "how they handle offline scenarios and performance. Ask about a Flutter app "
        "they shipped and the challenges they encountered."
    ),
    "android developer": (
        "Explore the candidate's Android development experience: Jetpack Compose vs XML, "
        "architecture patterns, Kotlin coroutines, and Jetpack libraries. Probe their "
        "approach to testing and device fragmentation. Ask about an Android app they built "
        "and the technical decisions they are most proud of."
    ),
    "ios developer": (
        "Probe the candidate's iOS and Swift experience: UIKit vs SwiftUI, concurrency, "
        "Core Data, and App Store submission. Ask how they handle memory management, "
        "background tasks, and accessibility. Have them walk through an iOS app they "
        "shipped and the most challenging aspect of building it."
    ),
    "infrastructure engineer": (
        "Explore the candidate's experience designing and managing cloud or on-premise "
        "infrastructure: networking, compute, storage, and security controls. Ask how they "
        "approach infrastructure-as-code, capacity planning, and incident response. Probe "
        "their experience with cost optimisation and high availability across distributed "
        "systems."
    ),
    "devops engineer": (
        "Probe the candidate's CI/CD pipeline experience, container orchestration, and "
        "cloud provider expertise. Ask how they implement monitoring, alerting, and on-call "
        "processes. Explore their approach to infrastructure-as-code, secrets management, "
        "and reducing deployment risk. Ask about an incident they resolved and the "
        "systemic improvements they made afterwards."
    ),
    "security engineer": (
        "Explore the candidate's security engineering experience: threat modelling, "
        "vulnerability assessment, secure SDLC practices, and incident response. Ask how "
        "they approach authentication design, secrets management, and penetration testing. "
        "Probe their experience with compliance frameworks and balancing security with "
        "development velocity."
    ),
    "qa engineer": (
        "Assess the candidate's testing philosophy and practical experience: unit, "
        "integration, end-to-end, and exploratory testing. Ask how they advocate for "
        "quality within a team, their automation framework experience, and how they handle "
        "flaky tests. Probe their ability to triage bugs and communicate risk to stakeholders."
    ),
    "database administrator": (
        "Explore the candidate's DBA experience: schema design, query optimisation, "
        "indexing strategies, backup and recovery, and replication. Ask how they handle "
        "migrations in production with minimal downtime and how they monitor and tune "
        "performance. Probe their experience with both relational and NoSQL systems."
    ),
    "machine learning engineer": (
        "Probe the candidate's ML engineering experience: training pipelines, feature "
        "engineering, experiment tracking, and deploying models to production. Ask how "
        "they handle data quality issues, model drift, and inference latency. Explore their "
        "ML framework experience and MLOps tooling. Have them describe an ML model they "
        "took from experimentation through to production."
    ),
    "data scientist": (
        "Explore the candidate's data science process: problem framing, data exploration, "
        "feature engineering, model selection, and communicating results to non-technical "
        "stakeholders. Ask about statistical methods they rely on, how they validate models, "
        "and their experience with large datasets. Have them walk through an analysis that "
        "influenced a business decision."
    ),
    "data analyst intern": (
        "Assess the candidate's analytical foundations: comfort with SQL, spreadsheets, "
        "and basic statistical concepts. Ask about a data project or assignment where they "
        "turned raw data into a clear insight. Explore their curiosity, how they question "
        "data, and what tools they have been learning."
    ),
    "head of engineering": (
        "Explore the candidate's experience leading engineering organisations: building "
        "teams, setting technical direction, and balancing delivery with technical "
        "investment. Ask about hiring, performance management, and engineering culture. "
        "Probe how they communicate technical strategy to non-technical leadership and "
        "how they have navigated a significant organisational challenge."
    ),
    "support engineer": (
        "Assess the candidate's technical troubleshooting skills and ability to communicate "
        "clearly with customers. Ask how they diagnose issues across the stack, manage a "
        "high-volume queue, and escalate effectively. Probe their experience writing "
        "internal documentation and how they contribute to reducing recurring issues."
    ),
    "technical writer": (
        "Explore the candidate's approach to writing technical documentation: how they "
        "research unfamiliar systems, structure content for different audiences, and "
        "maintain quality over time. Ask about tools they use and how they gather input "
        "from subject-matter experts. Have them describe a documentation project "
        "they are proud of."
    ),
    "scrum master": (
        "Probe the candidate's experience facilitating agile ceremonies and coaching teams. "
        "Ask how they handle impediments, manage team dynamics, and keep product and "
        "engineering aligned. Explore their approach to metrics and continuous improvement. "
        "Ask about a team challenge they helped resolve and the outcome."
    ),
    "senior accountant (manufacturing)": (
        "Probe the candidate's accounting experience in a manufacturing or cost-intensive "
        "environment: cost accounting, inventory valuation, WIP tracking, and variance "
        "analysis. Ask how they ensure accuracy of financial statements, manage month-end "
        "close, and coordinate with auditors. Explore their ERP experience and how they "
        "have improved financial controls or processes in a previous role."
    ),
    "finance intern": (
        "Assess the candidate's foundational finance and accounting knowledge, attention to "
        "detail, and ability to work accurately with numbers. Ask about relevant coursework, "
        "personal projects, or any hands-on exposure to financial data. Explore their "
        "proficiency with Excel and interest in a specific area of finance."
    ),
    "risk analyst": (
        "Explore the candidate's experience identifying, quantifying, and mitigating business "
        "or financial risks. Ask how they build risk models, communicate risk appetite to "
        "stakeholders, and monitor emerging risks. Probe their familiarity with regulatory "
        "requirements and how they have influenced risk decisions in a previous role."
    ),
    "marketers(fintech)": (
        "Explore the candidate's fintech marketing experience: translating complex financial "
        "products into compelling messaging for different customer segments. Ask about digital "
        "acquisition channels, campaign performance analysis, and regulatory constraints. "
        "Probe their understanding of fintech user trust and how they have grown or retained "
        "a user base."
    ),
    "marketers (fintech)": (
        "Explore the candidate's fintech marketing experience: translating complex financial "
        "products into compelling messaging for different customer segments. Ask about digital "
        "acquisition channels, campaign performance analysis, and regulatory constraints. "
        "Probe their understanding of fintech user trust and how they have grown or retained "
        "a user base."
    ),
    "growth marketing manager": (
        "Probe the candidate's growth marketing track record: acquisition experiments, funnel "
        "optimisation, retention strategies, and attribution modelling. Ask how they "
        "prioritise growth bets and work across product, engineering, and creative teams. "
        "Have them walk through a campaign or initiative that delivered measurable results."
    ),
    "sales executive": (
        "Explore the candidate's sales approach: how they prospect, qualify leads, manage a "
        "pipeline, and close deals. Ask about their CRM experience, handling objections, and "
        "building long-term client relationships. Probe their understanding of the product "
        "they would be selling in and how they have consistently hit or exceeded targets."
    ),
    "customer success manager": (
        "Explore the candidate's approach to customer onboarding, adoption, and retention. "
        "Ask how they identify at-risk accounts, drive product value realisation, and manage "
        "escalations. Probe their ability to translate customer feedback into product insights "
        "and how they have grown accounts or reduced churn in a previous role."
    ),
    "ui/ux designer": (
        "Explore the candidate's design process from research to delivery: user research, "
        "wireframes, prototypes, and design validation. Ask about their experience with "
        "design systems, working within engineering constraints, and communicating design "
        "rationale. Have them walk through a portfolio project and the decisions they made."
    ),
    "3d animation designer": (
        "Probe the candidate's end-to-end 3D production skills: modelling, rigging, "
        "texturing, lighting, animation, and rendering. Ask about their preferred software "
        "and how they approach a project from creative brief to final delivery. Explore how "
        "they handle feedback cycles, optimise assets for different platforms, and stay "
        "current with animation trends. Ask them to describe a portfolio project they are "
        "particularly proud of."
    ),
    "content writer": (
        "Explore the candidate's writing process: how they research topics, adapt tone "
        "for different audiences, and meet editorial standards and deadlines. Ask about "
        "their experience with SEO principles, content strategy, and working with subject "
        "matter experts. Have them describe a piece of content that performed well and "
        "why they think it resonated."
    ),
    "product manager": (
        "Explore how the candidate defines and prioritises product work: discovery, writing "
        "requirements, working with engineering and design, and measuring outcomes. Ask how "
        "they handle competing priorities and make trade-off decisions under uncertainty. "
        "Have them walk through a product they shipped, the problem it solved, and what "
        "they would do differently."
    ),
    "hr manager": (
        "Probe the candidate's experience across core HR functions: recruitment, onboarding, "
        "performance management, employee relations, and compliance. Ask how they have built "
        "or improved HR processes and how they handle sensitive employee situations. Explore "
        "their approach to workplace culture and supporting managers with people challenges."
    ),
    "office manager": (
        "Explore the candidate's experience managing day-to-day office operations, vendor "
        "relationships, and administrative processes. Ask how they prioritise competing "
        "demands, manage budgets, and keep the workplace running smoothly. Probe their "
        "communication style and how they have handled an operational challenge that "
        "required quick problem-solving."
    ),
    "business analyst": (
        "Explore the candidate's experience bridging business needs and technical solutions: "
        "requirements gathering, process mapping, stakeholder management, and solution "
        "validation. Ask how they handle ambiguous briefs and manage scope creep. Have them "
        "walk through an analysis that led to a meaningful business or process improvement."
    ),
    "mechanical & electrical engineer": (
        "Explore the candidate's engineering experience across mechanical and electrical "
        "systems: design, installation, testing, and maintenance. Ask how they approach "
        "fault diagnosis, compliance with relevant standards, and technical documentation. "
        "Probe their experience collaborating with other disciplines on complex projects "
        "and a challenging technical problem they have resolved."
    ),
    "hairdresser": (
        "Explore the candidate's professional experience across hair services: cutting, "
        "colouring, styling, and treatments. Ask how they conduct client consultations, "
        "handle difficult or first-time clients, and stay current with trends and techniques. "
        "Probe their approach to salon hygiene standards, time management across appointments, "
        "and their most technically challenging service."
    ),
    "compliance officer": (
        "Explore the candidate's compliance experience: regulatory frameworks they have "
        "worked within, how they conduct monitoring and gap assessments, and how they "
        "communicate requirements to business teams. Ask about their experience managing "
        "an audit, handling a compliance breach, and implementing a new regulatory requirement."
    ),
    "legal counsel": (
        "Probe the candidate's legal expertise: contract drafting and negotiation, risk "
        "advisory, regulatory compliance, or litigation experience as applicable. Ask how "
        "they communicate legal risk to non-lawyers, manage competing priorities, and stay "
        "current with relevant legislation. Have them describe a complex legal matter they "
        "navigated and the outcome."
    ),
}

SKIP_TITLES = {"dddddddddd", "dfffffffffffffffffffff", "sssssssssss"}


async def main() -> None:
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://elevare:elevare_dev@db:5432/elevare_db",
    ).replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(db_url)

    rows = await conn.fetch(
        "SELECT id, title FROM jobs WHERE interview_brief IS NULL "
        "AND is_general_interest = FALSE ORDER BY title"
    )
    print(f"Found {len(rows)} jobs without an interview brief.\n")

    updated, skipped_junk, skipped_no_match = 0, 0, 0

    for row in rows:
        job_id = row["id"]
        title: str = row["title"]
        key = title.strip().lower()

        if key in SKIP_TITLES:
            print(f"  SKIP (junk)  : {title}")
            skipped_junk += 1
            continue

        brief = BRIEFS_BY_TITLE.get(key)
        if not brief:
            print(f"  NO MATCH     : {title!r}")
            skipped_no_match += 1
            continue

        await conn.execute(
            "UPDATE jobs SET interview_brief = $1 WHERE id = $2",
            brief,
            job_id,
        )
        print(f"  UPDATED      : {title}")
        updated += 1

    await conn.close()

    print(
        f"\nDone.  Updated={updated}  "
        f"Skipped(junk)={skipped_junk}  No-match={skipped_no_match}"
    )


if __name__ == "__main__":
    asyncio.run(main())
