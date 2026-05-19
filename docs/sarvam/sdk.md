Sarvam Python Library
fern shield pypi

The Sarvam Python library provides convenient access to the Sarvam API from Python.

Documentation
API reference documentation is available here.

Installation
pip install sarvamai
Reference
A full reference for this library is available here.

Usage
Instantiate and use the client with the following:

from sarvamai import SarvamAI

client = SarvamAI(
    api_subscription_key="YOUR_API_SUBSCRIPTION_KEY",
)
client.text.translate(
    input="input",
    source_language_code="auto",
    target_language_code="bn-IN",
)
Async Client
The SDK also exports an async client so that you can make non-blocking calls to our API.

import asyncio

from sarvamai import AsyncSarvamAI

client = AsyncSarvamAI(
    api_subscription_key="YOUR_API_SUBSCRIPTION_KEY",
)


async def main() -> None:
    await client.text.translate(
        input="input",
        source_language_code="auto",
        target_language_code="bn-IN",
    )


asyncio.run(main())
Exception Handling
When the API returns a non-success status code (4xx or 5xx response), a subclass of the following error will be thrown.

from sarvamai.core.api_error import ApiError

try:
    client.text.translate(...)
except ApiError as e:
    print(e.status_code)
    print(e.body)
Advanced
Retries
The SDK is instrumented with automatic retries with exponential backoff. A request will be retried as long as the request is deemed retryable and the number of retry attempts has not grown larger than the configured retry limit (default: 2).

A request is deemed retryable when any of the following HTTP status codes is returned:

408 (Timeout)
429 (Too Many Requests)
5XX (Internal Server Errors)
Use the max_retries request option to configure this behavior.

client.text.translate(..., request_options={
    "max_retries": 1
})
Timeouts
The SDK defaults to a 60 second timeout. You can configure this with a timeout option at the client or request level.

from sarvamai import SarvamAI

client = SarvamAI(
    ...,
    timeout=20.0,
)


# Override timeout for a specific method
client.text.translate(..., request_options={
    "timeout_in_seconds": 1
})
Custom Client
You can override the httpx client to customize it for your use-case. Some common use-cases include support for proxies and transports.

import httpx
from sarvamai import SarvamAI

client = SarvamAI(
    ...,
    httpx_client=httpx.Client(
        proxies="http://my.test.proxy.example.com",
        transport=httpx.HTTPTransport(local_address="0.0.0.0"),
    ),
)
Contributing
While we value open-source contributions to this SDK, this library is generated programmatically. Additions made directly to this library would have to be moved over to our generation code, otherwise they would be overwritten upon the next generated release. Feel free to open a PR as a proof of concept, but know that we will not be able to merge it as-is. We suggest opening an issue first to discuss with us!

On the other hand, contributions to the README are always very welcome!

References
Text
client.text.translate(...)
client.text.identify_language(...)
client.text.transliterate(...)
SpeechToText
client.speech_to_text.transcribe(...)
📝 Description
Real-Time Speech to Text API
This API transcribes speech to text in multiple Indian languages and English. Supports real-time transcription for interactive applications.

Available Options:
Real-Time API (Current Endpoint): For quick responses under 30 seconds with immediate results
Batch API: For longer audio files, requires following a notebook script - View Notebook
Supports diarization (speaker identification)
Note:
Pricing differs for Real-Time and Batch APIs
Diarization is only available in Batch API with separate pricing
Please refer to dashboard.sarvam.ai for detailed pricing information
🔌 Usage
from sarvamai import SarvamAI

client = SarvamAI(
    api_subscription_key="YOUR_API_SUBSCRIPTION_KEY",
)
client.speech_to_text.transcribe()
⚙️ Parameters
file: `from future import annotations

core.File` — See core.File for more documentation

model: typing.Optional[SpeechToTextModel]

Specifies the model to use for speech-to-text conversion. Note:- Default model is saarika:v2

language_code: typing.Optional[SpeechToTextLanguage]

Specifies the language of the input audio. This parameter is required to ensure accurate transcription. For the saarika:v1 model, this parameter is mandatory. For the saarika:v2 model, it is optional. unknown: Use this when the language is not known; the API will detect it automatically. Note:- that the saarika:v1 model does not support unknown language code.

request_options: typing.Optional[RequestOptions] — Request-specific configuration.

client.speech_to_text.translate(...)
TextToSpeech
client.text_to_speech.convert(...)
📝 Description
This is the model to convert text into spoken audio. The output is a wave file encoded as a base64 string.

🔌 Usage
from sarvamai import SarvamAI

client = SarvamAI(
    api_subscription_key="YOUR_API_SUBSCRIPTION_KEY",
)
client.text_to_speech.convert(
    text="text",
    target_language_code="bn-IN",
)
⚙️ Parameters
text: str

target_language_code: TextToSpeechLanguage — The language of the text is BCP-47 format

speaker: typing.Optional[TextToSpeechSpeaker]

The speaker voice to be used for the output audio.

Default: Meera

Model Compatibility (Speakers compatible with respective models):

bulbul:v1:

Female: Diya, Maya, Meera, Pavithra, Maitreyi, Misha
Male: Amol, Arjun, Amartya, Arvind, Neel, Vian
bulbul:v2:

Female: Anushka, Manisha, Vidya, Arya
Male: Abhilash, Karun, Hitesh
Note: Speaker selection must match the chosen model version.

pitch: typing.Optional[float] — Controls the pitch of the audio. Lower values result in a deeper voice, while higher values make it sharper. The suitable range is between -0.75 and 0.75. Default is 0.0.

pace: typing.Optional[float] — Controls the speed of the audio. Lower values result in slower speech, while higher values make it faster. The suitable range is between 0.5 and 2.0. Default is 1.0.

loudness: typing.Optional[float] — Controls the loudness of the audio. Lower values result in quieter audio, while higher values make it louder. The suitable range is between 0.3 and 3.0. Default is 1.0.

speech_sample_rate: typing.Optional[SpeechSampleRate] — Specifies the sample rate of the output audio. Supported values are 8000, 16000, 22050, 24000 Hz. If not provided, the default is 22050 Hz.

enable_preprocessing: typing.Optional[bool] — Controls whether normalization of English words and numeric entities (e.g., numbers, dates) is performed. Set to true for better handling of mixed-language text. Default is false.

model: typing.Optional[TextToSpeechModel] — Specifies the model to use for text-to-speech conversion. Default is bulbul:v1.

request_options: typing.Optional[RequestOptions] — Request-specific configuration.