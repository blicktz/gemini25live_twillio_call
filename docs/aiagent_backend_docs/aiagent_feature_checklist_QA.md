**General Capabilities:*   "must not maintain its own database, the AI agent should be stateless, all necessary data should be retrieved from the web backend"
    *   **Question:** What specific data points will the AI agent need to retrieve from the web backend during a typical call? (e.g., customer history, product information, FAQs, business hours). Understanding the scope of data will be crucial gfor API design.
    *   **Answer:** The AI agent will primarily retrieve configuration data from the `/api/v1/ai-agent/config` endpoint (defined in <mcfile path="docs/web_backend_docs/apidoc/ai_agent.json" name="ai_agent.json"></mcfile>). This includes agent name, prompt templates, custom questions, FAQs, greeting message, and legal disclaimer. It will also retrieve business information (like business name) from the `/api/v1/businesses/me` endpoint (defined in <mcfile path="docs/web_backend_docs/apidoc/businesses.json" name="businesses.json"></mcfile>). While the API docs seem to cover most needs, we will flag any new endpoint requirements as they arise during detailed design.
    *   **Question:** For data retrieval, what are the expected response times from the web backend to ensure a smooth, real-time conversation flow?
    *   **Answer:** Expected response times from the web backend will not exceed a few hundred milliseconds, as both services will be deployed on Render.com, minimizing network latency, and backend processing is mainly database-related.

**Authentication:**
*   "must be able to authenticate with web backend to get information"
    *   **Question:** What authentication mechanism will be used between the AI agent and the web backend? (e.g., API keys, OAuth tokens, JWT). This needs to be defined for security and implementation.
    *   **Answer:** Authentication will be handled via a pre-configured static `WEB_BACKEND_API_KEY`. The AI agent will include this key in its requests to the web backend for verification. If implementing dedicated infrastructure for this proves too complex, we will explore leveraging existing authentication services (those used for front-end web user auth) following best practices for service-to-service authentication.

