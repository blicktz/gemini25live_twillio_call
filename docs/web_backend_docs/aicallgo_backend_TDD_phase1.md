# AICallGO Backend Technical Design Document (TDD) - Phase 1

## 1. Overview & Executive Summary

This Technical Design Document (TDD) outlines the architecture for the AICallGO backend system. The backend will be a Python FastAPI application deployed on Render.com, integrating with Stripe for payment processing, and designed to seamlessly communicate with a Vercel-hosted v0 frontend application.

The core problem this technical design solves is the creation of a scalable, secure, and maintainable backend infrastructure to support the AICallGO AI-powered call answering service. This includes user authentication, AI agent configuration, call log management, and payment processing.

**Key Architectural Decisions:**

*   **FastAPI Framework:** Chosen for its high performance, asynchronous capabilities, automatic data validation, and OpenAPI documentation generation, which are crucial for rapid development and clear API contracts with the frontend.
*   **Render.com Deployment:** Selected for its ease of use for deploying containerized applications, managed PostgreSQL and Redis services, auto-scaling capabilities, and straightforward environment variable management.
*   **Stripe Integration:** Leveraged for its robust and secure payment processing capabilities, including client-side tokenization for PCI compliance and comprehensive webhook support for managing subscriptions and payment events.
*   **PostgreSQL Database:** Chosen as the primary data store due to its reliability, ACID compliance, and strong support for structured data, suitable for managing user accounts, business information, and call logs.
*   **JWT-based Authentication:** Implemented for stateless and secure API authentication, allowing for easy integration with both web and mobile clients.
*   **Docker Containerization:** Used to ensure consistent development, testing, and production environments, simplifying deployment on Render.com.
*   **Celery for Asynchronous Tasks:** Integrated for handling background tasks such as processing Stripe webhooks, sending email notifications, and other long-running operations without blocking API responses.
*   **Google Business Profile API Integration:** Utilized to fetch business details (name, address, phone, services, hours) to streamline user onboarding and reduce manual data entry.

## 2. Technology Stack Selection

*   **Language/Framework:** Python 3.12 with FastAPI. Justification: FastAPI's modern features, async support, and Pydantic data validation accelerate development and ensure robust API performance. Python's extensive libraries and community support are beneficial for a growing application.
*   **Database:** PostgreSQL 16 (Managed on Render.com). Justification: PostgreSQL offers reliability, data integrity, and scalability. Render.com's managed service simplifies database administration and backups.
*   **Caching Layer:** Redis 7 (Managed on Render.com). Justification: Redis provides a high-performance in-memory data store, ideal for caching frequently accessed data, session management, and as a Celery message broker.
*   **Asynchronous Task Queue:** Celery with Redis as a broker. Justification: Celery is a mature and powerful distributed task queue, essential for offloading tasks like Stripe webhook processing and ensuring API responsiveness.
*   **Authentication Method:** JWT-based authentication. Justification: JWTs are a standard, stateless, and secure method for API authentication, well-suited for microservices and frontend applications.
*   **Containerization:** Docker. Justification: Docker ensures consistency across development, staging, and production environments, simplifying deployment and scaling on Render.com.
*   **Payment Processing:** Stripe Python SDK. Justification: Stripe's SDK provides a secure and developer-friendly way to integrate payment processing, handle subscriptions, and manage webhooks, ensuring PCI compliance.
*   **Frontend Integration:** FastAPI CORS (Cross-Origin Resource Sharing) middleware. Justification: Essential for allowing secure communication between the Vercel-hosted frontend and the Render.com-hosted backend.
*   **Google API Client Library for Python:** Justification: Required for interacting with the Google Business Profile API to search for businesses and retrieve profile data securely and efficiently.
*   **Firecrawl API Client:** Justification: To crawl website content provided by users, enabling the extraction of business details. <mcreference link="https://www.firecrawl.dev/" index="0">0</mcreference>
*   **LLM for Data Extraction (e.g., OpenAI API with GPT models):** Justification: To process crawled website content from Firecrawl and extract structured business information (name, address, phone, services, hours), improving the accuracy of auto-filled data.

## 3. System Architecture & Component Design

**High-Level System Diagram (Mermaid Syntax):**

```mermaid
graph TD
    A[Vercel Frontend (v0 App)] -- HTTPS/API Calls --> B(FastAPI Backend on Render.com);
    B -- Interacts with --> C{Stripe API Services};
    B -- Stores/Retrieves Data --> D[PostgreSQL Database on Render.com];
    B -- Uses for Caching/Task Brokering --> E[Redis on Render.com];
    B -- Publishes Tasks --> F[Celery Workers on Render.com];
    F -- Processes Tasks (e.g., Stripe Webhooks) --> B;
    C -- Sends Webhooks --> B;
    B -- Interacts with --> G{Google Business Profile API};
    B -- Interacts with --> H{Firecrawl API};
    H -- Crawled Data --> B;
    B -- Sends Data for Extraction --> I{LLM (e.g., OpenAI API)};
    I -- Extracted Info --> B;

    subgraph Render.com Infrastructure
        B
        D
        E
        F
    end
    subgraph External Services
        C
        G
        H
        I
    end
```

