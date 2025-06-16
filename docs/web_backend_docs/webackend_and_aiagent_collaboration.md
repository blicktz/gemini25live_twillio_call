Of course. It's a wise decision to solidify the architecture before development begins. A clear document ensures both teams are aligned, understand their responsibilities, and build their respective applications in a way that allows them to integrate seamlessly.  
Here is a complete best practice document for your teams based on our discussion.

## **Best Practices & Guidelines: Two-Service Decoupled Architecture**

**Document Version:** 1.0 **Date:** June 11, 2025 **Audience:** Web Backend Team, AI Agent Team

### **1\. Executive Summary**

This document outlines the official architectural direction for the Call Answering AI project. We will be implementing a **decoupled, two-service architecture**.

* **Service 1: The Web Backend:** A FastAPI application responsible for all user-facing operations, including account management, billing, call log display, and user authentication. **This service is the source of truth for all user data.**  
* **Service 2: The AI Agent:** A separate FastAPI application responsible for the real-time processing of phone calls, audio streaming, transcription, and interaction with the Gemini model.

This approach was chosen over a monolithic design to achieve **independent scalability**, **improved fault isolation**, and **focused development**. The AI Agent, being compute-heavy, can be scaled independently of the standard web-serving needs of the Web Backend, ensuring that high call volume will not impact a user's ability to access their account.

### **2\. Core Architectural Principles**

1. **Separate Services, Separate Concerns:** The Web Backend handles user data and business logic. The AI Agent handles call processing. Each service should be an expert in its domain and nothing more.  
2. **Database Per Service:** Each service will have its own dedicated database. The Web Backend's database contains all user information (accounts, billing, etc.). The AI Agent's database contains its own operational data (e.g., call processing state, logs, cached data). **There will be no direct database-level access between services.**  
3. **Communication via Internal API:** All communication from the AI Agent to the Web Backend will occur through a well-defined, secure, internal-only REST API.  
4. **Clear Ownership:**  
   * The **Web Backend Team** owns the user data, the internal API's definition and implementation, and service-to-service authentication.  
   * The **AI Agent Team** owns the call processing logic and is the consumer of the internal API. It is responsible for implementing resiliency patterns (caching, retries).

### **3\. The Internal API: The Contract Between Services**

The stability and clarity of this API are paramount to the project's success.

#### **3.1 API Design and Contract**

* **Responsibility:** The **Web Backend Team** is responsible for designing, building, and documenting this API.  
* **Principle of Least Privilege:** The API must only expose the absolute minimum data required for the AI Agent to function. Do not expose the entire User database model.  
  * **Example (Good):** An endpoint GET /internal/api/v1/users/lookup?phone\_number=+15551234567 returns:  
    `{`  
      `"user_id": "usr_abc123",`  
      `"is_active": true,`  
      `"greeting_name": "John",`  
      `"timezone": "America/New_York",`  
      `"plan_tier": "premium"`  
    `}`

  * **Example (Bad):** The endpoint returns the user's email, hashed password, billing ID, signup date, etc.  
* **Data Transfer Objects (DTOs):** Use Pydantic models in the Web Backend to strictly define the API response structure, ensuring no sensitive data is accidentally leaked.  
* **OpenAPI Specification:** The Web Backend will automatically generate an openapi.json schema. This schema is the definitive contract that the AI Agent team will use for development and testing.

#### **3.2 Versioning**

The API must be versioned to allow for future changes without breaking the AI Agent. Use URL-based versioning (e.g., /internal/api/v1/...). Any breaking change requires a new version (/v2/).

### **4\. Security: Service-to-Service Authentication**

The AI Agent must not be able to anonymously query the Web Backend.

* **Requirement:** All internal API endpoints must be protected.  
* **Recommended Method: API Keys**  
  1. The **Web Backend Team** will generate a strong, unique API key for the AI Agent.  
  2. This key will be securely stored in the AI Agent's environment via a secrets manager (e.g., Doppler, AWS Secrets Manager, HashiCorp Vault). **Do not hardcode keys.**  
  3. The **AI Agent Team** will ensure their HTTP client includes this key in a request header (e.g., X-API-Key) with every call.  
  4. The **Web Backend Team** will implement a FastAPI dependency to validate this key on all /internal/ routes. Unauthorized requests must be rejected with a 401 Unauthorized status.  
* **Future-Proofing:** For enhanced security as the system grows, we may evolve to use the OAuth 2.0 Client Credentials flow with short-lived JWTs.

### **5\. Data Management & Resiliency (AI Agent Responsibilities)**

The AI Agent must be designed to be efficient and robust, even if the Web Backend is slow or temporarily unavailable.

#### **5.1 Caching Strategy**

To minimize latency and reduce load on the Web Backend, the AI Agent must cache the user data it retrieves.

* **Technology:** A dedicated **Redis** instance is the recommended caching solution.  
* **Workflow:**  
  1. When a call arrives, the Agent first checks its local Redis cache for the required user info.  
  2. **Cache Hit:** If data is present, use it immediately.  
  3. **Cache Miss:** If data is not present, call the Web Backend's internal API.  
  4. Upon receiving a successful response, store the data in Redis with a reasonable **Time-to-Live (TTL)**, such as 5-15 minutes. This ensures that stale data is eventually flushed.

#### **5.2 Designing for Failure**

The AI Agent must handle API failures gracefully.

* **Retries with Exponential Backoff:** If a call to the Web Backend fails (e.g., network error, 5xx status code), do not fail instantly. The agent should retry the request 2-3 times, with an increasing delay between attempts. Use a library like tenacity to implement this.  
* **Circuit Breaker Pattern:** To prevent hammering a failing service, the AI Agent should implement a circuit breaker. After a configured number of consecutive failures, the "circuit opens," and subsequent calls will fail immediately for a cooldown period, giving the Web Backend time to recover. Use a library like pybreaker.  
* **Define a Fallback Strategy:** The **AI Agent Team** must define and implement behavior for when user information cannot be retrieved after all retries. This could be:  
  * Answering with a generic, non-personalized greeting.  
  * Forwarding the call to a default number.  
  * Rejecting the call. This business logic must be clearly defined.

### **6\. Summary of Responsibilities**

| Feature/Component | Owner Team | Key Responsibilities |
| :---- | :---- | :---- |
| **User Accounts & Data** | Web Backend | Own the database schema; ensure data integrity and security. |
| **Internal API** | Web Backend | Define, build, document, and secure the internal API. |
| **API Consumption** | AI Agent | Make calls to the internal API; handle responses. |
| **Service Authentication** | Web Backend | Generate and validate API keys. |
| **Resiliency Patterns** | AI Agent | Implement caching, retries, and circuit breakers. |
| **Call Processing Logic** | AI Agent | Own the core AI, audio, and transcription logic. |
| **Public Web App/UI** | Web Backend | Build and serve the user-facing web application. |

By adhering to these guidelines, both teams can work in parallel, building a robust, scalable, and maintainable system.