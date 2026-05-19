# Continuous Text Stream

GET /v1/speak

Convert text into natural-sounding speech using Deepgram's TTS WebSocket

Reference: https://developers.deepgram.com/reference/text-to-speech/speak-streaming

## AsyncAPI Specification

```yaml
asyncapi: 2.6.0
info:
  title: speak.v1
  version: subpackage_speak/v1.speak.v1
  description: Convert text into natural-sounding speech using Deepgram's TTS WebSocket
channels:
  /v1/speak:
    description: Convert text into natural-sounding speech using Deepgram's TTS WebSocket
    bindings:
      ws:
        query:
          type: object
          properties:
            encoding:
              $ref: '#/components/schemas/SpeakV1Encoding'
            mip_opt_out:
              $ref: '#/components/schemas/SpeakV1MipOptOut'
            model:
              $ref: '#/components/schemas/SpeakV1Model'
            sample_rate:
              $ref: '#/components/schemas/SpeakV1SampleRate'
            speed:
              $ref: '#/components/schemas/SpeakV1Speed'
        headers:
          type: object
          properties:
            Authorization:
              type: string
    publish:
      operationId: speak-v-1-publish
      summary: Server messages
      message:
        oneOf:
          - $ref: >-
              #/components/messages/subpackage_speak/v1.speak.v1-server-0-SpeakV1Audio
          - $ref: >-
              #/components/messages/subpackage_speak/v1.speak.v1-server-1-SpeakV1Metadata
          - $ref: >-
              #/components/messages/subpackage_speak/v1.speak.v1-server-2-SpeakV1Flushed
          - $ref: >-
              #/components/messages/subpackage_speak/v1.speak.v1-server-3-SpeakV1Cleared
          - $ref: >-
              #/components/messages/subpackage_speak/v1.speak.v1-server-4-SpeakV1Warning
    subscribe:
      operationId: speak-v-1-subscribe
      summary: Client messages
      message:
        oneOf:
          - $ref: >-
              #/components/messages/subpackage_speak/v1.speak.v1-client-0-SpeakV1Text
          - $ref: >-
              #/components/messages/subpackage_speak/v1.speak.v1-client-1-SpeakV1Flush
          - $ref: >-
              #/components/messages/subpackage_speak/v1.speak.v1-client-2-SpeakV1Clear
          - $ref: >-
              #/components/messages/subpackage_speak/v1.speak.v1-client-3-SpeakV1Close
servers:
  Production:
    url: wss://api.deepgram.com/
    protocol: wss
    x-default: true
components:
  messages:
    subpackage_speak/v1.speak.v1-server-0-SpeakV1Audio:
      name: SpeakV1Audio
      title: SpeakV1Audio
      description: Receive audio chunks as they are generated
      payload:
        $ref: '#/components/schemas/SpeakV1_SpeakV1Audio'
    subpackage_speak/v1.speak.v1-server-1-SpeakV1Metadata:
      name: SpeakV1Metadata
      title: SpeakV1Metadata
      description: Receive metadata about the audio generation
      payload:
        $ref: '#/components/schemas/SpeakV1_SpeakV1Metadata'
    subpackage_speak/v1.speak.v1-server-2-SpeakV1Flushed:
      name: SpeakV1Flushed
      title: SpeakV1Flushed
      description: Receive metadata about the audio generation
      payload:
        $ref: '#/components/schemas/SpeakV1_SpeakV1Flushed'
    subpackage_speak/v1.speak.v1-server-3-SpeakV1Cleared:
      name: SpeakV1Cleared
      title: SpeakV1Cleared
      description: Receive metadata about the audio generation
      payload:
        $ref: '#/components/schemas/SpeakV1_SpeakV1Cleared'
    subpackage_speak/v1.speak.v1-server-4-SpeakV1Warning:
      name: SpeakV1Warning
      title: SpeakV1Warning
      description: Receive a warning about the audio generation
      payload:
        $ref: '#/components/schemas/SpeakV1_SpeakV1Warning'
    subpackage_speak/v1.speak.v1-client-0-SpeakV1Text:
      name: SpeakV1Text
      title: SpeakV1Text
      description: Text to convert to audio
      payload:
        $ref: '#/components/schemas/SpeakV1_SpeakV1Text'
    subpackage_speak/v1.speak.v1-client-1-SpeakV1Flush:
      name: SpeakV1Flush
      title: SpeakV1Flush
      description: Flush the buffer and receive the final audio for text sent so far
      payload:
        $ref: '#/components/schemas/SpeakV1_SpeakV1Flush'
    subpackage_speak/v1.speak.v1-client-2-SpeakV1Clear:
      name: SpeakV1Clear
      title: SpeakV1Clear
      description: >-
        Clear the buffer and start a new audio generation. Potentially
        destructive operation for any text in the buffer
      payload:
        $ref: '#/components/schemas/SpeakV1_SpeakV1Clear'
    subpackage_speak/v1.speak.v1-client-3-SpeakV1Close:
      name: SpeakV1Close
      title: SpeakV1Close
      description: >-
        Flush the buffer and close the connection gracefully after all audio is
        generated
      payload:
        $ref: '#/components/schemas/SpeakV1_SpeakV1Close'
  schemas:
    SpeakV1Encoding:
      type: string
      enum:
        - linear16
        - mulaw
        - alaw
      default: linear16
      description: >-
        Encoding allows you to specify the expected encoding of your audio
        output for streaming TTS. Only streaming-compatible encodings are
        supported.
      title: SpeakV1Encoding
    SpeakV1MipOptOut:
      description: Any type
      title: SpeakV1MipOptOut
    SpeakV1Model:
      type: string
      enum:
        - aura-asteria-en
        - aura-luna-en
        - aura-stella-en
        - aura-athena-en
        - aura-hera-en
        - aura-orion-en
        - aura-arcas-en
        - aura-perseus-en
        - aura-angus-en
        - aura-orpheus-en
        - aura-helios-en
        - aura-zeus-en
        - aura-2-amalthea-en
        - aura-2-andromeda-en
        - aura-2-apollo-en
        - aura-2-arcas-en
        - aura-2-aries-en
        - aura-2-asteria-en
        - aura-2-athena-en
        - aura-2-atlas-en
        - aura-2-aurora-en
        - aura-2-callista-en
        - aura-2-cordelia-en
        - aura-2-cora-en
        - aura-2-delia-en
        - aura-2-draco-en
        - aura-2-electra-en
        - aura-2-harmonia-en
        - aura-2-helena-en
        - aura-2-hera-en
        - aura-2-hermes-en
        - aura-2-hyperion-en
        - aura-2-iris-en
        - aura-2-janus-en
        - aura-2-juno-en
        - aura-2-jupiter-en
        - aura-2-luna-en
        - aura-2-mars-en
        - aura-2-minerva-en
        - aura-2-neptune-en
        - aura-2-odysseus-en
        - aura-2-ophelia-en
        - aura-2-orion-en
        - aura-2-orpheus-en
        - aura-2-pandora-en
        - aura-2-phoebe-en
        - aura-2-pluto-en
        - aura-2-saturn-en
        - aura-2-selene-en
        - aura-2-thalia-en
        - aura-2-theia-en
        - aura-2-vesta-en
        - aura-2-zeus-en
        - aura-2-sirio-es
        - aura-2-nestor-es
        - aura-2-carina-es
        - aura-2-celeste-es
        - aura-2-alvaro-es
        - aura-2-diana-es
        - aura-2-aquila-es
        - aura-2-selena-es
        - aura-2-estrella-es
        - aura-2-javier-es
      default: aura-asteria-en
      description: AI model used to process submitted text
      title: SpeakV1Model
    SpeakV1SampleRate:
      type: string
      enum:
        - '8000'
        - '16000'
        - '24000'
        - '32000'
        - '48000'
      default: '24000'
      description: >-
        Sample Rate specifies the sample rate for the output audio. Based on
        encoding 8000 or 24000 are possible defaults. For some encodings sample
        rate is not configurable.
      title: SpeakV1SampleRate
    SpeakV1Speed:
      type: number
      format: double
      default: 1
      description: >-
        Speaking rate multiplier that adjusts the pace of generated speech while
        preserving natural prosody and voice quality. Not yet supported in all
        languages.
      title: SpeakV1Speed
    SpeakV1_SpeakV1Audio:
      type: string
      format: binary
      title: SpeakV1_SpeakV1Audio
    ChannelsSpeakV1MessagesSpeakV1MetadataType:
      type: string
      enum:
        - Metadata
      description: Message type identifier
      title: ChannelsSpeakV1MessagesSpeakV1MetadataType
    SpeakV1_SpeakV1Metadata:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/ChannelsSpeakV1MessagesSpeakV1MetadataType'
          description: Message type identifier
        request_id:
          type: string
          format: uuid
          description: Unique identifier for the request
        model_name:
          type: string
          description: Name of the model being used
        model_version:
          type: string
          description: Version of the primary model being used
        model_uuid:
          type: string
          format: uuid
          description: Unique identifier for the primary model used
        additional_model_uuids:
          type: array
          items:
            type: string
            format: uuid
          description: >-
            List of unique identifiers for any additional models used to serve
            the request
      required:
        - type
        - request_id
        - model_name
        - model_version
        - model_uuid
      title: SpeakV1_SpeakV1Metadata
    ChannelsSpeakV1MessagesSpeakV1FlushedType:
      type: string
      enum:
        - Flushed
        - Cleared
      description: Message type identifier
      title: ChannelsSpeakV1MessagesSpeakV1FlushedType
    SpeakV1_SpeakV1Flushed:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/ChannelsSpeakV1MessagesSpeakV1FlushedType'
          description: Message type identifier
        sequence_id:
          type: integer
          description: The sequence ID of the response
      required:
        - type
        - sequence_id
      title: SpeakV1_SpeakV1Flushed
    ChannelsSpeakV1MessagesSpeakV1ClearedType:
      type: string
      enum:
        - Flushed
        - Cleared
      description: Message type identifier
      title: ChannelsSpeakV1MessagesSpeakV1ClearedType
    SpeakV1_SpeakV1Cleared:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/ChannelsSpeakV1MessagesSpeakV1ClearedType'
          description: Message type identifier
        sequence_id:
          type: integer
          description: The sequence ID of the response
      required:
        - type
        - sequence_id
      title: SpeakV1_SpeakV1Cleared
    ChannelsSpeakV1MessagesSpeakV1WarningType:
      type: string
      enum:
        - Warning
      description: Message type identifier
      title: ChannelsSpeakV1MessagesSpeakV1WarningType
    SpeakV1_SpeakV1Warning:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/ChannelsSpeakV1MessagesSpeakV1WarningType'
          description: Message type identifier
        description:
          type: string
          description: A description of what went wrong
        code:
          type: string
          description: Error code identifying the type of error
      required:
        - type
        - description
        - code
      title: SpeakV1_SpeakV1Warning
    ChannelsSpeakV1MessagesSpeakV1TextType:
      type: string
      enum:
        - Speak
      description: Message type identifier
      title: ChannelsSpeakV1MessagesSpeakV1TextType
    SpeakV1_SpeakV1Text:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/ChannelsSpeakV1MessagesSpeakV1TextType'
          description: Message type identifier
        text:
          type: string
          description: The input text to be converted to speech
      required:
        - type
        - text
      title: SpeakV1_SpeakV1Text
    ChannelsSpeakV1MessagesSpeakV1FlushType:
      type: string
      enum:
        - Flush
        - Clear
        - Close
      description: Message type identifier
      title: ChannelsSpeakV1MessagesSpeakV1FlushType
    SpeakV1_SpeakV1Flush:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/ChannelsSpeakV1MessagesSpeakV1FlushType'
          description: Message type identifier
      required:
        - type
      title: SpeakV1_SpeakV1Flush
    ChannelsSpeakV1MessagesSpeakV1ClearType:
      type: string
      enum:
        - Flush
        - Clear
        - Close
      description: Message type identifier
      title: ChannelsSpeakV1MessagesSpeakV1ClearType
    SpeakV1_SpeakV1Clear:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/ChannelsSpeakV1MessagesSpeakV1ClearType'
          description: Message type identifier
      required:
        - type
      title: SpeakV1_SpeakV1Clear
    ChannelsSpeakV1MessagesSpeakV1CloseType:
      type: string
      enum:
        - Flush
        - Clear
        - Close
      description: Message type identifier
      title: ChannelsSpeakV1MessagesSpeakV1CloseType
    SpeakV1_SpeakV1Close:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/ChannelsSpeakV1MessagesSpeakV1CloseType'
          description: Message type identifier
      required:
        - type
      title: SpeakV1_SpeakV1Close

```