**Component Breakdown:**

*   **API Gateway (FastAPI Application):**
    *   **Purpose:** The main entry point for all client requests. Handles HTTP requests, routing, request validation, and response formatting.
    *   **Responsibilities:** Expose RESTful API endpoints, implement business logic for user management, AI agent configuration, call handling, and payment interactions. Orchestrate communication with other services (Database, Stripe, Celery).
*   **Core Application Service:**
    *   **Purpose:** Contains the primary business logic of AICallGO, not directly tied to web request handling.
    *   **Responsibilities:** Manage AI agent configurations, process call data, implement rules for call forwarding and message taking based on user settings.
*   **Authentication Service:**
    *   **Purpose:** Manages user authentication and authorization.
    *   **Responsibilities:** Handle user registration (email/password, Google OAuth), login, password reset, and JWT generation/validation. Secure API endpoints based on user roles and permissions.
*   **Stripe Payment Service:**
    *   **Purpose:** Integrates with Stripe for all payment-related operations.
    *   **Responsibilities:** Create and manage Stripe customers, handle payment intents for one-time charges, manage subscriptions (creation, cancellation, upgrades/downgrades), process Stripe webhooks securely (e.g., `payment_intent.succeeded`, `invoice.paid`, `customer.subscription.updated`), and update payment status in the local database.
*   **Asynchronous Workers (Celery):**
    *   **Purpose:** Execute background tasks that are time-consuming or do not require immediate response to the user.
    *   **Responsibilities:** Process Stripe webhooks, send email notifications (e.g., welcome emails, password resets, payment confirmations), perform data aggregation or cleanup tasks.
*   **Database (PostgreSQL on Render.com):**
    *   **Purpose:** Persistent storage for all application data.
    *   **Responsibilities:** Store user account information, business profiles, AI agent configurations, call logs, message transcripts, Stripe customer IDs, subscription details, and transaction records.
*   **Business Data Acquisition Service (formerly Google Business Profile Service):**
    *   **Purpose:** Integrates with Google Business Profile API and Firecrawl/LLM to fetch, crawl, and parse business information for auto-fill during onboarding.
    *   **Responsibilities:** 
        *   Provide an endpoint for the frontend to search for businesses by name via Google Business Profile API.
        *   Fetch business details (name, overview, address, phone, core services, hours) from the selected Google Business Profile.
        *   Accept a website URL, use Firecrawl API to crawl its content. <mcreference link="https://www.firecrawl.dev/" index="0">0</mcreference>
        *   Send crawled content to an LLM (e.g., OpenAI) with specific prompts to extract structured business information (name, address, phone, services, hours).
        *   Store and return the extracted information.
*   **Vercel Frontend Integration (CORS & API Contract):**
    *   **Purpose:** Enable secure and efficient communication with the frontend application.
    *   **Responsibilities:** Implement CORS policies in FastAPI to allow requests from the Vercel domain. Adhere to a clearly defined API contract (OpenAPI specification) for request/response formats.

## 4. Data Structure Design

**Database Schema (SQL-like):**

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NULL, -- Nullable for OAuth users
    google_id VARCHAR(255) UNIQUE NULL, -- For Google OAuth
    full_name VARCHAR(255) NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    stripe_customer_id VARCHAR(255) UNIQUE NULL
);

CREATE TABLE businesses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    business_name VARCHAR(255) NOT NULL,
    industry VARCHAR(255) NULL,
    google_business_profile_id VARCHAR(255) NULL,
    google_business_profile_raw_json JSONB NULL, -- Store raw response from Google API
    website_url VARCHAR(255) NULL,
    website_parsed_data_json JSONB NULL, -- Store parsed data from website URL
    business_overview TEXT NULL,
    primary_address_street VARCHAR(255) NULL,
    primary_address_city VARCHAR(100) NULL,
    primary_address_state VARCHAR(50) NULL,
    primary_address_zip_code VARCHAR(20) NULL,
    primary_business_phone_number VARCHAR(30) NULL, -- This is the number AICallGO will answer for
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE business_hours (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    day_of_week INTEGER NOT NULL, -- 0 for Sunday, 1 for Monday, ..., 6 for Saturday
    open_time TIME NULL,
    close_time TIME NULL,
    is_closed BOOLEAN DEFAULT FALSE, -- True if closed on this day
    UNIQUE (business_id, day_of_week)
);

