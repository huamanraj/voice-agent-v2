> ## Documentation Index
> Fetch the complete documentation index at: https://docs.cartesia.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Text to Speech (WebSocket)

> This endpoint creates a bidirectional WebSocket connection. The connection supports multiplexing, so you can send multiple requests and receive the corresponding responses in parallel.

The WebSocket API is built around contexts:

- When you send a generation request, you pass a `context_id`. Further inputs on the same `context_id` will [continue the generation](/build-with-cartesia/capability-guides/stream-inputs-using-continuations), maintaining prosody.
- Responses for a context contain the `context_id` you passed in so that you can match requests and responses.

Read the guide [on working with contexts](/use-the-api/tts-websocket/contexts) to learn more.

For the best performance, we recommend the following usage pattern:

1. **Do many generations over a single WebSocket**. Just use a separate context for each generation. The WebSocket scales up to dozens of concurrent generations.
2. **Set up the WebSocket before the first generation**. This ensures you don’t incur latency when you start generating speech.
3. **Include necessary spaces and punctuation**: This allows Sonic to generate speech more accurately and with better prosody.

For conversational agent use cases, we recommend the following usage pattern:

1. **Each turn in a conversation should correspond to a context**: For example, if you are using Sonic to power a voice agent, each turn in the conversation should be a new context.
2. **Start a new context for interruptions**: If the user interrupts the agent, start a new context for the agent’s response.

To learn more about managing concurrent generations and WebSocket connection limits, see the [concurrency limits and timeouts](/use-the-api/concurrency-limits-and-timeouts) page.




## AsyncAPI

````yaml asyncapi.yml /tts/websocket
id: /tts/websocket
title: /tts/websocket
description: >
  This endpoint creates a bidirectional WebSocket connection. The connection
  supports multiplexing, so you can send multiple requests and receive the
  corresponding responses in parallel.


  The WebSocket API is built around contexts:


  - When you send a generation request, you pass a `context_id`. Further inputs
  on the same `context_id` will [continue the
  generation](/build-with-cartesia/capability-guides/stream-inputs-using-continuations),
  maintaining prosody.

  - Responses for a context contain the `context_id` you passed in so that you
  can match requests and responses.


  Read the guide [on working with contexts](/use-the-api/tts-websocket/contexts)
  to learn more.


  For the best performance, we recommend the following usage pattern:


  1. **Do many generations over a single WebSocket**. Just use a separate
  context for each generation. The WebSocket scales up to dozens of concurrent
  generations.

  2. **Set up the WebSocket before the first generation**. This ensures you
  don’t incur latency when you start generating speech.

  3. **Include necessary spaces and punctuation**: This allows Sonic to generate
  speech more accurately and with better prosody.


  For conversational agent use cases, we recommend the following usage pattern:


  1. **Each turn in a conversation should correspond to a context**: For
  example, if you are using Sonic to power a voice agent, each turn in the
  conversation should be a new context.

  2. **Start a new context for interruptions**: If the user interrupts the
  agent, start a new context for the agent’s response.


  To learn more about managing concurrent generations and WebSocket connection
  limits, see the [concurrency limits and
  timeouts](/use-the-api/concurrency-limits-and-timeouts) page.
servers:
  - id: production
    protocol: wss
    host: api.cartesia.ai
    bindings: []
    variables: []
address: /tts/websocket
parameters:
  - id: cartesia_version
    jsonSchema:
      type: string
      description: >
        API version, e.g. `2026-03-01`.

        You can specify this instead of the Cartesia-Version header. This is
        particularly useful in the browser, where WebSockets do not support
        headers. You do not need to specify this if you are passing the header.
    description: >
      API version, e.g. `2026-03-01`.

      You can specify this instead of the Cartesia-Version header. This is
      particularly useful in the browser, where WebSockets do not support
      headers. You do not need to specify this if you are passing the header.
    type: string
    required: true
    deprecated: false
