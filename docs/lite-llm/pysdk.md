LiteLLM Python SDK
Streaming
Add stream=True to receive chunks as they are generated:

from litellm import completion
import os

os.environ["OPENAI_API_KEY"] = "your-api-key"

for chunk in completion(
  model="openai/gpt-4o",
  messages=[{"role": "user", "content": "Write a short poem"}],
  stream=True,
):
    print(chunk.choices[0].delta.content or "", end="")

Exception Handling
LiteLLM maps every provider's errors to the OpenAI exception types — your existing error handling works out of the box:

import litellm

try:
    litellm.completion(
      model="anthropic/claude-instant-1",
      messages=[{"role": "user", "content": "Hey!"}]
    )
except litellm.AuthenticationError as e:
    print(f"Bad API key: {e}")
except litellm.RateLimitError as e:
    print(f"Rate limited: {e}")
except litellm.APIError as e:
    print(f"API error: {e}")

Logging & Observability
Send input/output to Langfuse, MLflow, Helicone, Lunary, and more with a single line:

import litellm

litellm.success_callback = ["langfuse", "mlflow", "helicone"]

response = litellm.completion(
  model="gpt-4o",
  messages=[{"role": "user", "content": "Hi!"}]
)

📖 See all observability integrations →

Track Costs & Usage
Use a callback to capture cost per response:

import litellm

def track_cost(kwargs, completion_response, start_time, end_time):
    print("Cost:", kwargs.get("response_cost", 0))

litellm.success_callback = [track_cost]

litellm.completion(
  model="gpt-4o",
  messages=[{"role": "user", "content": "Hello!"}],
  stream=True
)

📖 Custom callback docs →import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Input Params

