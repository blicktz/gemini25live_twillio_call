Please implement the  ai agent backend according to this @aiaigent_backend_TDD_phase1.md tdd document in full. you must make sure you complete every needed functionality in the TDD 100%. when implmenting the communication with the webbackend api, here is the api spec for reference @webbackend_api_update_specification.md before start implementing the ai agent, ask me any questions until you have >95% confidence you understand what you need to do
Before I begin implementing the AI agent backend, I'd like to clarify a few important details to ensure I fully understand the requirements:

## 1. **Environment & Configuration**
- Should I create a complete Docker setup with all necessary configurations for local development and Render deployment?
Answer: Yes, complete docker setup for both local and render deployment
- For the Google Cloud credentials (`GOOGLE_APPLICATION_CREDENTIALS`), should I create placeholder configuration or assume this will be provided externally?
Answer: create placeholder configuration that can be easily replaced with real configuration later
- What should be the default system prompt for the AI agent? The TDD mentions it's configurable via `SYSTEM_PROMPT` env var but doesn't specify a default.
Answer: you should create the full system prompt for ai agent, and place it in a python file. ignore the env var of 'SYSTEM_PROMPT', we will not do that. Your system prompt will be the only system prompt we will use. so be very detailed and clear about what you want to do.

## 2. **Audio Processing Requirements**
- The TDD mentions using `audioop` for mulaw conversion and potentially `scipy` for resampling. Should I implement both approaches (with scipy as optional dependency)?
answer: use `audioop` only, DO NOT use `scipy`.
- For debug audio saving (`SAVE_DEBUG_AUDIO`), what directory structure should be used for storing these files?
answer: DO NO need to implement this feature.

## 3. **Web Backend Integration**
- The Web Backend API specification shows these endpoints need to be called. Should I implement retry logic with exponential backoff for all Web Backend API calls or only specific ones?
answer: """

## **Selective Retry Logic Approach** ✅
**no need to implement retry logic for all Web Backend API calls**. Here's the strategic breakdown:

### **Endpoints That NEED Retry Logic:**

#### 1. **Pre-call Verification API** (`POST /api/v1/businesses/verify-call-reception`)
- **Critical Path**: < 200ms response time requirement
- **High Impact**: Call acceptance/rejection decision
- **Retry Scenarios**: 500, 503 (Service Unavailable), network timeouts
- **Strategy**: Fast retry (2-3 attempts, 100ms intervals)
- **Skip Retry**: 400, 401, 402, 404, 429 (business logic errors)

#### 2. **Business/AI Agent Configuration APIs** (Internal endpoints)
- **Moderate Impact**: Call quality degradation if failed
- **Retry Scenarios**: 500, 503, network timeouts
- **Strategy**: Standard exponential backoff (3 attempts, 200ms → 400ms → 800ms)

### **Endpoints That DON'T Need Retry Logic:**

#### 1. **Event Notification API** (`POST /api/v1/businesses/notify-event`)
- **Non-Critical**: Logging/monitoring only
- **Async Processing**: < 500ms with background processing
- **Impact**: Low - failed events don't affect call quality

#### 2. **Call Log Creation API**
- **Non-Blocking**: < 1000ms with idempotency
- **Post-Call**: Doesn't affect real-time call experience
- **Built-in Protection**: Idempotency handling prevents duplicates


### **Why This Approach:**

1. **Performance Focus**: Only retry time-sensitive, critical-path operations
2. **Resource Efficiency**: Avoid unnecessary network overhead
3. **Failure Isolation**: Non-critical failures don't cascade
4. **Complexity Management**: Simpler debugging and monitoring
5. **Cost Optimization**: Fewer API calls = lower costs

### **Alternative for Non-Critical APIs:**
- **Circuit Breaker Pattern**: Fail fast after consecutive failures
- **Background Retry Queue**: For event notifications and call logs
- **Graceful Degradation**: Continue call processing even if logging fails

**Bottom Line**: Implement retry logic only for the pre-call verification API and configuration lookups. The specification's performance targets and error handling patterns support this selective approach.
        """