CREATE TABLE core_services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    service_name VARCHAR(255) NOT NULL,
    description TEXT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ai_agent_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE UNIQUE,
    greeting_message TEXT NULL, -- e.g., "Thank you for calling [Business Name], how can I help you?"
    message_taking_preference JSONB NULL, -- { "caller_name_required": true, "caller_reason_required": false }
    voicemail_instructions TEXT NULL,
    call_forwarding_number VARCHAR(30) NULL,
    call_forwarding_enabled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE custom_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ai_agent_configuration_id UUID NOT NULL REFERENCES ai_agent_configurations(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    expected_answer_type VARCHAR(50) DEFAULT 'text', -- e.g., text, number, date, yes_no
    is_required BOOLEAN DEFAULT FALSE,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE call_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    caller_phone_number VARCHAR(30) NOT NULL,
    call_start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    call_end_time TIMESTAMP WITH TIME ZONE NULL,
    call_duration_seconds INTEGER NULL,
    call_status VARCHAR(50) NOT NULL, -- e.g., answered_by_ai, forwarded, missed, voicemail
    ai_summary TEXT NULL,
    full_transcript TEXT NULL,
    recording_url VARCHAR(255) NULL, -- If call recording is implemented
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE call_log_answers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_log_id UUID NOT NULL REFERENCES call_logs(id) ON DELETE CASCADE,
    question_asked TEXT NOT NULL, -- Could be a standard question or a custom_question.question_text
    answer_provided TEXT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Stripe Related Tables
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE, -- Assuming one active subscription per user
    stripe_subscription_id VARCHAR(255) UNIQUE NOT NULL,
    stripe_plan_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL, -- e.g., active, trialing, past_due, canceled, unpaid
    current_period_start TIMESTAMP WITH TIME ZONE NULL,
    current_period_end TIMESTAMP WITH TIME ZONE NULL,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stripe_invoice_id VARCHAR(255) UNIQUE NOT NULL,
    stripe_subscription_id VARCHAR(255) NULL REFERENCES subscriptions(stripe_subscription_id),
    amount_paid INTEGER NULL, -- in cents
    amount_due INTEGER NULL, -- in cents
    currency VARCHAR(10) NOT NULL,
    status VARCHAR(50) NOT NULL, -- e.g., paid, open, void, uncollectible
    hosted_invoice_url VARCHAR(255) NULL,
    invoice_pdf_url VARCHAR(255) NULL,
    due_date TIMESTAMP WITH TIME ZONE NULL,
    paid_at TIMESTAMP WITH TIME ZONE NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP -- Stripe's created timestamp for the invoice
);

CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stripe_product_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE prices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stripe_price_id VARCHAR(255) UNIQUE NOT NULL,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL, -- e.g., one_time, recurring
    unit_amount INTEGER NOT NULL, -- in cents
    currency VARCHAR(10) NOT NULL,
    recurring_interval VARCHAR(50) NULL, -- e.g., month, year, week, day (if type is recurring)
    recurring_interval_count INTEGER NULL, -- (if type is recurring)
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_businesses_user_id ON businesses(user_id);
CREATE INDEX idx_call_logs_business_id ON call_logs(business_id);
CREATE INDEX idx_call_logs_caller_phone_number ON call_logs(caller_phone_number);
CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_stripe_subscription_id ON subscriptions(stripe_subscription_id);
CREATE INDEX idx_invoices_user_id ON invoices(user_id);
CREATE INDEX idx_invoices_stripe_invoice_id ON invoices(stripe_invoice_id);
```

**Application-Layer Data Models (Pydantic `BaseModel`):**

```python
from pydantic import BaseModel, EmailStr, HttpUrl
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, time

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: UUID
    is_active: bool = True
    is_superuser: bool = False
    stripe_customer_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class BusinessBase(BaseModel):
    business_name: str
    industry: Optional[str] = None
    google_business_profile_id: Optional[str] = None
    google_business_profile_raw_json: Optional[Dict[str, Any]] = None
    website_url: Optional[HttpUrl] = None
    website_parsed_data_json: Optional[Dict[str, Any]] = None
    business_overview: Optional[str] = None
    primary_address_street: Optional[str] = None
    primary_address_city: Optional[str] = None
    primary_address_state: Optional[str] = None
    primary_address_zip_code: Optional[str] = None
    primary_business_phone_number: Optional[str] = None # This is the number AICallGO will answer for

class BusinessCreate(BusinessBase):
    pass

