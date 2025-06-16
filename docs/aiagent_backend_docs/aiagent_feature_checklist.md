
# AI Agent Capability Checklist

## General Capabilities
- must be able to take calls from twilio, and stream to twilio call with audio in real-time 
- must be able to connect to gemini 2.0 live model on vertex AI through Google ADK, and stream real-time audio from twilio call to it, and stream real-time audio from it to twilio call
- must not maintain its own database, the AI agent should be stateless, all necessary data should be retreieved fromt the webbackend
- must not make any out-going calls from the AI agent, it should only answer incoming calls

## Authentication
- must be able authenticate with webbackend to get information

## Telephony interaction
- must be able to pull the call recording for the call from twilio, and save it to a permanent storage, then post the link to the webbackend when the call is over
- must be able to hang-up calls when necessary, not wait for the caller to hang-up
- must be able to follow a pre-configured max time to maintain a call, when the time is up, the call will be ended automatically

## Agent customization

### Basic
- must be able to be configured to use a pre-configured Name to refer to the agent herself
- must be able to be configured to adapt her tone: causual, cheerful, formal
- must be able to initiate conversation with caller, without waiting the caller to speak first
- must be able to be configured to use a specific greeting message (including customer business name, name of herself, and preconfigured legal disclaimer)
- must be able to collect caller's name and other up to 5 questions defined by th customer

### Conversation
- must be able to save transcriptions of both caller and agent, and save them to a temporary storage during call, and post the complete conversation transcription (separated by roles, """ agent:"xxx", caller:"xxx", agent: "xxx" """) to the webbackend when the call is over

### Spam
- must be able to block 1-800 callers
- must be able to detect sales conversation and hang-up

### FAQ
- must be able to take a list of up to 20 FAQs, and answer caller accordingly

## Technical Stack Requirements
- must be written in python 3.12
- must use Google ADK for AI agent setup
- must use model "gemini-2.0-flash-live-preview-04-09" from vertex AI
- must use google cloud storage for permanent storage
- must use twilio for telephony interaction
- must be a fastapi backend that has rate limiter and other necessary security measures

## Logging
- must use structured logging
- must log all errors
- must log all incoming calls information whether we pick it up or not

