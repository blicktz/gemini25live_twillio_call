# AI Agent Web Backend API Update Specification

**Document Version**: 1.0  
**Date**: June 2025  
**Status**: Ready for Implementation

## 📋 Overview

This document provides the complete specification for updating the Web Backend API to support AI Agent integration. All requirements have been analyzed against the existing codebase and clarified with the AI-agent team.

## 🔑 AI-Agent Integration Flow

**Question**: How should the AI-agent identify and query business/AI-agent configuration information?

**Answer**: Use the `business_id` approach for optimal performance:

1. **Step 1**: Call `POST /api/v1/businesses/verify-call-reception` with phone number
2. **Step 2**: Receive `business_id` in response (when `can_receive_call=true`)
3. **Step 3**: Use `business_id` to query business and AI agent configuration via dedicated internal endpoints

**Why `business_id` instead of phone number repeated queries?**
- ✅ **Performance**: Avoids repeated phone number lookups (database indexed queries)
- ✅ **Efficiency**: Single UUID lookup is faster than string-based phone searches
- ✅ **Caching**: Business info can be cached by `business_id` for subsequent calls
- ✅ **Consistency**: Uses existing CRUD patterns (`get_by_business_id` methods already exist)
- ✅ **Scalability**: Better for high-volume call scenarios (60 calls/minute target)

### Example Integration Flow

```bash
# Step 1: Verify call reception
curl -X POST '/api/v1/businesses/verify-call-reception' \
  -H 'X-API-Key: your_key' \
  -d '{"to_phone_number": "+1234567890"}'

# Response:
{
  "can_receive_call": true,
  "reason_code": "OK",
  "reason_message": "Customer verified with sufficient credits",
  "business_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "current_credit_balance": 45.5
}

# Step 2: Get business information
curl -X GET '/api/v1/internal/businesses/a1b2c3d4-e5f6-7890-abcd-ef1234567890' \
  -H 'X-API-Key: your_key'

# Step 3: Get AI agent configuration
curl -X GET '/api/v1/internal/ai-agent/a1b2c3d4-e5f6-7890-abcd-ef1234567890/config' \
  -H 'X-API-Key: your_key'
```

---

## 🚨 Critical New APIs to Implement

### 1. Pre-call Verification API

**Endpoint**: `POST /api/v1/businesses/verify-call-reception`

**Purpose**: Verify that a phone number belongs to a customer with sufficient credits before answering calls.

**Rate Limiting**: 60 calls/minute

**Authentication**: Service-to-service using existing `X-API-Key` header

#### Request Schema
```json
{
  "to_phone_number": "string (E.164 format, required)"
}
```

#### Response Schema
```json
{
  "can_receive_call": "boolean",
  "reason_code": "string (enum: OK, NOT_CUSTOMER, INSUFFICIENT_CREDITS, INTERNAL_NUMBER, API_ERROR)",
  "reason_message": "string",
  "business_id": "string (UUID, required when can_receive_call=true)",
  "current_credit_balance": "number (optional, in minutes)"
}
```

#### Implementation Requirements
- ✅ Leverage existing `UsageTrackingService.check_usage_limit()` for credit verification
- ✅ Add phone number indexing to `businesses` table for fast lookup
- ✅ Implement business phone number lookup in `crud_business`
- ✅ Add caching for business information (Redis, 5-minute TTL)
- ❌ **NO** real-time credit deduction - verification only
- ❌ **NO** caching for credit information (accuracy concerns)

#### Response Time Target
< 200ms (critical path)

---

### 2. Event Notification API

**Endpoint**: `POST /api/v1/businesses/notify-event`

**Purpose**: Notify the web backend about important AI agent events for logging and monitoring.

**Rate Limiting**: 60 events/hour

**Authentication**: Service-to-service using existing `X-API-Key` header

#### Request Schema
```json
{
  "event_type": "string (enum: INSUFFICIENT_CREDITS_CALL_ATTEMPT, CALL_FAILED, CALL_REJECTED, etc.)",
  "event_timestamp": "string (ISO 8601 datetime)",
  "details": {
    "customer_phone_number": "string",
    "attempted_caller_phone_number": "string (optional)",
    "additional_context": "object (flexible)"
  }
}
```