class Business(BusinessBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class BusinessHour(BaseModel):
    day_of_week: int # 0 for Sunday, ..., 6 for Saturday
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    is_closed: bool = False

    class Config:
        orm_mode = True

class CoreService(BaseModel):
    service_name: str
    description: Optional[str] = None

    class Config:
        orm_mode = True

class CustomQuestion(BaseModel):
    question_text: str
    expected_answer_type: str = 'text'
    is_required: bool = False
    display_order: int = 0

    class Config:
        orm_mode = True

class AIAgentConfigurationBase(BaseModel):
    greeting_message: Optional[str] = None
    message_taking_preference: Optional[Dict[str, Any]] = None
    voicemail_instructions: Optional[str] = None
    call_forwarding_number: Optional[str] = None
    call_forwarding_enabled: bool = False

class AIAgentConfigurationCreate(AIAgentConfigurationBase):
    custom_questions: Optional[List[CustomQuestion]] = []
    business_hours: Optional[List[BusinessHour]] = []
    core_services: Optional[List[CoreService]] = []

class AIAgentConfiguration(AIAgentConfigurationBase):
    id: UUID
    business_id: UUID
    custom_questions: List[CustomQuestion] = []
    business_hours: List[BusinessHour] = []
    core_services: List[CoreService] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

# Stripe Models
class Product(BaseModel):
    id: UUID
    stripe_product_id: str
    name: str
    description: Optional[str] = None
    is_active: bool

    class Config:
        orm_mode = True

class Price(BaseModel):
    id: UUID
    stripe_price_id: str
    product_id: UUID
    type: str # one_time, recurring
    unit_amount: int # cents
    currency: str
    recurring_interval: Optional[str] = None
    recurring_interval_count: Optional[int] = None
    is_active: bool

    class Config:
        orm_mode = True

class Subscription(BaseModel):
    id: UUID
    user_id: UUID
    stripe_subscription_id: str
    stripe_plan_id: str # Corresponds to a Price ID
    status: str
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool

    class Config:
        orm_mode = True

class CreateCheckoutSessionRequest(BaseModel):
    price_id: str # Stripe Price ID
    success_url: HttpUrl
    cancel_url: HttpUrl

class CreateCheckoutSessionResponse(BaseModel):
    session_id: str
    url: HttpUrl

class CreatePortalSessionResponse(BaseModel):
    url: HttpUrl

class StripeWebhookEvent(BaseModel):
    id: str
    type: str # e.g., "payment_intent.succeeded"
    data: Dict[str, Any]
    # ... other relevant fields from Stripe event object

```

## 5. API Endpoint Design

This section outlines the API endpoints required for Phase 1. All endpoints should be protected as necessary (e.g., JWT authentication). Standard success (200, 201, 204) and error (400, 401, 403, 404, 500) responses apply.

### 5.1 Authentication Endpoints

*   **`POST /auth/register`**
    *   Description: Register a new user with email and password.
    *   Request Body: `UserCreate` (email, password, full_name)
    *   Response Body: `User` (user details), JWT tokens.
    *   Notes: Handles new user creation. If pre-login onboarding data is passed, it should be processed here or in a subsequent onboarding step.
*   **`POST /auth/login`**
    *   Description: Log in an existing user.
    *   Request Body: `OAuth2PasswordRequestForm` (username=email, password)
    *   Response Body: `{ "access_token": str, "token_type": "bearer" }`
*   **`POST /auth/google`**
    *   Description: Handles Google OAuth2 authentication (this might be a callback URL).
    *   Request: Depends on OAuth library (e.g., code, state from Google redirect).
    *   Response: JWT tokens.
    *   Notes: Creates or logs in a user based on Google profile email.
*   **`POST /auth/forgot-password`**
    *   Description: Initiate password reset process.
    *   Request Body: `{ "email": EmailStr }`
    *   Response: 202 Accepted (email will be sent if user exists).
    *   Notes: Triggers a Celery task to send a password reset email.
*   **`POST /auth/reset-password`**
    *   Description: Reset password using a token from email.
    *   Request Body: `{ "token": str, "new_password": str }`
    *   Response: 200 OK.
*   **`POST /auth/refresh-token`**
    *   Description: Obtain a new access token using a refresh token.
    *   Request Body: `{ "refresh_token": str }` (or handled by OAuth2PasswordBearer with refresh token in header/cookie)
    *   Response Body: `{ "access_token": str, "token_type": "bearer" }`

### 5.2 User Account Endpoints (Authenticated)

*   **`GET /users/me`**
    *   Description: Get current authenticated user's details.
    *   Response Body: `User`
*   **`PUT /users/me`**
    *   Description: Update current user's profile (e.g., full_name).
    *   Request Body: `UserUpdate` (subset of `User` fields, e.g., `full_name: Optional[str] = None`)
    *   Response Body: `User`
*   **`PUT /users/me/password`**
    *   Description: Change current user's password (when logged in).
    *   Request Body: `{ "current_password": str, "new_password": str }`
    *   Response: 200 OK.

### 5.3 Business & AI Agent Configuration Endpoints (Authenticated)

*   **`POST /businesses`** (or `PUT /businesses/me` if only one business per user)
    *   Description: Create or update the user's business profile and initial AI agent setup. Handles data from onboarding.
    *   Request Body: `BusinessCreateWithAgentConfig` (combining `BusinessCreate` and initial parts of `AIAgentConfigurationCreate`, including pre-login data if available).
    *   Response Body: `Business` (with nested `AIAgentConfiguration`).
*   **`GET /businesses/me`**
    *   Description: Get the current user's business profile and AI agent configuration.
    *   Response Body: `Business` (with nested `AIAgentConfiguration`).
*   **`PUT /businesses/me/ai-agent`**
    *   Description: Update the AI agent configuration (greeting, hours, questions, etc.).
    *   Request Body: `AIAgentConfigurationUpdate` (Pydantic model for updating agent settings).
    *   Response Body: `AIAgentConfiguration`.
*   **`GET /businesses/search-gmb?query={search_term}`**
    *   Description: Search Google Business Profile for a business.
    *   Response Body: `List[GMBSearchResult]` (e.g., `[{ "place_id": str, "name": str, "address": str }]`).
*   **`POST /businesses/fetch-gmb-details`**
    *   Description: Fetch detailed information for a selected Google Business Profile ID.
    *   Request Body: `{ "place_id": str }`
    *   Response Body: `BusinessProfileDataFromGMB` (parsed GMB data, e.g., name, address, phone, hours, services, overview).
*   **`POST /businesses/crawl-website`**
    *   Description: Submit a website URL for crawling and data extraction.
    *   Request Body: `{ "url": HttpUrl }`
    *   Response: 202 Accepted (crawling and parsing will be done asynchronously by a Celery task).
    *   Alternative: Could be synchronous if fast, or provide a task ID to check status.
    *   Response Body (if sync or after polling): `WebsiteParsedData` (parsed website data, e.g., name, address, phone, services, overview).

### 5.4 AI Agent Interaction Endpoints (Authenticated)

*   **`POST /ai-agent/test-interaction`**
    *   Description: Simulate an interaction with the configured AI agent (for "Talk to Rosie" feature).
    *   Request Body: `{ "caller_input": Optional[str] = None, "session_id": Optional[str] = None }` (session_id to maintain conversation context if multi-turn).
    *   Response Body: `{ "ai_response": str, "session_id": Optional[str] = None, "interaction_complete": bool }`.
    *   Notes: This endpoint would use the current business's AI agent configuration to generate a response. The exact mechanism (scripted, simple NLU, LLM call) depends on the AI Voice Interaction service chosen.
*   **`POST /ai-agent/launch`**
    *   Description: Mark the AI agent as fully configured and ready to take calls ("Launch Rosie").
    *   Request Body: (Potentially empty, or final confirmation flags)
    *   Response: 200 OK.
    *   Notes: Backend actions might include: validating configuration completeness, activating the assigned phone number with the Telephony Provider, setting an 'active' flag on the business/agent.

### 5.5 Call Log Endpoints (Authenticated)

*   **`GET /call-logs`**
    *   Description: List call logs for the user's business with pagination and filtering.
    *   Query Params: `page: int = 1`, `size: int = 20`, `start_date: Optional[date]`, `end_date: Optional[date]`, `status: Optional[str]`.
    *   Response Body: `Page[CallLogSummary]` (Paginated list of call log summaries).
*   **`GET /call-logs/{log_id}`**
    *   Description: Get detailed information for a specific call log.
    *   Response Body: `CallLogDetail` (includes full transcript, answers to questions, etc.).

### 5.6 Billing & Subscription Endpoints (Authenticated)

*   **`GET /billing/products-prices`**
    *   Description: List available subscription products and their prices (fetched from DB, synced from Stripe).
    *   Response Body: `List[ProductWithPrices]` (Product model with a list of its associated Price models).
*   **`POST /billing/create-checkout-session`**
    *   Description: Create a Stripe Checkout session for a new subscription.
    *   Request Body: `CreateCheckoutSessionRequest` (price_id, success_url, cancel_url).
    *   Response Body: `{ "session_id": str, "checkout_url": HttpUrl }` (Stripe Checkout session ID and URL).
*   **`POST /billing/create-portal-session`**
    *   Description: Create a Stripe Customer Portal session to manage existing subscription.
    *   Request Body: `{ "return_url": HttpUrl }`
    *   Response Body: `{ "portal_url": HttpUrl }` (Stripe Customer Portal URL).
*   **`GET /billing/subscription`**
    *   Description: View current user's active subscription details.
    *   Response Body: `Optional[Subscription]`.
*   **`GET /billing/invoices`**
    *   Description: List user's invoices from Stripe with pagination.
    *   Query Params: `page: int = 1`, `size: int = 10`.
    *   Response Body: `Page[Invoice]`.

### 5.7 Webhook Endpoints (Public, but secured with signature verification)

*   **`POST /webhooks/stripe`**
    *   Description: Receive and process webhooks from Stripe.
    *   Request Body: Stripe Event object.
    *   Response: 200 OK (or 202 Accepted if offloaded to Celery immediately).
    *   Notes: Requires Stripe signature verification. Triggers Celery tasks to handle events (e.g., `invoice.paid`, `customer.subscription.updated`).
*   **`POST /webhooks/telephony`**
    *   Description: Receive webhooks from the Telephony Service (e.g., incoming call, call status changes).
    *   Request Body: Event object specific to the chosen Telephony Provider.
    *   Response: Instructions to Telephony Provider (e.g., TwiML for Twilio) or 200 OK.
    *   Notes: This is a critical endpoint for live call handling. It will interact with the AI Voice Interaction Service.

## 6. Implementation Guidelines & Best Practices

**Project Structure (Recommended):**

```
/app
├── alembic/                  # Alembic migration scripts
├── alembic.ini               # Alembic configuration
├── core/
│   ├── config.py             # Pydantic Settings for environment variables
│   └── security.py           # Password hashing, JWT creation/validation
├── crud/
│   ├── base.py               # Base CRUD operations
│   ├── crud_user.py
│   ├── crud_business.py
│   └── crud_stripe.py        # CRUD for local Stripe-related data
├── db/
│   ├── base_class.py         # SQLAlchemy Base
│   ├── database.py           # SQLAlchemy engine and session setup
│   └── init_db.py            # (Optional) Initial database data seeding
├── models/
│   ├── user.py
│   ├── business.py
│   ├── ai_agent.py
│   ├── call_log.py
│   └── stripe_models.py      # Local representations of Stripe objects (Subscription, Invoice)
├── schemas/
│   ├── user.py               # Pydantic schemas for User
│   ├── business.py
│   ├── ai_agent.py
│   ├── call_log.py
│   ├── token.py              # Schema for JWT token
│   └── stripe_schemas.py     # Pydantic schemas for Stripe requests/responses
├── services/
│   ├── ai_call_handling_service.py # Logic for AI call interactions (placeholder for future)
│   ├── stripe_service.py     # Business logic for Stripe interactions (creating sessions, etc.)
│   ├── business_data_acquisition_service.py # Logic for Google Business Profile, Firecrawl, and LLM data extraction
│   └── llm_service.py          # Service for interacting with LLM APIs
├── clients/
│   └── firecrawl_client.py   # Client for interacting with Firecrawl API
├── api/
│   ├── deps.py               # FastAPI dependencies (e.g., get_current_user)
│   └── v1/
│       ├── endpoints/
│       │   ├── auth.py
│       │   ├── users.py
│       │   ├── businesses.py
│       │   ├── agent_configs.py
│       │   └── stripe_webhooks.py
│       │   └── stripe_payments.py
│       └── api.py            # Main API router for v1
├── tasks/
│   ├── celery_app.py         # Celery application instance
│   └── stripe_tasks.py       # Celery tasks for Stripe webhook processing
├── tests/
│   ├── conftest.py           # Pytest fixtures
│   ├── utils/
│   └── api/
│       └── v1/
├── .env.example              # Example environment variables
├── Dockerfile
├── main.py                   # FastAPI application entry point
├── prestart.sh               # Script to run before starting app (e.g., run migrations)
├── requirements.txt
└── README.md
```

**Configuration Management:**

*   Use `.env` files for local development, loaded into a Pydantic `Settings` model (e.g., `app/core/config.py`).
*   Stripe API keys (secret and publishable), database URLs, JWT secrets, and other sensitive information will be managed as environment variables.
*   On Render.com, these will be set as environment variables in the service configuration, ensuring they are not hardcoded in the repository.
*   API keys for Google Business Profile, Firecrawl, and the chosen LLM provider must also be managed as secure environment variables.

**Testing Strategy:**

*   **Unit Tests:** (`pytest`) Focus on individual functions and classes (e.g., CRUD operations, utility functions, schema validation). Mock external dependencies like database calls and Stripe API calls.
*   **Integration Tests:** (`pytest`, `httpx`) Test interactions between components, such as API endpoints calling service layers and interacting with a test database. Test Stripe webhook handlers by simulating webhook events.
*   **E2E Tests:** (Optional for backend, more frontend-focused) Can be implemented to test full user flows if necessary, but primary focus for backend is unit and integration.
*   **Libraries:** `pytest` for test framework, `pytest-asyncio` for async code, `httpx` for testing API endpoints, `factory_boy` for generating test data, `freezegun` for time-sensitive tests.
*   **Stripe Specific Tests:**
    *   Test webhook signature verification logic.
    *   Test processing of key Stripe events (`payment_intent.succeeded`, `invoice.paid`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`). Ensure database updates correctly reflect these events.
    *   Mock Stripe API calls during tests to avoid actual charges.
