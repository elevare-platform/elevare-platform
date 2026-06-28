SKILLS_TAXONOMY = {
    # ── PROGRAMMING LANGUAGES ──
    "python", "javascript", "typescript", "java", "c", "c++", "c#",
    "go", "golang", "rust", "ruby", "php", "swift", "kotlin", "scala",
    "r", "matlab", "perl", "bash", "shell", "powershell", "groovy",
    "dart", "elixir", "haskell", "lua", "fortran", "cobol", "vba",

    # ── WEB FRAMEWORKS & LIBRARIES ──
    "fastapi", "django", "flask", "express", "nodejs", "node", "nestjs", "nextjs", "nuxtjs",
    "react", "vue", "angular", "svelte", "jquery", "bootstrap", "tailwind",
    "spring", "spring boot", "laravel", "rails", "ruby on rails", "asp.net",
    "gatsby", "remix", "htmx", "alpinejs",

    # ── DATABASES ──
    "postgresql", "mysql", "sqlite", "mongodb", "redis", "elasticsearch",
    "cassandra", "dynamodb", "firebase", "supabase", "oracle", "mssql",
    "sql server", "mariadb", "cockroachdb", "neo4j", "influxdb",
    "clickhouse", "snowflake", "bigquery", "redshift",

    # ── CLOUD & DEVOPS ──
    "aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "k8s",
    "terraform", "ansible", "jenkins", "github actions", "gitlab ci",
    "circleci", "travis ci", "helm", "prometheus", "grafana", "datadog",
    "nginx", "apache", "linux", "ubuntu", "debian", "centos",
    "cloudflare", "vercel", "netlify", "heroku", "digitalocean",

    # ── DATA & AI ──
    "machine learning", "deep learning", "nlp", "natural language processing",
    "computer vision", "pytorch", "tensorflow", "keras", "scikit-learn",
    "pandas", "numpy", "scipy", "matplotlib", "seaborn", "plotly",
    "hugging face", "langchain", "openai", "anthropic", "llm",
    "data science", "data analysis", "data engineering", "data visualization",
    "tableau", "power bi", "looker", "metabase", "apache spark",
    "hadoop", "kafka", "airflow", "dbt", "etl",

    # ── TOOLS & PLATFORMS ──
    "git", "github", "gitlab", "bitbucket", "jira", "confluence",
    "notion", "slack", "trello", "asana", "figma", "sketch", "zeplin",
    "postman", "swagger", "graphql", "rest api", "grpc", "websockets",
    "celery", "rabbitmq", "sqs", "pubsub",

    # ── MOBILE ──
    "react native", "flutter", "android", "ios", "swift", "kotlin",
    "xamarin", "ionic", "expo",

    # ── TESTING ──
    "pytest", "jest", "mocha", "cypress", "selenium", "playwright",
    "unit testing", "integration testing", "tdd", "bdd",

    # ── SECURITY ──
    "cybersecurity", "penetration testing", "ethical hacking", "siem",
    "owasp", "soc", "iso 27001", "gdpr", "ndpr", "vulnerability assessment",
    "network security", "firewall", "iam", "sso", "oauth", "jwt",

    # ── FINANCE & ACCOUNTING ──
    "financial modelling", "financial analysis", "financial reporting",
    "budgeting", "forecasting", "ifrs", "gaap", "auditing", "taxation",
    "treasury management", "risk management", "credit analysis",
    "investment analysis", "portfolio management", "equity research",
    "corporate finance", "mergers and acquisitions", "m&a", "valuation",
    "accounts payable", "accounts receivable", "reconciliation",
    "bookkeeping", "payroll", "cost accounting", "management accounting",
    "quickbooks", "sage", "tally", "oracle financials", "sap fi",

    # ── BANKING ──
    "retail banking", "commercial banking", "investment banking",
    "trade finance", "credit risk", "market risk", "operational risk",
    "kyc", "aml", "anti-money laundering", "compliance",
    "basel iii", "loan origination", "credit scoring",
    "relationship management", "business development",

    # ── HUMAN RESOURCES ──
    "recruitment", "talent acquisition", "onboarding", "performance management",
    "learning and development", "l&d", "compensation and benefits",
    "hr business partner", "hrbp", "organisational development",
    "employee relations", "workforce planning", "succession planning",
    "hris", "bamboohr", "workday", "sap hr", "oracle hcm",
    "job evaluation", "hay method", "competency framework",

    # ── MARKETING & COMMUNICATIONS ──
    "digital marketing", "content marketing", "seo", "sem", "ppc",
    "social media marketing", "email marketing", "marketing automation",
    "hubspot", "salesforce", "mailchimp", "google analytics", "ga4",
    "brand management", "market research", "copywriting",
    "public relations", "pr", "media relations", "crisis communication",
    "google ads", "meta ads", "facebook ads",

    # ── SALES ──
    "sales management", "business development", "key account management",
    "crm", "salesforce crm", "cold calling", "b2b sales", "b2c sales",
    "solution selling", "consultative selling", "sales forecasting",
    "territory management", "channel sales",

    # ── OPERATIONS & SUPPLY CHAIN ──
    "project management", "programme management", "pmp", "prince2",
    "agile", "scrum", "kanban", "lean", "six sigma", "operations management",
    "supply chain management", "logistics", "procurement", "inventory management",
    "vendor management", "contract management", "warehouse management",
    "erp", "sap", "oracle erp",

    # ── ENGINEERING (NON-SOFTWARE) ──
    "civil engineering", "structural engineering", "mechanical engineering",
    "electrical engineering", "chemical engineering", "petroleum engineering",
    "oil and gas", "autocad", "solidworks", "ansys", "revit",
    "project controls", "quantity surveying", "hse", "health and safety",
    "iso 9001", "quality management",

    # ── SOFT SKILLS ──
    "leadership", "communication", "teamwork", "problem solving",
    "critical thinking", "analytical skills", "attention to detail",
    "time management", "adaptability", "emotional intelligence",
    "stakeholder management", "negotiation", "presentation skills",
    "mentoring", "coaching", "conflict resolution",

    # ── NIGERIAN PROFESSIONAL CERTIFICATIONS ──
    "ican", "ican fellow", "acca", "cfa", "cpa", "cima", "cibn",
    "cipm", "cipd", "pmp", "prince2", "cisa", "cism", "cissp",
    "aws certified", "azure certified", "google certified",
    "ican membership", "nysc", "fca", "aca",

    # ── NIGERIAN INDUSTRY SPECIFIC ──
    "fintech", "insurtech", "edtech", "healthtech", "agritech",
    "mobile money", "ussd", "payment gateway", "pos", "agency banking",
    "microfinance", "pension management", "pencom",
    "ncc compliance", "cbn regulations", "sec regulations",
    "nigerian stock exchange", "ngx", "fmdq",
}

# Normalisation map — common variants to canonical form
SKILLS_NORMALISATION = {
    "node.js": "nodejs",
    "node js": "nodejs",
    "reactjs": "react",
    "react.js": "react",
    "vuejs": "vue",
    "vue.js": "vue",
    "golang": "go",
    "k8s": "kubernetes",
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "postgres": "postgresql",
    "mongo": "mongodb",
    "gcp": "google cloud",
    "ms sql": "sql server",
    "mssql": "sql server",
}