## Common Params 
LiteLLM accepts and translates the [OpenAI Chat Completion params](https://platform.openai.com/docs/api-reference/chat/create) across all providers. 

### Usage
```python
import litellm

# set env variables
os.environ["OPENAI_API_KEY"] = "your-openai-key"

## SET MAX TOKENS - via completion() 
response = litellm.completion(
            model="gpt-3.5-turbo",
            messages=[{ "content": "Hello, how are you?","role": "user"}],
            max_tokens=10
        )

print(response)
```

### Translated OpenAI params

Use this function to get an up-to-date list of supported openai params for any model + provider. 

```python
from litellm import get_supported_openai_params

response = get_supported_openai_params(model="anthropic.claude-3", custom_llm_provider="bedrock")

print(response) # ["max_tokens", "tools", "tool_choice", "stream"]
```

This is a list of openai params we translate across providers.

Use `litellm.get_supported_openai_params()` for an updated list of params for each model + provider 

| Provider | temperature | max_completion_tokens | max_tokens | top_p | stream | stream_options | stop | n | presence_penalty | frequency_penalty | functions | function_call | logit_bias | user | response_format | seed| tools | tool_choice | logprobs | top_logprobs | extra_headers |
|--------------|-------------|------------------------|------------|-------|--------|----------------|------|-----|------------------|-------------------|-----------|----------------|-------------|------|------------------|-------------------|--------|--------------|----------|---------------|----------------------|
| Anthropic| â| â | â | â| â | â | â | || | || | â | â | | â | â || | â|
| OpenAI | â| â | â | â| â | â | â | â| â | â| â| â | â| â | â | â| â | â | â | â| â|
| Azure OpenAI | â| â | â | â| â | â | â | â| â | â| â| â | â| â | â | â| â | â | â | â| â|
| xAI| â|| â | â| â | â | â | â| â | â| || â| â | â | â| â | â | â | â||
| Replicate| â| â | â | â| â | â || || | || ||| |||| ||
| Anyscale | â| â | â | â| â | â || || | || ||| |||| ||
| Cohere | â| â | â | â| â | â | â | â|| | || ||| |||| ||
| Huggingface| â| â | â | â| â | â | â | || | || ||| |||| ||
| Openrouter | â| â | â | â| â | â | â | â| â | â| â|| ||| â| â ||| ||
| AI21 | â| â | â | â| â | â | â | â|| | || ||| |||| ||
| VertexAI | â| â | â | | â | â || || | || || â | â|||| ||
| Bedrock| â| â | â | â| â | â || || | || || â (model dependent) | |||| ||
| Sagemaker| â| â | â | â| â | â | â | || | || ||| |||| ||
| TogetherAI | â| â | â | â| â | â || || | â|| || â | | â | â || ||
| Sambanova| â| â | â | â| â | â | â | || | || || â | | â | â || ||
| AlephAlpha | â| â | â | â| â | â | â | || | || ||| |||| ||
| NLP Cloud| â| â | â | â| â | â || || | || ||| |||| ||
| Petals | â| â || â| â ||| || | || ||| |||| ||
| Ollama | â| â | â | â| â | â || â|| | || â||| | â ||| ||
| Databricks | â| â | â | â| â | â || || | || ||| |||| ||
| ClarifAI | â| â | â | | â | â || || | || ||| |||| ||
| Github | â| â | â | â| â | â | â | â| â | â| â|| || â | â (model dependent) | â (model dependent) || ||
| Novita AI| â| â || â| â | â | â | â| â | â| || â||| |||| ||
| Bytez | â| â || â| â | | | â|| || || || || || ||
| OVHCloud AI Endpoints | â | | â | â | â | â | â | | | | | | | | â | â | â | â | â | â | |

:::note

By default, LiteLLM raises an exception if the openai param being passed in isn't supported. 

To drop the param instead, set `litellm.drop_params = True` or `completion(..drop_params=True)`.

This **ONLY DROPS UNSUPPORTED OPENAI PARAMS**. 

LiteLLM assumes any non-openai param is provider specific and passes it in as a kwarg in the request body

::: 

## Input Params

```python
def completion(
    model: str,
    messages: List = [],
    # Optional OpenAI params
    timeout: Optional[Union[float, int]] = None,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    n: Optional[int] = None,
    stream: Optional[bool] = None,
    stream_options: Optional[dict] = None,
    stop=None,
    max_completion_tokens: Optional[int] = None,
    max_tokens: Optional[int] = None,
    presence_penalty: Optional[float] = None,
    frequency_penalty: Optional[float] = None,
    logit_bias: Optional[dict] = None,
    user: Optional[str] = None,
    # openai v1.0+ new params
    response_format: Optional[dict] = None,
    seed: Optional[int] = None,
    tools: Optional[List] = None,
    tool_choice: Optional[str] = None,
    parallel_tool_calls: Optional[bool] = None,
    logprobs: Optional[bool] = None,
    top_logprobs: Optional[int] = None,
    safety_identifier: Optional[str] = None,
    deployment_id=None,
    # soon to be deprecated params by OpenAI
    functions: Optional[List] = None,
    function_call: Optional[str] = None,
    # set api_base, api_version, api_key
    base_url: Optional[str] = None,
    api_version: Optional[str] = None,
    api_key: Optional[str] = None,
    model_list: Optional[list] = None,  # pass in a list of api_base,keys, etc.
    # Optional liteLLM function params
    **kwargs,

) -> ModelResponse:
```
### Required Fields

- `model`: *string* - ID of the model to use. Refer to the model endpoint compatibility table for details on which models work with the Chat API.
  
- `messages`: *array* - A list of messages comprising the conversation so far.

#### Properties of `messages`
*Note* - Each message in the array contains the following properties:

- `role`: *string* - The role of the message's author. Roles can be: system, user, assistant, function or tool.

- `content`: *string or list[dict] or null* - The contents of the message. It is required for all messages, but may be null for assistant messages with function calls.

- `name`: *string (optional)* - The name of the author of the message. It is required if the role is "function". The name should match the name of the function represented in the content. It can contain characters (a-z, A-Z, 0-9), and underscores, with a maximum length of 64 characters.

- `function_call`: *object (optional)* - The name and arguments of a function that should be called, as generated by the model.

- `tool_call_id`: *str (optional)* - Tool call that this message is responding to.


[**See All Message Values**](https://github.com/BerriAI/litellm/blob/main/litellm/types/llms/openai.py#L664)

#### Content Types

`content` can be a string (text only) or a list of content blocks (multimodal):

| Type | Description | Docs |
|------|-------------|------|
| `text` | Text content | [Type Definition](https://github.com/BerriAI/litellm/blob/main/litellm/types/llms/openai.py#L598) |
| `image_url` | Images | [Vision](./vision.md) |
| `input_audio` | Audio input | [Audio](./audio.md) |
| `video_url` | Video input | [Type Definition](https://github.com/BerriAI/litellm/blob/main/litellm/types/llms/openai.py#L625) |
| `file` | Files | [Document Understanding](./document_understanding.md) |
| `document` | Documents/PDFs | [Document Understanding](./document_understanding.md) |

**Examples:**
```python
# Text
messages=[{"role": "user", "content": [{"type": "text", "text": "Hello!"}]}]

# Image
messages=[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}]}]

# Audio
messages=[{"role": "user", "content": [{"type": "input_audio", "input_audio": {"data": "<base64>", "format": "wav"}}]}]

# Video
messages=[{"role": "user", "content": [{"type": "video_url", "video_url": {"url": "https://example.com/video.mp4"}}]}]

# File
messages=[{"role": "user", "content": [{"type": "file", "file": {"file_id": "https://example.com/doc.pdf"}}]}]

# Document
messages=[{"role": "user", "content": [{"type": "document", "source": {"type": "text", "media_type": "application/pdf", "data": "<base64>"}}]}]

# Combining multiple types (multimodal)
messages=[{"role": "user", "content": [
    {"type": "text", "text": "Generate a product description based on this image"},
    {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}
]}]
```

## Optional Fields

- `temperature`: *number or null (optional)* - The sampling temperature to be used, between 0 and 2. Higher values like 0.8 produce more random outputs, while lower values like 0.2 make outputs more focused and deterministic. 

- `top_p`: *number or null (optional)* - An alternative to sampling with temperature. It instructs the model to consider the results of the tokens with top_p probability. For example, 0.1 means only the tokens comprising the top 10% probability mass are considered.

- `n`: *integer or null (optional)* - The number of chat completion choices to generate for each input message.

- `stream`: *boolean or null (optional)* - If set to true, it sends partial message deltas. Tokens will be sent as they become available, with the stream terminated by a [DONE] message.

- `stream_options` *dict or null (optional)* - Options for streaming response. Only set this when you set `stream: true`

    - `include_usage` *boolean (optional)* - If set, an additional chunk will be streamed before the data: [DONE] message. The usage field on this chunk shows the token usage statistics for the entire request, and the choices field will always be an empty array. All other chunks will also include a usage field, but with a null value. 

- `stop`: *string/ array/ null (optional)* - Up to 4 sequences where the API will stop generating further tokens.
  
  **Note**: OpenAI supports a maximum of 4 stop sequences. If you provide more than 4, LiteLLM will automatically truncate the list to the first 4 elements. To disable this automatic truncation, set `litellm.disable_stop_sequence_limit = True`.

- `max_completion_tokens`: *integer (optional)* -  An upper bound for the number of tokens that can be generated for a completion, including visible output tokens and reasoning tokens.

- `max_tokens`: *integer (optional)* - The maximum number of tokens to generate in the chat completion.

- `presence_penalty`: *number or null (optional)* - It is used to penalize new tokens based on their existence in the text so far.

- `response_format`: *object (optional)* - An object specifying the format that the model must output.

    - Setting to `{ "type": "json_object" }` enables JSON mode, which guarantees the message the model generates is valid JSON.
    
    - Important: when using JSON mode, you must also instruct the model to produce JSON yourself via a system or user message. Without this, the model may generate an unending stream of whitespace until the generation reaches the token limit, resulting in a long-running and seemingly "stuck" request. Also note that the message content may be partially cut off if finish_reason="length", which indicates the generation exceeded max_tokens or the conversation exceeded the max context length.

- `seed`: *integer or null (optional)* - This feature is in Beta. If specified, our system will make a best effort to sample deterministically, such that repeated requests with the same seed and parameters should return the same result. Determinism is not guaranteed, and you should refer to the `system_fingerprint` response parameter to monitor changes in the backend.

- `tools`: *array (optional)* - A list of tools the model may call. Use this to provide a list of functions the model may generate JSON inputs for.

    - `type`: *string* - The type of the tool. You can set this to `"function"` or `"mcp"` (matching the `/responses` schema) to call LiteLLM-registered MCP servers directly from `/chat/completions`.

    - `function`: *object* - Required for function tools.

- `tool_choice`: *string or object (optional)* - Controls which (if any) function is called by the model. none means the model will not call a function and instead generates a message. auto means the model can pick between generating a message or calling a function. Specifying a particular function via `{"type": "function", "function": {"name": "my_function"}}` forces the model to call that function.

    - `none` is the default when no functions are present. `auto` is the default if functions are present.

- `parallel_tool_calls`: *boolean (optional)* - Whether to enable parallel function calling during tool use. OpenAI default is true.

- `frequency_penalty`: *number or null (optional)* - It is used to penalize new tokens based on their frequency in the text so far.

- `logit_bias`: *map (optional)* - Used to modify the probability of specific tokens appearing in the completion.

- `user`: *string (optional)* - A unique identifier representing your end-user. This can help OpenAI to monitor and detect abuse.

- `timeout`: *int (optional)* - Timeout in seconds for completion requests (Defaults to 600 seconds)

- `logprobs`: * bool (optional)* - Whether to return log probabilities of the output tokens or not. If true returns the log probabilities of each output token returned in the content of message
        
- `top_logprobs`: *int (optional)* - An integer between 0 and 5 specifying the number of most likely tokens to return at each token position, each with an associated log probability. `logprobs` must be set to true if this parameter is used.

- `safety_identifier`: *string (optional)* - A unique identifier for tracking and managing safety-related requests. This parameter helps with safety monitoring and compliance tracking.

- `headers`: *dict (optional)* - A dictionary of headers to be sent with the request.

- `extra_headers`: *dict (optional)* - Alternative to `headers`, used to send extra headers in LLM API request. 

#### Deprecated Params
- `functions`: *array* - A list of functions that the model may use to generate JSON inputs. Each function should have the following properties:

    - `name`: *string* - The name of the function to be called. It should contain a-z, A-Z, 0-9, underscores and dashes, with a maximum length of 64 characters.
    
    - `description`: *string (optional)* - A description explaining what the function does. It helps the model to decide when and how to call the function.
    
    - `parameters`: *object* - The parameters that the function accepts, described as a JSON Schema object.
    
- `function_call`: *string or object (optional)* - Controls how the model responds to function calls.


#### litellm-specific params 

- `api_base`: *string (optional)* - The api endpoint you want to call the model with

- `api_version`: *string (optional)* - (Azure-specific) the api version for the call

- `num_retries`: *int (optional)* - The number of times to retry the API call if an APIError, TimeoutError or ServiceUnavailableError occurs 

- `context_window_fallback_dict`: *dict (optional)* - A mapping of model to use if call fails due to context window error

- `fallbacks`: *list (optional)* - A list of model names + params to be used, in case the initial call fails

- `metadata`: *dict (optional)* - Any additional data you want to be logged when the call is made (sent to logging integrations, eg. promptlayer and accessible via custom callback function)

**CUSTOM MODEL COST** 
- `input_cost_per_token`: *float (optional)* - The cost per input token for the completion call 

- `output_cost_per_token`: *float (optional)* - The cost per output token for the completion call 

**CUSTOM PROMPT TEMPLATE** (See [prompt formatting for more info](./prompt_formatting.md#format-prompt-yourself))
- `initial_prompt_value`: *string (optional)* - Initial string applied at the start of the input messages

- `roles`: *dict (optional)* - Dictionary specifying how to format the prompt based on the role + message passed in via `messages`. 

- `final_prompt_value`: *string (optional)* - Final string applied at the end of the input messages

- `bos_token`: *string (optional)* - Initial string applied at the start of a sequence

- `eos_token`: *string (optional)* - Initial string applied at the end of a sequence

- `hf_model_name`: *string (optional)* - [Sagemaker Only] The corresponding huggingface name of the model, used to pull the right chat template for the model. 
# Setting API Keys, Base, Version

LiteLLM allows you to specify the following:
* API Key
* API Base
* API Version
* API Type
* Project
* Location
* Token

Useful Helper functions: 
* [`check_valid_key()`](#check_valid_key)
* [`get_valid_models()`](#get_valid_models)

You can set the API configs using:
* Environment Variables
* litellm variables `litellm.api_key`
* Passing args to `completion()`

## Environment Variables

### Setting API Keys

Set the liteLLM API key or specific provider key:

```python
import os 

# Set OpenAI API key
os.environ["OPENAI_API_KEY"] = "Your API Key"
os.environ["ANTHROPIC_API_KEY"] = "Your API Key"
os.environ["XAI_API_KEY"] = "Your API Key"
os.environ["REPLICATE_API_KEY"] = "Your API Key"
os.environ["TOGETHERAI_API_KEY"] = "Your API Key"
```

### Setting API Base, API Version, API Type

```python
# for azure openai
os.environ['AZURE_API_BASE'] = "https://openai-gpt-4-test2-v-12.openai.azure.com/"
os.environ['AZURE_API_VERSION'] = "2023-05-15" # [OPTIONAL]
os.environ['AZURE_API_TYPE'] = "azure" # [OPTIONAL]

# for openai
os.environ['OPENAI_BASE_URL'] = "https://your_host/v1"
```

### Setting Project, Location, Token

For cloud providers:
- Azure
- Bedrock
- GCP
- Watson AI 

you might need to set additional parameters. LiteLLM provides a common set of params, that we map across all providers. 

|      | LiteLLM param | Watson       | Vertex AI    | Azure        | Bedrock      |
|------|--------------|--------------|--------------|--------------|--------------|
| Project | project | watsonx_project | vertex_project | n/a | n/a |
| Region | region_name | watsonx_region_name | vertex_location | n/a | aws_region_name |
| Token | token | watsonx_token or token | n/a | azure_ad_token | n/a |

If you want, you can call them by their provider-specific params as well. 

## litellm variables

### litellm.api_key
This variable is checked for all providers

```python
import litellm
# openai call
litellm.api_key = "sk-OpenAIKey"
response = litellm.completion(messages=messages, model="gpt-3.5-turbo")

# anthropic call
litellm.api_key = "sk-AnthropicKey"
response = litellm.completion(messages=messages, model="claude-2")
```

### litellm.provider_key (example litellm.openai_key)

```python
litellm.openai_key = "sk-OpenAIKey"
response = litellm.completion(messages=messages, model="gpt-3.5-turbo")

# anthropic call
litellm.anthropic_key = "sk-AnthropicKey"
response = litellm.completion(messages=messages, model="claude-2")
```

### litellm.api_base

```python
import litellm
litellm.api_base = "https://hosted-llm-api.co"
response = litellm.completion(messages=messages, model="gpt-3.5-turbo")
```

### litellm.api_version

```python
import litellm
litellm.api_version = "2023-05-15"
response = litellm.completion(messages=messages, model="gpt-3.5-turbo")
```

### litellm.organization
```python
import litellm
litellm.organization = "LiteLlmOrg"
response = litellm.completion(messages=messages, model="gpt-3.5-turbo")
```

## Passing Args to completion() (or any litellm endpoint - `transcription`, `embedding`, `text_completion`, etc)

You can pass the API key within `completion()` call:

### api_key
```python
from litellm import completion

messages = [{ "content": "Hello, how are you?","role": "user"}]

response = completion("command-nightly", messages, api_key="Your-Api-Key")
```

### api_base

```python
from litellm import completion

messages = [{ "content": "Hello, how are you?","role": "user"}]

response = completion("command-nightly", messages, api_base="https://hosted-llm-api.co")
```

### api_version

```python
from litellm import completion

messages = [{ "content": "Hello, how are you?","role": "user"}]

response = completion("command-nightly", messages, api_version="2023-02-15")
```

## Helper Functions

### `check_valid_key()`

Check if a user submitted a valid key for the model they're trying to call. 

```python
key = "bad-key"
response = check_valid_key(model="gpt-3.5-turbo", api_key=key)
assert(response == False)
```

### `get_valid_models()`

This helper reads the .env and returns a list of supported llms for user

```python
old_environ = os.environ
os.environ = {'OPENAI_API_KEY': 'temp'} # mock set only openai key in environ

valid_models = get_valid_models()
print(valid_models)

# list of openai supported llms on litellm
expected_models = litellm.open_ai_chat_completion_models + litellm.open_ai_text_completion_models

assert(valid_models == expected_models)

# reset replicate env key
os.environ = old_environ
```

### `get_valid_models(check_provider_endpoint: True)`

This helper will check the provider's endpoint for valid models.

Currently implemented for:
- OpenAI (if OPENAI_API_KEY is set)
- Fireworks AI (if FIREWORKS_AI_API_KEY is set)
- LiteLLM Proxy (if LITELLM_PROXY_API_KEY is set)
- Gemini (if GEMINI_API_KEY is set)
- XAI (if XAI_API_KEY is set)   
- Anthropic (if ANTHROPIC_API_KEY is set)

You can also specify a custom provider to check:

**All providers**:
```python
from litellm import get_valid_models

valid_models = get_valid_models(check_provider_endpoint=True)
print(valid_models)
```

**Specific provider**:
```python
from litellm import get_valid_models

valid_models = get_valid_models(check_provider_endpoint=True, custom_llm_provider="openai")
print(valid_models)
```

### `validate_environment(model: str)`

This helper tells you if you have all the required environment variables for a model, and if not - what's missing. 

```python
from litellm import validate_environment

print(validate_environment("openai/gpt-3.5-turbo"))
```

# Exception Mapping

LiteLLM maps exceptions across all providers to their OpenAI counterparts.

All exceptions can be imported from `litellm` - e.g. `from litellm import BadRequestError`

## LiteLLM Exceptions

| Status Code | Error Type               | Inherits from | Description |
|-------------|--------------------------|---------------|-------------|
| 400         | BadRequestError          | openai.BadRequestError |
| 400 | UnsupportedParamsError | litellm.BadRequestError | Raised when unsupported params are passed |
| 400         | ContextWindowExceededError| litellm.BadRequestError | Special error type for context window exceeded error messages - enables context window fallbacks |
| 400         | ContentPolicyViolationError| litellm.BadRequestError | Special error type for content policy violation error messages - enables content policy fallbacks |
| 400         | ImageFetchError | litellm.BadRequestError | Raised when there are errors fetching or processing images |
| 400 | InvalidRequestError | openai.BadRequestError | Deprecated error, use BadRequestError instead |
| 401         | AuthenticationError      | openai.AuthenticationError |
| 403         | PermissionDeniedError    | openai.PermissionDeniedError |
| 404         | NotFoundError            | openai.NotFoundError | raise when invalid models passed, example gpt-8 |
| 408 | Timeout | openai.APITimeoutError | Raised when a timeout occurs |
| 422         | UnprocessableEntityError | openai.UnprocessableEntityError |
| 429         | RateLimitError           | openai.RateLimitError |
| 500         | APIConnectionError       | openai.APIConnectionError | If any unmapped error is returned, we return this error |
| 500         | APIError | openai.APIError | Generic 500-status code error | 
| 503 | ServiceUnavailableError | openai.APIStatusError | If provider returns a service unavailable error, this error is raised |
| >=500       | InternalServerError      | openai.InternalServerError | If any unmapped 500-status code error is returned, this error is raised |
| N/A         | APIResponseValidationError | openai.APIResponseValidationError | If Rules are used, and request/response fails a rule, this error is raised |
| N/A | BudgetExceededError | Exception | Raised for proxy, when budget is exceeded |
| N/A | JSONSchemaValidationError | litellm.APIResponseValidationError | Raised when response does not match expected json schema - used if `response_schema` param passed in with `enforce_validation=True` |
| N/A | MockException | Exception | Internal exception, raised by mock_completion class. Do not use directly | 
| N/A | OpenAIError | openai.OpenAIError | Deprecated internal exception, inherits from openai.OpenAIError. |



Base case we return APIConnectionError

All our exceptions inherit from OpenAI's exception types, so any error-handling you have for that, should work out of the box with LiteLLM. 

For all cases, the exception returned inherits from the original OpenAI Exception but contains 3 additional attributes: 
* status_code - the http status code of the exception
* message - the error message
* llm_provider - the provider raising the exception

## Usage

```python 
import litellm
import openai

try:
    response = litellm.completion(
                model="gpt-4",
                messages=[
                    {
                        "role": "user",
                        "content": "hello, write a 20 pageg essay"
                    }
                ],
                timeout=0.01, # this will raise a timeout exception
            )
except openai.APITimeoutError as e:
    print("Passed: Raised correct exception. Got openai.APITimeoutError\nGood Job", e)
    print(type(e))
    pass
```

## Usage - Catching Streaming Exceptions
```python
import litellm
try:
    response = litellm.completion(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "user",
                "content": "hello, write a 20 pg essay"
            }
        ],
        timeout=0.0001, # this will raise an exception
        stream=True,
    )
    for chunk in response:
        print(chunk)
except openai.APITimeoutError as e:
    print("Passed: Raised correct exception. Got openai.APITimeoutError\nGood Job", e)
    print(type(e))
    pass
except Exception as e:
    print(f"Did not raise error `openai.APITimeoutError`. Instead raised error type: {type(e)}, Error: {e}")

```

## Usage - Should you retry exception? 

```
import litellm
import openai

try:
    response = litellm.completion(
                model="gpt-4",
                messages=[
                    {
                        "role": "user",
                        "content": "hello, write a 20 pageg essay"
                    }
                ],
                timeout=0.01, # this will raise a timeout exception
            )
except openai.APITimeoutError as e:
    should_retry = litellm._should_retry(e.status_code)
    print(f"should_retry: {should_retry}")
```

## Advanced

### Accessing Provider-Specific Error Details

LiteLLM exceptions include a `provider_specific_fields` attribute that contains additional error information specific to each provider. This is particularly useful for Azure OpenAI, which provides detailed content filtering information.

#### Azure OpenAI - Content Policy Violation Inner Error Access

When Azure OpenAI returns content policy violations, you can access the detailed content filtering results through the `innererror` field:

```python
import litellm
from litellm.exceptions import ContentPolicyViolationError

try:
    response = litellm.completion(
        model="azure/gpt-4",
        messages=[
            {
                "role": "user", 
                "content": "Some content that might violate policies"
            }
        ]
    )
except ContentPolicyViolationError as e:
    # Access Azure-specific error details
    if e.provider_specific_fields and "innererror" in e.provider_specific_fields:
        innererror = e.provider_specific_fields["innererror"]
        
        # Access content filter results
        content_filter_result = innererror.get("content_filter_result", {})
        
        print(f"Content filter code: {innererror.get('code')}")
        print(f"Hate filtered: {content_filter_result.get('hate', {}).get('filtered')}")
        print(f"Violence severity: {content_filter_result.get('violence', {}).get('severity')}")
        print(f"Sexual content filtered: {content_filter_result.get('sexual', {}).get('filtered')}")
```

**Example Response Structure:**

When calling the LiteLLM proxy, content policy violations will return detailed filtering information:

```json
{
  "error": {
    "message": "litellm.ContentPolicyViolationError: AzureException - The response was filtered due to the prompt triggering Azure OpenAI's content management policy...",
    "type": null,
    "param": null,
    "code": "400",
    "provider_specific_fields": {
      "innererror": {
        "code": "ResponsibleAIPolicyViolation",
        "content_filter_result": {
          "hate": {
            "filtered": true,
            "severity": "high"
          },
          "jailbreak": {
            "filtered": false,
            "detected": false
          },
          "self_harm": {
            "filtered": false,
            "severity": "safe"
          },
          "sexual": {
            "filtered": false,
            "severity": "safe"
          },
          "violence": {
            "filtered": true,
            "severity": "medium"
          }
        }
      }
    }
  }
}

## Details 

To see how it's implemented - [check out the code](https://github.com/BerriAI/litellm/blob/a42c197e5a6de56ea576c73715e6c7c6b19fa249/litellm/utils.py#L1217)

[Create an issue](https://github.com/BerriAI/litellm/issues/new) **or** [make a PR](https://github.com/BerriAI/litellm/pulls) if you want to improve the exception mapping. 

**Note** For OpenAI and Azure we return the original exception (since they're of the OpenAI Error type). But we add the 'llm_provider' attribute to them. [See code](https://github.com/BerriAI/litellm/blob/a42c197e5a6de56ea576c73715e6c7c6b19fa249/litellm/utils.py#L1221)

LiteLLM Exceptions
Status Code	Error Type	Inherits from	Description
400	BadRequestError	openai.BadRequestError	
400	UnsupportedParamsError	litellm.BadRequestError	Raised when unsupported params are passed
400	ContextWindowExceededError	litellm.BadRequestError	Special error type for context window exceeded error messages - enables context window fallbacks
400	ContentPolicyViolationError	litellm.BadRequestError	Special error type for content policy violation error messages - enables content policy fallbacks
400	ImageFetchError	litellm.BadRequestError	Raised when there are errors fetching or processing images
400	InvalidRequestError	openai.BadRequestError	Deprecated error, use BadRequestError instead
401	AuthenticationError	openai.AuthenticationError	
403	PermissionDeniedError	openai.PermissionDeniedError	
404	NotFoundError	openai.NotFoundError	raise when invalid models passed, example gpt-8
408	Timeout	openai.APITimeoutError	Raised when a timeout occurs
422	UnprocessableEntityError	openai.UnprocessableEntityError	
429	RateLimitError	openai.RateLimitError	
500	APIConnectionError	openai.APIConnectionError	If any unmapped error is returned, we return this error
500	APIError	openai.APIError	Generic 500-status code error
503	ServiceUnavailableError	openai.APIStatusError	If provider returns a service unavailable error, this error is raised
>=500	InternalServerError	openai.InternalServerError	If any unmapped 500-status code error is returned, this error is raised
N/A	APIResponseValidationError	openai.APIResponseValidationError	If Rules are used, and request/response fails a rule, this error is raised
N/A	BudgetExceededError	Exception	Raised for proxy, when budget is exceeded
N/A	JSONSchemaValidationError	litellm.APIResponseValidationError	Raised when response does not match expected json schema - used if response_schema param passed in with enforce_validation=True
N/A	MockException	Exception	Internal exception, raised by mock_completion class. Do not use directly
N/A	OpenAIError	openai.OpenAIError	Deprecated internal exception, inherits from openai.OpenAIError.
Base case we return APIConnectionError

All our exceptions inherit from OpenAI's exception types, so any error-handling you have for that, should work out of the box with LiteLLM.

For all cases, the exception returned inherits from the original OpenAI Exception but contains 3 additional attributes:

status_code - the http status code of the exception
message - the error message
llm_provider - the provider raising the exception

> For a deeper understanding of these exceptions, you can check out [this](https://github.com/BerriAI/litellm/blob/d7e58d13bf9ba9edbab2ab2f096f3de7547f35fa/litellm/utils.py#L1544) implementation for additional insights.

The `ContextWindowExceededError` is a sub-class of `InvalidRequestError`. It was introduced to provide more granularity for exception-handling scenarios. Please refer to [this issue to learn more](https://github.com/BerriAI/litellm/issues/228).

Contributions to improve exception mapping are [welcome](https://github.com/BerriAI/litellm#contributing)


