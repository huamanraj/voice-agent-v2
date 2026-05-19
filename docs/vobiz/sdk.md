> ## Documentation Index
> Fetch the complete documentation index at: https://docs.vobiz.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Voice XML Streaming WebSockets

> Stream raw phone call audio over WebSocket directly to your AI pipeline on Vobiz - the most direct, cost-effective alternative to SIP trunking at scale.

Instead of routing calls through a SIP signaling layer to a platform like LiveKit, you instruct Vobiz to answer the call directly and **stream the raw audio over a standard WebSocket connection straight to your server**. Your server is the AI pipeline.

This is the lowest-level, most direct integration path available. No third-party platform sits between Vobiz and your code. Every byte of audio is yours to process however you choose - which means maximum control, minimum cost, and full responsibility for everything that connects the pieces.

<Info>
  **Key Insight:** Voice XML streaming is not a replacement for SIP - it is a different integration layer entirely. SIP handles call routing and control at the telephony layer. WebSocket streaming handles audio delivery at the application layer. You can use both in the same architecture (e.g., SIP to route the call to Vobiz, then VoiceXML streaming to pipe audio to your Python server).
</Info>

## How WebSocket streaming works

When an inbound call arrives at Vobiz, the platform needs to know what to do with it. With Voice XML streaming, you configure a webhook URL that Vobiz fetches, which returns a VoiceXML document containing a `<Stream>` directive. This tells Vobiz: *"Connect this call to my WebSocket server and start streaming audio."*

```xml The VoiceXML directive that starts WebSocket streaming theme={null}
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak voice="WOMAN" language="en-US">
    </Speak>
    <Stream>
wss://yourapp.com/ws
    </Stream>
</Response>
```

Once Vobiz receives this directive, it establishes a WebSocket connection to your server and begins forwarding the caller's audio in real time. Simultaneously, any audio your server sends back over the same WebSocket is played to the caller. The connection is bidirectional and persistent for the entire duration of the call.

```text WebSocket Audio Pipeline Flow theme={null}
PSTN          Caller dials your Vobiz DID number
              ↳ Vobiz fetches your webhook URL → receives VoiceXML <Stream> directive

Vobiz         Opens WebSocket to wss://your-server.com/ws
              ↳ Sends "connected" + "start" JSON messages with call metadata
              ↳ Streams raw audio as "media" messages (base64 µ-law, 20ms chunks)

Your Server   Receives audio → STT → LLM → TTS → sends audio back via WebSocket
(AI Pipeline) ↳ Vobiz plays returned audio to caller in real time

PSTN          Caller hears your AI agent's voice response
```

### WebSocket message types

All messages over the WebSocket connection are JSON. There are five event types your server will receive, and one type you will send back:

| Event       | Direction      | Description                                                                                                                                                                                                                                |
| ----------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `connected` | Receive        | Sent immediately when the WebSocket connection is established. Contains the WebSocket protocol version. No call-specific data yet.                                                                                                         |
| `start`     | Receive        | Sent once when the audio stream begins. Contains the StreamSid (unique stream identifier), CallSid, and any custom parameters you configured on the Stream directive. This is where you initialize your per-call state.                    |
| `media`     | Receive + Send | The audio data itself. Received continuously while the caller is speaking. Contains a base64-encoded payload of G.711 µ-law audio at 8kHz. To send audio to the caller, you send the same format back with the StreamSid.                  |
| `dtmf`      | Receive        | Sent when the caller presses a phone key (0–9, \*, #). Contains the digit pressed. Important: DTMF tones are detected by Vobiz and delivered as discrete events - they do NOT appear in the audio stream. You must handle this separately. |
| `stop`      | Receive        | Sent when the call ends (caller hangs up, or the call is terminated programmatically). After receiving this, the WebSocket connection will close. Clean up all per-call resources here.                                                    |

### G.711 µ-law: the audio encoding

Every audio payload arriving from Vobiz (and that you must send back) is encoded as **G.711 µ-law (PCMU)**. This is not an arbitrary choice - it is the standard audio encoding of the global telephone network, and has been since the 1960s. Understanding what it is, and why your AI models cannot use it directly, is essential.

<CardGroup cols={3}>
  <Card title="Sample Rate" icon="wave-sine">
    **8,000 Hz** - Telephone-quality (narrow band). Human voice is 300–3400 Hz. Sufficient for intelligibility but poor for high-fidelity synthesis.
  </Card>

  <Card title="Bit Depth" icon="layer-group">
    **8 bits / sample** - After companding (non-linear compression). Equivalent to \~12 bits of linear PCM in perceived dynamic range.
  </Card>

  <Card title="Bitrate" icon="gauge">
    **64 kbps** - 8,000 samples/sec × 8 bits = 64,000 bits/sec. Delivered in precise 20ms frames = 160 bytes per packet.
  </Card>
</CardGroup>

The **µ (mu) in µ-law** refers to a logarithmic companding function that applies non-linear compression to the audio signal before encoding. This gives more dynamic range resolution to quiet sounds and compresses loud sounds. It is not standard PCM - you cannot feed µ-law bytes directly to a speech recognition model.

<Warning>
  **Why this matters:** When Vobiz sends you audio, it arrives base64-encoded in JSON. Before your STT model can process it, you must: (1) base64-decode it, (2) decode µ-law to linear 16-bit PCM, (3) upsample from 8kHz to 16kHz (or whatever rate your STT model expects). Before sending audio back, you must reverse the chain. Frameworks like Pipecat handle this automatically via serializers.
</Warning>

### The audio conversion pipeline

Every WebSocket voice AI implementation involves this conversion chain on both the inbound and outbound paths. Understanding each step prevents the most common bugs: distorted audio, incorrect volume levels, and desynchronized playback.

<CardGroup cols={2}>
  <Card title="Inbound - Caller → JSON → AI Pipeline" icon="arrow-down">
    1. **Receive JSON** - `media` event with base64 payload
    2. **Base64 Decode** - String → bytes (µ-law)
    3. **Decode µ-law** - 8-bit µ-law → 16-bit PCM (8kHz)
    4. **Resample** - 8kHz → 16kHz/24kHz PCM
    5. **Feed STT** - Stream to STT engine explicitly
  </Card>

  <Card title="Outbound - AI Response → JSON → Caller" icon="arrow-up">
    1. **Generate Audio** - TTS engine returns 16kHz/24kHz PCM
    2. **Resample** - 16kHz/24kHz → 8kHz PCM
    3. **Encode µ-law** - 16-bit 8kHz PCM → 8-bit µ-law
    4. **Base64 Encode** - µ-law bytes → base64 string
    5. **Send JSON** - Transmit `{"event":"media"}` over wss
  </Card>
</CardGroup>

<Note>
  Python's built-in `audioop` module handles µ-law conversion and resampling natively. Functions like `audioop.ulaw2lin()` and `audioop.ratecv()` perform companding and sample-rate conversion. Pipecat's serializers handle all of this automatically.
</Note>

## Advantages

* **No Third-Party Platform Cost** - There is no LiveKit, VAPI, or Retell layer. You pay Vobiz for the channel and the raw AI API costs (STT, LLM, TTS). At scale, this is a significant cost difference.
* **Direct AI Model Integration** - Deepgram, OpenAI, Anthropic, and Cartesia all natively consume and produce WebSocket audio streams. Your Vobiz stream connects almost directly without additional SDK abstractions in between.
* **Full Pipeline Control** - Every byte of audio flows through your code. You can implement custom VAD logic, custom barge-in states, and bespoke routing trees.
* **Easiest to Debug Locally** - A WebSocket server is just a web server. Test locally with ngrok and inspect messages in browser DevTools. SIP debugging requires specialized tools like Wireshark.
* **Familiar Technology Stack** - WebSockets are standard web technologies. Any Python, Node.js, or Go developer can work with them without needing to master legacy SIP headers and RTP setups.
* **No IP Allowlisting Required** - Authentication happens at the connection level via URL parameters or headers - simpler than IP-based ACLs that break when provider networks change.

## Disadvantages

* **One Stateful Connection Per Call** - You own the state. 100 concurrent calls means 100 simultaneously open sockets, each maintaining its own context buffer. Crashing mid-call destroys that call's state immediately.
* **Barge-In Requires Implementation** - Getting AI interruptions right requires orchestrating VAD thresholds, aborting in-flight TTS playback, flushing buffers, and resetting logic - all of which is complex to implement correctly.
* **Turn Detection is Extremely Hard** - Separating sentence pauses from true turn handovers requires locally running machine learning models (such as Silero VAD) to avoid false-positive interruptions triggered by background noise.
* **Conversion Chain Complexity** - The µ-law → PCM → AI conversion cycle is unforgiving about byte matching. Wrong endianness or sample-rate mismatches produce severely distorted static with no clear error logs.
* **TCP vs. UDP Protocol Tradeoffs** - WebSockets use reliable TCP, which guarantees delivery but introduces head-of-line blocking. If an audio packet stalls, TCP retransmission delays all subsequent packets, injecting jitter where UDP would simply drop and move on.
* **No Enterprise PBX Out-of-the-Box** - Large corporate phone infrastructures (Avaya, Teams) do not natively support WebSocket streams. If PBX integration is a hard requirement, you will need a SIP trunk architecture.

## Pipecat integration

**Pipecat** (open-source, from Daily.co) is the leading Python framework for building WebSocket-based voice pipelines. It provides abstractions that make streaming architectures production-viable - handling audio conversion, pipeline orchestration, VAD, and barge-in logic for you.

### Pipeline Architecture

Pipecat models a voice call as a linear chain of processors. Each processor receives **frames** (audio, text, control markers) and passes outputs downstream - a clean mapping of voice pipeline concepts.

```text Conceptual Pipecat pipeline theme={null}
transport.input()
  ↓ AudioRawFrame (µ-law from Vobiz)
stt    # e.g. DeepgramSTTService
  ↓ TranscriptionFrame (text)
llm    # e.g. OpenAILLMService
  ↓ TextFrame (response tokens)
tts    # e.g. ElevenLabsTTSService
  ↓ AudioRawFrame (PCM)
transport.output()
```

### Vobiz Serializer

The `VobizFrameSerializer` handles all base64 decoding, µ-law ↔ PCM conversion, and Vobiz-specific JSON message framing automatically - so your pipeline receives clean audio frames with no manual conversion code.

### Built-in VAD

Integrates a pre-calibrated Silero VAD model out of the box. It suppresses false positives and triggers TTS cancellation immediately, producing smooth conversational turn-taking.

<Warning>
  **Important Constraints:** Pipecat's `WebSocketServerTransport` handles **one active connection per process**. If multiple callers connect simultaneously, you must run a separate Pipecat worker for each one - for example, using independent process pools or Docker containers. A single server cannot handle two concurrent WebSocket streams.
</Warning>

[Read Pipecat Guide](/integrations/pipecat)

## Direct Python + Vobiz

The alternative is to run a bare ASGI/WSGI server and own every encoding layer yourself. This gives maximum flexibility but significantly increases implementation complexity.

<CardGroup cols={2}>
  <Card title="Framework Heavy Lifting" icon="circle-check">
    * Automatic µ-law bindings
    * Base64 decode array loops
    * STT module synchronicity
    * Silero threshold tweaking
    * Turn-detection history states
  </Card>

  <Card title="Bare-Metal Responsibilities" icon="screwdriver-wrench">
    * Asyncio multiplexer state trees
    * Buffer bit-math equations
    * Latency compensation code
    * In-flight manual TTS pausing
    * DTMF intercept flags
  </Card>
</CardGroup>

### When extreme control matters

<Steps>
  <Step title="Highly Custom Pipelines">
    Building experimental multimodal architectures not yet supported by open-source serialization frameworks.
  </Step>

  <Step title="Existing FastAPI Monolith">
    Adding WebSocket endpoints directly to a large existing Python API without introducing a separate orchestration tool.
  </Step>

  <Step title="Millisecond-Precision Audio">
    Injecting specific IVR prompts at precise points in a call where pipeline abstraction layers add unacceptable latency.
  </Step>
</Steps>

## Key implementation factors

<CardGroup cols={2}>
  <Card title="Development Complexity" icon="bolt">
    **Medium (Pipecat) / High (Bare-Metal)** - With Pipecat, a working voice agent can be built in hours. Bare-metal Python requires implementing all byte manipulation and encoding logic manually.
  </Card>

  <Card title="Cost" icon="dollar-sign">
    **Minimum Overhead** - Your costs are limited to Vobiz channel minutes and your AI API calls (STT, LLM, TTS). There is no intermediary platform fee. This makes the approach attractive at scale.
  </Card>

  <Card title="Time to First Call" icon="clock">
    **2–4 hours (Pipecat)** - Using a framework, you can validate end-to-end connectivity and get live audio transcribing within a single afternoon.
  </Card>

  <Card title="Connection Latency" icon="microchip">
    **Near-instant link + 20ms audio frames** - Without a SIP handshake, WebSocket calls become active faster. End-to-end latency then depends on your AI API response times.
  </Card>

  <Card title="Scaling Model" icon="server">
    **One process per call** - Each active call holds an open WebSocket connection with its own state. Horizontal scaling under high load is more operationally intensive than a typical SIP architecture.
  </Card>
</CardGroup>

## Common developer pitfalls

<Warning>
  **01. Sending Large Audio Chunks**

  Flushing a large TTS response as a single payload into a socket designed for 20ms frames can overwhelm the platform and cause packet rejections. Send audio in small, evenly-spaced chunks.
</Warning>

<Warning>
  **02. Byte-Order Mismatches**

  Python structures data in little-endian format by default. If a downstream model or endpoint requires big-endian audio, the result is static - and there is typically no clear error message. Verify byte order at each handoff.
</Warning>

<Warning>
  **03. Memory Leaks on Disconnect**

  If you do not explicitly clean up async STT generators and buffers when the WebSocket `stop` event arrives, long-running servers will accumulate memory over time until they crash.
</Warning>

<Warning>
  **04. Concurrent Writes to One Socket**

  If multiple async tasks write to the same WebSocket output simultaneously, you will get write collision errors. Use a dedicated output queue or lock to serialize all outbound writes.
</Warning>

<Warning>
  **05. VAD False Positives from Ambient Audio**

  Simple energy-based VAD fails in noisy environments (television, sirens) and will continuously cancel outgoing TTS responses. Use a trained VAD model such as Silero to distinguish speech from noise.
</Warning>

<Warning>
  **06. DTMF Injected into the Audio Stream**

  DTMF tones embedded in raw audio break transcription. Vobiz detects and delivers DTMF as discrete events - handle them via the `dtmf` event type only, never from the audio stream.
</Warning>

## When to choose WebSocket streaming

<CardGroup cols={3}>
  <Card title="Strict Cost Objectives" icon="circle-check">
    Eliminates intermediary platform fees, keeping costs to Vobiz channel minutes and direct AI API usage.
  </Card>

  <Card title="Custom AI Architecture" icon="circle-check">
    Gives you full ownership of every processing step - audio encoding, VAD thresholds, pipeline branching, and state management.
  </Card>

  <Card title="Pipecat-Based Builds" icon="circle-check">
    Pipecat is designed around WebSocket transport, making it a natural fit for this integration path.
  </Card>

  <Card title="Rapid Prototyping" icon="circle-check">
    A WebSocket server is easy to run locally with ngrok, making it straightforward to get a working demo live quickly.
  </Card>

  <Card title="No Live Transfer Required" icon="circle-check">
    If your use case involves single, self-contained conversations without live call transfers, WebSocket streaming is sufficient.
  </Card>

  <Card title="Web-Centric Team" icon="circle-check">
    Python and JavaScript developers can work with WebSockets comfortably without needing to learn SIP or RTP.
  </Card>
</CardGroup>

<Tip>
  **Need PBX integration or live call transfers?** If enterprise PBX connectivity, LiveKit routing, or VAPI integration are hard requirements, review the SIP architecture. [Compare SIP vs WebSockets](/concepts/sip-vs-websockets)
</Tip>

## What developers usually do next

<CardGroup cols={2}>
  <Card title="SIP Trunking" icon="phone" href="/concepts/sip-trunking">
    Deep dive on the telephony-layer alternative
  </Card>

  <Card title="SIP vs WebSockets" icon="scale-balanced" href="/concepts/sip-vs-websockets">
    Full decision matrix - 10 factors, real latency numbers
  </Card>

  <Card title="Pipecat Integration" icon="plug" href="/integrations/pipecat">
    Open-source Python framework for WSS pipelines
  </Card>

  <Card title="Direct WebSocket Setup" icon="code" href="/integrations/websockets">
    Bare-metal Python WebSocket handler against Vobiz
  </Card>
</CardGroup>