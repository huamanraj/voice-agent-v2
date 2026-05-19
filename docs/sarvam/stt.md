# WebSocket

GET /speech-to-text/ws

WebSocket channel for real-time speech to text streaming.

**Note:** This API Reference page is provided for informational purposes only. 
The Try It playground may not provide the best experience for streaming audio. 
For optimal streaming performance, please use the SDK or implement your own WebSocket client.


Reference: https://docs.sarvam.ai/api-reference-docs/speech-to-text/transcribe/ws

## AsyncAPI Specification

```yaml
asyncapi: 2.6.0
info:
  title: speechToTextStreaming
  version: subpackage_speechToTextStreaming.speechToTextStreaming
  description: >
    WebSocket channel for real-time speech to text streaming.


    **Note:** This API Reference page is provided for informational purposes
    only. 

    The Try It playground may not provide the best experience for streaming
    audio. 

    For optimal streaming performance, please use the SDK or implement your own
    WebSocket client.
channels:
  /speech-to-text/ws:
    description: >
      WebSocket channel for real-time speech to text streaming.


      **Note:** This API Reference page is provided for informational purposes
      only. 

      The Try It playground may not provide the best experience for streaming
      audio. 

      For optimal streaming performance, please use the SDK or implement your
      own WebSocket client.
    bindings:
      ws:
        query:
          type: object
          properties:
            language-code:
              $ref: '#/components/schemas/speechToTextStreaming_language-code'
            model:
              $ref: '#/components/schemas/speechToTextStreaming_model'
              default: saaras:v3
            mode:
              $ref: '#/components/schemas/speechToTextStreaming_mode'
              default: transcribe
            sample_rate:
              $ref: '#/components/schemas/speechToTextStreaming_sample_rate'
              default: 16000
            high_vad_sensitivity:
              $ref: '#/components/schemas/speechToTextStreaming_high_vad_sensitivity'
            positive_speech_threshold:
              type: string
            negative_speech_threshold:
              type: string
            min_speech_frames:
              type: string
            first_turn_min_speech_frames:
              type: string
            negative_frames_count:
              type: string
            negative_frames_window:
              type: string
            start_speech_volume_threshold:
              type: string
            interrupt_min_speech_frames:
              type: string
            pre_speech_pad_frames:
              type: string
            num_initial_ignored_frames:
              type: string
            vad_signals:
              $ref: '#/components/schemas/speechToTextStreaming_vad_signals'
            flush_signal:
              $ref: '#/components/schemas/speechToTextStreaming_flush_signal'
            input_audio_codec:
              $ref: '#/components/schemas/speechToTextStreaming_input_audio_codec'
        headers:
          type: object
          properties:
            Api-Subscription-Key:
              type: string
    publish:
      operationId: speech-to-text-streaming-publish
      summary: Transcription
      description: Receive real-time transcription results from the WebSocket
      message:
        name: Transcription
        title: Transcription
        description: Receive real-time transcription results from the WebSocket
        payload:
          $ref: >-
            #/components/schemas/speechToTextStreaming_speechToTextStreamingResponse
    subscribe:
      operationId: speech-to-text-streaming-subscribe
      summary: Client messages
      message:
        oneOf:
          - $ref: >-
              #/components/messages/subpackage_speechToTextStreaming.speechToTextStreaming-client-0-Audio
              Transcription Message
          - $ref: >-
              #/components/messages/subpackage_speechToTextStreaming.speechToTextStreaming-client-1-Speech
              Flush Signal
servers:
  Production:
    url: wss://api.sarvam.ai/
    protocol: wss
    x-default: true
components:
  messages:
    subpackage_speechToTextStreaming.speechToTextStreaming-client-0-Audio Transcription Message:
      name: Audio Transcription Message
      title: Audio Transcription Message
      description: Send audio data for real-time speech to text streaming
      payload:
        $ref: '#/components/schemas/speechToTextStreaming_audioMessage'
    subpackage_speechToTextStreaming.speechToTextStreaming-client-1-Speech Flush Signal:
      name: Speech Flush Signal
      title: Speech Flush Signal
      description: Send signal to flush audio buffer and finalize transcription
      payload:
        $ref: '#/components/schemas/speechToTextStreaming_flushSignal'
  schemas:
    speechToTextStreaming_language-code:
      type: string
      enum:
        - unknown
        - en-IN
        - hi-IN
        - bn-IN
        - gu-IN
        - kn-IN
        - ml-IN
        - mr-IN
        - od-IN
        - pa-IN
        - ta-IN
        - te-IN
        - as-IN
        - ur-IN
        - ne-IN
        - kok-IN
        - ks-IN
        - sd-IN
        - sa-IN
        - sat-IN
        - mni-IN
        - brx-IN
        - mai-IN
        - doi-IN
      description: >
        Specifies the language of the input audio in BCP-47 format.


        **Available Options (saarika:v2.5, legacy):**

        - `unknown` (default): Use when the language is not known; the API will
        auto-detect.

        - `hi-IN`: Hindi

        - `bn-IN`: Bengali

        - `gu-IN`: Gujarati

        - `kn-IN`: Kannada

        - `ml-IN`: Malayalam

        - `mr-IN`: Marathi

        - `od-IN`: Odia

        - `pa-IN`: Punjabi

        - `ta-IN`: Tamil

        - `te-IN`: Telugu

        - `en-IN`: English


        **Additional Options (saaras:v3, recommended):**

        - `as-IN`: Assamese

        - `ur-IN`: Urdu

        - `ne-IN`: Nepali

        - `kok-IN`: Konkani

        - `ks-IN`: Kashmiri

        - `sd-IN`: Sindhi

        - `sa-IN`: Sanskrit

        - `sat-IN`: Santali

        - `mni-IN`: Manipuri

        - `brx-IN`: Bodo

        - `mai-IN`: Maithili

        - `doi-IN`: Dogri
      title: speechToTextStreaming_language-code
    speechToTextStreaming_model:
      type: string
      enum:
        - saaras:v3
        - saarika:v2.5
      default: saaras:v3
      description: >
        Specifies the model to use for speech-to-text conversion.


        - **saaras:v3** (default, recommended): State-of-the-art model with
        flexible output formats. Supports multiple modes via the `mode`
        parameter: transcribe, translate, verbatim, translit, codemix.


        - **saarika:v2.5** (legacy): Transcribes audio in the spoken language.
        Kept for backward compatibility.
      title: speechToTextStreaming_model
    speechToTextStreaming_mode:
      type: string
      enum:
        - transcribe
        - translate
        - verbatim
        - translit
        - codemix
      default: transcribe
      description: >
        Mode of operation. **Only applicable when using saaras:v3 model.**


        Example audio: 'मेरा फोन नंबर है 9840950950'


        - **transcribe** (default): Standard transcription in the original
        language with proper formatting and number normalization.
          - Output: `मेरा फोन नंबर है 9840950950`

        - **translate**: Translates speech from any supported Indic language to
        English.
          - Output: `My phone number is 9840950950`

        - **verbatim**: Exact word-for-word transcription without normalization,
        preserving filler words and spoken numbers as-is.
          - Output: `मेरा फोन नंबर है नौ आठ चार zero नौ पांच zero नौ पांच zero`

        - **translit**: Romanization - Transliterates speech to Latin/Roman
        script only.
          - Output: `mera phone number hai 9840950950`

        - **codemix**: Code-mixed text with English words in English and Indic
        words in native script.
          - Output: `मेरा phone number है 9840950950`
      title: speechToTextStreaming_mode
    speechToTextStreaming_sample_rate:
      type: string
      enum:
        - '16000'
        - '8000'
      description: >-
        Audio sample rate for the WebSocket connection. When specified as a
        connection parameter, only 16kHz and 8kHz are supported. 8kHz is only
        available via this connection parameter. If not specified, defaults to
        16kHz.
      title: speechToTextStreaming_sample_rate
    speechToTextStreaming_high_vad_sensitivity:
      type: string
      enum:
        - 'true'
        - 'false'
      description: Enable high VAD (Voice Activity Detection) sensitivity
      title: speechToTextStreaming_high_vad_sensitivity
    speechToTextStreaming_vad_signals:
      type: string
      enum:
        - 'true'
        - 'false'
      description: Enable VAD signals in response
      title: speechToTextStreaming_vad_signals
    speechToTextStreaming_flush_signal:
      type: string
      enum:
        - 'true'
        - 'false'
      description: Signal to flush the audio buffer and finalize transcription
      title: speechToTextStreaming_flush_signal
    speechToTextStreaming_input_audio_codec:
      type: string
      enum:
        - wav
        - pcm_s16le
        - pcm_l16
        - pcm_raw
      description: >
        Audio codec/format of the input stream. Use this when sending raw PCM
        audio.

        Supported values: wav, pcm_s16le, pcm_l16, pcm_raw.
      title: speechToTextStreaming_input_audio_codec
    ResponseType:
      type: string
      enum:
        - data
        - error
        - events
      description: Type of WebSocket response
      title: ResponseType
    SpeechToTextTranscriptionDataTimestamps:
      type: object
      properties: {}
      description: Timestamp information (if available)
      title: SpeechToTextTranscriptionDataTimestamps
    SpeechToTextTranscriptionDataDiarizedTranscript:
      type: object
      properties: {}
      description: Diarized transcript of the provided speech
      title: SpeechToTextTranscriptionDataDiarizedTranscript
    TranscriptionMetrics:
      type: object
      properties:
        audio_duration:
          type: number
          format: double
          description: Duration of processed audio in seconds
        processing_latency:
          type: number
          format: double
          description: Processing latency in seconds
      required:
        - audio_duration
        - processing_latency
      title: TranscriptionMetrics
    SpeechToTextTranscriptionData:
      type: object
      properties:
        request_id:
          type: string
          description: Unique identifier for the request
        transcript:
          type: string
          description: Transcript of the provided speech in original language
        timestamps:
          oneOf:
            - $ref: '#/components/schemas/SpeechToTextTranscriptionDataTimestamps'
            - type: 'null'
          description: Timestamp information (if available)
        diarized_transcript:
          oneOf:
            - $ref: >-
                #/components/schemas/SpeechToTextTranscriptionDataDiarizedTranscript
            - type: 'null'
          description: Diarized transcript of the provided speech
        language_code:
          type:
            - string
            - 'null'
          description: BCP-47 code of detected language
        language_probability:
          type:
            - number
            - 'null'
          format: double
          description: >
            Float value (0.0 to 1.0) indicating the probability of the detected
            language being correct. Higher values indicate higher confidence.


            **When it returns a value:**

            - When `language_code` is not provided in the request

            - When `language_code` is set to `unknown`


            **When it returns null:**

            - When a specific `language_code` is provided (language detection is
            skipped)


            The parameter is always present in the response.
        metrics:
          $ref: '#/components/schemas/TranscriptionMetrics'
      required:
        - request_id
        - transcript
        - metrics
      title: SpeechToTextTranscriptionData
    ErrorData:
      type: object
      properties:
        error:
          type: string
          description: Error message
        code:
          type: string
          description: Error code
      required:
        - error
        - code
      title: ErrorData
    EventsDataSignalType:
      type: string
      enum:
        - START_SPEECH
        - END_SPEECH
      description: VAD signal type
      title: EventsDataSignalType
    EventsData:
      type: object
      properties:
        event_type:
          type: string
          description: Type of event
        timestamp:
          type: string
          format: date-time
          description: Event timestamp
        signal_type:
          $ref: '#/components/schemas/EventsDataSignalType'
          description: VAD signal type
        occured_at:
          type: number
          format: double
          description: Epoch timestamp when the event occurred
      description: >
        VAD events are sent when vad_signals=true. Fields may vary by event
        type.
      title: EventsData
    SpeechToTextResponseData:
      oneOf:
        - $ref: '#/components/schemas/SpeechToTextTranscriptionData'
        - $ref: '#/components/schemas/ErrorData'
        - $ref: '#/components/schemas/EventsData'
      title: SpeechToTextResponseData
    speechToTextStreaming_speechToTextStreamingResponse:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/ResponseType'
        data:
          $ref: '#/components/schemas/SpeechToTextResponseData'
      required:
        - type
        - data
      title: speechToTextStreaming_speechToTextStreamingResponse
    AudioDataSampleRate:
      type: string
      enum:
        - '16000'
        - '22050'
        - '24000'
      description: >
        Audio sample rate in Hz for individual audio messages. 


        **Backward Compatibility**: This property is maintained for legacy
        support.

        **Recommended**: Use the connection-level sample_rate parameter instead.

        **Note**: 8kHz is only supported via connection parameter, not in
        AudioData messages.


        Supported values: 16kHz (preferred), 22.05kHz, 24kHz
      title: AudioDataSampleRate
    AudioDataEncoding:
      type: string
      enum:
        - audio/wav
      default: audio/wav
      description: Audio encoding format
      title: AudioDataEncoding
    AudioData:
      type: object
      properties:
        data:
          type: string
          format: base64
          description: Base64 encoded audio data
        sample_rate:
          $ref: '#/components/schemas/AudioDataSampleRate'
          description: >
            Audio sample rate in Hz for individual audio messages. 


            **Backward Compatibility**: This property is maintained for legacy
            support.

            **Recommended**: Use the connection-level sample_rate parameter
            instead.

            **Note**: 8kHz is only supported via connection parameter, not in
            AudioData messages.


            Supported values: 16kHz (preferred), 22.05kHz, 24kHz
        encoding:
          $ref: '#/components/schemas/AudioDataEncoding'
          description: Audio encoding format
      required:
        - data
        - sample_rate
        - encoding
      title: AudioData
    speechToTextStreaming_audioMessage:
      type: object
      properties:
        audio:
          $ref: '#/components/schemas/AudioData'
      required:
        - audio
      title: speechToTextStreaming_audioMessage
    ChannelsSpeechToTextStreamingMessagesFlushSignalType:
      type: string
      enum:
        - flush
      default: flush
      description: Type identifier for flush signal
      title: ChannelsSpeechToTextStreamingMessagesFlushSignalType
    speechToTextStreaming_flushSignal:
      type: object
      properties:
        type:
          $ref: >-
            #/components/schemas/ChannelsSpeechToTextStreamingMessagesFlushSignalType
          description: Type identifier for flush signal
      required:
        - type
      description: >-
        Signal to flush the audio buffer and force finalize partial
        transcriptions/translations
      title: speechToTextStreaming_flushSignal

```