Agent Customization - Spam:
- no whitelist for now
- we don't need a specific message, just add instructions in the system prompt for the AI model to interrupt the conversation if it detects a sales conversation and politely refuse anyhing offered by the caller and then hang-up immediately
- we should be almost 100% sure the call is a sales call then hang-up immediately, to minimize false positive.

Logging:
- we don't need anything special, follow state-of-the-art logging practices. and use best practices
- log all available info from twilio for the calls (whether we pick up or not) 
- you can define reasons for not picking up and put it in logging
- just use standard logging, not redirections for now

API Schema Confirmation - Call Logs:
- what we have here is the complete api docs. if things are missing, please document them, and we need to provide to the webbackend team to implement