*   **Code Coverage:** Aim for a minimum of 85% code coverage, tracked using tools like `coverage.py`.

**Logging Strategy:**

*   Implement structured logging (e.g., using `structlog` or standard Python logging configured for JSON output).
*   **INFO:** Log significant application lifecycle events (e.g., application start/stop), successful API requests (method, path, status code, latency), successful Stripe interactions (e.g., checkout session created, webhook received).
*   **WARN:** Log recoverable errors or unexpected situations that don't halt execution (e.g., failed validation attempt, retriable Stripe API error).
*   **ERROR:** Log unrecoverable errors, exceptions, failed Stripe API calls, and critical failures in webhook processing. Include stack traces and relevant context (e.g., request ID, user ID if available).
*   Log Stripe API request IDs and webhook event IDs for easier debugging and correlation with Stripe dashboard logs.
*   Ensure logs are easily searchable and filterable on Render.com's logging platform.

**Deployment (Render.com):**

*   **Containerization:** The FastAPI application will be containerized using Docker. The `Dockerfile` will define the environment, copy application code, install dependencies, and specify the command to run the application (e.g., `uvicorn main:app --host 0.0.0.0 --port $PORT`).
*   **Render Services:**
    *   **Web Service:** For the FastAPI application. Configured to build from the Git repository and run the Docker container. Environment variables (Stripe keys, DB URL, JWT secret, Vercel frontend URL for CORS) will be set here.
    *   **Background Worker:** For Celery workers. Configured similarly to the web service but with a different start command (e.g., `celery -A app.tasks.celery_app worker -l info`).
    *   **Managed PostgreSQL Database:** Provisioned directly on Render.com. The connection URL will be provided as an environment variable to the web service and background worker.
    *   **Managed Redis Instance:** Provisioned on Render.com. The connection URL will be provided as an environment variable for caching and Celery broker.
