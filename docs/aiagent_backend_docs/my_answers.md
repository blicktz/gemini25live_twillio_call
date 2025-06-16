General Capabilities:
 - datapoints for retrieval of info: see '/Users/blickt/Documents/src/twillio_gemini25/docs/web_backend_docs/apidoc' for all defined api endpoints of the webbackend. the ai_agent and busineess json files are important info our AI agent need to get from the webbackend. the call_logs json are related to the call transcriptions. note that 1) these endpoints are also used by the web front-end, so there are mostly for the web front-end to use. only a few of theose endpoints are for the ai agent 2) these api may not be enough for implementing all the features in the ai agent. make sure you flag any missing/necessary new endpoints we may need to add.
 - the webbackend is deployed on render.com where our ai agent will be deployed too. so the latency of the network should be minimal, and the processing of these endpoints are mainly database related, therefore should not exceed a few hundres of milliseconds. take that performance as a starting assumption for the latency of the ai agent
 
 Authentication
 - the authentication between the ai agent and the webackend is through a pre-configure randowm WEB_BACKEND_API_KEY, the AI agent should use this api key to verify itself for all the requests to webbackend. Note that we may need to add new infrastructure to support this. if it's too complicated, you may suggests best practices ways of authentication between two services leveraging existing services ( the one that already set up for front-end web user auth) if possible
 
 Telephony Interaction:
 - permanent storage: google cloud storage should be used for storing the recording we pull from twilio.
 - recording should follow the original format from twilio for simplicity. we don't want to transcoding the recording.
 - the recording file name should include the business name, datetime timestamp. you may check if you need additional meta data. we should be able to you call_logs api to communicate additional meta data (recommend changes to the call_logs api if we need)
 - we need the message, we should make this message configurable at the ai agent level (statically configurable via env vars). 

 Agent Customization - Basic:
- agent name should come from the ai_agent api ( seems missing right now, but we need to add this to the api endpoint)
- the tone configuration should be part of the system prompt to the ai agent, and we should be able to configure this via env vars.
- the SMB owner should be able to call the ai agent when configuration is complete to test the tone. we don't need additional steps for a preview
- the customer business name should come from the businesses api endpoints (should exist right now). the legal disclarimer should be part of the ai_agent api endpooint. (but seem missing right now, we should add), and it should be just a sentence, will be guarded by the front-end web ui to limit its length
- the 5 questoins should comme from the ai_agent api (should exist right now) customquestions. it may be more than 5, we should allow as many questions as the api provide. the front-end web ui will limit the number of questions to a set number.
- we should not push for caller's name or any answers that the caller is not willing to provide. but we must make sure we ask them to the caller

Agent Customization - Conversation:
- 1-800 caller, we shuold not pick the calls if we detect from the twilio call info it's a 1-800 call. I think this is possible with twilio, to check if the caller is a 1-800 call then decide to pick up or not.
- I'll leave the temporary storage for the dev team to decide, the goal for this temporary storage is to save the call transcriptions during the call. and post the complete conversation transcript (separated by roles, "agent:"xxx", caller:"xxx", agent: "xxx") to the web backend when the call is over. after the call logs are successfully posted to webbackend, we should delete the temporary storage.
- "detect sales conversation and hang-up" we should leave this up to the AI model, what we need is to design a specific part of the system prompt so that the AI model can make the decision.

Agent Customization - FAQ:
- the 20 FAQs should come from the ai_agent api endpoint (but missing right now, i think), we should add this to the api endpoint. the SMB owner will input these FAQs in the web ui. the ai agent will use these FAQs to answer the caller's questions.
- we should provide the FAQ to the AI model in the system prompt (for now, we just use system prompt, if necessary later, we can think about set up RAG system for the AI agent).
- if the caller ask any things that are not in the FAQ, we should tell the caller we don't have the answer but will document the questions and send them to the SMB owner.

Technical Stack Requirements:
- other security measures: should be miminal assuming the AI agent and webbackend will locate in the same private network isolated from the public access ( especialy the ai agent, it will only be accessible by the twilio api and the webbackend). all communication should be well-defined api calls with clear json data format.
- no encryptions at our AI agent application level
- think about any non-functional requirements for this AI agent. i'm not expert on this