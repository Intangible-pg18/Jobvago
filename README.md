# 🚀 Jobvago - A Cloud-Native Job Aggregation Platform

Jobvago is a fully automated, event-driven, and serverless application built on Microsoft Azure that scrapes job postings from multiple sources, processes them, and serves them via a clean REST API. It's a demonstration of modern backend architecture, designed for scalability, resilience, and security.

![C#](https://img.shields.io/badge/c%23-%23239120.svg?style=for-the-badge&logo=c-sharp&logoColor=white)![.NET](https://img.shields.io/badge/.NET-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)![Azure](https://img.shields.io/badge/azure-%230072C6.svg?style=for-the-badge&logo=microsoftazure&logoColor=white)![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=for-the-badge&logo=redis&logoColor=white)

---

## 🏛️ High-Level Architecture

The entire system is designed around a decoupled, event-driven philosophy. No component talks directly to the next; instead, they communicate through a central message queue. This ensures that if one part of the system fails or slows down, the others are not affected.

![Architecture Diagram](./Jobvago.drawio.svg)

---

## 🔧 Technology Stack

*   **Cloud Platform:** Microsoft Azure
*   **Backend API:** C# with .NET 8 on Azure App Service
*   **Data Processing:** C# Azure Functions (.NET Isolated Worker Model)
*   **Scraping & Scheduling:** Python script in a **Docker** container, run by a scheduled **Azure Container App Job**.
*   **Database:** Azure SQL Database (Serverless Tier)
*   **Messaging:** Azure Service Bus (Queue)
*   **Caching:** Azure Cache for Redis
*   **Secrets Management:** Azure Key Vault & .NET User Secrets
*   **Scraping Library:** Playwright
*   **ORM:** Entity Framework Core 8
*   **Data Validation (Python):** Pydantic

---

## 🧠 Component Deep-Dive & Design Decisions

Each component was designed with specific principles in mind.

### 1. The Scheduler (`jobvago-scheduler`)

This component kicks off the entire process.

*   **Implementation:** A **scheduled Azure Container App Job** that runs a Docker container on a CRON schedule.
*   **Design Decision: The Evolution from Azure Functions to Container Apps**
    *   **Initial Choice:** We began with a Python Azure Function on a Timer Trigger. This is ideal for simple, lightweight scheduled tasks due to its serverless nature and low cost.
    *   **The Problem:** The scraping engine requires Playwright and a full browser engine (Chromium), which are large, complex dependencies. The standard Azure Functions environment, especially on the Consumption plan, has limitations on package size and startup time. This resulted in repeated deployment and runtime failures—the environment was too constrained for our specific needs.
    *   **The Solution:** We migrated to Azure Container Apps. This approach allows us to define the *exact* runtime environment using a `Dockerfile`. We build an image that includes Python, all `pip` packages, **and the Playwright browser dependencies**. The Container App Job simply runs this pre-built, guaranteed-to-work container.
    *   **The Benefit:** This gives us the best of both worlds: the complete environmental control of a dedicated server, but with the cost-effective, serverless model of paying only for the time the job is running. It is the modern, robust solution for running containerized, scheduled tasks in Azure.

### 2. The Scraper Engine (`run_scraper.py`)

This is the core data collection engine running inside the container.

*   **Design Decision:** Why Playwright over Scrapy?
    *   **Trade-off:** Scrapy is incredibly fast for crawling simple, static HTML. However, modern websites (like Naukri.com) are dynamic web applications that heavily rely on JavaScript to load content.
    *   **Choice:** Playwright was chosen because it automates a real browser engine (Chromium). This allows it to handle complex JavaScript, deal with pop-ups, and interact with the page like a real user, making it far more robust and capable for the modern web, at the cost of being slightly slower than a pure HTTP-based crawler.
*   **Design Decision:** The **Strategy & Factory Patterns**.
    *   Initially, the main script was hardcoded for one site. This was brittle.
    *   We refactored this by defining a `ScraperStrategy` abstract base class (the "contract"). Each scraper (`InternshalaScraper`) is a concrete implementation of this strategy.
    *   A `scraper_factory` function was created to dynamically load and instantiate the correct scraper based on a configuration file. This makes the system **extensible**. To add a new site, we simply create a new scraper class and update the config; the orchestrator code doesn't change.
*   **Design Decision:** Self-Sufficient Scrapers (The `discover_jobs` Refactor).
    *   The orchestrator initially handled pagination logic, which was not scalable, as different sites have different pagination methods (page numbers vs. "Load More" buttons).
    *   We refactored the design to make each scraper fully responsible for its own pagination. The `discover_jobs` method is an **async generator** (`yield`) that discovers jobs and yields them one by one, hiding the implementation details from the orchestrator. This is a much cleaner, more decoupled design.

### 3. The Message Queue (`Azure Service Bus`)

This is the architectural lynchpin of the entire system.

*   **Implementation:** An Azure Service Bus Queue named `new-jobs-queue`.
*   **Design Decision:** Why use a queue instead of calling the processor directly?
    *   **Decoupling (Most Important):** The scraper's job ends when it drops a message in the queue. It knows nothing about the database or the processor. If we need to change the database or rewrite the processor in a different language, the scraper is completely unaffected.
    *   **Resilience:** If the processor function or the database is down for maintenance, messages simply pile up safely in the queue. Once the downstream systems are back online, they process the backlog. **No data is lost.**
    *   **Load Leveling:** If the scrapers find 50,000 jobs in a 5-minute burst, they can all be rapidly sent to the queue. The processor function can then consume them at a steady, manageable pace, preventing the database from being overwhelmed.

#### Screenshot of Service Bus Queue
`[YOUR-SCREENSHOT-HERE - A picture of the 'new-jobs-queue' in the Azure Portal, showing some active messages if possible]`

### 4. The Data Processor (`jobvago-processor`)

This is the "assembly station" that ensures data quality.

*   **Implementation:** A C# Azure Function with a **Service Bus Trigger** running on the modern **.NET Isolated Worker Model**.
*   **Design Decision:** Why `.NET Isolated Worker`?
    *   This is the current Microsoft standard. It runs our function code in a separate process from the Functions host, giving us full control over dependencies and avoiding version conflicts. This was a critical lesson learned during development.
*   **Key Logic: "Upsert" and Transactions**
    *   To maintain data integrity, the function doesn't blindly insert data. For entities like `Company`, it uses a "Get-or-Create" (Upsert) pattern to avoid duplicates.
    *   The entire set of database operations for a single message is wrapped in a **database transaction**. If any part fails (e.g., the job insert fails after a new company was created), the entire transaction is rolled back, leaving the database in a clean, consistent state. This is non-negotiable for professional data processing.

### 5. The Database (`Azure SQL Database`)

This is our structured "warehouse."

*   **Implementation:** Azure SQL Database on the **Serverless Tier**.
*   **Design Decision:** Why SQL over NoSQL?
    *   The data we are collecting is highly structured and relational (Jobs belong to Companies, have Locations, etc.). A relational database like SQL Server allows us to enforce data integrity with foreign keys and perform powerful, efficient `JOIN` queries.
*   **Design Decision:** Why the Serverless Tier?
    *   **Cost-Effectiveness:** For a project with intermittent workloads like ours, the serverless tier is perfect. It can automatically scale down to zero and **auto-pause** when not in use, dramatically reducing costs.
*   **Schema Design:** The schema is highly **normalized** to reduce data redundancy and improve integrity (The DRY Principle - Don't Repeat Yourself). We use lookup tables (`Companies`, `Locations`, `Skills`) and linking tables (`JobLocations`, `JobSkills`) to model many-to-many relationships efficiently.
*   **Performance:** Non-clustered indexes were explicitly created on foreign key columns (`CompanyID`, `SourceID`, etc.) to dramatically speed up query performance as the `Jobs` table grows.

#### Screenshot of Database Schema
`[YOUR-SCREENSHOT-HERE - A picture from VS Code or Azure Data Studio showing the database tables and their relationships]`

### 6. The API Layer (`jobvago-api`)

The public "shipping department" for our data.

*   **Implementation:** An ASP.NET Core 8 Web API hosted on **Azure App Service**.
*   **Design Decision:** Why a separate API?
    *   This follows the **Single Responsibility Principle**. The API's only job is to handle HTTP requests, apply business logic, and serve data. It is decoupled from the data ingestion pipeline.
*   **Key Technology: Entity Framework Core 8**
    *   EF Core acts as our Object-Relational Mapper (ORM), translating our C# LINQ queries (e.g., `_context.Jobs.ToListAsync()`) into efficient, parameterized SQL. This improves developer productivity and provides automatic protection against SQL Injection attacks.

---

## 🛡️ Security: The Journey to a Password-less Architecture

Handling secrets is one of the most critical aspects of professional software development.

1.  **Anti-Pattern (Initial Mistake):** The database connection string was accidentally committed to `appsettings.json` and pushed to GitHub. This is a critical security flaw.
2.  **Remediation:** The secret was immediately invalidated by resetting the database password in Azure.
3.  **Local Development Solution:** We implemented **.NET User Secrets**. This tool stores secrets in a secure JSON file *outside* the project folder, so they can never be accidentally committed to Git.
4.  **Production Solution (The Gold Standard):** We integrated **Azure Key Vault**.
    *   All secrets (like the SQL connection string) are stored centrally and securely in Key Vault.
    *   The deployed Azure services (the App Service and Function Apps) are given a **Managed Identity**, which is like an automated, secure ID card from Azure AD.
    *   We create an **Access Policy** in Key Vault that grants this Managed Identity permission to read secrets.
    *   The application code uses the `DefaultAzureCredential()` library, which automatically authenticates using its Managed Identity. The result is a **passwordless architecture**. The code contains no secrets, the configuration contains no secrets, and authentication is handled securely and automatically by the Azure platform.

#### Screenshot of Key Vault
`[YOUR-SCREENSHOT-HERE - A picture of your Azure Key Vault homepage]`

---

## ⚡ Performance: Caching with Redis

To ensure the API is fast and responsive, and to reduce load on the database, a caching layer was implemented.

*   **Implementation:** An **Azure Cache for Redis** instance.
*   **Pattern:** The **Cache-Aside Pattern** was used in the .NET API.
    1.  When a request for data arrives, the API first checks Redis for the result.
    2.  **Cache Hit:** If the data is in Redis, it's returned instantly to the user without touching the database.
    3.  **Cache Miss:** If the data is not in Redis, the API queries the SQL database, returns the result to the user, and simultaneously saves that result in Redis for subsequent requests.

This dramatically improves performance for frequently accessed data and enhances the scalability of the application.

#### Screenshot of Redis Cache
`[YOUR-SCREENSHOT-HERE - A picture of your Azure Cache for Redis homepage]`

---

## ☁️ Final Deployed Azure Resources

`[YOUR-SCREENSHOT-HERE - A picture of your 'Jobvago-RG' Resource Group in the Azure Portal, showing the list of all created services: App Service, Function Apps, SQL Server, Service Bus, Redis, Key Vault, etc.]`

---

## 📈 Future Improvements

No project is ever truly finished. Here are the next logical steps to enhance `Jobvago`:

*   **Implement CI/CD:** Create GitHub Actions workflows to fully automate the testing and deployment of all three components (API, Processor, Scheduler).
*   **Add More Scrapers:** Leverage the extensible factory pattern to add scrapers for other sites like LinkedIn, Naukri, etc.
*   **User Account Management:** Embed User Account Management allowing them to create profiles, upload resumes, setup push notifications for new jobs etc.
*   **AI Integration:** AI (with RAG capabilities) can analyse resume, give ATS scores to them, shortlist most compatable jobs for the user etc.
*   **Containerize All Services:** Migrate the remaining services (.NET API, Processor) to Docker containers and deploy them to Azure Container Apps for a unified, portable, and highly scalable architecture.

---
## 🔀 Alternate Design Choices & Trade-offs

Every architectural decision in Jobvago involved careful consideration of multiple alternatives. This section provides a comprehensive analysis of alternative approaches for each major architectural decision point, demonstrating the depth of thought behind the current design while helping others understand the trade-offs involved in modern system architecture.

### 1. Scheduling & Orchestration Architecture

#### **Current Choice: Azure Container Apps Job (CRON-based)**

**Current Implementation:**
- Docker container running Python scraper on CRON schedule
- Azure Container Apps Job for serverless execution
- Schedule-driven batch processing

**Alternative 1: Kubernetes CronJobs + AKS**

**Description:** Deploy scrapers as Kubernetes CronJobs on Azure Kubernetes Service, using Helm charts for configuration management and kubectl for deployment.

**Architectural Changes Required:**
- Set up AKS cluster with node pools
- Create Kubernetes CronJob manifests
- Implement Helm charts for deployment
- Add cluster monitoring and logging
- Configure RBAC and network policies

**Pros:**
- Industry-standard container orchestration
- Advanced scheduling capabilities (timezone support, multiple schedules)
- Excellent horizontal scaling and resource management
- Built-in job history and cleanup policies
- Cloud-agnostic portability
- Superior resource utilization across multiple workloads
- Advanced networking and security controls

**Cons:**
- Significant operational overhead and complexity
- Always-on cluster costs even when no jobs are running
- Requires Kubernetes expertise for management
- More complex troubleshooting and debugging
- Overkill for simple scheduled tasks
- Higher minimum infrastructure costs
- Steeper learning curve for team members

**When Preferred:** When running dozens of different scheduled jobs, need advanced scheduling features, require multi-cloud portability, or already have Kubernetes expertise in the team.

**Implementation Complexity:** High (requires cluster management, networking, security configuration)
**Performance:** Excellent for complex workloads, overhead for simple tasks
**Cost:** Higher baseline cost due to always-on cluster
**Scalability:** Excellent for multiple diverse workloads

**Alternative 2: Azure Data Factory (ETL Pipeline)**

**Description:** Use Azure Data Factory pipelines with custom activities for web scraping, leveraging its scheduling and monitoring capabilities.

**Architectural Changes Required:**
- Create ADF instance and linked services
- Develop custom activities for scraping logic
- Design pipeline with control flow activities
- Implement datasets and data flows
- Set up integration runtime for execution

**Pros:**
- Purpose-built for data integration pipelines
- Rich monitoring and alerting capabilities
- Built-in data movement and transformation
- Visual pipeline designer
- Excellent for complex ETL scenarios
- Strong data lineage tracking

**Cons:**
- Overkill for simple web scraping
- Limited support for complex custom logic
- Higher learning curve for scraping use cases
- More expensive than simple alternatives
- Not designed for browser automation
- Complex setup for simple scenarios

**When Preferred:** When scraping is part of larger ETL processes, need extensive data transformation, or require sophisticated pipeline monitoring.

**Implementation Complexity:** Medium to High (designed for data scenarios)
**Performance:** Excellent for data pipelines, overhead for simple scraping
**Cost:** Higher for simple use cases
**Scalability:** Excellent for data processing workloads

### 2. Data Processing Architecture

#### **Current Choice: Event-Driven Azure Functions with Service Bus Triggers**

**Current Implementation:**
- C# Azure Functions triggered by Service Bus messages
- Asynchronous message processing
- Individual message handling with transactions
- .NET Isolated Worker Model

**Alternative 1: Apache Kafka Streaming Architecture**

**Description:** Replace Azure Service Bus with Apache Kafka for high-throughput event streaming, using Kafka Streams for real-time data processing.

**Architectural Changes Required:**
- Set up Kafka cluster (using Confluent Cloud or self-managed)
- Implement Kafka producers in scraper components
- Create Kafka consumers for data processing
- Design event schemas using Avro or Protobuf
- Implement stream processing topologies
- Add monitoring with Kafka tools

**Pros:**
- Extremely high throughput (millions of messages/second)
- Built-in replication and fault tolerance
- Strong ordering guarantees within partitions
- Excellent for real-time analytics and streaming
- Event sourcing capabilities with log compaction
- Rich ecosystem of connectors and tools
- Horizontal scalability

**Cons:**
- Significant operational overhead and complexity
- Requires Kafka expertise for proper configuration
- Overkill for simple queue scenarios
- More expensive than simple messaging solutions
- Complex topic and partition management
- Steeper learning curve
- Requires careful capacity planning

**When Preferred:** For high-volume real-time processing, when building data streaming platforms, or need event sourcing capabilities.

**Implementation Complexity:** Very High (Kafka cluster management and streaming concepts)
**Performance:** Excellent for high-volume streaming
**Cost:** Higher operational costs for small workloads
**Scalability:** Excellent for large-scale streaming

**Alternative 2: Batch Processing with Scheduled Jobs**

**Description:** Replace real-time processing with periodic batch processing, collecting scraped data and processing in scheduled intervals.

**Architectural Changes Required:**
- Implement data staging area (blob storage or database)
- Create batch processing jobs (Azure Batch or similar)
- Design data partitioning and processing windows
- Implement checkpoint and restart mechanisms
- Add batch monitoring and alerting

**Pros:**
- More predictable resource usage and costs
- Better for large dataset processing
- Easier error handling and recovery
- More efficient resource utilization
- Better suited for complex analytics
- Simpler debugging and monitoring

**Cons:**
- Higher latency for data availability
- Less responsive to demand changes
- Risk of data buildup during failures
- Fixed processing schedule may not match data arrival
- Potential for larger failure blast radius
- Users see stale data between batch runs

**When Preferred:** When real-time processing isn't required, dealing with large datasets, or when processing costs need to be optimized.

**Implementation Complexity:** Medium (batch job design and scheduling)
**Performance:** Excellent for large batches, poor for real-time needs
**Cost:** Lower overall costs, better resource utilization
**Scalability:** Excellent for large dataset processing

### 3. API Architecture & Communication Patterns

#### **Current Choice: REST API with ASP.NET Core**

**Current Implementation:**
- RESTful endpoints using HTTP verbs
- JSON request/response format
- Stateless communication
- Standard HTTP status codes

**Alternative 1: Event-Driven API with WebSockets**

**Description:** Implement real-time API using WebSockets for bidirectional communication, allowing server to push updates to clients immediately.

**Architectural Changes Required:**
- Implement WebSocket server with SignalR or similar
- Design event-based API contracts
- Add connection management and scaling
- Implement authentication for persistent connections
- Create event routing and subscription management
- Add fallback mechanisms for connection failures

**Pros:**
- Real-time data updates without polling
- Lower latency for time-sensitive data
- Reduced server load from polling
- Better user experience for dynamic data
- Bidirectional communication capabilities
- Lower bandwidth usage for frequent updates
- Natural fit for collaborative features

**Cons:**
- More complex client-side state management
- Connection management and scaling challenges
- Harder to cache and CDN deployment
- More complex load balancing
- Debugging real-time issues is challenging
- Browser compatibility considerations
- Higher server resource usage for persistent connections

**When Preferred:** Real-time job alerts, collaborative features, or when data freshness is critical.

**Implementation Complexity:** High (connection management and scaling)
**Performance:** Excellent for real-time scenarios
**Cost:** Higher server resources for persistent connections
**Scalability:** Challenging due to persistent connections

### 4. Caching Strategy & Architecture

#### **Current Choice: Redis Cache-Aside Pattern**

**Current Implementation:**
- External Redis cache for API responses
- Manual cache management in application code
- TTL-based expiration
- Cache-aside (lazy loading) pattern

**Alternative 1: CDN-Based Caching with Edge Locations**

**Description:** Use Azure CDN or Cloudflare for geographic distribution of cached API responses, with cache invalidation strategies.

**Architectural Changes Required:**
- Configure CDN with API endpoint caching rules
- Implement cache headers and TTL strategies
- Add cache invalidation triggers on data updates
- Design cache key strategies for different endpoints
- Implement geo-based cache optimization
- Add CDN monitoring and analytics

**Pros:**
- Global edge locations reduce latency worldwide
- Massive scale and automatic load handling
- Reduced bandwidth costs for origin servers
- Built-in DDoS protection and security features
- Improved user experience across geographies
- Reduced origin server load
- Cost-effective for high-traffic APIs

**Cons:**
- Cache invalidation delays across edge locations
- Limited control over cache behavior
- Not suitable for personalized or user-specific data
- Debugging cache issues across multiple locations
- Additional cost for CDN services
- Complexity in cache purging strategies
- Limited to cacheable content types

**When Preferred:** Global user base, high-traffic public APIs, static or semi-static data, or when geographic performance is critical.

**Implementation Complexity:** Medium (CDN configuration and invalidation)
**Performance:** Excellent for global users
**Cost:** CDN costs offset by reduced origin load
**Scalability:** Excellent global scalability

### 5. Authentication & Security Architecture

#### **Current Choice: Azure Key Vault + Managed Identity**

**Current Implementation:**
- Passwordless authentication using Azure Managed Identity
- Centralized secret management in Azure Key Vault
- Role-based access control (RBAC)
- No embedded credentials in code

**Alternative 1: OAuth 2.0 + JWT Token-Based Authentication**

**Description:** Implement OAuth 2.0 authorization server with JWT tokens for stateless authentication, supporting multiple grant types and scopes.

**Architectural Changes Required:**
- Set up OAuth 2.0 authorization server (IdentityServer or Azure AD)
- Implement JWT token validation middleware
- Design scope and claims-based authorization
- Add token refresh and revocation mechanisms
- Implement client registration and management
- Create user consent and authorization flows

**Pros:**
- Industry-standard authentication protocol
- Stateless tokens reduce server-side session management
- Fine-grained access control with scopes
- Support for multiple client types (web, mobile, APIs)
- Token-based approach scales well
- Interoperability with third-party services
- Support for federated identity scenarios

**Cons:**
- More complex implementation and management
- Token lifecycle management challenges
- Security concerns with token storage and transmission
- Requires secure token storage on clients
- Complex debugging of authentication flows
- Potential for token leakage or misuse
- Higher development and operational complexity

**When Preferred:** Multi-tenant applications, mobile/SPA clients, third-party integrations, or when fine-grained authorization is needed.

**Implementation Complexity:** High (OAuth flows and token management)
**Performance:** Good for stateless scenarios
**Cost:** Higher development complexity
**Scalability:** Excellent for distributed systems

---