*   **Pre-deploy Script:** A `prestart.sh` script (or Render build script commands) will run database migrations (Alembic) before the application starts.
*   **Auto-scaling:** Configure auto-scaling rules for the web service based on CPU/memory usage or request load to handle varying traffic.
*   **Monitoring & Alerting:** Utilize Render.com's built-in monitoring for resource usage, request metrics, and logs. Set up alerts for critical errors or performance degradation.
*   **Health Checks:** Implement a `/health` endpoint in FastAPI that Render.com can use to verify application health.

**Google Business Profile Integration Guidelines:**

*   **API Key Management:** Store the Google API Key securely as an environment variable (e.g., `GOOGLE_API_KEY`) and load it via the Pydantic `Settings` model. Never hardcode it.
*   **Client Library:** Utilize the official Google API Client Library for Python for robust interaction with the Google Business Profile API.
*   **Dynamic Search:** Implement the business name search to be dynamic, providing suggestions as the user types. Consider debouncing requests to avoid excessive API calls.
*   **Data Parsing:** Carefully parse the response from Google API to extract relevant fields (Business Name, Overview, Address, Phone, Core Services, Hours). Store the raw JSON response in the `businesses.google_business_profile_raw_json` field for auditing or future enhancements.
*   **Error Handling (Google API):** Implement comprehensive error handling for Google API calls (e.g., API rate limits, invalid requests, no profile found). Provide clear feedback to the user.
*   **Rate Limiting (Google API):** Be mindful of Google API rate limits. Implement caching for search results where appropriate if high traffic is anticipated for the same queries.
*   **User Consent & Data Privacy (Google API):** Ensure compliance with Google's API terms of service and data privacy best practices when handling user data obtained from Google.

