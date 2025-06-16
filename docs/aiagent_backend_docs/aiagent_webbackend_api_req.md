# AI Agent Web Backend API Requirements

This document outlines the API requirements for the AI Agent backend to integrate with the Web Backend, including missing endpoints, schema modifications, and new API proposals.

## Current API Status Analysis

Based on the review of existing API documentation in `/docs/web_backend_docs/apidoc/`, the following endpoints are currently available:

### ✅ Available APIs

1. **AI Agent Configuration**: `GET/PUT/POST /api/v1/ai-agent/config`
2. **Business Information**: `GET /api/v1/businesses/me`
3. **Call Logs**: `GET /api/v1/call-logs` (list), `GET /api/v1/call-logs/{id}` (detail)
4. **Internal Call Log Creation**: `POST /api/v1/internal/call-logs` (uses `CallLogCreate` schema)

## Missing APIs & Required Implementations

### 🚨 Critical Missing APIs

#### 1. Pre-call Verification API

**Requirement**: Before answering any call, the AI agent must verify that the 'to' phone number belongs to a customer with sufficient credits.

**Proposed Endpoint**: `POST /api/v1/businesses/verify-call-reception`

**Request Schema**:
```json
{
  "to_phone_number": "string (E.164 format)",
  "from_phone_number": "string (E.164 format, optional)"
}
```

**Response Schema**:
```json
{
  "can_receive_call": "boolean",
  "reason_code": "string (enum: OK, NOT_CUSTOMER, INSUFFICIENT_CREDITS, INTERNAL_NUMBER, API_ERROR)",
  "reason_message": "string",
  "customer_id": "string (optional)",
  "current_credit_balance": "number (optional)"
}
```

**Why Needed**: This is a critical security and billing control mechanism. Without it, the AI agent cannot determine whether to answer calls or verify customer eligibility.

#### 2. Event Notification API

**Requirement**: Notify the web backend about important events (e.g., insufficient credits, failed calls).

**Proposed Endpoint**: `POST /api/v1/businesses/notify-event`

**Request Schema**:
```json
{
  "event_type": "string (enum: INSUFFICIENT_CREDITS_CALL_ATTEMPT, CALL_FAILED, etc.)",
  "event_timestamp": "string (ISO 8601 datetime)",
  "details": {
    "customer_phone_number": "string",
    "attempted_caller_phone_number": "string",
    "additional_context": "object (flexible)"
  }
}
```

**Response Schema**:
```json
{
  "status": "string",
  "message_id": "string (optional)"
}
```

**Why Needed**: Essential for business intelligence, alerting SMB owners about missed opportunities due to insufficient credits, and system monitoring.

## Schema Modifications Required

### 🔧 AI Agent Configuration Schema Gaps

The current `AIAgentConfiguration` schema is missing several required fields:

#### Missing Fields in `AIAgentConfiguration`:

```json
{
  "agent_name": "string (maxLength: 100)",
  "legal_disclaimer_template": "string (maxLength: 500)",
  "faq_list": [
    {
      "question": "string (maxLength: 200)",
      "answer": "string (maxLength: 1000)"
    }
  ],
  "tone": "string (enum: casual, cheerful, formal)",
  "max_call_duration_minutes": "integer (default: 30)",
  "enable_1800_blocking": "boolean (default: true)",
  "enable_sales_detection": "boolean (default: true)"
}
```

**Why Needed**: These fields are explicitly required by the AI agent feature checklist for:
- Agent self-identification (`agent_name`)
- Legal compliance (`legal_disclaimer_template`)
- FAQ functionality (`faq_list` - up to 20 FAQs)
- Conversation tone control (`tone`)
- Call management (`max_call_duration_minutes`)
- Spam protection (`enable_1800_blocking`, `enable_sales_detection`)

### 🔧 Call Log Schema Enhancements

The current `CallLogCreate` schema needs additional fields:

#### Additional Fields for `CallLogCreate`:

```json
{
  "twilio_call_sid": "string (optional)",
  "call_not_answered_reason": "string (optional, enum: NOT_CUSTOMER, INSUFFICIENT_CREDITS, 1800_BLOCKED, SALES_DETECTED, TECHNICAL_ERROR)",
  "transcription_text": "string (optional)",
  "ai_agent_version": "string (optional)",
  "gemini_model_version": "string (optional)"
}
```

**Why Needed**:
- `twilio_call_sid`: Essential for call tracking and debugging
- `call_not_answered_reason`: Required for analytics and business intelligence
- `transcription_text`: Explicitly mentioned in requirements for storing conversation transcripts
- Version fields: Important for debugging and system monitoring

## Authentication Requirements

### 🔐 Service-to-Service Authentication

**Current Gap**: No defined authentication mechanism between AI agent and web backend.

**Proposed Solution**: Static API key authentication
- AI agent will include `WEB_BACKEND_API_KEY` in request headers
- Header format: `Authorization: Bearer {WEB_BACKEND_API_KEY}`
- Key should be configurable via environment variables


## API Performance Requirements

### ⚡ Response Time Expectations

1. **Pre-call Verification API**: < 200ms (critical path)
2. **AI Agent Configuration API**: < 500ms (called at startup)
3. **Business Information API**: < 300ms (called during greeting)
4. **Call Log Creation API**: < 1000ms (called post-call, non-blocking)
5. **Event Notification API**: < 500ms (important for real-time alerts)

## Error Handling Requirements

### 📋 Standard Error Response Format

All APIs should return consistent error responses:

```json
{
  "error": {
    "code": "string (e.g., INSUFFICIENT_CREDITS)",
    "message": "string (human-readable)",
    "details": "object (optional, additional context)",
    "timestamp": "string (ISO 8601)"
  }
}
```

### 🚨 Critical Error Scenarios

1. **Database Connection Failures**: Return 503 Service Unavailable
2. **Invalid Phone Number Format**: Return 400 Bad Request
3. **Customer Not Found**: Return 404 Not Found
4. **Insufficient Credits**: Return 402 Payment Required
5. **Rate Limiting**: Return 429 Too Many Requests

## Security Considerations

### 🔒 Data Protection

1. **Input Validation**: Strict validation on all phone number formats and text inputs
2. **Audit Logging**: Log all API calls for security monitoring
