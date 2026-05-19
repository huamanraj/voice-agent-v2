# WebSocket

GET /text-to-speech/ws

WebSocket channel for real-time TTS synthesis.

**Note:** This API Reference page is provided for informational purposes only. 
The Try It playground may not provide the best experience for streaming audio. 
For optimal streaming performance, please use the SDK or implement your own WebSocket client.

**Model-Specific Notes:**
- **bulbul:v2:** Supports pitch, loudness, pace (0.3-3.0). Default sample rate: 22050 Hz.
- **bulbul:v3:** Does NOT support pitch/loudness. Pace range: 0.5-2.0. Supports temperature parameter. Default sample rate: 24000 Hz. Preprocessing is always enabled.


Reference: https://docs.sarvam.ai/api-reference-docs/text-to-speech/stream

## AsyncAPI Specification

```yaml
asyncapi: 2.6.0
info:
  title: textToSpeechStreaming
  version: subpackage_textToSpeechStreaming.textToSpeechStreaming
  description: >
    WebSocket channel for real-time TTS synthesis.


    **Note:** This API Reference page is provided for informational purposes
    only. 

    The Try It playground may not provide the best experience for streaming
    audio. 

    For optimal streaming performance, please use the SDK or implement your own
    WebSocket client.


    **Model-Specific Notes:**

    - **bulbul:v2:** Supports pitch, loudness, pace (0.3-3.0). Default sample
    rate: 22050 Hz.

    - **bulbul:v3:** Does NOT support pitch/loudness. Pace range: 0.5-2.0.
    Supports temperature parameter. Default sample rate: 24000 Hz. Preprocessing
    is always enabled.
channels:
  /text-to-speech/ws:
    description: >
      WebSocket channel for real-time TTS synthesis.


      **Note:** This API Reference page is provided for informational purposes
      only. 

      The Try It playground may not provide the best experience for streaming
      audio. 

      For optimal streaming performance, please use the SDK or implement your
      own WebSocket client.


      **Model-Specific Notes:**

      - **bulbul:v2:** Supports pitch, loudness, pace (0.3-3.0). Default sample
      rate: 22050 Hz.

      - **bulbul:v3:** Does NOT support pitch/loudness. Pace range: 0.5-2.0.
      Supports temperature parameter. Default sample rate: 24000 Hz.
      Preprocessing is always enabled.
    bindings:
      ws:
        query:
          type: object
          properties:
            model:
              $ref: '#/components/schemas/textToSpeechStreaming_model'
              default: bulbul:v2
            send_completion_event:
              $ref: '#/components/schemas/textToSpeechStreaming_send_completion_event'
              default: 'true'
        headers:
          type: object
          properties:
            Api-Subscription-Key:
              type: string
    publish:
      operationId: text-to-speech-streaming-publish
      summary: Server messages
      message:
        oneOf:
          - $ref: >-
              #/components/messages/subpackage_textToSpeechStreaming.textToSpeechStreaming-server-0-Audio
              Output
          - $ref: >-
              #/components/messages/subpackage_textToSpeechStreaming.textToSpeechStreaming-server-1-Event
              Notification
          - $ref: >-
              #/components/messages/subpackage_textToSpeechStreaming.textToSpeechStreaming-server-2-Error
              Response
    subscribe:
      operationId: text-to-speech-streaming-subscribe
      summary: Client messages
      message:
        oneOf:
          - $ref: >-
              #/components/messages/subpackage_textToSpeechStreaming.textToSpeechStreaming-client-0-Configure
              Connection
          - $ref: >-
              #/components/messages/subpackage_textToSpeechStreaming.textToSpeechStreaming-client-1-Send
              Text
          - $ref: >-
              #/components/messages/subpackage_textToSpeechStreaming.textToSpeechStreaming-client-2-Flush
              Signal
          - $ref: >-
              #/components/messages/subpackage_textToSpeechStreaming.textToSpeechStreaming-client-3-Ping
              Signal
servers:
  Production:
    url: wss://api.sarvam.ai/
    protocol: wss
    x-default: true
components:
  messages:
    subpackage_textToSpeechStreaming.textToSpeechStreaming-server-0-Audio Output:
      name: Audio Output
      title: Audio Output
      description: Receive audio chunks from the TTS WebSocket.
      payload:
        $ref: '#/components/schemas/textToSpeechStreaming_AudioOutput'
    subpackage_textToSpeechStreaming.textToSpeechStreaming-server-1-Event Notification:
      name: Event Notification
      title: Event Notification
      description: >-
        Receive completion event notifications from the TTS WebSocket (if
        send_completion_event is enabled)
      payload:
        $ref: '#/components/schemas/textToSpeechStreaming_EventResponse'
    subpackage_textToSpeechStreaming.textToSpeechStreaming-server-2-Error Response:
      name: Error Response
      title: Error Response
      description: Receive error messages from the TTS WebSocket
      payload:
        $ref: '#/components/schemas/textToSpeechStreaming_ErrorResponse'
    subpackage_textToSpeechStreaming.textToSpeechStreaming-client-0-Configure Connection:
      name: Configure Connection
      title: Configure Connection
      description: Send initial configuration for text-to-speech streaming
      payload:
        $ref: '#/components/schemas/textToSpeechStreaming_ConfigureConnection'
    subpackage_textToSpeechStreaming.textToSpeechStreaming-client-1-Send Text:
      name: Send Text
      title: Send Text
      description: Send text chunk for speech synthesis
      payload:
        $ref: '#/components/schemas/textToSpeechStreaming_SendText'
    subpackage_textToSpeechStreaming.textToSpeechStreaming-client-2-Flush Signal:
      name: Flush Signal
      title: Flush Signal
      description: Send signal to end text streaming.
      payload:
        $ref: '#/components/schemas/textToSpeechStreaming_FlushSignal'
    subpackage_textToSpeechStreaming.textToSpeechStreaming-client-3-Ping Signal:
      name: Ping Signal
      title: Ping Signal
      description: Send ping signal to keep the TTS WebSocket connection alive.
      payload:
        $ref: '#/components/schemas/textToSpeechStreaming_PingSignal'
  schemas:
    textToSpeechStreaming_model:
      type: string
      enum:
        - bulbul:v2
        - bulbul:v3
      default: bulbul:v2
      description: >
        Text to speech model to use.

        - **bulbul:v2** (default): Standard TTS model with pitch/loudness
        support

        - **bulbul:v3**: Advanced model with temperature control (no
        pitch/loudness)
      title: textToSpeechStreaming_model
    textToSpeechStreaming_send_completion_event:
      type: string
      enum:
        - 'true'
        - 'false'
      default: 'true'
      description: >-
        Enable completion event notifications when TTS generation finishes. When
        set to true, an event message will be sent when the final audio chunk
        has been generated.
      title: textToSpeechStreaming_send_completion_event
    ChannelsTextToSpeechStreamingMessagesAudioOutputType:
      type: string
      enum:
        - audio
      title: ChannelsTextToSpeechStreamingMessagesAudioOutputType
    ChannelsTextToSpeechStreamingMessagesAudioOutputData:
      type: object
      properties:
        content_type:
          type: string
          description: MIME type of the audio content (e.g., 'audio/mp3', 'audio/wav')
        audio:
          type: string
          format: base64
          description: Base64-encoded audio data ready for playback or download
        request_id:
          type: string
          description: Unique identifier for the request
      required:
        - content_type
        - audio
      title: ChannelsTextToSpeechStreamingMessagesAudioOutputData
    textToSpeechStreaming_AudioOutput:
      type: object
      properties:
        type:
          $ref: >-
            #/components/schemas/ChannelsTextToSpeechStreamingMessagesAudioOutputType
        data:
          $ref: >-
            #/components/schemas/ChannelsTextToSpeechStreamingMessagesAudioOutputData
      required:
        - type
        - data
      title: textToSpeechStreaming_AudioOutput
    ChannelsTextToSpeechStreamingMessagesEventResponseType:
      type: string
      enum:
        - event
      description: Message type identifier for events
      title: ChannelsTextToSpeechStreamingMessagesEventResponseType
    ChannelsTextToSpeechStreamingMessagesEventResponseDataEventType:
      type: string
      enum:
        - final
      description: Type of event that occurred
      title: ChannelsTextToSpeechStreamingMessagesEventResponseDataEventType
    ChannelsTextToSpeechStreamingMessagesEventResponseData:
      type: object
      properties:
        event_type:
          $ref: >-
            #/components/schemas/ChannelsTextToSpeechStreamingMessagesEventResponseDataEventType
          description: Type of event that occurred
        message:
          type: string
          description: Human-readable description of the event
        timestamp:
          type: string
          format: date-time
          description: ISO 8601 timestamp when the event occurred
      required:
        - event_type
      title: ChannelsTextToSpeechStreamingMessagesEventResponseData
    textToSpeechStreaming_EventResponse:
      type: object
      properties:
        type:
          $ref: >-
            #/components/schemas/ChannelsTextToSpeechStreamingMessagesEventResponseType
          description: Message type identifier for events
        data:
          $ref: >-
            #/components/schemas/ChannelsTextToSpeechStreamingMessagesEventResponseData
      required:
        - type
        - data
      description: >-
        Event notification message sent when specific events occur during TTS
        processing
      title: textToSpeechStreaming_EventResponse
    ChannelsTextToSpeechStreamingMessagesErrorResponseType:
      type: string
      enum:
        - error
      title: ChannelsTextToSpeechStreamingMessagesErrorResponseType
    ChannelsTextToSpeechStreamingMessagesErrorResponseData:
      type: object
      properties:
        message:
          type: string
        code:
          type: integer
          description: Optional error code for programmatic error handling
        details:
          type: object
          additionalProperties:
            description: Any type
          description: Additional error details and context information
        request_id:
          type: string
          description: Unique identifier for the request
      required:
        - message
      title: ChannelsTextToSpeechStreamingMessagesErrorResponseData
    textToSpeechStreaming_ErrorResponse:
      type: object
      properties:
        type:
          $ref: >-
            #/components/schemas/ChannelsTextToSpeechStreamingMessagesErrorResponseType
        data:
          $ref: >-
            #/components/schemas/ChannelsTextToSpeechStreamingMessagesErrorResponseData
      required:
        - type
        - data
      title: textToSpeechStreaming_ErrorResponse
    ChannelsTextToSpeechStreamingMessagesConfigureConnectionType:
      type: string
      enum:
        - config
      title: ChannelsTextToSpeechStreamingMessagesConfigureConnectionType
    ChannelsTextToSpeechStreamingMessagesConfigureConnectionDataModel:
      type: string
      enum:
        - bulbul:v2
        - bulbul:v3
      default: bulbul:v2
      description: >
        Specifies the model to use for text-to-speech conversion.

        - **bulbul:v2** (default): Standard TTS model with pitch/loudness
        support

        - **bulbul:v3**: Advanced model with temperature control (no
        pitch/loudness)
      title: ChannelsTextToSpeechStreamingMessagesConfigureConnectionDataModel
    ChannelsTextToSpeechStreamingMessagesConfigureConnectionDataTargetLanguageCode:
      type: string
      enum:
        - bn-IN
        - en-IN
        - gu-IN
        - hi-IN
        - kn-IN
        - ml-IN
        - mr-IN
        - od-IN
        - pa-IN
        - ta-IN
        - te-IN
      description: The language of the text in BCP-47 format
      title: >-
        ChannelsTextToSpeechStreamingMessagesConfigureConnectionDataTargetLanguageCode
    ChannelsTextToSpeechStreamingMessagesConfigureConnectionDataSpeaker:
      type: string
      enum:
        - anushka
        - abhilash
        - manisha
        - vidya
        - arya
        - karun
        - hitesh
        - aditya
        - ritu
        - priya
        - neha
        - rahul
        - pooja
        - rohan
        - simran
        - kavya
        - amit
        - dev
        - ishita
        - shreya
        - ratan
        - varun
        - manan
        - sumit
        - roopa
        - kabir
        - aayan
        - shubh
        - ashutosh
        - advait
        - amelia
        - sophia
      default: anushka
      description: >
        The speaker voice to be used for the output audio.


        **Model Compatibility:**

        - **bulbul:v2:** anushka (default), abhilash, manisha, vidya, arya,
        karun, hitesh

        - **bulbul:v3:** aditya (default), ritu, priya, neha, rahul, pooja,
        rohan, simran, kavya, amit, dev, ishita, shreya, ratan, varun, manan,
        sumit, roopa, kabir, aayan, shubh, ashutosh, advait, amelia, sophia


        **Note:** Speaker selection must match the chosen model version.
      title: ChannelsTextToSpeechStreamingMessagesConfigureConnectionDataSpeaker
    ChannelsTextToSpeechStreamingMessagesConfigureConnectionDataSpeechSampleRate:
      type: string
      enum:
        - '8000'
        - '16000'
        - '22050'
        - '24000'
      description: |
        Specifies the sample rate of the output audio. Supported values are 
        8000, 16000, 22050, 24000 Hz.

        **Model-specific defaults:**
        - **bulbul:v2:** 22050 Hz
        - **bulbul:v3:** 24000 Hz
      title: >-
        ChannelsTextToSpeechStreamingMessagesConfigureConnectionDataSpeechSampleRate
    ChannelsTextToSpeechStreamingMessagesConfigureConnectionDataOutputAudioCodec:
      type: string
      enum:
        - linear16
        - mulaw
        - alaw
        - opus
        - flac
        - aac
        - wav
        - mp3
      default: mp3
      description: >-
        Audio codec (currently supports MP3 only, optimized for real-time
        playback)
      title: >-
        ChannelsTextToSpeechStreamingMessagesConfigureConnectionDataOutputAudioCodec
    ChannelsTextToSpeechStreamingMessagesConfigureConnectionDataOutputAudioBitrate:
      type: string
      enum:
        - 32k
        - 64k
        - 96k
        - 128k
        - 192k
      default: 128k
      description: Audio bitrate (choose from 5 supported bitrate options)
      title: >-
        ChannelsTextToSpeechStreamingMessagesConfigureConnectionDataOutputAudioBitrate
    ChannelsTextToSpeechStreamingMessagesConfigureConnectionData:
      type: object
      properties:
        model:
          $ref: >-
            #/components/schemas/ChannelsTextToSpeechStreamingMessagesConfigureConnectionDataModel
          default: bulbul:v2
          description: >
            Specifies the model to use for text-to-speech conversion.

            - **bulbul:v2** (default): Standard TTS model with pitch/loudness
            support

            - **bulbul:v3**: Advanced model with temperature control (no
            pitch/loudness)
        target_language_code:
          $ref: >-
            #/components/schemas/ChannelsTextToSpeechStreamingMessagesConfigureConnectionDataTargetLanguageCode
          description: The language of the text in BCP-47 format
        speaker:
          $ref: >-
            #/components/schemas/ChannelsTextToSpeechStreamingMessagesConfigureConnectionDataSpeaker
          description: >
            The speaker voice to be used for the output audio.


            **Model Compatibility:**

            - **bulbul:v2:** anushka (default), abhilash, manisha, vidya, arya,
            karun, hitesh

            - **bulbul:v3:** aditya (default), ritu, priya, neha, rahul, pooja,
            rohan, simran, kavya, amit, dev, ishita, shreya, ratan, varun,
            manan, sumit, roopa, kabir, aayan, shubh, ashutosh, advait, amelia,
            sophia


            **Note:** Speaker selection must match the chosen model version.
        pitch:
          type: number
          format: double
          default: 0
          description: >
            Controls the pitch of the audio. Lower values result in a deeper
            voice, 

            while higher values make it sharper. The suitable range is between
            -0.75 

            and 0.75. Default is 0.0.


            **Note:** NOT supported for bulbul:v3. Will be ignored if provided.
        pace:
          type: number
          format: double
          default: 1
          description: >
            Controls the speed of the audio. Lower values result in slower
            speech, 

            while higher values make it faster. Default is 1.0.


            **Model-specific ranges:**

            - **bulbul:v2:** 0.3 to 3.0

            - **bulbul:v3:** 0.5 to 2.0
        loudness:
          type: number
          format: double
          default: 1
          description: >
            Controls the loudness of the audio. Lower values result in quieter
            audio, 

            while higher values make it louder. The suitable range is between
            0.3 

            and 3.0. Default is 1.0.


            **Note:** NOT supported for bulbul:v3. Will be ignored if provided.
        temperature:
          type: number
          format: double
          default: 0.6
          description: >
            Controls the randomness of the output. Lower values make the output
            more 

            focused and deterministic, while higher values make it more random. 

            The suitable range is between 0.01 and 1.0. Default is 0.6.


            **Note:** Only supported for bulbul:v3. Will be ignored for
            bulbul:v2.
        speech_sample_rate:
          $ref: >-
            #/components/schemas/ChannelsTextToSpeechStreamingMessagesConfigureConnectionDataSpeechSampleRate
          default: 22050
          description: |
            Specifies the sample rate of the output audio. Supported values are 
            8000, 16000, 22050, 24000 Hz.

            **Model-specific defaults:**
            - **bulbul:v2:** 22050 Hz
            - **bulbul:v3:** 24000 Hz
        enable_preprocessing:
          type: boolean
          default: false
          description: >
            Controls whether normalization of English words and numeric
            entities 

            (e.g., numbers, dates) is performed. Set to true for better
            handling 

            of mixed-language text.


            **Model-specific defaults:**

            - **bulbul:v2:** false (optional)

            - **bulbul:v3:** Always enabled (cannot be disabled)
        output_audio_codec:
          $ref: >-
            #/components/schemas/ChannelsTextToSpeechStreamingMessagesConfigureConnectionDataOutputAudioCodec
          default: mp3
          description: >-
            Audio codec (currently supports MP3 only, optimized for real-time
            playback)
        output_audio_bitrate:
          $ref: >-
            #/components/schemas/ChannelsTextToSpeechStreamingMessagesConfigureConnectionDataOutputAudioBitrate
          default: 128k
          description: Audio bitrate (choose from 5 supported bitrate options)
        dict_id:
          type: string
          description: >
            The ID of a pronunciation dictionary to apply during synthesis. 

            When provided, matching words in the input text will be replaced 

            with their custom pronunciations before generating speech.


            Create and manage dictionaries via the
            `/text-to-speech/pronunciation-dictionary` endpoints.


            **Note:** Only supported by **bulbul:v3**.
        min_buffer_size:
          type: integer
          default: 50
          description: >-
            Minimum character length that triggers buffer flushing for TTS model
            processing
        max_chunk_length:
          type: integer
          default: 150
          description: >-
            Maximum length for sentence splitting (adjust based on content
            length)
      required:
        - target_language_code
        - speaker
      title: ChannelsTextToSpeechStreamingMessagesConfigureConnectionData
    textToSpeechStreaming_ConfigureConnection:
      type: object
      properties:
        type:
          $ref: >-
            #/components/schemas/ChannelsTextToSpeechStreamingMessagesConfigureConnectionType
        data:
          $ref: >-
            #/components/schemas/ChannelsTextToSpeechStreamingMessagesConfigureConnectionData
      required:
        - type
        - data
      description: >
        Configuration message required as the first message after establishing
        the WebSocket connection. 

        This initializes TTS parameters and can be updated at any time during
        the WebSocket lifecycle 

        by sending a new config message. When a config update is sent, any text
        currently in the buffer 

        will be automatically flushed and processed before applying the new
        configuration.


        **Model-Specific Notes:**

        - **bulbul:v2:** Supports pitch, loudness, pace (0.3-3.0). Default
        sample rate: 22050 Hz.

        - **bulbul:v3:** Does NOT support pitch/loudness. Pace range: 0.5-2.0.
        Supports temperature. Default sample rate: 24000 Hz.
      title: textToSpeechStreaming_ConfigureConnection
    ChannelsTextToSpeechStreamingMessagesSendTextType:
      type: string
      enum:
        - text
      title: ChannelsTextToSpeechStreamingMessagesSendTextType
    ChannelsTextToSpeechStreamingMessagesSendTextData:
      type: object
      properties:
        text:
          type: string
      required:
        - text
      title: ChannelsTextToSpeechStreamingMessagesSendTextData
    textToSpeechStreaming_SendText:
      type: object
      properties:
        type:
          $ref: >-
            #/components/schemas/ChannelsTextToSpeechStreamingMessagesSendTextType
        data:
          $ref: >-
            #/components/schemas/ChannelsTextToSpeechStreamingMessagesSendTextData
      required:
        - type
        - data
      title: textToSpeechStreaming_SendText
    ChannelsTextToSpeechStreamingMessagesFlushSignalType:
      type: string
      enum:
        - flush
      default: flush
      title: ChannelsTextToSpeechStreamingMessagesFlushSignalType
    textToSpeechStreaming_FlushSignal:
      type: object
      properties:
        type:
          $ref: >-
            #/components/schemas/ChannelsTextToSpeechStreamingMessagesFlushSignalType
      required:
        - type
      description: >
        Forces the text buffer to process immediately, regardless of the
        min_buffer_size threshold. 

        Use this when you need to process remaining text that hasn't reached the
        minimum buffer size.
      title: textToSpeechStreaming_FlushSignal
    ChannelsTextToSpeechStreamingMessagesPingSignalType:
      type: string
      enum:
        - ping
      default: ping
      title: ChannelsTextToSpeechStreamingMessagesPingSignalType
    textToSpeechStreaming_PingSignal:
      type: object
      properties:
        type:
          $ref: >-
            #/components/schemas/ChannelsTextToSpeechStreamingMessagesPingSignalType
      required:
        - type
      description: >
        Send ping signal to keep the WebSocket connection alive. The connection
        automatically 

        closes after one minute of inactivity.
      title: textToSpeechStreaming_PingSignal

```