**Firecrawl Integration Guidelines (for Website Crawling):**

*   **API Key Management:** Store the Firecrawl API Key securely as an environment variable (e.g., `FIRECRAWL_API_KEY`) and load it via the Pydantic `Settings` model.
*   **Client Usage:** Implement a client (e.g., `app/clients/firecrawl_client.py`) to interact with the Firecrawl API (`https://www.firecrawl.dev/`). This client will handle making requests to Firecrawl's `/crawl` or `/scrape` endpoints.
*   **Crawling Strategy:**
    *   Initially, crawl the main URL provided by the user.
    *   If initial results are insufficient, consider strategies to find and crawl specific pages like "Contact Us", "About Us", or "Services" if Firecrawl supports targeted crawling or if subsequent LLM processing can identify these links from the main crawl data.
*   **Data Handling:** Firecrawl will return structured data (e.g., markdown or JSON containing main content, metadata). This data will be passed to the LLM for information extraction. Store the raw crawled data if necessary for debugging or reprocessing, potentially in a temporary cache or a designated field if small enough.
*   **Error Handling:** Implement robust error handling for Firecrawl API calls (e.g., invalid URL, crawl failures, API errors). Provide clear feedback or fallback mechanisms.
*   **Rate Limiting & Cost:** Be mindful of Firecrawl API rate limits and associated costs. Implement caching of crawled data for a short period if users might re-request the same URL.