**Telephony Interaction:**
*   "must be able to pull the call recording for the call from twilio, and save it to a permanent storage, then post the link to the web backend when the call is over"
    *   **Question:** What is the defined "permanent storage"? (The technical stack mentions Google Cloud Storage, but it's good to confirm this specific use case).
    *   **Answer:** Permanent storage for call recordings will be Google Cloud Storage.
    *   **Question:** What is the required format for the call recording? (e.g., mp3, wav).
    *   **Answer:** Call recordings will be stored in their original format as provided by Twilio to maintain simplicity and avoid transcoding.
    *   **Question:** Are there any specific requirements for the naming convention or metadata to be stored with the recording link in the web backend?
    *   **Answer:** The recording filename will include the business name and a datetime timestamp. The link to this recording will be posted to the web backend via the call_logs API (likely a POST to create a new call log entry, schema `CallLogCreate` in <mcfile path="docs/web_backend_docs/apidoc/call_logs.json" name="call_logs.json"></mcfile>). We will assess if the current `CallLogCreate` schema (which includes `recording_url`) is sufficient or if it needs modification for additional metadata.
*   "must be able to follow a pre-configured max time to maintain a call, when the time is up, the call will be ended automatically"
    *   **Question:** When a call is automatically ended due to max time, what message, if any, will the AI agent deliver to the caller before disconnecting? (e.g., "Our call time is now complete. Thank you for calling.")
    *   **Answer:** A message will be delivered to the caller before disconnecting. This message will be statically configurable at the AI agent level via environment variables.

**Agent Customization - Basic:**
*   "must be able to be configured to use a pre-configured Name to refer to the agent herself"
    *   **Question:** How will this configuration be managed? (e.g., via an admin interface in the web backend, a configuration file).
    *   **Answer:** The agent's name will be configured via the `/api/v1/ai-agent/config` endpoint (field `agent_name` in schema `AIAgentConfiguration` from <mcfile path="docs/web_backend_docs/apidoc/ai_agent.json" name="ai_agent.json"></mcfile>).
*   "must be able to be configured to adapt her tone: casual, cheerful, formal"
    *   **Question:** How will these tones be practically defined and implemented in the AI's responses? Will there be specific prompt engineering guidelines or model fine-tuning for each tone?
    *   **Answer:** Agent tones (casual, cheerful, formal) will be implemented as part of the system prompt provided to the AI model. The specific tone will be configurable via environment variables for the AI agent service.
    *   **Question:** Can an SMB owner easily preview or test how these different tones sound or read?
    *   **Answer:** The SMB owner will be able to test the configured tone by calling the AI agent directly after configuration. No separate preview mechanism is planned.
*   "must be able to initiate conversation with caller, without waiting the caller to speak first"
    *   This is clear.
*   "must be able to be configured to use a specific greeting message (including customer business name, name of herself, and preconfigured legal disclaimer)"
    *   **Question:** How will the "customer business name" be dynamically inserted? Will it be fetched from the web backend based on the incoming call number or another identifier?
    *   **Answer:** The customer business name will be fetched from the `/api/v1/businesses/me` endpoint (field `name` in schema `Business` from <mcfile path="docs/web_backend_docs/apidoc/businesses.json" name="businesses.json"></mcfile>).
    *   **Question:** What is the maximum length or complexity anticipated for the legal disclaimer? This might impact delivery and caller experience.
    *   **Answer:** The legal disclaimer will be configured via the `/api/v1/ai-agent/config` endpoint (field `legal_disclaimer_template` in schema `AIAgentConfiguration` from <mcfile path="docs/web_backend_docs/apidoc/ai_agent.json" name="ai_agent.json"></mcfile>). It is expected to be a single sentence, and its length will be managed/limited by the front-end web UI.
*   "must be able to collect caller's name and other up to 5 questions defined by the customer"
    *   **Question:** How will these "up to 5 questions" be configured by the SMB owner? (e.g., through a simple interface in the web backend).
    *   **Answer:** These custom questions will be configured via the `/api/v1/ai-agent/config` endpoint (field `custom_questions` in schema `AIAgentConfiguration` from <mcfile path="docs/web_backend_docs/apidoc/ai_agent.json" name="ai_agent.json"></mcfile>). The AI agent will ask all questions provided by the API; the front-end web UI will enforce any numerical limits (e.g., up to 5).
    *   **Question:** What happens if the caller doesn't want to provide their name or answer these questions? How will the agent handle this gracefully?
    *   **Answer:** The AI agent will ask for the caller's name and the custom questions but will not push if the caller is unwilling to provide answers. It will proceed gracefully.
    *   **Question:** Where will the answers to these questions be stored, and how will they be made accessible to the SMB owner? (e.g., posted to the web backend along with the call transcript).
    *   **Answer:** Answers to these questions will be part of the call conversation and thus included in the `transcription_text` posted to the web backend via the `call_logs` API (schema `CallLogCreate` in <mcfile path="docs/web_backend_docs/apidoc/call_logs.json" name="call_logs.json"></mcfile>).

**Agent Customization - Conversation:**
*   "must be able to save transcriptions of both caller and agent, and save them to a temporary storage during call, and post the complete conversation transcription (separated by roles, \"\"\" agent:\"xxx\", caller:\"xxx\", agent: \"xxx\" \"\"\") to the web backend when the call is over"
    *   **Question:** What is the defined "temporary storage" and its retention policy during the call?
    *   **Answer:** The specifics of the temporary storage for transcriptions during the call will be decided by the development team. The key requirement is that this storage is used to hold transcriptions during the call, and the data will be deleted from this temporary storage after the complete conversation transcript is successfully posted to the web backend.
    *   **Question:** In what format will the final transcription be posted to the web backend? (e.g., JSON, plain text). The example `\"\"\" agent:\"xxx\", caller:\"xxx\", agent: \"xxx\" \"\"\"` is a good start, but a formal structure would be beneficial.
    *   **Answer:** The final transcription will be a plain text string with roles clearly separated (e.g., "agent: xxx, caller: xxx, agent: xxx"). This will be stored in the `transcription_text` field of the `CallLogCreate` schema when posting to the `call_logs` API.

**Agent Customization - Spam:**
*   "must be able to block 1-800 callers"
    *   **Question:** How will "blocking" be implemented? Will the call be immediately disconnected, or will a message be played?
    *   **Answer:** For 1-800 callers, the AI agent will not pick up the call if the caller ID is identified as a 1-800 number by Twilio before the call is answered.
    *   **Question:** Will there be an option for the SMB owner to whitelist specific 1-800 numbers if needed (e.g., legitimate suppliers)?
    *   **Answer:** No whitelist for 1-800 numbers for now.
*   "must be able to detect sales conversation and hang-up"
    *   **Question:** This is a complex AI task. What are the key indicators or keywords that will be used to "detect a sales conversation"? How will the accuracy of this detection be measured and improved over time?
    *   **Answer:** The detection of sales conversations will be delegated to the AI model's capabilities, guided by specific instructions within the system prompt. The definition of "key indicators" will be part of this prompt engineering.
    *   **Question:** What message, if any, will be played before hanging up on a detected sales call?
    *   **Answer:** No specific message will be played. The AI model will be instructed via the system prompt to interrupt the conversation if it detects a sales call, politely refuse any offers, and then hang up immediately.
    *   **Question:** Is there a risk of false positives (flagging legitimate calls as sales)? How will this be mitigated?
    *   **Answer:** The system will aim for almost 100% certainty before classifying a call as a sales call and hanging up to minimize false positives. This will be managed through prompt engineering.

**Agent Customization - FAQ:**
*   "must be able to take a list of up to 20 FAQs, and answer caller accordingly"
    *   **Question:** How will the SMB owner input and manage these 20 FAQs? (e.g., a simple text interface, CSV upload).
    *   **Answer:** FAQs will be managed by the SMB owner via the web UI and configured for the AI agent via the `/api/v1/ai-agent/config` endpoint (field `faq_list` in schema `AIAgentConfiguration` from <mcfile path="docs/web_backend_docs/apidoc/ai_agent.json" name="ai_agent.json"></mcfile>).
    *   **Question:** How will the AI agent determine the "most relevant" FAQ to answer a caller's question? What level of natural language understanding is expected for matching questions to FAQs?
    *   **Answer:** The list of FAQs will be provided to the AI model as part of its system prompt. The model's natural language understanding capabilities will be leveraged to match caller questions to the provided FAQs. If this approach proves insufficient, a RAG (Retrieval Augmented Generation) system will be considered for future enhancement.
    *   **Question:** What happens if the caller's question doesn't match any of the 20 FAQs? How will the agent respond? (e.g., "I'm sorry, I don't have information on that. Can I help with something else?").
    *   **Answer:** If a caller's question does not match any of the provided FAQs, the AI agent will inform the caller that it doesn't have the answer, state that the question will be documented, and offer to forward it to the SMB owner.

**Technical Stack Requirements:**
*   "must be a fastapi backend that has rate limiter and other necessary security measures"
    *   **Question:** Beyond rate limiting, what are the other "necessary security measures" envisioned? (e.g., input validation, protection against common web vulnerabilities, data encryption in transit/rest for any sensitive configuration data it might handle, even if stateless).
    *   **Answer:** Security measures will be minimal at the AI agent application level, focusing on well-defined API interactions with clear JSON data formats. This assumes the AI agent and web backend will operate within the same private network, isolated from public internet access (especially the AI agent, which will only be accessible by Twilio and the web backend). No application-level data encryption is planned for the AI agent itself.

**Logging (New Section from Checklist):**
*   Requirement: "must use structured logging"
    *   **Question:** What specific format or schema is required for structured logging (e.g., JSON logs)? Are there preferred logging libraries or standards to adhere to?
    *   **Answer:** Standard, state-of-the-art logging practices will be followed. Specific libraries or detailed schema are not defined yet, but best practices will be used.
*   Requirement: "must log all errors"
    *   **Question:** What level of detail is required for error logs (e.g., stack traces, request context, user identifiers if applicable)?
    *   **Answer:** (Covered by "log all available info" and "best practices" but specific fields for error context can be further defined if needed during development).
*   Requirement: "must log all incoming calls information whether we pick it up or not"
    *   **Question:** What specific information fields about incoming calls need to be logged (e.g., timestamp, caller ID, Twilio call SID, reason for not picking up if applicable)?
    *   **Answer:** All available information from Twilio for the calls will be logged. Reasons for not picking up will be defined and logged.
    *   **Question:** Where will these logs be stored or sent (e.g., console output, file, a log management service like Google Cloud Logging)?
    *   **Answer:** Standard logging will be used; no specific redirection or log management service is defined for now.

**API Schema Confirmation - Call Logs:**
*   User Statement: "what we have here is the complete api docs. if things are missing, please document them, and we need to provide to the webbackend team to implement"
    *   **Note:** This implies that if the current `CallLogCreate` schema in <mcfile path="docs/web_backend_docs/apidoc/call_logs.json" name="call_logs.json"></mcfile> is missing fields required by the AI agent (e.g., `transcription_text` if it's not already there, or specific fields for reasons for not picking up a call), these will need to be documented as requirements for the web backend team.

**Authentication (New Requirement from Checklist):**
*   Requirement: "when receiving a incoming call, before pick-up the call, the agent must verify the 'to' phone number by querying the webbakend api whether the 'to' phone number belongs to a customer, and the customer has enough credits (free or paid minutes of calls) to use the AI agent"
    *   **Question:** Which specific web backend API endpoint will be used for this pre-call verification (checking 'to' number and customer credits)?
    *   **Answer:** An API endpoint for this is currently missing. A proposal will be made.
    *   **Proposal for Pre-call Verification API:**
        *   **Endpoint Location:** Consider adding to `businesses.json` as it pertains to customer status and credits, which are business-centric.
        *   **Proposed Endpoint:** `POST /api/v1/businesses/verify-call-reception`
        *   **Request Body Schema:**
            ```json
            {
              "to_phone_number": "string (E.164 format)",
              "from_phone_number": "string (E.164 format, optional, for context/logging)"
            }
            ```
        *   **Response Body Schema (Success 200 OK):**
            ```json
            {
              "can_receive_call": "boolean",
              "reason_code": "string (enum: OK, NOT_CUSTOMER, INSUFFICIENT_CREDITS, INTERNAL_NUMBER, API_ERROR, CACHE_USED_API_UNAVAILABLE, CACHE_MISS_API_UNAVAILABLE)",
              "reason_message": "string (human-readable explanation)",
              "customer_id": "string (optional, if 'to_phone_number' is a customer)",
              "current_credit_balance": "number (optional, if applicable and user has permission to see)"
            }
            ```
        *   **Rationale:** This structure provides a clear go/no-go signal (`can_receive_call`) and a `reason_code` for detailed logic and logging by the AI agent.

    *   **Question:** What specific data fields will this API endpoint expect in the request from the AI agent (e.g., just the 'to' phone number)? and What specific data fields will this API endpoint return in the response (e.g., boolean for 'belongs_to_customer', boolean for 'has_sufficient_credits', current_credit_balance)?
    *   **Answer:** (Covered by the API proposal above). 

    *   **Question:** What is the expected behavior if the web backend API is unavailable or returns an error during this pre-call check? Will the call be rejected, or is there a fallback?
    *   **Answer:** If the web backend API is unavailable or returns an error, the AI agent will attempt to use a local cache of previous verification results. This cache will have a configurable TTL (e.g., 24 hours). If the 'to' number is not in the cache or the cache entry has expired, the call will not be picked up.
    *   **Further Question (Cache):** How will the TTL for this local cache be configured (e.g., environment variable in the AI agent service)?
    *   **Answer (Cache TTL):** The TTL for the local cache will be configured via local environment variables in the AI agent service.

    *   **Question:** How will the AI agent handle the call if the API indicates the 'to' number does not belong to a customer, or the customer has insufficient credits? (e.g., reject the call, play a specific message).
    *   **Answer:** The handling will be as follows:
        1.  **'to' number does not belong to a customer (`reason_code: NOT_CUSTOMER`):** The AI agent will not pick up the call. This will be logged.
        2.  **'to' number belongs to a customer, but insufficient credits (`reason_code: INSUFFICIENT_CREDITS`):** The AI agent will not pick up the call. A notification will be posted to the web backend. This will be logged.
        3.  **'to' number is the Twilio account's own number (`reason_code: INTERNAL_NUMBER`):** The AI agent will pick up the call. The AI will attempt to determine the caller's intent, and the caller's number will be logged for further investigation.
    *   **Proposal for Insufficient Credits Notification API:**
        *   **Endpoint Location:** Consider adding to `businesses.json` or a new `notifications.json`.
        *   **Proposed Endpoint:** `POST /api/v1/businesses/notify-event` (more generic for future use)
        *   **Request Body Schema:**
            ```json
            {
              "event_type": "string (enum: INSUFFICIENT_CREDITS_CALL_ATTEMPT, ...)",
              "event_timestamp": "string (ISO 8601 datetime)",
              "details": {
                "customer_phone_number": "string (E.164 format of the 'to' number)",
                "attempted_caller_phone_number": "string (E.164 format, the 'from' number)"
                // other relevant details based on event_type
              }
            }
            ```
        *   **Response Body Schema (Success 202 Accepted):**
            ```json
            {
              "status": "string", // e.g., "NotificationQueued"
              "message_id": "string (optional, for tracking)"
            }
            ```
    *   **Further Question (Internal Number Handling):** For scenario 3 (internal Twilio number), what specific behavior or script should the AI agent follow after picking up the call? (e.g., standard greeting then open-ended question, or a specific message like "This number is for automated services, how can I direct your query?").
    *   **Answer (Internal Number Handling):** The AI agent will use a standard greeting with open-ended questions.

        