---
title: Streaming Text-to-Speech API
description: >-
  Real-time conversion of text into speech using WebSocket connections.
  Efficient streaming for long texts with progressive audio generation and
  low-latency playback.
canonical-url: 'https://docs.sarvam.ai/api-reference-docs/text-to-speech/api/streaming'
'og:title': Streaming Text-to-Speech API - Real-time Voice Synthesis by Sarvam AI
'og:description': >-
  Stream text to speech in real-time with Sarvam AI's WebSocket API. Progressive
  audio generation for long texts with low-latency and efficient processing.
'og:type': article
'og:site_name': Sarvam AI Developer Documentation
'og:image':
  type: url
  value: >-
    https://res.cloudinary.com/dvcb20x9a/image/upload/v1743510800/image_3_rpnrug.png
'og:image:width': 1200
'og:image:height': 630
'twitter:card': summary_large_image
'twitter:title': Streaming Text-to-Speech API - Real-time Voice Synthesis by Sarvam AI
'twitter:description': >-
  Stream text to speech in real-time with Sarvam AI's WebSocket API. Progressive
  audio generation for long texts with low-latency and efficient processing.
'twitter:image':
  type: url
  value: >-
    https://res.cloudinary.com/dvcb20x9a/image/upload/v1743510800/image_3_rpnrug.png