**LLM for Data Extraction Guidelines:**

*   **API Key Management:** Store the LLM provider's API Key (e.g., OpenAI API Key) securely as an environment variable (e.g., `OPENAI_API_KEY`) and load it via the Pydantic `Settings` model.
*   **Client Usage:** Utilize an LLM service (e.g., `app/services/llm_service.py`) with the appropriate client library (e.g., OpenAI's Python library) to send requests to the LLM.
*   **Prompt Engineering:**
    *   Design clear and specific prompts to instruct the LLM to extract required business information (Business Name, Overview/Description, Full Address, Phone Number, Core Services, Business Hours) from the content provided by Firecrawl.
    *   Specify the desired output format (e.g., JSON) to simplify parsing.
    *   Example prompt fragment: "Extract the following business details from the provided website content: business name, full address, primary phone number, a list of services offered, and operating hours. Format the output as a JSON object. If some information is not found, use null for its value."
*   **Data Validation & Structuring:** The `BusinessDataAcquisitionService` will be responsible for taking the LLM's JSON output and mapping it to the `BusinessBase` Pydantic model. Implement validation for extracted data (e.g., address format, phone number format if possible).
*   **Content Chunking:** If crawled website content is very large, it may need to be chunked to fit within the LLM's context window. Develop a strategy for this if necessary.
*   **Cost Management:** Be aware of LLM API token usage and costs. Optimize prompts and select models that balance capability with cost-effectiveness.
*   **Error Handling & Fallbacks:** Implement error handling for LLM API calls (e.g., rate limits, content filtering, API errors). If the LLM fails to extract data or provides poor quality results, have a fallback (e.g., allowing manual entry, indicating data couldn't be auto-filled).
*   **Data Storage:** Store the LLM-extracted and structured data in the `businesses.website_parsed_data_json` field.

**Stripe Integration Guidelines:**

*   **Client-Side Tokenization:** The frontend (Vercel v0 app) will use Stripe.js or Stripe Elements to collect payment information directly from the user and send a payment method ID or token to the backend. The backend will **never** handle raw card details.
*   **Webhook Handling:**
    *   Implement a dedicated webhook endpoint (e.g., `/api/v1/stripe/webhooks`).
    *   **Verify Signatures:** CRITICAL: Always verify the `Stripe-Signature` header to ensure webhooks are genuinely from Stripe. Use the webhook signing secret provided by Stripe.
    *   **Idempotency:** Design webhook handlers to be idempotent. Process events only once, even if Stripe sends them multiple times (e.g., by checking if an event ID has already been processed).
    *   **Asynchronous Processing:** Process webhooks asynchronously using Celery tasks to avoid timing out Stripe's requests and to handle potential retries gracefully.
    *   **Respond Quickly:** Respond to Stripe with a `200 OK` status as soon as the webhook is received and queued for processing, before actual business logic is executed.
    *   **Events to Handle:** `payment_intent.succeeded`, `payment_intent.payment_failed`, `invoice.paid`, `invoice.payment_failed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `checkout.session.completed`.
*   **Metadata Storage:** Store only necessary Stripe identifiers (e.g., `stripe_customer_id`, `stripe_subscription_id`, `stripe_price_id`) in the local database. Avoid storing sensitive payment data.
*   **Error Handling:** Implement robust error handling for Stripe API calls and webhook processing. Log errors comprehensively.
*   **Customer Portal:** Utilize Stripe Customer Portal to allow users to manage their subscriptions, payment methods, and view billing history, reducing development overhead.

**Frontend Integration (Vercel v0 App):**

*   **CORS Configuration:** Configure FastAPI's `CORSMiddleware` to allow requests specifically from the Vercel frontend domain(s). Specify allowed origins, methods, and headers.
    ```python
    # Example in main.py
    from fastapi.middleware.cors import CORSMiddleware

    origins = [
        "https://your-vercel-frontend-domain.vercel.app", # Production frontend
        "http://localhost:3000", # Local frontend development
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    ```
*   **OpenAPI Documentation:** FastAPI automatically generates OpenAPI (Swagger) documentation (e.g., at `/docs` and `/redoc`). Provide this to the frontend team for clear API contract understanding.
*   **API Responses:** Ensure all API responses are JSON-compliant. Use standard HTTP status codes to indicate success or failure. Provide clear error messages in a consistent format for frontend handling.
    ```json
    // Example error response
    {
        "detail": "User with this email already exists."
    }
    ```
*   **Authentication Flow:** The frontend will handle redirecting to Google for OAuth or sending email/password for login. Upon successful authentication, the backend will return a JWT, which the frontend will store securely (e.g., `localStorage` or `HttpOnly` cookie if applicable for web) and include in the `Authorization` header (e.g., `Bearer <token>`) for subsequent authenticated requests.