#### Response Schema
```json
{
  "status": "string",
  "message": "string"
}
```

#### Implementation Requirements
- ✅ Use existing structured logging infrastructure (`app/core/logging.py`)
- ✅ Leverage Celery task queue for async processing
- ✅ Events are logged only, **NOT** stored persistently
- ✅ Integration with existing event handling patterns

#### Response Time Target
< 500ms (async processing)

---

### 3. Business Information Lookup APIs (For AI-Agent Use)

**Purpose**: Allow AI-agent to query business and AI agent configuration using the `business_id` returned from pre-call verification.

#### 3a. Get Business Information by Business ID

**Endpoint**: `GET /api/v1/internal/businesses/{business_id}`

**Authentication**: Service-to-service using existing `X-API-Key` header

**Response Schema**:
```json
{
  "id": "string (UUID)",
  "business_name": "string",
  "phone_number": "string",
  "business_hours": [
    {
      "day_of_week": "integer (0-6)",
      "open_time": "string (HH:MM format)",
      "close_time": "string (HH:MM format)",
      "is_closed": "boolean"
    }
  ],
  "core_services": [
    {
      "service_name": "string",
      "description": "string"
    }
  ],
  "timezone": "string",
  "address": "string (optional)",
  "website": "string (optional)"
}
```

#### 3b. Get AI Agent Configuration by Business ID

**Endpoint**: `GET /api/v1/internal/ai-agent/{business_id}/config`

**Authentication**: Service-to-service using existing `X-API-Key` header

**Response Schema**:
```json
{
  "id": "string (UUID)",
  "business_id": "string (UUID)",
  "agent_name": "string",
  "greeting_message": "string",
  "legal_disclaimer_template": "string",
  "tone": "string (enum: casual, cheerful, formal)",
  "max_call_duration_minutes": "integer",
  "enable_1800_blocking": "boolean",
  "enable_sales_detection": "boolean",
  "voicemail_instructions": "string",
  "call_forwarding_number": "string",
  "call_forwarding_enabled": "boolean",
  "faq_list": [
    {
      "question": "string",
      "answer": "string",
      "display_order": "integer"
    }
  ],
  "custom_questions": [
    {
      "question_text": "string",
      "expected_answer_type": "string",
      "is_required": "boolean"
    }
  ]
}
```

#### Implementation Requirements
- ✅ Leverage existing `crud_business.get()` and `crud_ai_agent.get_by_business_id()` methods
- ✅ Add to `/api/v1/internal/*` endpoints with existing authentication
- ✅ Include business hours and core services in business response
- ✅ Include both FAQ and custom questions in AI agent config response

#### Response Time Targets
- Business Information API: < 300ms
- AI Agent Configuration API: < 500ms

---

## 🔧 Schema Updates Required

### 3. AI Agent Configuration Schema Enhancements

#### New Database Table: FAQ
Create a new `faq` table separate from `custom_questions`:

```sql
CREATE TABLE faq (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ai_agent_configuration_id UUID NOT NULL REFERENCES ai_agent_configurations(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### Updated AIAgentConfiguration Schema
Add these fields to the existing `AIAgentConfiguration` model:

```python
class AIAgentConfigurationBase(BaseModel):
    # ... existing fields ...
    
    # New required fields
    agent_name: str | None = Field(None, max_length=100)
    legal_disclaimer_template: str | None = Field(None, max_length=500) 
    tone: AgentTone | None = Field(None)
    max_call_duration_minutes: int = Field(default=30, ge=1, le=120)
    enable_1800_blocking: bool = Field(default=True)
    enable_sales_detection: bool = Field(default=True)

class AgentTone(str, Enum):
    """Enumeration for AI agent conversation tone."""
    CASUAL = "casual"
    CHEERFUL = "cheerful" 
    FORMAL = "formal"

class FAQItem(BaseModel):
    """Schema for FAQ items."""
    question: str = Field(..., max_length=500)
    answer: str = Field(..., max_length=2000)
    display_order: int = Field(default=0, ge=0)
