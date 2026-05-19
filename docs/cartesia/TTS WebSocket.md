> ## Documentation Index
> Fetch the complete documentation index at: https://docs.cartesia.ai/llms.txt
> Use this file to discover all available pages before exploring further.
> ## Documentation Index
> Fetch the complete documentation index at: https://docs.cartesia.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# WebSocket Basic

> Basic WebSocket usage with websocket_connect() context manager.

<Tabs>
  <Tab title="Python">
    ```python theme={null}
    def tts_websocket_basic(client: Cartesia) -> None:
        """Basic WebSocket usage with websocket_connect() context manager."""
        with client.tts.websocket_connect() as connection:
            connection.send({
                "model_id": "sonic-3.5",
                "transcript": "Hello, world!",
                "voice": {"mode": "id", "id": "voice-id"},
                "output_format": {"container": "raw", "encoding": "pcm_f32le", "sample_rate": 44100},
            })

            import datetime
            filename = f"tts_websocket_basic_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pcm"

            # Write chunks to file as they arrive.
            # You could also send chunks over the network, play them in real-time, etc.
            with open(filename, "wb") as f:
                for response in connection:
                    if response.type == "chunk" and response.audio:
                        f.write(response.audio)
                    elif response.done:
                        break

            print(f"Saved audio to {filename}")
            print(f"Play with:\n  $ ffplay -f f32le -ar 44100 {filename}")
    ```

    From [cartesia-python/examples/examples.py:196](https://github.com/cartesia-ai/cartesia-python/blob/main/examples/examples.py#L196)
  </Tab>

  <Tab title="Python (Async)">
    ```python theme={null}
    async def tts_websocket_basic_async(client: AsyncCartesia) -> None:
        """Basic WebSocket usage with websocket_connect() context manager."""
        async with client.tts.websocket_connect() as connection:
            await connection.send({
                "model_id": "sonic-3.5",
                "transcript": "Hello, world!",
                "voice": {"mode": "id", "id": "6ccbfb76-1fc6-48f7-b71d-91ac6298247b"},
                "output_format": {"container": "raw", "encoding": "pcm_f32le", "sample_rate": 44100},
            })

            filename = f"tts_ws_basic_async_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pcm"

            with open(filename, "wb") as f:
                async for response in connection:
                    if response.type == "chunk" and response.audio:
                        f.write(response.audio)
                    elif response.done:
                        break
            
            print(f"Saved audio to {filename}")
            print(f"Play with: ffplay -f f32le -ar 44100 {filename}")
    ```

    From [cartesia-python/examples/async\_examples.py:109](https://github.com/cartesia-ai/cartesia-python/blob/main/examples/async_examples.py#L109)
  </Tab>

  <Tab title="TypeScript">
    ```typescript theme={null}
    async function ttsWebsocketBasic(client: Cartesia): Promise<void> {
      /** Basic WebSocket usage with websocket_connect() context manager. */
      const ws = await client.tts.websocket();
      ws.on('error', (err) => console.error('WS error:', err.message));

      const filename = `tts_websocket_basic_${timestamp()}.pcm`;
      const file = fs.createWriteStream(filename);

      for await (const event of ws.generate({
        model_id: 'sonic-3.5',
        transcript: 'Hello, world!',
        voice: { mode: 'id', id: '6ccbfb76-1fc6-48f7-b71d-91ac6298247b' },
        output_format: { container: 'raw', encoding: 'pcm_f32le', sample_rate: 44100 },
      })) {
        if (event.type === 'chunk') {
          if (event.audio) file.write(event.audio);
        }
      }

      file.end();
      ws.close();
      console.log(`Saved audio to ${filename}`);
      console.log(`Play with:\n  $ ffplay -f f32le -ar 44100 ${filename}`);
    }
    ```

    From [cartesia-js/examples/node\_examples.ts:48](https://github.com/cartesia-ai/cartesia-js/blob/main/examples/node_examples.ts#L48)
  </Tab>
</Tabs>

## Run this example

<Tabs>
  <Tab title="Python">
    ```sh theme={null}
    cd cartesia-python
    CARTESIA_API_KEY=YOUR_KEY python3 examples/examples.py tts_websocket_basic
    ```
  </Tab>

  <Tab title="Python (Async)">
    ```sh theme={null}
    cd cartesia-python
    CARTESIA_API_KEY=YOUR_KEY python3 examples/async_examples.py tts_websocket_basic_async
    ```
  </Tab>

  <Tab title="TypeScript">
    ```sh theme={null}
    cd cartesia-js
    CARTESIA_API_KEY=YOUR_KEY npx ts-node examples/node_examples.ts ttsWebsocketBasic
    ```
  </Tab>
</Tabs>

# WebSocket Continuations

> Streaming a transcript split into multiple parts, using continuations.

<Tabs>
  <Tab title="Python">
    Useful for streaming transcripts generated by an LLM.

    ```python theme={null}
    def tts_websocket_continuations(client: Cartesia) -> None:
        """Streaming a transcript split into multiple parts, using continuations.
        Useful for streaming transcripts generated by an LLM."""
        with client.tts.websocket_connect() as connection:
            ctx = connection.context(
                model_id="sonic-3.5",
                voice={"mode": "id", "id": "6ccbfb76-1fc6-48f7-b71d-91ac6298247b"},
                output_format={
                    "container": "raw",
                    "encoding": "pcm_f32le",
                    "sample_rate": 44100,
                },
            )

            for part in ["The road ", "goes ever ", "on and ", "on."]:
                ctx.push(part)

            ctx.no_more_inputs()

            import datetime
            filename = f"tts_websocket_continuations_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pcm"

            # Write chunks to file as they arrive.
            # You could also send chunks over the network, play them in real-time, etc.
            with open(filename, "wb") as f:
                for response in ctx.receive():
                    if response.type == "chunk" and response.audio:
                        f.write(response.audio)

            print(f"Saved audio to {filename}")
            print(f"Play with:\n  $ ffplay -f f32le -ar 44100 {filename}")
    ```

    From [cartesia-python/examples/examples.py:222](https://github.com/cartesia-ai/cartesia-python/blob/main/examples/examples.py#L222)
  </Tab>

  <Tab title="Python (Async)">
    ```python theme={null}
    async def tts_websocket_continuations_async(client: AsyncCartesia) -> None:
        """Streaming a transcript split into multiple parts, using continuations."""
        transcripts = ["The only thing we have to fear ", "is ", "fear itself."]
        output_format = {"container": "raw", "encoding": "pcm_f32le", "sample_rate": 44100}

        async with client.tts.websocket_connect() as connection:
            ctx = connection.context()

            for transcript in transcripts:
                await ctx.send(
                    model_id="sonic-3.5",
                    transcript=transcript,
                    voice={"mode": "id", "id": "6ccbfb76-1fc6-48f7-b71d-91ac6298247b"},
                    output_format=output_format,
                    continue_=True,
                )

            await ctx.no_more_inputs()

            filename = f"tts_ws_continuations_async_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pcm"

            with open(filename, "wb") as f:
                async for response in ctx.receive():
                    if response.type == "chunk" and response.audio:
                        f.write(response.audio)

            print(f"Saved audio to {filename}")
            print(f"Play with: ffplay -f f32le -ar 44100 {filename}")
    ```

    From [cartesia-python/examples/async\_examples.py:131](https://github.com/cartesia-ai/cartesia-python/blob/main/examples/async_examples.py#L131)
  </Tab>

  <Tab title="TypeScript">
    ```typescript theme={null}
    async function ttsWebsocketContinuations(client: Cartesia): Promise<void> {
      /** Streaming a transcript split into multiple parts, using continuations. */
      const ws = await client.tts.websocket();
      ws.on('error', (err) => console.error('WS error:', err.message));

      const ctx = ws.context({
        model_id: 'sonic-3.5',
        voice: { mode: 'id', id: '6ccbfb76-1fc6-48f7-b71d-91ac6298247b' },
        output_format: { container: 'raw', encoding: 'pcm_f32le', sample_rate: 44100 },
      });

      for (const part of ['The road ', 'goes ever ', 'on and ', 'on.']) {
        await ctx.push({ transcript: part });
      }
      await ctx.no_more_inputs();

      const filename = `tts_websocket_continuations_${timestamp()}.pcm`;
      const file = fs.createWriteStream(filename);

      for await (const event of ctx.receive()) {
        if (event.type === 'chunk') {
          if (event.audio) file.write(event.audio);
        }
      }

      file.end();
      ws.close();
      console.log(`Saved audio to ${filename}`);
      console.log(`Play with:\n  $ ffplay -f f32le -ar 44100 ${filename}`);
    }
    ```

    From [cartesia-js/examples/node\_examples.ts:73](https://github.com/cartesia-ai/cartesia-js/blob/main/examples/node_examples.ts#L73)
  </Tab>
</Tabs>

## Run this example

<Tabs>
  <Tab title="Python">
    ```sh theme={null}
    cd cartesia-python
    CARTESIA_API_KEY=YOUR_KEY python3 examples/examples.py tts_websocket_continuations
    ```
  </Tab>

  <Tab title="Python (Async)">
    ```sh theme={null}
    cd cartesia-python
    CARTESIA_API_KEY=YOUR_KEY python3 examples/async_examples.py tts_websocket_continuations_async
    ```
  </Tab>

  <Tab title="TypeScript">
    ```sh theme={null}
    cd cartesia-js
    CARTESIA_API_KEY=YOUR_KEY npx ts-node examples/node_examples.ts ttsWebsocketContinuations
    ```
  </Tab>
</Tabs>
> ## Documentation Index
> Fetch the complete documentation index at: https://docs.cartesia.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# WebSocket Continuations

> Streaming a transcript split into multiple parts, using continuations.

<Tabs>
  <Tab title="Python">
    Useful for streaming transcripts generated by an LLM.

    ```python theme={null}
    def tts_websocket_continuations(client: Cartesia) -> None:
        """Streaming a transcript split into multiple parts, using continuations.
        Useful for streaming transcripts generated by an LLM."""
        with client.tts.websocket_connect() as connection:
            ctx = connection.context(
                model_id="sonic-3.5",
                voice={"mode": "id", "id": "6ccbfb76-1fc6-48f7-b71d-91ac6298247b"},
                output_format={
                    "container": "raw",
                    "encoding": "pcm_f32le",
                    "sample_rate": 44100,
                },
            )

            for part in ["The road ", "goes ever ", "on and ", "on."]:
                ctx.push(part)

            ctx.no_more_inputs()

            import datetime
            filename = f"tts_websocket_continuations_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pcm"

            # Write chunks to file as they arrive.
            # You could also send chunks over the network, play them in real-time, etc.
            with open(filename, "wb") as f:
                for response in ctx.receive():
                    if response.type == "chunk" and response.audio:
                        f.write(response.audio)

            print(f"Saved audio to {filename}")
            print(f"Play with:\n  $ ffplay -f f32le -ar 44100 {filename}")
    ```

    From [cartesia-python/examples/examples.py:222](https://github.com/cartesia-ai/cartesia-python/blob/main/examples/examples.py#L222)
  </Tab>

  <Tab title="Python (Async)">
    ```python theme={null}
    async def tts_websocket_continuations_async(client: AsyncCartesia) -> None:
        """Streaming a transcript split into multiple parts, using continuations."""
        transcripts = ["The only thing we have to fear ", "is ", "fear itself."]
        output_format = {"container": "raw", "encoding": "pcm_f32le", "sample_rate": 44100}

        async with client.tts.websocket_connect() as connection:
            ctx = connection.context()

            for transcript in transcripts:
                await ctx.send(
                    model_id="sonic-3.5",
                    transcript=transcript,
                    voice={"mode": "id", "id": "6ccbfb76-1fc6-48f7-b71d-91ac6298247b"},
                    output_format=output_format,
                    continue_=True,
                )

            await ctx.no_more_inputs()

            filename = f"tts_ws_continuations_async_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pcm"

            with open(filename, "wb") as f:
                async for response in ctx.receive():
                    if response.type == "chunk" and response.audio:
                        f.write(response.audio)

            print(f"Saved audio to {filename}")
            print(f"Play with: ffplay -f f32le -ar 44100 {filename}")
    ```

    From [cartesia-python/examples/async\_examples.py:131](https://github.com/cartesia-ai/cartesia-python/blob/main/examples/async_examples.py#L131)
  </Tab>

  <Tab title="TypeScript">
    ```typescript theme={null}
    async function ttsWebsocketContinuations(client: Cartesia): Promise<void> {
      /** Streaming a transcript split into multiple parts, using continuations. */
      const ws = await client.tts.websocket();
      ws.on('error', (err) => console.error('WS error:', err.message));

      const ctx = ws.context({
        model_id: 'sonic-3.5',
        voice: { mode: 'id', id: '6ccbfb76-1fc6-48f7-b71d-91ac6298247b' },
        output_format: { container: 'raw', encoding: 'pcm_f32le', sample_rate: 44100 },
      });

      for (const part of ['The road ', 'goes ever ', 'on and ', 'on.']) {
        await ctx.push({ transcript: part });
      }
      await ctx.no_more_inputs();

      const filename = `tts_websocket_continuations_${timestamp()}.pcm`;
      const file = fs.createWriteStream(filename);

      for await (const event of ctx.receive()) {
        if (event.type === 'chunk') {
          if (event.audio) file.write(event.audio);
        }
      }

      file.end();
      ws.close();
      console.log(`Saved audio to ${filename}`);
      console.log(`Play with:\n  $ ffplay -f f32le -ar 44100 ${filename}`);
    }
    ```

    From [cartesia-js/examples/node\_examples.ts:73](https://github.com/cartesia-ai/cartesia-js/blob/main/examples/node_examples.ts#L73)
  </Tab>
</Tabs>

## Run this example

<Tabs>
  <Tab title="Python">
    ```sh theme={null}
    cd cartesia-python
    CARTESIA_API_KEY=YOUR_KEY python3 examples/examples.py tts_websocket_continuations
    ```
  </Tab>

  <Tab title="Python (Async)">
    ```sh theme={null}
    cd cartesia-python
    CARTESIA_API_KEY=YOUR_KEY python3 examples/async_examples.py tts_websocket_continuations_async
    ```
  </Tab>

  <Tab title="TypeScript">
    ```sh theme={null}
    cd cartesia-js
    CARTESIA_API_KEY=YOUR_KEY npx ts-node examples/node_examples.ts ttsWebsocketContinuations
    ```
  </Tab>
</Tabs>
> ## Documentation Index
> Fetch the complete documentation index at: https://docs.cartesia.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# WebSocket Response Handling

> WebSocket response type handling.

<Tabs>
  <Tab title="Python">
    ```python theme={null}
    def tts_websocket_response_handling(client: Cartesia) -> None:
        """WebSocket response type handling."""
        with client.tts.websocket_connect() as connection:
            connection.send({
                "model_id": "sonic-3.5",
                "transcript": "Hello, world!",
                "voice": {"mode": "id", "id": "voice-id"},
                "output_format": {"container": "raw", "encoding": "pcm_f32le", "sample_rate": 44100},
            })

            import datetime
            filename = f"tts_websocket_response_handling_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pcm"

            # Write chunks to file as they arrive.
            # You could also send chunks over the network, play them in real-time, etc.
            with open(filename, "wb") as f:
                for response in connection:
                    if response.type == "chunk" and response.audio:
                        f.write(response.audio)
                    elif response.type == "timestamps":
                        process_timestamps(response.word_timestamps)
                    elif response.type == "done" or response.done:
                        break
                    elif response.type == "error":
                        raise Exception(response.error)

            print(f"Saved audio to {filename}")
            print(f"Play with: ffplay -f f32le -ar 44100 {filename}")
    ```

    From [cartesia-python/examples/examples.py:427](https://github.com/cartesia-ai/cartesia-python/blob/main/examples/examples.py#L427)
  </Tab>

  <Tab title="TypeScript">
    ```typescript theme={null}
    async function ttsWebsocketResponseHandling(client: Cartesia): Promise<void> {
      /** WebSocket response type handling. */
      const ws = await client.tts.websocket();
      ws.on('error', (err) => console.error('WS error:', err.message));

      const filename = `tts_websocket_response_handling_${timestamp()}.pcm`;
      const file = fs.createWriteStream(filename);

      for await (const event of ws.generate({
        model_id: 'sonic-3.5',
        transcript: 'Hello, world!',
        voice: { mode: 'id', id: '6ccbfb76-1fc6-48f7-b71d-91ac6298247b' },
        output_format: { container: 'raw', encoding: 'pcm_f32le', sample_rate: 44100 },
        add_timestamps: true,
      })) {
        if (event.type === 'chunk') {
          if (event.audio) file.write(event.audio);
        } else if (event.type === 'timestamps') {
          const wt = (event as any).word_timestamps;
          if (wt) {
            console.log(`Words: ${wt.words}, Starts: ${wt.start}, Ends: ${wt.end}`);
          }
        } else if (event.type === 'error') {
          throw new Error(JSON.stringify(event));
        }
      }

      file.end();
      ws.close();
      console.log(`Saved audio to ${filename}`);
      console.log(`Play with: ffplay -f f32le -ar 44100 ${filename}`);
    }
    ```

    From [cartesia-js/examples/node\_examples.ts:298](https://github.com/cartesia-ai/cartesia-js/blob/main/examples/node_examples.ts#L298)
  </Tab>
</Tabs>

## Run this example

<Tabs>
  <Tab title="Python">
    ```sh theme={null}
    cd cartesia-python
    CARTESIA_API_KEY=YOUR_KEY python3 examples/examples.py tts_websocket_response_handling
    ```
  </Tab>

  <Tab title="TypeScript">
    ```sh theme={null}
    cd cartesia-js
    CARTESIA_API_KEY=YOUR_KEY npx ts-node examples/node_examples.ts ttsWebsocketResponseHandling
    ```
  </Tab>
</Tabs>