bindings: []
operations:
  - &ref_1
    id: sendTTSGeneration
    title: Send t t s generation
    type: receive
    messages:
      - &ref_3
        id: generationRequest
        payload:
          - name: Generation Request
            description: Use this to generate speech for a transcript.
            type: object
            properties:
              - name: model_id
                type: string
                description: >-
                  The ID of the model to use for the generation. See
                  [Models](/build-with-cartesia/tts-models/latest) for available
                  models.
                required: true
              - name: transcript
                type: string
                description: The transcript to generate speech for.
                required: true
              - name: voice
                type: object
                description: Voice configuration
                required: true
                properties:
                  - name: mode
                    type: string
                    description: Voice selection mode
                    enumValues:
                      - id
                    required: false
                  - name: id
                    type: string
                    description: The ID of the voice.
                    required: false
              - name: output_format
                type: object
                description: Audio output format configuration
                required: true
                properties:
                  - name: container
                    type: string
                    description: Audio container format
                    enumValues:
                      - raw
                    required: false
                  - name: encoding
                    type: string
                    description: >-
                      Audio encoding format. See [Choosing TTS
                      Parameters](/build-with-cartesia/capability-guides/choosing-tts-parameters)
                      if you're unsure what to use.
                    enumValues:
                      - pcm_f32le
                      - pcm_s16le
                      - pcm_mulaw
                      - pcm_alaw
                    required: false
                  - name: sample_rate
                    type: integer
                    description: Audio sample rate in Hz.
                    enumValues:
                      - 8000
                      - 16000
                      - 22050
                      - 24000
                      - 44100
                      - 48000
                    required: false
              - name: language
                type: string
                description: >-
                  The language that the given voice should speak the transcript
                  in. For valid options, see
                  [Models](/build-with-cartesia/tts-models/latest).
                enumValues:
                  - en
                  - fr
                  - de
                  - es
                  - pt
                  - zh
                  - ja
                  - hi
                  - it
                  - ko
                  - nl
                  - pl
                  - ru
                  - sv
                  - tr
                  - tl
                  - bg
                  - ro
                  - ar
                  - cs
                  - el
                  - fi
                  - hr
                  - ms
                  - sk
                  - da
                  - ta
                  - uk
                  - hu
                  - 'no'
                  - vi
                  - bn
                  - th
                  - he
                  - ka
                  - id
                  - te
                  - gu
                  - kn
                  - ml
                  - mr
                  - pa
                required: false
              - name: context_id
                type: string
                description: >
                  A unique identifier for the context. You can use any unique
                  identifier, like a UUID or human ID.
                required: true
              - name: continue
                type: boolean
                description: >-
                  Whether this input may be followed by more inputs. If not
                  specified, this defaults to false.
                required: false
              - name: max_buffer_delay_ms
                type: integer
                description: >
                  The maximum time in milliseconds to buffer text before
                  starting generation. Values between [0, 5000]ms are supported.
                  Defaults to 3000ms.


                  When set, the model will buffer incoming text chunks until
                  it's confident it has enough context to generate high-quality
                  speech, or the buffer delay elapses, whichever comes first.
                  Without this option set, the model will kick off generations
                  immediately, ceding control of buffering to the user.


                  Use this to balance responsiveness with higher quality speech
                  generation, which often benefits from having more context.
                required: false
              - name: flush
                type: boolean
                description: Whether to flush the context.
                required: false
              - name: add_timestamps
                type: boolean
                description: >
                  Whether to return word-level timestamps. If false (default),
                  no word timestamps will be produced at all. If true, the
                  server will return timestamp events containing word-level
                  timing information.
                required: false
              - name: add_phoneme_timestamps
                type: boolean
                description: >
                  Whether to return phoneme-level timestamps. If false
                  (default), no phoneme timestamps will be produced. If true,
                  the server will return timestamp events containing
                  phoneme-level timing information.
                required: false
              - name: use_normalized_timestamps
                type: boolean
                description: >-
                  Whether to use normalized timestamps (True) or original
                  timestamps (False).
                required: false
              - name: pronunciation_dict_id
                type: string
                description: >-
                  The ID of a pronunciation dictionary to use for the
                  generation. Pronunciation dictionaries are supported by
                  `sonic-3` models and newer.
                required: false
              - name: generation_config
                type: object
                description: >-
                  Configure the various attributes of the generated speech.
                  Available on `sonic-3` and `sonic-3.5` (with `speed` and
                  `volume` temporarily disabled on `sonic-3.5`); not available
                  on earlier models. See [Volume, Speed, and
                  Emotion](/build-with-cartesia/capability-guides/volume-speed-emotion)
                  for a guide on this option.
                required: false
                properties:
                  - name: volume
                    type: number
                    description: >-
                      Adjust the volume of the generated speech between 0.5x and
                      2.0x the original volume (default is 1.0x). Valid values
                      are between [0.5, 2.0] inclusive.
                    required: false
                  - name: speed
                    type: number
                    description: >-
                      Adjust the speed of the generated speech between 0.6x and
                      2.0x the original speed(default is 1.0x). Valid values are
                      between [0.6, 1.5] inclusive.
                    required: false
                  - name: emotion
                    type: string
                    description: >-
                      The primary emotions are `neutral`, `calm`, `angry`,
                      `content`, `sad`, `scared`. For more options, see [Volume,
                      Speed, and
                      Emotion](/build-with-cartesia/capability-guides/volume-speed-emotion#emotion-controls-beta).
                    enumValues:
                      - Happy
                      - Excited
                      - Enthusiastic
                      - Elated
                      - Euphoric
                      - Triumphant
                      - Amazed
                      - Surprised
                      - Flirtatious
                      - Joking/Comedic
                      - Curious
                      - Content
                      - Peaceful
                      - Serene
                      - Calm
                      - Grateful
                      - Affectionate
                      - Trust
                      - Sympathetic
                      - Anticipation
                      - Mysterious
                      - Angry
                      - Mad
                      - Outraged
                      - Frustrated
                      - Agitated
                      - Threatened
                      - Disgusted
                      - Contempt
                      - Envious
                      - Sarcastic
                      - Ironic
                      - Sad
                      - Dejected
                      - Melancholic
                      - Disappointed
                      - Hurt
                      - Guilty
                      - Bored
                      - Tired
                      - Rejected
                      - Nostalgic
                      - Wistful
                      - Apologetic
                      - Hesitant
                      - Insecure
                      - Confused
                      - Resigned
                      - Anxious
                      - Panicked
                      - Alarmed
                      - Scared
                      - Neutral
                      - Proud
                      - Confident
                      - Distant
                      - Skeptical
                      - Contemplative
                      - Determined
                    required: false
              - name: speed
                type: string
                description: >
                  Use `generation_config.speed` for sonic-3.


                  Speed setting for the model. Defaults to `normal`.


                  This feature is experimental and may not work for all voices.


                  Influences the speed of the generated speech. Faster speeds
                  may reduce hallucination rate.
                enumValues:
                  - slow
                  - normal
                  - fast
                deprecated: true
                required: false
        headers: []
        jsonPayloadSchema:
          type: object
          required:
            - model_id
            - transcript
            - voice
            - output_format
            - context_id
          properties:
            model_id:
              type: string
              description: >-
                The ID of the model to use for the generation. See
                [Models](/build-with-cartesia/tts-models/latest) for available
                models.
              x-parser-schema-id: <anonymous-schema-2>
            transcript:
              type: string
              description: The transcript to generate speech for.
              x-parser-schema-id: <anonymous-schema-3>
            voice:
              type: object
              description: Voice configuration
              required:
                - mode
                - id
              properties:
                mode:
                  type: string
                  enum:
                    - id
                  description: Voice selection mode
                  default: id
                  x-parser-schema-id: <anonymous-schema-5>
                id:
                  type: string
                  description: The ID of the voice.
                  x-parser-schema-id: <anonymous-schema-6>
              x-parser-schema-id: <anonymous-schema-4>
            output_format:
              type: object
              description: Audio output format configuration
              required:
                - container
                - encoding
                - sample_rate
              properties:
                container:
                  type: string
                  enum:
                    - raw
                  description: Audio container format
                  default: raw
                  x-parser-schema-id: <anonymous-schema-8>
                encoding:
                  type: string
                  enum:
                    - pcm_f32le
                    - pcm_s16le
                    - pcm_mulaw
                    - pcm_alaw
                  description: >-
                    Audio encoding format. See [Choosing TTS
                    Parameters](/build-with-cartesia/capability-guides/choosing-tts-parameters)
                    if you're unsure what to use.
                  x-parser-schema-id: <anonymous-schema-9>
                sample_rate:
                  type: integer
                  enum:
                    - 8000
                    - 16000
                    - 22050
                    - 24000
                    - 44100
                    - 48000
                  description: Audio sample rate in Hz.
                  x-parser-schema-id: <anonymous-schema-10>
              x-parser-schema-id: <anonymous-schema-7>
            language:
              type: string
              description: >-
                The language that the given voice should speak the transcript
                in. For valid options, see
                [Models](/build-with-cartesia/tts-models/latest).
              enum:
                - en
                - fr
                - de
                - es
                - pt
                - zh
                - ja
                - hi
                - it
                - ko
                - nl
                - pl
                - ru
                - sv
                - tr
                - tl
                - bg
                - ro
                - ar
                - cs
                - el
                - fi
                - hr
                - ms
                - sk
                - da
                - ta
                - uk
                - hu
                - 'no'
                - vi
                - bn
                - th
                - he
                - ka
                - id
                - te
                - gu
                - kn
                - ml
                - mr
                - pa
              x-parser-schema-id: <anonymous-schema-11>
            context_id:
              type: string
              description: >
                A unique identifier for the context. You can use any unique
                identifier, like a UUID or human ID.
              x-parser-schema-id: <anonymous-schema-12>
            continue:
              type: boolean
              description: >-
                Whether this input may be followed by more inputs. If not
                specified, this defaults to false.
              default: false
              x-parser-schema-id: <anonymous-schema-13>
            max_buffer_delay_ms:
              type: integer
              description: >
                The maximum time in milliseconds to buffer text before starting
                generation. Values between [0, 5000]ms are supported. Defaults
                to 3000ms.


                When set, the model will buffer incoming text chunks until it's
                confident it has enough context to generate high-quality speech,
                or the buffer delay elapses, whichever comes first. Without this
                option set, the model will kick off generations immediately,
                ceding control of buffering to the user.


                Use this to balance responsiveness with higher quality speech
                generation, which often benefits from having more context.
              default: 3000
              x-parser-schema-id: <anonymous-schema-14>
            flush:
              type: boolean
              description: Whether to flush the context.
              x-parser-schema-id: <anonymous-schema-15>
            add_timestamps:
              type: boolean
              description: >
                Whether to return word-level timestamps. If false (default), no
                word timestamps will be produced at all. If true, the server
                will return timestamp events containing word-level timing
                information.
              default: false
              x-parser-schema-id: <anonymous-schema-16>
            add_phoneme_timestamps:
              type: boolean
              description: >
                Whether to return phoneme-level timestamps. If false (default),
                no phoneme timestamps will be produced. If true, the server will
                return timestamp events containing phoneme-level timing
                information.
              default: false
              x-parser-schema-id: <anonymous-schema-17>
            use_normalized_timestamps:
              type: boolean
              description: >-
                Whether to use normalized timestamps (True) or original
                timestamps (False).
              x-parser-schema-id: <anonymous-schema-18>
            pronunciation_dict_id:
              type: string
              description: >-
                The ID of a pronunciation dictionary to use for the generation.
                Pronunciation dictionaries are supported by `sonic-3` models and
                newer.
              x-parser-schema-id: <anonymous-schema-19>
            generation_config:
              type: object
              description: >-
                Configure the various attributes of the generated speech.
                Available on `sonic-3` and `sonic-3.5` (with `speed` and
                `volume` temporarily disabled on `sonic-3.5`); not available on
                earlier models. See [Volume, Speed, and
                Emotion](/build-with-cartesia/capability-guides/volume-speed-emotion)
                for a guide on this option.
              properties:
                volume:
                  type: number
                  description: >-
                    Adjust the volume of the generated speech between 0.5x and
                    2.0x the original volume (default is 1.0x). Valid values are
                    between [0.5, 2.0] inclusive.
                  minimum: 0.5
                  maximum: 1.5
                  default: 1
                  x-parser-schema-id: <anonymous-schema-21>
                speed:
                  type: number
                  description: >-
                    Adjust the speed of the generated speech between 0.6x and
                    2.0x the original speed(default is 1.0x). Valid values are
                    between [0.6, 1.5] inclusive.
                  minimum: 0.6
                  maximum: 1.5
                  default: 1
                  x-parser-schema-id: <anonymous-schema-22>
                emotion:
                  title: Emotion
                  type: string
                  description: >-
                    The primary emotions are `neutral`, `calm`, `angry`,
                    `content`, `sad`, `scared`. For more options, see [Volume,
                    Speed, and
                    Emotion](/build-with-cartesia/capability-guides/volume-speed-emotion#emotion-controls-beta).
                  enum:
                    - Happy
                    - Excited
                    - Enthusiastic
                    - Elated
                    - Euphoric
                    - Triumphant
                    - Amazed
                    - Surprised
                    - Flirtatious
                    - Joking/Comedic
                    - Curious
                    - Content
                    - Peaceful
                    - Serene
                    - Calm
                    - Grateful
                    - Affectionate
                    - Trust
                    - Sympathetic
                    - Anticipation
                    - Mysterious
                    - Angry
                    - Mad
                    - Outraged
                    - Frustrated
                    - Agitated
                    - Threatened
                    - Disgusted
                    - Contempt
                    - Envious
                    - Sarcastic
                    - Ironic
                    - Sad
                    - Dejected
                    - Melancholic
                    - Disappointed
                    - Hurt
                    - Guilty
                    - Bored
                    - Tired
                    - Rejected
                    - Nostalgic
                    - Wistful
                    - Apologetic
                    - Hesitant
                    - Insecure
                    - Confused
                    - Resigned
                    - Anxious
                    - Panicked
                    - Alarmed
                    - Scared
                    - Neutral
                    - Proud
                    - Confident
                    - Distant
                    - Skeptical
                    - Contemplative
                    - Determined
                  x-parser-schema-id: <anonymous-schema-23>
              x-parser-schema-id: <anonymous-schema-20>
            speed:
              type: string
              deprecated: true
              description: >
                Use `generation_config.speed` for sonic-3.


                Speed setting for the model. Defaults to `normal`.


                This feature is experimental and may not work for all voices.


                Influences the speed of the generated speech. Faster speeds may
                reduce hallucination rate.
              enum:
                - slow
                - normal
                - fast
              default: normal
              x-parser-schema-id: <anonymous-schema-24>
          x-parser-schema-id: GenerationRequest
        title: Generation Request
        description: Use this to generate speech for a transcript.
        example: |-
          {
            "model_id": "sonic-3",
            "transcript": "Hello, world! I'm generating audio on Cartesia!",
            "voice": {
              "mode": "id",
              "id": "a0e99841-438c-4a64-b679-ae501e7d6091"
            },
            "language": "en",
            "context_id": "ab977222-f9e0-4563-a1c0-5a934ae8fdd6",
            "output_format": {
              "container": "raw",
              "encoding": "pcm_s16le",
              "sample_rate": 8000
            },
            "add_timestamps": true,
            "continue": false
          }
        bindings: []
        extensions:
          - id: x-parser-unique-object-id
            value: generationRequest
      - &ref_4
        id: cancelRequest
        payload:
          - name: Cancel Context Request
            description: >-
              Use this to cancel a context, so that no more messages are
              generated for that context.
            type: object
            properties:
              - name: context_id
                type: string
                description: The ID of the context to cancel.
                required: true
              - name: cancel
                type: boolean
                description: >-
                  Whether to cancel the context, so that no more messages are
                  generated for that context.
                enumValues:
                  - true
                required: true
        headers: []
        jsonPayloadSchema:
          type: object
          required:
            - context_id
            - cancel
          properties:
            context_id:
              type: string
              description: The ID of the context to cancel.
              x-parser-schema-id: <anonymous-schema-25>
            cancel:
              type: boolean
              enum:
                - true
              description: >-
                Whether to cancel the context, so that no more messages are
                generated for that context.
              x-parser-schema-id: <anonymous-schema-26>
          x-parser-schema-id: CancelRequest
        title: Cancel Context Request
        description: >-
          Use this to cancel a context, so that no more messages are generated
          for that context.
        example: |-
          {
            "context_id": "50dc3b5e-5841-4aa1-9f94-60cfb9aead79",
            "cancel": true
          }
        bindings: []
        extensions:
          - id: x-parser-unique-object-id
            value: cancelRequest
    bindings: []
    extensions: &ref_0
      - id: x-parser-unique-object-id
        value: /tts/websocket
  - &ref_2
    id: receiveTTSAudio
    title: Receive t t s audio
    description: >-
      The server will send you back a stream of messages with the same
      `context_id` as your request. The messages can be of type `chunk`,
      `timestamps`, `phoneme_timestamps``,` `error`, or `done`.
    type: send
    messages:
      - &ref_5
        id: chunkResponse
        payload:
          - name: Audio Chunk Response
            description: Audio data chunk
            type: object
            properties:
              - name: type
                type: string
                description: Response type identifier
                enumValues:
                  - chunk
                required: true
              - name: data
                type: string
                description: Base64-encoded audio data
                required: true
              - name: done
                type: boolean
                description: Whether this is the final chunk for this context
                required: true
              - name: status_code
                type: integer
                description: HTTP-style status code
                required: true
              - name: step_time
                type: number
                description: Server-side processing time for this chunk in milliseconds
                required: true
              - name: context_id
                type: string
                description: >
                  A unique identifier for the context. You can use any unique
                  identifier, like a UUID or human ID.
                required: true
        headers: []
        jsonPayloadSchema:
          type: object
          required:
            - type
            - data
            - done
            - status_code
            - step_time
            - context_id
          properties:
            type:
              type: string
              enum:
                - chunk
              description: Response type identifier
              x-parser-schema-id: <anonymous-schema-27>
            data:
              type: string
              description: Base64-encoded audio data
              x-parser-schema-id: <anonymous-schema-28>
            done:
              type: boolean
              description: Whether this is the final chunk for this context
              x-parser-schema-id: <anonymous-schema-29>
            status_code:
              type: integer
              description: HTTP-style status code
              x-parser-schema-id: <anonymous-schema-30>
            step_time:
              type: number
              description: Server-side processing time for this chunk in milliseconds
              x-parser-schema-id: <anonymous-schema-31>
            context_id:
              type: string
              description: >
                A unique identifier for the context. You can use any unique
                identifier, like a UUID or human ID.
              x-parser-schema-id: <anonymous-schema-32>
          x-parser-schema-id: ChunkResponse
        title: Audio Chunk Response
        description: Audio data chunk
        example: |-
          {
            "type": "chunk",
            "data": "aSDinaTvuI8gbWludGxpZnk=",
            "done": false,
            "status_code": 206,
            "step_time": 123,
            "context_id": "50dc3b5e-5841-4aa1-9f94-60cfb9aead79"
          }
        bindings: []
        extensions:
          - id: x-parser-unique-object-id
            value: chunkResponse
      - &ref_6
        id: flushDoneResponse
        payload:
          - name: Flush Done Response
            description: Acknowledgment that flush command was received
            type: object
            properties:
              - name: type
                type: string
                description: Response type identifier
                enumValues:
                  - flush_done
                required: true
              - name: done
                type: boolean
                description: Whether generation is complete
                required: true
              - name: flush_done
                type: boolean
                description: Whether the flush is complete
                required: true
              - name: flush_id
                type: integer
                description: >-
                  An identifier corresponding to the number of flush commands
                  that have been sent for this context. Starts at 1. This can be
                  used to map chunks of audio to certain transcript submissions.
                required: true
              - name: status_code
                type: integer
                description: HTTP-style status code
                required: true
              - name: context_id
                type: string
                description: >
                  A unique identifier for the context. You can use any unique
                  identifier, like a UUID or human ID.
                required: true
        headers: []
        jsonPayloadSchema:
          type: object
          required:
            - type
            - done
            - flush_done
            - flush_id
            - status_code
            - context_id
          properties:
            type:
              type: string
              enum:
                - flush_done
              description: Response type identifier
              x-parser-schema-id: <anonymous-schema-33>
            done:
              type: boolean
              description: Whether generation is complete
              x-parser-schema-id: <anonymous-schema-34>
            flush_done:
              type: boolean
              description: Whether the flush is complete
              x-parser-schema-id: <anonymous-schema-35>
            flush_id:
              type: integer
              description: >-
                An identifier corresponding to the number of flush commands that
                have been sent for this context. Starts at 1. This can be used
                to map chunks of audio to certain transcript submissions.
              x-parser-schema-id: <anonymous-schema-36>
            status_code:
              type: integer
              description: HTTP-style status code
              x-parser-schema-id: <anonymous-schema-37>
            context_id:
              type: string
              description: >
                A unique identifier for the context. You can use any unique
                identifier, like a UUID or human ID.
              x-parser-schema-id: <anonymous-schema-38>
          x-parser-schema-id: FlushDoneResponse
        title: Flush Done Response
        description: Acknowledgment that flush command was received
        example: |-
          {
            "type": "flush_done",
            "done": false,
            "flush_done": true,
            "flush_id": 1,
            "status_code": 206,
            "context_id": "50dc3b5e-5841-4aa1-9f94-60cfb9aead79"
          }
        bindings: []
        extensions:
          - id: x-parser-unique-object-id
            value: flushDoneResponse
      - &ref_7
        id: doneResponse
        payload:
          - name: Done Response
            description: Generation completion signal
            type: object
            properties:
              - name: type
                type: string
                description: Response type identifier
                enumValues:
                  - done
                required: true
              - name: done
                type: boolean
                description: Whether generation is complete
                required: true
              - name: status_code
                type: integer
                description: HTTP-style status code
                required: true
              - name: context_id
                type: string
                description: >
                  A unique identifier for the context. You can use any unique
                  identifier, like a UUID or human ID.
                required: true
        headers: []
        jsonPayloadSchema:
          type: object
          required:
            - type
            - done
            - status_code
            - context_id
          properties:
            type:
              type: string
              enum:
                - done
              description: Response type identifier
              x-parser-schema-id: <anonymous-schema-39>
            done:
              type: boolean
              description: Whether generation is complete
              x-parser-schema-id: <anonymous-schema-40>
            status_code:
              type: integer
              description: HTTP-style status code
              x-parser-schema-id: <anonymous-schema-41>
            context_id:
              type: string
              description: >
                A unique identifier for the context. You can use any unique
                identifier, like a UUID or human ID.
              x-parser-schema-id: <anonymous-schema-42>
          x-parser-schema-id: DoneResponse
        title: Done Response
        description: Generation completion signal
        example: |-
          {
            "type": "done",
            "done": true,
            "status_code": 206,
            "context_id": "50dc3b5e-5841-4aa1-9f94-60cfb9aead79"
          }
        bindings: []
        extensions:
          - id: x-parser-unique-object-id
            value: doneResponse
      - &ref_8
        id: timestampsResponse
        payload:
          - name: Word Timestamps Response
            description: Word-level timing information
            type: object
            properties:
              - name: type
                type: string
                description: Response type identifier
                enumValues:
                  - timestamps
                required: true
              - name: done
                type: boolean
                description: Whether generation is complete
                required: true
              - name: status_code
                type: integer
                description: HTTP-style status code
                required: true
              - name: context_id
                type: string
                description: >
                  A unique identifier for the context. You can use any unique
                  identifier, like a UUID or human ID.
                required: true
              - name: word_timestamps
                type: object
                description: Word-level timing information
                required: false
                properties:
                  - name: words
                    type: array
                    description: List of words in order
                    required: false
                  - name: start
                    type: array
                    description: Start times in seconds for each word
                    required: false
                  - name: end
                    type: array
                    description: End times in seconds for each word
                    required: false
        headers: []
        jsonPayloadSchema:
          type: object
          required:
            - type
            - done
            - status_code
            - context_id
          properties:
            type:
              type: string
              enum:
                - timestamps
              description: Response type identifier
              x-parser-schema-id: <anonymous-schema-43>
            done:
              type: boolean
              description: Whether generation is complete
              x-parser-schema-id: <anonymous-schema-44>
            status_code:
              type: integer
              description: HTTP-style status code
              x-parser-schema-id: <anonymous-schema-45>
            context_id:
              type: string
              description: >
                A unique identifier for the context. You can use any unique
                identifier, like a UUID or human ID.
              x-parser-schema-id: <anonymous-schema-46>
            word_timestamps:
              type: object
              description: Word-level timing information
              properties:
                words:
                  type: array
                  items:
                    type: string
                    x-parser-schema-id: <anonymous-schema-49>
                  description: List of words in order
                  x-parser-schema-id: <anonymous-schema-48>
                start:
                  type: array
                  items:
                    type: number
                    x-parser-schema-id: <anonymous-schema-51>
                  description: Start times in seconds for each word
                  x-parser-schema-id: <anonymous-schema-50>
                end:
                  type: array
                  items:
                    type: number
                    x-parser-schema-id: <anonymous-schema-53>
                  description: End times in seconds for each word
                  x-parser-schema-id: <anonymous-schema-52>
              x-parser-schema-id: <anonymous-schema-47>
          x-parser-schema-id: TimestampsResponse
        title: Word Timestamps Response
        description: Word-level timing information
        example: |-
          {
            "type": "timestamps",
            "done": false,
            "status_code": 206,
            "context_id": "872ec12d-bc63-4e1e-a241-4f58c879d105",
            "word_timestamps": {
              "words": [
                "Hello",
                "world"
              ],
              "start": [
                0,
                0.5
              ],
              "end": [
                0.4,
                0.9
              ]
            }
          }
        bindings: []
        extensions:
          - id: x-parser-unique-object-id
            value: timestampsResponse
      - &ref_9
        id: phonemeTimestampsResponse
        payload:
          - name: Phoneme Timestamps Response
            description: Phoneme-level timing information
            type: object
            properties:
              - name: type
                type: string
                description: Response type identifier
                enumValues:
                  - phoneme_timestamps
                required: true
              - name: done
                type: boolean
                description: Whether generation is complete
                required: true
              - name: status_code
                type: integer
                description: HTTP-style status code
                required: true
              - name: context_id
                type: string
                description: >
                  A unique identifier for the context. You can use any unique
                  identifier, like a UUID or human ID.
                required: true
              - name: phoneme_timestamps
                type: object
                description: Phoneme-level timing information
                required: false
                properties:
                  - name: phonemes
                    type: array
                    description: List of phonemes in order
                    required: false
                  - name: start
                    type: array
                    description: Start times in seconds for each phoneme
                    required: false
                  - name: end
                    type: array
                    description: End times in seconds for each phoneme
                    required: false
        headers: []
        jsonPayloadSchema:
          type: object
          required:
            - type
            - done
            - status_code
            - context_id
          properties:
            type:
              type: string
              enum:
                - phoneme_timestamps
              description: Response type identifier
              x-parser-schema-id: <anonymous-schema-54>
            done:
              type: boolean
              description: Whether generation is complete
              x-parser-schema-id: <anonymous-schema-55>
            status_code:
              type: integer
              description: HTTP-style status code
              x-parser-schema-id: <anonymous-schema-56>
            context_id:
              type: string
              description: >
                A unique identifier for the context. You can use any unique
                identifier, like a UUID or human ID.
              x-parser-schema-id: <anonymous-schema-57>
            phoneme_timestamps:
              type: object
              description: Phoneme-level timing information
              properties:
                phonemes:
                  type: array
                  items:
                    type: string
                    x-parser-schema-id: <anonymous-schema-60>
                  description: List of phonemes in order
                  x-parser-schema-id: <anonymous-schema-59>
                start:
                  type: array
                  items:
                    type: number
                    x-parser-schema-id: <anonymous-schema-62>
                  description: Start times in seconds for each phoneme
                  x-parser-schema-id: <anonymous-schema-61>
                end:
                  type: array
                  items:
                    type: number
                    x-parser-schema-id: <anonymous-schema-64>
                  description: End times in seconds for each phoneme
                  x-parser-schema-id: <anonymous-schema-63>
              x-parser-schema-id: <anonymous-schema-58>
          x-parser-schema-id: PhonemeTimestampsResponse
        title: Phoneme Timestamps Response
        description: Phoneme-level timing information
        example: |-
          {
            "type": "phoneme_timestamps",
            "done": false,
            "status_code": 206,
            "context_id": "872ec12d-bc63-4e1e-a241-4f58c879d105",
            "phoneme_timestamps": {
              "phonemes": [
                "h",
                "ə",
                "l",
                "oʊ"
              ],
              "start": [
                0.093,
                0.174,
                0.255,
                0.337
              ],
              "end": [
                0.174,
                0.255,
                0.337,
                0.418
              ]
            }
          }
        bindings: []
        extensions:
          - id: x-parser-unique-object-id
            value: phonemeTimestampsResponse
      - &ref_10
        id: ttsErrorResponse
        payload:
          - name: Error Response
            description: Error information for TTS WebSocket connections.
            type: object
            properties:
              - name: type
                type: string
                description: Response type identifier
                enumValues:
                  - error
                required: true
              - name: done
                type: boolean
                description: Whether generation is complete
                required: true
              - name: error_code
                type: string
                description: Machine-readable error code.
                required: false
              - name: status_code
                type: number
                description: An HTTP response status code.
                required: false
              - name: title
                type: string
                description: Human-readable error title.
                required: false
              - name: message
                type: string
                description: Human-readable error message.
                required: false
              - name: doc_url
                type: string
                description: URL to relevant documentation
                required: false
              - name: request_id
                type: string
                description: Unique identifier for this websocket connection
                required: false
              - name: context_id
                type: string
                description: >
                  A unique identifier for the context. You can use any unique
                  identifier, like a UUID or human ID.
                required: false
        headers: []
        jsonPayloadSchema:
          type: object
          required:
            - type
            - done
          properties:
            type:
              type: string
              enum:
                - error
              description: Response type identifier
              x-parser-schema-id: <anonymous-schema-65>
            done:
              type: boolean
              description: Whether generation is complete
              x-parser-schema-id: <anonymous-schema-66>
            error_code:
              type: string
              description: Machine-readable error code.
              x-parser-schema-id: <anonymous-schema-67>
            status_code:
              type: number
              format: integer
              description: An HTTP response status code.
              x-parser-schema-id: <anonymous-schema-68>
            title:
              type: string
              description: Human-readable error title.
              x-parser-schema-id: <anonymous-schema-69>
            message:
              type: string
              description: Human-readable error message.
              x-parser-schema-id: <anonymous-schema-70>
            doc_url:
              type: string
              description: URL to relevant documentation
              x-parser-schema-id: <anonymous-schema-71>
            request_id:
              type: string
              description: Unique identifier for this websocket connection
              x-parser-schema-id: <anonymous-schema-72>
            context_id:
              type: string
              description: >
                A unique identifier for the context. You can use any unique
                identifier, like a UUID or human ID.
              x-parser-schema-id: <anonymous-schema-73>
          x-parser-schema-id: TTSErrorResponse
        title: Error Response
        description: Error information for TTS WebSocket connections.
        example: |-
          {
            "type": "error",
            "done": true,
            "title": "Invalid model",
            "message": "The model is not valid, make sure it is a valid model ID.",
            "error_code": "model_not_found",
            "status_code": 400,
            "doc_url": "https://docs.cartesia.ai/build-with-cartesia/tts-models/latest",
            "request_id": "2ff8af53-4d38-479d-8287-58940f01c701",
            "context_id": "50dc3b5e-5841-4aa1-9f94-60cfb9aead79"
          }
        bindings: []
        extensions:
          - id: x-parser-unique-object-id
            value: ttsErrorResponse
    bindings: []
    extensions: *ref_0
sendOperations:
  - *ref_1
receiveOperations:
  - *ref_2
sendMessages:
  - *ref_3
  - *ref_4
receiveMessages:
  - *ref_5
  - *ref_6
  - *ref_7
  - *ref_8
  - *ref_9
  - *ref_10
extensions:
  - id: x-parser-unique-object-id
    value: /tts/websocket
securitySchemes:
  - id: apiKey
    name: X-API-Key
    type: httpApiKey
    description: API key passed in a header.
    in: header
    extensions: []
  - id: accessTokenQuery
    name: access_token
    type: httpApiKey
    description: >
      A short-lived access token passed in a query param to make API requests
      from a client.

      This is particularly useful in the browser, where WebSockets do not
      support headers.

      See [Authenticate client
      apps](/get-started/authenticate-your-client-applications) to generate an
      access token.
    in: query
    extensions: []

````