```

#### Configuration Create/Update Schemas
```python
class AIAgentConfigurationCreate(AIAgentConfigurationBase):
    # ... existing fields ...
    faq_list: list[FAQItem] | None = Field(default_factory=list, max_items=20)

class AIAgentConfiguration(AIAgentConfigurationBase):
    # ... existing fields ...
    faq_list: list[FAQItem] = Field(default_factory=list)
```

---

### 4. Call Log Schema Enhancements

#### Add New Fields to CallLogCreate Schema
```python
class CallLogCreate(CallLogBase):
    # ... existing fields ...
    
    # New fields
    twilio_call_sid: str | None = Field(None, max_length=100)
    call_not_answered_reason: CallNotAnsweredReason | None = Field(None)
    ai_agent_version: str | None = Field(None, max_length=50)
    gemini_model_version: str | None = Field(None, max_length=50)

class CallNotAnsweredReason(str, Enum):
    """Enumeration for call not answered reasons."""
    NOT_CUSTOMER = "not_customer"
    INSUFFICIENT_CREDITS = "insufficient_credits"
    BLOCKED_1800 = "1800_blocked"
    SALES_DETECTED = "sales_detected"  
    TECHNICAL_ERROR = "technical_error"

class TechnicalErrorCode(str, Enum):
    """Specific technical error codes."""
    NETWORK_ERROR = "network_error"
    API_TIMEOUT = "api_timeout"
    SERVICE_UNAVAILABLE = "service_unavailable"
    INVALID_PHONE_FORMAT = "invalid_phone_format"
    AUTHENTICATION_FAILED = "authentication_failed"
```

#### Database Migration Required
```sql
ALTER TABLE call_logs ADD COLUMN twilio_call_sid VARCHAR(100);
ALTER TABLE call_logs ADD COLUMN call_not_answered_reason VARCHAR(50);
ALTER TABLE call_logs ADD COLUMN ai_agent_version VARCHAR(50);
ALTER TABLE call_logs ADD COLUMN gemini_model_version VARCHAR(50);
ALTER TABLE call_logs ADD COLUMN technical_error_code VARCHAR(50);
```

---

## 🔐 Authentication Documentation

### Service-to-Service Authentication (Already Implemented)

**Method**: API Key Authentication  
**Header Format**: `X-API-Key: {INTERNAL_API_KEY}`  
**Environment Variable**: `INTERNAL_API_KEY`

#### Usage Example
```bash
curl -X POST \
  'https://api.aicallgo.com/api/v1/businesses/verify-call-reception' \
  -H 'X-API-Key: your_internal_api_key_here' \
  -H 'Content-Type: application/json' \
  -d '{
    "to_phone_number": "+1234567890"
  }'
