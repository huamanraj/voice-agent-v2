> ## Documentation Index
> Fetch the complete documentation index at: https://docs.cartesia.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Speech-to-Text (Streaming)

> This endpoint creates a bidirectional WebSocket connection for real-time speech transcription.

Our STT endpoint enables sending in a stream of audio as bytes, and provides transcription results as they become available.

**Usage Pattern**:

1. Connect to the WebSocket with appropriate query parameters
2. Send audio chunks as binary WebSocket messages in the specified encoding format
3. Receive transcription messages as JSON with word-level timestamps
4. Send `finalize` as a text message to flush any remaining audio (receives `flush_done` acknowledgment)
5. Send `done` as a text message to close the session cleanly (receives `done` acknowledgment and closes)

**Performance Recommendation**: For best performance, it is recommended to resample audio before streaming and send audio chunks in `pcm_s16le` format at 16kHz sample rate.

**Pricing**: Speech-to-text streaming is priced at **1 credit per 1 second** of audio streamed in.

For WebSocket connection limits, see the [concurrency limits and timeouts](/use-the-api/concurrency-limits-and-timeouts) page.




## AsyncAPI

````yaml asyncapi.yml /stt/websocket
id: /stt/websocket
title: /stt/websocket
description: >
  This endpoint creates a bidirectional WebSocket connection for real-time
  speech transcription.


  Our STT endpoint enables sending in a stream of audio as bytes, and provides
  transcription results as they become available.


  **Usage Pattern**:


  1. Connect to the WebSocket with appropriate query parameters

  2. Send audio chunks as binary WebSocket messages in the specified encoding
  format

  3. Receive transcription messages as JSON with word-level timestamps

  4. Send `finalize` as a text message to flush any remaining audio (receives
  `flush_done` acknowledgment)

  5. Send `done` as a text message to close the session cleanly (receives `done`
  acknowledgment and closes)


  **Performance Recommendation**: For best performance, it is recommended to
  resample audio before streaming and send audio chunks in `pcm_s16le` format at
  16kHz sample rate.


  **Pricing**: Speech-to-text streaming is priced at **1 credit per 1 second**
  of audio streamed in.


  For WebSocket connection limits, see the [concurrency limits and
  timeouts](/use-the-api/concurrency-limits-and-timeouts) page.
servers:
  - id: production
    protocol: wss
    host: api.cartesia.ai
    bindings: []
    variables: []