- For the recording URL extraction from Twilio, should I implement a polling mechanism if the recording isn't immediately available?
answer: """
## Recommended Celery Implementation for Twilio Recording URL Extraction

### Architecture Overview

The recommended approach uses **Celery background tasks** to handle Twilio recording URL extraction asynchronously, preventing any impact on the AI agent's real-time call processing concurrency.

### Core Implementation Strategy

**1. Immediate Call Completion**
- When a call ends, immediately complete the call processing and respond to the client
- Create the initial call log entry without the recording URL
- Queue a Celery task for recording extraction
- Return success immediately to maintain real-time performance

**2. Background Recording Extraction**
- Use a dedicated Celery task that runs independently of the main application
- Implement exponential backoff retry logic (3-5 attempts)
- Handle Twilio's recording availability delays (can take 30 seconds to several minutes)
- Update the call log with the recording URL once extracted

### Celery Task Design

**Task Configuration:**
- **Task Name**: `extract_twilio_recording_url`
- **Retry Policy**: Exponential backoff with 3-5 attempts
- **Initial Delay**: 30 seconds (Twilio recordings aren't immediately available)
- **Max Retry Delay**: 10 minutes
- **Failure Handling**: Log failure and mark recording as unavailable

**Task Parameters:**
- Call SID from Twilio
- Business ID for context
- Call log ID for updating
- Attempt counter for retry logic

### Benefits of This Approach

**1. Concurrency Protection**
- Zero impact on AI agent's real-time processing
- No blocking operations during active calls
- Maintains WebSocket connection stability

**2. Resilience**
- Automatic retries handle Twilio's variable recording availability
- Graceful failure handling without affecting call quality
- Task persistence survives application restarts

**3. Scalability**
- Background workers can scale independently
- Queue can handle high call volumes
- No resource contention with real-time operations

**4. Monitoring & Observability**
- Celery provides built-in task monitoring
- Clear separation of concerns for debugging
- Detailed logging of recording extraction attempts

### Implementation Requirements

**Dependencies:**
- `celery[redis]` for task queue
- `redis` as message broker
- Existing `twilio` SDK for API calls

**Infrastructure:**
- Redis instance for Celery broker
- Separate Celery worker processes
- Task monitoring dashboard (optional but recommended)

**Error Handling:**
- Network timeouts with Twilio API
- Recording not found scenarios
- Invalid call SID handling
- Database update failures
"""

## 4. **Error Handling & Fallbacks**
- What should be the default greeting message if we can't fetch the AI agent configuration from the Web Backend?
answer: you can create the default greeting message based on your best knowledge
- If pre-call verification fails due to Web Backend timeout, should the call be rejected or answered with a generic message?
answer: if verfication fails, do not pick up the call from twilio, and log errors to the webbackend service

## 5. **Call Flow Logic**
- The TDD mentions VAD (Voice Activity Detection) is handled by Gemini, but the MVP code shows some VAD timer logic. Should I include any client-side VAD logic or rely entirely on Gemini?
answer: NO, ignore that, we do not include any client side VAD logic, and rely on Gemini 2.0 live model to handle it
- For the legal disclaimer, should it be played at the beginning of every call or only under certain conditions?
answer: the legal disclaimer should be appended to the end of the greeting message that we will speak to the caller when we pick up the call for every call we pick up
## 6. **Testing & Development**
- Should I include mock implementations for Twilio webhooks and Web Backend endpoints for local testing?
answer: include mock for the unit testing only.
- Do you want me to implement the full test suite (unit, integration tests) or focus on the core implementation first?
answer: only the unit testing of the newly implemented code is needed.

## 7. **Project Structure**
- Should I follow the exact directory structure mentioned in the TDD or can I make minor adjustments for better organization?
answer: you can make adjustments for better organization.
- Do you want me to include development tools configuration (e.g., pre-commit hooks, linting configs)?
answer: yes, all the best practice tools should be included. pre-commit hooks, lint (black, ruff check etc.), and CI/CD actions for github actions.