```

#### Implementation Location
- Authentication function: `app/api/v1/endpoints/internal.py:verify_internal_api_key()`
- Used in existing endpoints: `/api/v1/internal/*`
- Rate limiting: Applied per API key

---

## ⚡ Performance Requirements & Optimizations

### Response Time Targets
- **Pre-call Verification API**: < 200ms (critical path)
- **AI Agent Configuration API**: < 500ms  
- **Business Information API**: < 300ms
- **Call Log Creation API**: < 1000ms (non-blocking)
- **Event Notification API**: < 500ms (async processing)

### Caching Strategy

#### Business Information Cache
- **Implementation**: Redis cache
- **TTL**: 5 minutes
- **Cache Key Pattern**: `business:phone:{phone_number}`
- **Invalidation**: On business updates

```python
# Cache Implementation Example
@cached(ttl=300, cache=RedisCache, key="business:phone:{phone_number}")
async def get_business_by_phone_number(db: Session, phone_number: str):
    # Implementation here
    pass
```

#### Credit Information
- **❌ NO CACHING** for credit balances to maintain accuracy
- Real-time credit checks via `UsageTrackingService.check_usage_limit()`

### Database Optimizations

#### Required Indexes
```sql
-- Phone number lookup optimization
CREATE INDEX idx_businesses_phone_number ON businesses(phone_number);
CREATE INDEX idx_businesses_phone_normalized ON businesses(phone_number_normalized);

-- Call log performance
CREATE INDEX idx_call_logs_business_start_time ON call_logs(business_id, call_start_time);
CREATE INDEX idx_call_logs_twilio_sid ON call_logs(twilio_call_sid);

-- FAQ performance  
CREATE INDEX idx_faq_agent_config_order ON faq(ai_agent_configuration_id, display_order);
```

---

## 📋 Error Handling Specification

### Standard Error Response Format
All APIs must return consistent error responses:

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

### HTTP Status Code Mapping
- **400 Bad Request**: Invalid phone number format, validation errors
- **401 Unauthorized**: Invalid or missing API key
- **402 Payment Required**: Insufficient credits
- **404 Not Found**: Customer/business not found
- **429 Too Many Requests**: Rate limiting exceeded
- **500 Internal Server Error**: Database/service errors
- **503 Service Unavailable**: System maintenance, dependency failures

### Error Code Standards
Use existing error code patterns from `app/core/config.py:ErrorCodes`:

```python
# New error codes to add
PHONE_NUMBER_NOT_FOUND = "AICG-0206"
INSUFFICIENT_CREDITS = "AICG-0405" # Already exists
TECHNICAL_CALL_ERROR = "AICG-0505"
```

---

## 🛠️ Implementation Tasks

### Phase 1: Critical APIs (Week 1-2)

#### Database Changes
- [ ] Create `faq` table migration
- [ ] Add new fields to `call_logs` table  
- [ ] Add phone number indexes to `businesses` table
- [ ] Create phone number normalization function

#### API Endpoints
- [ ] `POST /api/v1/businesses/verify-call-reception`
- [ ] `POST /api/v1/businesses/notify-event`  
- [ ] `GET /api/v1/internal/businesses/{business_id}` (new internal endpoint)
- [ ] `GET /api/v1/internal/ai-agent/{business_id}/config` (new internal endpoint)
- [ ] Update AI agent configuration endpoints to support FAQ

#### CRUD Operations
- [ ] `crud_business.get_by_phone_number()` with caching
- [ ] `crud_faq` for FAQ management
- [ ] Update `crud_ai_agent` for new fields

### Phase 2: Schema Updates 

#### Schema Updates
- [ ] Update `AIAgentConfiguration` schemas
- [ ] Update `CallLogCreate` schemas
- [ ] Create `FAQ` schemas

#### Service Updates
- [ ] Phone number normalization service
- [ ] Event logging service enhancement
- [ ] Cache invalidation for business updates

### Phase 3: Performance & Polish 

#### Performance Optimizations
- [ ] Redis caching implementation
- [ ] Database query optimization
- [ ] Rate limiting configuration

#### Documentation & Testing
- [ ] API documentation updates
- [ ] Integration tests

---

## 🧪 Testing Requirements

### Unit Tests Required
- Phone number lookup and normalization
- Credit verification logic
- FAQ CRUD operations
- Error handling scenarios

### Integration Tests Required  
- End-to-end pre-call verification flow
- Event notification processing
- Performance testing for 60 calls/minute

---

## 📊 Monitoring & Observability

### Key Metrics to Track
- Pre-call verification response times
- Cache hit ratios for business lookups
- Error rates by reason code
- API usage patterns and rate limiting

### Logging Requirements
- All pre-call verification attempts (success/failure)
- Credit verification decisions
- Phone number lookup performance
- Event notification processing

### Alerts to Configure
- Pre-call verification response time > 200ms
- Error rate > 5% for verification API
- Cache miss ratio > 20% for business lookups
- Rate limiting activation

---

## 🚀 Deployment Checklist

### Environment Variables
- [ ] `INTERNAL_API_KEY` configured in AI-agent environment
- [ ] Redis cache URLs configured
- [ ] Rate limiting thresholds set

### Database Migrations
- [ ] Run FAQ table creation migration
- [ ] Run call_logs schema update migration  
- [ ] Create database indexes
- [ ] Verify migration rollback procedures

### API Documentation
- [ ] Update OpenAPI/Swagger documentation
- [ ] Create AI-agent integration guide
- [ ] Document authentication examples

### Performance Validation
- [ ] Load test pre-call verification endpoint
- [ ] Validate cache performance
- [ ] Monitor response times in production