address: /stt/websocket
parameters:
  - id: model
    jsonSchema:
      type: string
      description: >-
        ID of the model to use for transcription. See
        [Models](/build-with-cartesia/stt-models) for available models.
    description: >-
      ID of the model to use for transcription. See
      [Models](/build-with-cartesia/stt-models) for available models.
    type: string
    required: true
    deprecated: false
  - id: language
    jsonSchema:
      type: string
      description: |
        The language of the input audio in ISO-639-1 format. Defaults to `en`.

        See [Models](/build-with-cartesia/stt-models) for supported languages.
    description: |
      The language of the input audio in ISO-639-1 format. Defaults to `en`.

      See [Models](/build-with-cartesia/stt-models) for supported languages.
    type: string
    required: true
    deprecated: false
  - id: encoding
    jsonSchema:
      type: string
      description: >
        The encoding format of the audio data. This determines how the server
        interprets the raw binary audio data you send.


        For guidance on choosing an encoding, see [Audio
        encodings](/build-with-cartesia/capability-guides/stt-input-encodings).
    description: >
      The encoding format of the audio data. This determines how the server
      interprets the raw binary audio data you send.


      For guidance on choosing an encoding, see [Audio
      encodings](/build-with-cartesia/capability-guides/stt-input-encodings).
    type: string
    required: true
    deprecated: false
  - id: sample_rate
    jsonSchema:
      type: string
      description: |
        The sample rate of the audio in Hz.
    description: |
      The sample rate of the audio in Hz.
    type: string
    required: true
    deprecated: false
  - id: min_volume
    jsonSchema:
      type: string
      description: >
        Volume threshold for voice activity detection. Audio below this
        threshold will be considered silence.

        Range: 0.0-1.0. Higher values = more aggressive filtering of quiet
        speech.
    description: >
      Volume threshold for voice activity detection. Audio below this threshold
      will be considered silence.

      Range: 0.0-1.0. Higher values = more aggressive filtering of quiet speech.
    type: string
    required: true
    deprecated: false
  - id: max_silence_duration_secs
    jsonSchema:
      type: string
      description: >
        Maximum duration of silence (in seconds) before the system considers the
        utterance complete and triggers endpointing.

        Higher values allow for longer pauses within utterances.
    description: >
      Maximum duration of silence (in seconds) before the system considers the
      utterance complete and triggers endpointing.

      Higher values allow for longer pauses within utterances.
    type: string
    required: true
    deprecated: false
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
  - &ref_5
    id: sendSTTAudio
    title: Send s t t audio
    type: receive
    messages:
      - &ref_7
        id: sttAudioData
        payload:
          - type: string
            format: binary
            description: >
              Send binary WebSocket messages containing raw audio data in the
              format specified by the `encoding` and `sample_rate` connection
              parameters.


              Audio Requirements:

              - Send audio in small chunks (e.g., 100ms intervals) for optimal
              latency

              - Audio format must match the `encoding` and `sample_rate`
              parameters


              Timeout Behavior:

              - If no audio data is sent for 3 minutes, the WebSocket will
              automatically disconnect

              - The timeout resets with each audio chunk sent to the server
            x-parser-schema-id: <anonymous-schema-81>
            name: Send Audio Data
        headers: []
        jsonPayloadSchema:
          type: string
          format: binary
          description: >-
            Raw audio data in the format specified by the `encoding` parameter.
            Send in small chunks (e.g., 100ms intervals) for optimal latency.
          x-parser-schema-id: <anonymous-schema-81>
        title: Send Audio Data
        description: >
          Send binary WebSocket messages containing raw audio data in the format
          specified by the `encoding` and `sample_rate` connection parameters.


          Audio Requirements:

          - Send audio in small chunks (e.g., 100ms intervals) for optimal
          latency

          - Audio format must match the `encoding` and `sample_rate` parameters


          Timeout Behavior:

          - If no audio data is sent for 3 minutes, the WebSocket will
          automatically disconnect

          - The timeout resets with each audio chunk sent to the server
        example: '{}'
        bindings: []
        extensions:
          - id: x-parser-unique-object-id
            value: sttAudioData
      - &ref_8
        id: sttFinalizeCommand
        payload:
          - type: string
            enum: &ref_0
              - finalize
            description: >-
              Send `finalize` as a text message to flush any remaining audio and
              receive flush_done acknowledgment
            examples: &ref_1
              - finalize
            x-parser-schema-id: <anonymous-schema-82>
            name: Finalize Command
        headers: []
        jsonPayloadSchema:
          type: string
          enum: *ref_0
          description: Send `finalize` as a text message to flush any remaining audio
          examples: *ref_1
          x-parser-schema-id: <anonymous-schema-82>
        title: Finalize Command
        description: >-
          Send `finalize` as a text message to flush any remaining audio and
          receive flush_done acknowledgment
        example: '"finalize"'
        bindings: []
        extensions:
          - id: x-parser-unique-object-id
            value: sttFinalizeCommand
      - &ref_9
        id: sttDoneCommand
        payload:
          - type: string
            enum: &ref_2
              - done
            description: >-
              Send `done` as a text message to flush remaining audio, close
              session, and receive done acknowledgment
            examples: &ref_3
              - done
            x-parser-schema-id: <anonymous-schema-83>
            name: Done Command
        headers: []
        jsonPayloadSchema:
          type: string
          enum: *ref_2
          description: >-
            Send `done` as a text message to flush remaining audio and close the
            session
          examples: *ref_3
          x-parser-schema-id: <anonymous-schema-83>
        title: Done Command
        description: >-
          Send `done` as a text message to flush remaining audio, close session,
          and receive done acknowledgment
        example: '"done"'
        bindings: []
        extensions:
          - id: x-parser-unique-object-id
            value: sttDoneCommand
    bindings: []
    extensions: &ref_4
      - id: x-parser-unique-object-id
        value: /stt/websocket
  - &ref_6
    id: receiveSTTTranscription
    title: Receive s t t transcription
    description: >-
      The server will send transcription results as they become available.
      Messages can be of type `transcript`, `flush_done`, `done`, or `error`.
      Each transcript response includes word-level timestamps.
    type: send
    messages:
      - &ref_10
        id: sttTranscriptResponse
        payload:
          - name: Receive Transcription
            description: >-
              The server will send transcription results as they become
              available. Messages can be of type transcript, flush_done, done,
              or error. Each transcript response includes word-level timestamps.
            type: object
            properties:
              - name: type
                type: string
                description: Response type identifier
                enumValues:
                  - transcript
                required: true
              - name: is_final
                type: boolean
                description: Whether this is the final transcription result
                required: true
              - name: request_id
                type: string
                description: Unique identifier for this WebSocket connection.
                required: true
              - name: text
                type: string
                description: Transcribed text
                required: true
              - name: duration
                type: number
                description: Duration of the audio in seconds
                required: true
              - name: language
                type: string
                description: Detected or specified language code
                required: true
              - name: words
                type: array
                description: Word-level timestamps
                required: false
        headers: []
        jsonPayloadSchema:
          type: object
          required:
            - type
            - is_final
            - request_id
            - text
            - duration
            - language
          properties:
            type:
              type: string
              enum:
                - transcript
              description: Response type identifier
              x-parser-schema-id: <anonymous-schema-84>
            is_final:
              type: boolean
              description: Whether this is the final transcription result
              x-parser-schema-id: <anonymous-schema-85>
            request_id:
              type: string
              description: Unique identifier for this WebSocket connection.
              x-parser-schema-id: <anonymous-schema-86>
            text:
              type: string
              description: Transcribed text
              x-parser-schema-id: <anonymous-schema-87>
            duration:
              type: number
              description: Duration of the audio in seconds
              x-parser-schema-id: <anonymous-schema-88>
            language:
              type: string
              description: Detected or specified language code
              x-parser-schema-id: <anonymous-schema-89>
            words:
              type: array
              description: Word-level timestamps
              items:
                type: object
                required:
                  - word
                  - start
                  - end
                properties:
                  word:
                    type: string
                    description: The transcribed word
                    x-parser-schema-id: <anonymous-schema-92>
                  start:
                    type: number
                    description: Start time in seconds
                    x-parser-schema-id: <anonymous-schema-93>
                  end:
                    type: number
                    description: End time in seconds
                    x-parser-schema-id: <anonymous-schema-94>
                x-parser-schema-id: <anonymous-schema-91>
              x-parser-schema-id: <anonymous-schema-90>
          x-parser-schema-id: STTTranscriptResponse
        title: Receive Transcription
        description: >-
          The server will send transcription results as they become available.
          Messages can be of type transcript, flush_done, done, or error. Each
          transcript response includes word-level timestamps.
        example: |-
          {
            "type": "transcript",
            "is_final": false,
            "request_id": "58dfa4d4-91c5-410c-8529-6824c8f7aedc",
            "text": "How are you doing today?",
            "duration": 0.5,
            "language": "en",
            "words": [
              {
                "word": "How",
                "start": 0,
                "end": 0.12
              },
              {
                "word": "are",
                "start": 0.15,
                "end": 0.25
              },
              {
                "word": "you",
                "start": 0.28,
                "end": 0.35
              },
              {
                "word": "doing",
                "start": 0.38,
                "end": 0.55
              },
              {
                "word": "today?",
                "start": 0.58,
                "end": 0.78
              }
            ]
          }
        bindings: []
        extensions:
          - id: x-parser-unique-object-id
            value: sttTranscriptResponse
      - &ref_11
        id: sttFlushDoneResponse
        payload:
          - name: Flush Done Response
            description: Acknowledgment that finalize command was received
            type: object
            properties:
              - name: type
                type: string
                description: Response type identifier
                enumValues:
                  - flush_done
                required: true
              - name: request_id
                type: string
                description: Unique identifier for this websocket connection
                required: true
        headers: []
        jsonPayloadSchema:
          type: object
          required:
            - type
            - request_id
          properties:
            type:
              type: string
              enum:
                - flush_done
              description: Response type identifier
              x-parser-schema-id: <anonymous-schema-95>
            request_id:
              type: string
              description: Unique identifier for this websocket connection
              x-parser-schema-id: <anonymous-schema-96>
          x-parser-schema-id: STTFlushDoneResponse
        title: Flush Done Response
        description: Acknowledgment that finalize command was received
        example: |-
          {
            "type": "flush_done",
            "request_id": "b67e1c5d-2f4c-4c3d-9f82-96eb4d2f12a8"
          }
        bindings: []
        extensions:
          - id: x-parser-unique-object-id
            value: sttFlushDoneResponse
      - &ref_12
        id: sttDoneResponse
        payload:
          - name: Done Response
            description: Acknowledgment that session is closing
            type: object
            properties:
              - name: type
                type: string
                description: Response type identifier
                enumValues:
                  - done
                required: true
              - name: request_id
                type: string
                description: Unique identifier for this websocket connection
                required: true
        headers: []
        jsonPayloadSchema:
          type: object
          required:
            - type
            - request_id
          properties:
            type:
              type: string
              enum:
                - done
              description: Response type identifier
              x-parser-schema-id: <anonymous-schema-97>
            request_id:
              type: string
              description: Unique identifier for this websocket connection
              x-parser-schema-id: <anonymous-schema-98>
          x-parser-schema-id: STTDoneResponse
        title: Done Response
        description: Acknowledgment that session is closing
        example: |-
          {
            "type": "done",
            "request_id": "b67e1c5d-2f4c-4c3d-9f82-96eb4d2f12a8"
          }
        bindings: []
        extensions:
          - id: x-parser-unique-object-id
            value: sttDoneResponse
      - &ref_13
        id: sttErrorResponse
        payload:
          - name: Error Response
            description: Error information for STT WebSocket connections.
            type: object
            properties:
              - name: type
                type: string
                description: Event type identifier.
                enumValues:
                  - error
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
        headers: []
        jsonPayloadSchema:
          type: object
          required:
            - type
          properties:
            type:
              type: string
              enum:
                - error
              description: Event type identifier.
              x-parser-schema-id: <anonymous-schema-99>
            error_code:
              type: string
              description: Machine-readable error code.
              x-parser-schema-id: <anonymous-schema-100>
            status_code:
              type: number
              format: integer
              description: An HTTP response status code.
              x-parser-schema-id: <anonymous-schema-101>
            title:
              type: string
              description: Human-readable error title.
              x-parser-schema-id: <anonymous-schema-102>
            message:
              type: string
              description: Human-readable error message.
              x-parser-schema-id: <anonymous-schema-103>
            doc_url:
              type: string
              description: URL to relevant documentation
              x-parser-schema-id: <anonymous-schema-104>
            request_id:
              type: string
              description: Unique identifier for this websocket connection
              x-parser-schema-id: <anonymous-schema-105>
          x-parser-schema-id: STTErrorResponse
        title: Error Response
        description: Error information for STT WebSocket connections.
        example: |-
          {
            "type": "error",
            "title": "Invalid model",
            "message": "The model is not valid, make sure it is a valid model ID.",
            "error_code": "model_not_found",
            "doc_url": "https://docs.cartesia.ai/build-with-cartesia/stt-models",
            "status_code": 400,
            "request_id": "2ff8af53-4d38-479d-8287-58940f01c701"
          }
        bindings: []
        extensions:
          - id: x-parser-unique-object-id
            value: sttErrorResponse
    bindings: []
    extensions: *ref_4
sendOperations:
  - *ref_5
receiveOperations:
  - *ref_6
sendMessages:
  - *ref_7
  - *ref_8
  - *ref_9
receiveMessages:
  - *ref_10
  - *ref_11
  - *ref_12
  - *ref_13
extensions:
  - id: x-parser-unique-object-id
    value: /stt/websocket
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