'twitter:site': '@SarvamAI'
---

WebSocket-based streaming endpoint that sends audio chunks progressively as text is processed. Connect once, stream text in, receive audio out — no polling, no repeated HTTP calls.

<Info>
For complete API reference documentation, see the [Text-to-Speech API Reference](https://docs.sarvam.ai/api-reference-docs/text-to-speech/convert) section.
</Info>

**Common use cases:**
- **Conversational AI agents** — Stream TTS responses in real time for voice-based assistants
- **Interactive podcasts** — Generate and play back dialogue on the fly with minimal delay
- **Low-latency applications** — Any scenario where time-to-first-byte (TTFB) matters (IVR, live narration, kiosks)

## Why WebSocket Streaming

<CardGroup cols={2}>
  <Card title="Low Latency Playback" icon="bolt">
    Audio playback begins as soon as the first chunk is synthesized — no need to wait for the full response.
  </Card>
  <Card title="11 Languages (10 Indian + English)" icon="language">
    Hindi, Bengali, Tamil, Telugu, Kannada, Malayalam, Marathi, Gujarati, Punjabi, Odia, and English (Indian accent).
  </Card>
  <Card title="Persistent Connection" icon="plug">
    Single WebSocket connection handles multiple text to speech conversions. Send config once, then stream text continuously.
  </Card>
  <Card title="SDK Support" icon="code">
    Python (`AsyncSarvamAI`) and JavaScript (`SarvamAIClient`) SDKs with built-in async/await and event-driven patterns for seamless integration.
  </Card>
</CardGroup>

## Code Examples

### Best Practices

- Always send the config message first
- Use flush messages strategically to ensure complete text processing
- Send ping messages to maintain long-running connections

<CodeGroup>
<CodeBlock title="Python" active>

```python

from sarvamai import AsyncSarvamAI, AudioOutput

async def tts_stream():
    client = AsyncSarvamAI(api_subscription_key="YOUR_SARVAM_API_KEY")

    async with client.text_to_speech_streaming.connect(model="bulbul:v3") as ws:
        await ws.configure(target_language_code="hi-IN", speaker="shubh")
        print("Sent configuration")

        long_text = (
            "भारत की संस्कृति विश्व की सबसे प्राचीन और समृद्ध संस्कृतियों में से एक है।"
            "यह विविधता, सहिष्णुता और परंपराओं का अद्भुत संगम है, "
            "जिसमें विभिन्न धर्म, भाषाएं, त्योहार, संगीत, नृत्य, वास्तुकला और जीवनशैली शामिल हैं।"
        )

        await ws.convert(long_text)
        print("Sent text message")

        await ws.flush()
        print("Flushed buffer")

        chunk_count = 0
        with open("output.mp3", "wb") as f:
            async for message in ws:
                if isinstance(message, AudioOutput):
                    chunk_count += 1
                    audio_chunk = base64.b64decode(message.data.audio)
                    f.write(audio_chunk)
                    f.flush()

        print(f"All {chunk_count} chunks saved to output.mp3")
        print("Audio generation complete")

        if hasattr(ws, "_websocket") and not ws._websocket.closed:
            await ws._websocket.close()
            print("WebSocket connection closed.")

if __name__ == "__main__":
    asyncio.run(tts_stream())

# --- Notebook/Colab usage ---
# await tts_stream()
```

</CodeBlock>
<CodeBlock title="JavaScript">
```javascript

async function main() {
const client = new SarvamAIClient({
apiSubscriptionKey: "YOUR_SARVAM_API_KEY",
});

const socket = await client.textToSpeechStreaming.connect({
model: "bulbul:v3",
});

let chunkCount = 0;
const outputStream = fs.createWriteStream("output.mp3");

let closeTimeout = null;

socket.on("open", () => {
console.log("Connection opened");

    socket.configureConnection({
      type: "config",
      data: {
        speaker: "shubh",
        target_language_code: "hi-IN",
      },
    });

    console.log("Configuration sent");

    const longText =
      "भारत की संस्कृति विश्व की सबसे प्राचीन और समृद्ध संस्कृतियों में से एक है।"+
      "यह विविधता, सहिष्णुता और परंपराओं का अद्भुत संगम है, जिसमें विभिन्न धर्म, भाषाएं, त्योहार, संगीत, नृत्य, वास्तुकला और जीवनशैली शामिल हैं।";

    socket.convert(longText);
    console.log("Text sent for conversion");

    closeTimeout = setTimeout(() => {
      console.log("Forcing socket close after timeout");
      socket.close();
    }, 10000);

});

socket.on("message", (message) => {
if (message.type === "audio") {
chunkCount++;
const audioBuffer = Buffer.from(message.data.audio, "base64");
outputStream.write(audioBuffer);
console.log(`Received and wrote chunk ${chunkCount}`);
} else {
console.log("Received message:", message);
}
});

socket.on("close", (event) => {
console.log("Connection closed:", event);
if (closeTimeout) clearTimeout(closeTimeout);
outputStream.end(() => {
console.log(`All ${chunkCount} chunks saved to output.mp3`);
});
});

socket.on("error", (error) => {
console.error("Error occurred:", error);
if (closeTimeout) clearTimeout(closeTimeout);
outputStream.end();
});

await socket.waitForOpen();
console.log("WebSocket is ready");
}

main().catch(console.error);

```
</CodeBlock>

</CodeGroup>

## End of Speech Signal

The TTS streaming API now supports an end of speech signal that allows for clean stream termination when speech generation is complete.

### Using `send_completion_event`

When you set `send_completion_event=True` in the connection, the API will send a completion event when speech generation ends, allowing your application to handle stream termination gracefully.

<CodeGroup>
<CodeBlock title="Python" active>

```python

from sarvamai import AsyncSarvamAI, AudioOutput, EventResponse

async def tts_stream():
    client = AsyncSarvamAI(api_subscription_key="YOUR_SARVAM_API_KEY")

    async with client.text_to_speech_streaming.connect(
        model="bulbul:v3", send_completion_event=True
    ) as ws:
        await ws.configure(
            target_language_code="hi-IN",
            speaker="shubh",
        )
        print("Sent configuration")

        long_text = (
            "भारत की संस्कृति विश्व की सबसे प्राचीन और समृद्ध "
            "संस्कृतियों में से एक है।"
            "यह विविधता, सहिष्णुता और परंपराओं का अद्भुत संगम है, "
            "जिसमें विभिन्न धर्म, भाषाएं, त्योहार, संगीत, नृत्य, "
            "वास्तुकला और जीवनशैली शामिल हैं।"
        )

        await ws.convert(long_text)
        print("Sent text message")

        await ws.flush()
        print("Flushed buffer")

        chunk_count = 0
        with open("output.mp3", "wb") as f:
            async for message in ws:
                if isinstance(message, AudioOutput):
                    chunk_count += 1
                    audio_chunk = base64.b64decode(message.data.audio)
                    f.write(audio_chunk)
                    f.flush()
                elif isinstance(message, EventResponse):
                    print(f"Received completion event: {message.data.event_type}")
                    # Break when we receive the final event
                    if message.data.event_type == "final":
                        break

        print(f"All {chunk_count} chunks saved to output.mp3")
        print("Audio generation complete")

if __name__ == "__main__":
    asyncio.run(tts_stream())

# --- Notebook/Colab usage ---
# await tts_stream()
```

</CodeBlock>
</CodeGroup>

## Streaming TTS WebSocket – Integration Guide
Easily convert text to speech in real time using Sarvam's low-latency WebSocket-based TTS API.

### Input Message Types

<Tabs>
<Tab title="Config Message">
Sets up voice parameters and must be the first message sent after connection.
**Parameters:**
<ul>
  <li><code>min_buffer_size</code>: Minimum character length that triggers buffer flushing for TTS model processing</li>
  <li><code>max_chunk_length</code>: Maximum length for sentence splitting (adjust based on content length)</li>
  <li><code>output_audio_codec</code>: Supports multiple formats: `mp3`, `wav`, `aac`, `opus`, `flac`, `pcm` (LINEAR16), `mulaw` (μ-law), and `alaw` (A-law)</li>
  <li><code>output_audio_bitrate</code>: Choose from 5 supported bitrate options</li>
  </ul>

```json
{
  "type": "config",
  "data": {
    "speaker": "shubh",
    "target_language_code": "en-IN",
    "pace": 1.2,
    "min_buffer_size": 50,
    "max_chunk_length": 200,
    "output_audio_codec": "mp3",
    "output_audio_bitrate": "128k"
  }
}
```

</Tab>
<Tab title="Text Message">
Sends text to be converted to speech.
- **Range**: 0-2500 characters
- **Recommended**: &lt;500 characters for optimal streaming performance
<Note>Real-time endpoints perform better with longer character counts</Note>

```json
{
  "type": "text",
  "data": {
    "text": "This is an example sentence that will be converted to speech."
  }
}
```

</Tab>
<Tab title="Flush Message">
Forces the text buffer to process immediately, regardless of the min_buffer_size threshold.
Use to ensure all text is processed.

```json
{
  "type": "flush"
}
```

</Tab>
<Tab title="Ping Message">
Keeps the WebSocket connection alive; send periodically to avoid timeout.
The connection automatically closes after one minute of inactivity.

```json
{
  "type": "ping"
}
```

</Tab>
</Tabs>

