## User Experience & Business Logic
7. Sales Call Detection Accuracy

- Question: What's the acceptable false positive rate for sales call detection? Should there be a "confidence threshold" before hanging up?
- answers: Yes, there should be a confidence threshold before hanging up.  let's set the confidence threshold to 95%

- Question: How should the agent handle edge cases like legitimate business calls that mention sales/products?
- answers: we should instruct the AI model to consider the context, the more we talk with the caller, the more likely the AI model should be able to figure out whether it's a legimate call for query of the SMB owner's business, or just a sales spam call

8. FAQ Matching & Fallback Behavior

- Question: When the AI can't match a question to the 20 FAQs, the QA says it will "offer to forward it to the SMB owner." How will this forwarding mechanism work (email, SMS, in-app notification)?
- answers: good catch, we can't forward call to SMB owner in real-time now. it should not offer to forward to SMB owner. only the message taken will be offered to the SMB owner, not the call

9. Call Time Limits & Grace Periods

- Question: Should there be a warning before the max time limit is reached (e.g., "We have 2 minutes remaining")?
- Answers: NO, abosulately not, this feature is more like a safety net against anyone who would abuse our AI agent service. we don't expect a lot of the caller will encouner this max time limit ( it will be set well-longer than normal call length)
- Question: What happens if the caller is mid-sentence when the time limit hits?
- Answers: if that does happen, we should cut off the caller, and say something like 'sorry, we're unable to process your call further for now' etc.

10. Multi-language Support
- Question: The checklist doesn't mention language support. Should the AI agent detect caller language and respond accordingly, or is English-only acceptable for MVP?
- Answers: only English for now

11. Error Handling & Failover

- Question: If the Gemini 2.0 model becomes unavailable mid-call, what's the fallback behavior? Should calls be transferred to voicemail or a human?
- answer: this is single failure point in our system, we don't have a good fall back now. please make this clear that we need to figure this out after the first MVP is out

12. Call Quality & Performance Metrics

- Question: What specific metrics should be tracked for call quality (latency, audio clarity, conversation success rate)? How will these be exposed to the SMB owner?
- Answers: for now, we don't track call quality explicitly, we'll review call recording and transcriptions offline. but no explicit metrics will be exposed to SMB owner

13. Compliance & Legal Requirements

- Question: Are there specific compliance requirements for call recording consent, data retention, or TCPA compliance that should be built into the system?
- answers: the legal disclaimer will cover this, we don't need to implement any additional features.