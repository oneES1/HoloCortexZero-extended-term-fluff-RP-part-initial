# Chat 聊天接口

## OpenAPI Specification

```yaml
openapi: 3.0.1
info:
  title: ''
  description: ''
  version: 1.0.0
paths:
  /v1/chat/completions:
    post:
      summary: Chat 聊天接口
      deprecated: false
      description: |-
        OpenAI Chat Completions API
        文档有滞后性，最新文档见：https://platform.openai.com/docs/api-reference/chat/create
      operationId: createChatCompletion
      tags:
        - 语言模型/OpenAI
        - Chat
      parameters: []
      requestBody:
        content:
          application/json:
            schema:
              $ref: >-
                #/components/schemas/%E8%81%8A%E5%A4%A9%E6%8E%A5%E5%8F%A3%E8%AF%B7%E6%B1%82
            examples:
              '1':
                value:
                  model: gpt-5.2
                  messages:
                    - role: developer
                      content: You are a helpful assistant.
                    - role: user
                      content: Hello!
                summary: 文本请求
              '2':
                value:
                  model: gpt-4.1
                  messages:
                    - role: user
                      content:
                        - type: text
                          text: What is in this image?
                        - type: image_url
                          image_url:
                            url: >-
                              https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg
                  max_tokens: 300
                summary: 图像输入
              '3':
                value:
                  model: gpt-5.2
                  messages:
                    - role: developer
                      content: You are a helpful assistant.
                    - role: user
                      content: Hello!
                  stream: true
                summary: 流式输出
              '4':
                value:
                  model: gpt-4.1
                  messages:
                    - role: user
                      content: What is the weather like in Boston today?
                  tools:
                    - type: function
                      function:
                        name: get_current_weather
                        description: Get the current weather in a given location
                        parameters:
                          type: object
                          properties:
                            location:
                              type: string
                              description: The city and state, e.g. San Francisco, CA
                            unit:
                              type: string
                              enum:
                                - celsius
                                - fahrenheit
                          required:
                            - location
                  tool_choice: auto
                summary: 函数调用
              '5':
                value:
                  model: gpt-5.2
                  messages:
                    - role: user
                      content: Hello!
                  logprobs: true
                  top_logprobs: 2
                summary: logprobs
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CreateChatCompletionResponse'
              examples:
                '1':
                  summary: 文本请求
                  value:
                    id: chatcmpl-B9MBs8CjcvOU2jLn4n570S5qMJKcT
                    object: chat.completion
                    created: 1741569952
                    model: gpt-4.1-2025-04-14
                    choices:
                      - index: 0
                        message:
                          role: assistant
                          content: Hello! How can I assist you today?
                          refusal: null
                          annotations: []
                        logprobs: null
                        finish_reason: stop
                    usage:
                      prompt_tokens: 19
                      completion_tokens: 10
                      total_tokens: 29
                      prompt_tokens_details:
                        cached_tokens: 0
                        audio_tokens: 0
                      completion_tokens_details:
                        reasoning_tokens: 0
                        audio_tokens: 0
                        accepted_prediction_tokens: 0
                        rejected_prediction_tokens: 0
                    service_tier: default
                '2':
                  summary: 图像输入
                  value:
                    id: chatcmpl-B9MHDbslfkBeAs8l4bebGdFOJ6PeG
                    object: chat.completion
                    created: 1741570283
                    model: gpt-4.1-2025-04-14
                    choices:
                      - index: 0
                        message:
                          role: assistant
                          content: >-
                            The image shows a wooden boardwalk path running
                            through a lush green field or meadow. The sky is
                            bright blue with some scattered clouds, giving the
                            scene a serene and peaceful atmosphere. Trees and
                            shrubs are visible in the background.
                          refusal: null
                          annotations: []
                        logprobs: null
                        finish_reason: stop
                    usage:
                      prompt_tokens: 1117
                      completion_tokens: 46
                      total_tokens: 1163
                      prompt_tokens_details:
                        cached_tokens: 0
                        audio_tokens: 0
                      completion_tokens_details:
                        reasoning_tokens: 0
                        audio_tokens: 0
                        accepted_prediction_tokens: 0
                        rejected_prediction_tokens: 0
                    service_tier: default
                '3':
                  summary: 流式请求
                  value: |-
                    {
                        "id": "chatcmpl-123",
                        "object": "chat.completion.chunk",
                        "created": 1694268190,
                        "model": "gpt-4o-mini",
                        "system_fingerprint": "fp_44709d6fcb",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "role": "assistant",
                                    "content": ""
                                },
                                "logprobs": null,
                                "finish_reason": null
                            }
                        ]
                    }

                    {
                        "id": "chatcmpl-123",
                        "object": "chat.completion.chunk",
                        "created": 1694268190,
                        "model": "gpt-4o-mini",
                        "system_fingerprint": "fp_44709d6fcb",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "content": "Hello"
                                },
                                "logprobs": null,
                                "finish_reason": null
                            }
                        ]
                    }

                    ....

                    {
                        "id": "chatcmpl-123",
                        "object": "chat.completion.chunk",
                        "created": 1694268190,
                        "model": "gpt-4o-mini",
                        "system_fingerprint": "fp_44709d6fcb",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {},
                                "logprobs": null,
                                "finish_reason": "stop"
                            }
                        ]
                    }
                '4':
                  summary: 函数调用
                  value:
                    id: chatcmpl-abc123
                    object: chat.completion
                    created: 1699896916
                    model: gpt-4o-mini
                    choices:
                      - index: 0
                        message:
                          role: assistant
                          content: null
                          tool_calls:
                            - id: call_abc123
                              type: function
                              function:
                                name: get_current_weather
                                arguments: |-
                                  {
                                  "location": "Boston, MA"
                                  }
                        logprobs: null
                        finish_reason: tool_calls
                    usage:
                      prompt_tokens: 82
                      completion_tokens: 17
                      total_tokens: 99
                      completion_tokens_details:
                        reasoning_tokens: 0
                        accepted_prediction_tokens: 0
                        rejected_prediction_tokens: 0
                '5':
                  summary: logprobs
                  value:
                    id: chatcmpl-123
                    object: chat.completion
                    created: 1702685778
                    model: gpt-4o-mini
                    choices:
                      - index: 0
                        message:
                          role: assistant
                          content: Hello! How can I assist you today?
                        logprobs:
                          content:
                            - token: Hello
                              logprob: -0.31725305
                              bytes:
                                - 72
                                - 101
                                - 108
                                - 108
                                - 111
                              top_logprobs:
                                - token: Hello
                                  logprob: -0.31725305
                                  bytes:
                                    - 72
                                    - 101
                                    - 108
                                    - 108
                                    - 111
                                - token: Hi
                                  logprob: -1.3190403
                                  bytes:
                                    - 72
                                    - 105
                            - token: '!'
                              logprob: -0.02380986
                              bytes:
                                - 33
                              top_logprobs:
                                - token: '!'
                                  logprob: -0.02380986
                                  bytes:
                                    - 33
                                - token: ' there'
                                  logprob: -3.787621
                                  bytes:
                                    - 32
                                    - 116
                                    - 104
                                    - 101
                                    - 114
                                    - 101
                            - token: ' How'
                              logprob: -0.000054669687
                              bytes:
                                - 32
                                - 72
                                - 111
                                - 119
                              top_logprobs:
                                - token: ' How'
                                  logprob: -0.000054669687
                                  bytes:
                                    - 32
                                    - 72
                                    - 111
                                    - 119
                                - token: <|end|>
                                  logprob: -10.953937
                                  bytes: null
                            - token: ' can'
                              logprob: -0.015801601
                              bytes:
                                - 32
                                - 99
                                - 97
                                - 110
                              top_logprobs:
                                - token: ' can'
                                  logprob: -0.015801601
                                  bytes:
                                    - 32
                                    - 99
                                    - 97
                                    - 110
                                - token: ' may'
                                  logprob: -4.161023
                                  bytes:
                                    - 32
                                    - 109
                                    - 97
                                    - 121
                            - token: ' I'
                              logprob: -0.0000037697225
                              bytes:
                                - 32
                                - 73
                              top_logprobs:
                                - token: ' I'
                                  logprob: -0.0000037697225
                                  bytes:
                                    - 32
                                    - 73
                                - token: ' assist'
                                  logprob: -13.596657
                                  bytes:
                                    - 32
                                    - 97
                                    - 115
                                    - 115
                                    - 105
                                    - 115
                                    - 116
                            - token: ' assist'
                              logprob: -0.04571125
                              bytes:
                                - 32
                                - 97
                                - 115
                                - 115
                                - 105
                                - 115
                                - 116
                              top_logprobs:
                                - token: ' assist'
                                  logprob: -0.04571125
                                  bytes:
                                    - 32
                                    - 97
                                    - 115
                                    - 115
                                    - 105
                                    - 115
                                    - 116
                                - token: ' help'
                                  logprob: -3.1089056
                                  bytes:
                                    - 32
                                    - 104
                                    - 101
                                    - 108
                                    - 112
                            - token: ' you'
                              logprob: -0.0000054385737
                              bytes:
                                - 32
                                - 121
                                - 111
                                - 117
                              top_logprobs:
                                - token: ' you'
                                  logprob: -0.0000054385737
                                  bytes:
                                    - 32
                                    - 121
                                    - 111
                                    - 117
                                - token: ' today'
                                  logprob: -12.807695
                                  bytes:
                                    - 32
                                    - 116
                                    - 111
                                    - 100
                                    - 97
                                    - 121
                            - token: ' today'
                              logprob: -0.0040071653
                              bytes:
                                - 32
                                - 116
                                - 111
                                - 100
                                - 97
                                - 121
                              top_logprobs:
                                - token: ' today'
                                  logprob: -0.0040071653
                                  bytes:
                                    - 32
                                    - 116
                                    - 111
                                    - 100
                                    - 97
                                    - 121
                                - token: '?'
                                  logprob: -5.5247097
                                  bytes:
                                    - 63
                            - token: '?'
                              logprob: -0.0008108172
                              bytes:
                                - 63
                              top_logprobs:
                                - token: '?'
                                  logprob: -0.0008108172
                                  bytes:
                                    - 63
                                - token: |
                                    ?
                                  logprob: -7.184561
                                  bytes:
                                    - 63
                                    - 10
                        finish_reason: stop
                    usage:
                      prompt_tokens: 9
                      completion_tokens: 9
                      total_tokens: 18
                      completion_tokens_details:
                        reasoning_tokens: 0
                        accepted_prediction_tokens: 0
                        rejected_prediction_tokens: 0
                    system_fingerprint: null
          headers: {}
          x-apifox-name: 成功
      security:
        - bearer: []
      x-oaiMeta:
        name: Create chat completion
        group: chat
        returns: >
          Returns a [chat completion](/docs/api-reference/chat/object) object,
          or a streamed sequence of [chat completion
          chunk](/docs/api-reference/chat/streaming) objects if the request is
          streamed.
        path: create
        examples:
          - title: Default
            request:
              curl: |
                curl https://api.openai.com/v1/chat/completions \
                  -H "Content-Type: application/json" \
                  -H "Authorization: Bearer $OPENAI_API_KEY" \
                  -d '{
                    "model": "VAR_chat_model_id",
                    "messages": [
                      {
                        "role": "developer",
                        "content": "You are a helpful assistant."
                      },
                      {
                        "role": "user",
                        "content": "Hello!"
                      }
                    ]
                  }'
              python: |
                from openai import OpenAI
                client = OpenAI()

                completion = client.chat.completions.create(
                  model="VAR_chat_model_id",
                  messages=[
                    {"role": "developer", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Hello!"}
                  ]
                )

                print(completion.choices[0].message)
              node.js: |
                import OpenAI from "openai";

                const openai = new OpenAI();

                async function main() {
                  const completion = await openai.chat.completions.create({
                    messages: [{ role: "developer", content: "You are a helpful assistant." }],
                    model: "VAR_chat_model_id",
                    store: true,
                  });

                  console.log(completion.choices[0]);
                }

                main();
              csharp: |
                using System;
                using System.Collections.Generic;

                using OpenAI.Chat;

                ChatClient client = new(
                    model: "gpt-4.1",
                    apiKey: Environment.GetEnvironmentVariable("OPENAI_API_KEY")
                );

                List<ChatMessage> messages =
                [
                    new SystemChatMessage("You are a helpful assistant."),
                    new UserChatMessage("Hello!")
                ];

                ChatCompletion completion = client.CompleteChat(messages);

                Console.WriteLine(completion.Content[0].Text);
            response: |
              {
                "id": "chatcmpl-B9MBs8CjcvOU2jLn4n570S5qMJKcT",
                "object": "chat.completion",
                "created": 1741569952,
                "model": "gpt-4.1-2025-04-14",
                "choices": [
                  {
                    "index": 0,
                    "message": {
                      "role": "assistant",
                      "content": "Hello! How can I assist you today?",
                      "refusal": null,
                      "annotations": []
                    },
                    "logprobs": null,
                    "finish_reason": "stop"
                  }
                ],
                "usage": {
                  "prompt_tokens": 19,
                  "completion_tokens": 10,
                  "total_tokens": 29,
                  "prompt_tokens_details": {
                    "cached_tokens": 0,
                    "audio_tokens": 0
                  },
                  "completion_tokens_details": {
                    "reasoning_tokens": 0,
                    "audio_tokens": 0,
                    "accepted_prediction_tokens": 0,
                    "rejected_prediction_tokens": 0
                  }
                },
                "service_tier": "default"
              }
          - title: Image input
            request:
              curl: |
                curl https://api.openai.com/v1/chat/completions \
                  -H "Content-Type: application/json" \
                  -H "Authorization: Bearer $OPENAI_API_KEY" \
                  -d '{
                    "model": "gpt-4.1",
                    "messages": [
                      {
                        "role": "user",
                        "content": [
                          {
                            "type": "text",
                            "text": "What is in this image?"
                          },
                          {
                            "type": "image_url",
                            "image_url": {
                              "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
                            }
                          }
                        ]
                      }
                    ],
                    "max_tokens": 300
                  }'
              python: |
                from openai import OpenAI

                client = OpenAI()

                response = client.chat.completions.create(
                    model="gpt-4.1",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "What's in this image?"},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg",
                                    }
                                },
                            ],
                        }
                    ],
                    max_tokens=300,
                )

                print(response.choices[0])
              node.js: |
                import OpenAI from "openai";

                const openai = new OpenAI();

                async function main() {
                  const response = await openai.chat.completions.create({
                    model: "gpt-4.1",
                    messages: [
                      {
                        role: "user",
                        content: [
                          { type: "text", text: "What's in this image?" },
                          {
                            type: "image_url",
                            image_url: {
                              "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg",
                            },
                          }
                        ],
                      },
                    ],
                  });
                  console.log(response.choices[0]);
                }
                main();
              csharp: |
                using System;
                using System.Collections.Generic;

                using OpenAI.Chat;

                ChatClient client = new(
                    model: "gpt-4.1",
                    apiKey: Environment.GetEnvironmentVariable("OPENAI_API_KEY")
                );

                List<ChatMessage> messages =
                [
                    new UserChatMessage(
                    [
                        ChatMessageContentPart.CreateTextPart("What's in this image?"),
                        ChatMessageContentPart.CreateImagePart(new Uri("https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"))
                    ])
                ];

                ChatCompletion completion = client.CompleteChat(messages);

                Console.WriteLine(completion.Content[0].Text);
            response: |
              {
                "id": "chatcmpl-B9MHDbslfkBeAs8l4bebGdFOJ6PeG",
                "object": "chat.completion",
                "created": 1741570283,
                "model": "gpt-4.1-2025-04-14",
                "choices": [
                  {
                    "index": 0,
                    "message": {
                      "role": "assistant",
                      "content": "The image shows a wooden boardwalk path running through a lush green field or meadow. The sky is bright blue with some scattered clouds, giving the scene a serene and peaceful atmosphere. Trees and shrubs are visible in the background.",
                      "refusal": null,
                      "annotations": []
                    },
                    "logprobs": null,
                    "finish_reason": "stop"
                  }
                ],
                "usage": {
                  "prompt_tokens": 1117,
                  "completion_tokens": 46,
                  "total_tokens": 1163,
                  "prompt_tokens_details": {
                    "cached_tokens": 0,
                    "audio_tokens": 0
                  },
                  "completion_tokens_details": {
                    "reasoning_tokens": 0,
                    "audio_tokens": 0,
                    "accepted_prediction_tokens": 0,
                    "rejected_prediction_tokens": 0
                  }
                },
                "service_tier": "default"
              }
          - title: Streaming
            request:
              curl: |
                curl https://api.openai.com/v1/chat/completions \
                  -H "Content-Type: application/json" \
                  -H "Authorization: Bearer $OPENAI_API_KEY" \
                  -d '{
                    "model": "VAR_chat_model_id",
                    "messages": [
                      {
                        "role": "developer",
                        "content": "You are a helpful assistant."
                      },
                      {
                        "role": "user",
                        "content": "Hello!"
                      }
                    ],
                    "stream": true
                  }'
              python: |
                from openai import OpenAI
                client = OpenAI()

                completion = client.chat.completions.create(
                  model="VAR_chat_model_id",
                  messages=[
                    {"role": "developer", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Hello!"}
                  ],
                  stream=True
                )

                for chunk in completion:
                  print(chunk.choices[0].delta)
              node.js: |
                import OpenAI from "openai";

                const openai = new OpenAI();

                async function main() {
                  const completion = await openai.chat.completions.create({
                    model: "VAR_chat_model_id",
                    messages: [
                      {"role": "developer", "content": "You are a helpful assistant."},
                      {"role": "user", "content": "Hello!"}
                    ],
                    stream: true,
                  });

                  for await (const chunk of completion) {
                    console.log(chunk.choices[0].delta.content);
                  }
                }

                main();
              csharp: >
                using System;

                using System.ClientModel;

                using System.Collections.Generic;

                using System.Threading.Tasks;


                using OpenAI.Chat;


                ChatClient client = new(
                    model: "gpt-4.1",
                    apiKey: Environment.GetEnvironmentVariable("OPENAI_API_KEY")
                );


                List<ChatMessage> messages =

                [
                    new SystemChatMessage("You are a helpful assistant."),
                    new UserChatMessage("Hello!")
                ];


                AsyncCollectionResult<StreamingChatCompletionUpdate>
                completionUpdates = client.CompleteChatStreamingAsync(messages);


                await foreach (StreamingChatCompletionUpdate completionUpdate in
                completionUpdates)

                {
                    if (completionUpdate.ContentUpdate.Count > 0)
                    {
                        Console.Write(completionUpdate.ContentUpdate[0].Text);
                    }
                }
            response: >
              {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1694268190,"model":"gpt-4o-mini",
              "system_fingerprint": "fp_44709d6fcb",
              "choices":[{"index":0,"delta":{"role":"assistant","content":""},"logprobs":null,"finish_reason":null}]}


              {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1694268190,"model":"gpt-4o-mini",
              "system_fingerprint": "fp_44709d6fcb",
              "choices":[{"index":0,"delta":{"content":"Hello"},"logprobs":null,"finish_reason":null}]}


              ....


              {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1694268190,"model":"gpt-4o-mini",
              "system_fingerprint": "fp_44709d6fcb",
              "choices":[{"index":0,"delta":{},"logprobs":null,"finish_reason":"stop"}]}
          - title: Functions
            request:
              curl: |
                curl https://api.openai.com/v1/chat/completions \
                -H "Content-Type: application/json" \
                -H "Authorization: Bearer $OPENAI_API_KEY" \
                -d '{
                  "model": "gpt-4.1",
                  "messages": [
                    {
                      "role": "user",
                      "content": "What is the weather like in Boston today?"
                    }
                  ],
                  "tools": [
                    {
                      "type": "function",
                      "function": {
                        "name": "get_current_weather",
                        "description": "Get the current weather in a given location",
                        "parameters": {
                          "type": "object",
                          "properties": {
                            "location": {
                              "type": "string",
                              "description": "The city and state, e.g. San Francisco, CA"
                            },
                            "unit": {
                              "type": "string",
                              "enum": ["celsius", "fahrenheit"]
                            }
                          },
                          "required": ["location"]
                        }
                      }
                    }
                  ],
                  "tool_choice": "auto"
                }'
              python: >
                from openai import OpenAI

                client = OpenAI()


                tools = [
                  {
                    "type": "function",
                    "function": {
                      "name": "get_current_weather",
                      "description": "Get the current weather in a given location",
                      "parameters": {
                        "type": "object",
                        "properties": {
                          "location": {
                            "type": "string",
                            "description": "The city and state, e.g. San Francisco, CA",
                          },
                          "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                        },
                        "required": ["location"],
                      },
                    }
                  }
                ]

                messages = [{"role": "user", "content": "What's the weather like
                in Boston today?"}]

                completion = client.chat.completions.create(
                  model="VAR_chat_model_id",
                  messages=messages,
                  tools=tools,
                  tool_choice="auto"
                )


                print(completion)
              node.js: |
                import OpenAI from "openai";

                const openai = new OpenAI();

                async function main() {
                  const messages = [{"role": "user", "content": "What's the weather like in Boston today?"}];
                  const tools = [
                      {
                        "type": "function",
                        "function": {
                          "name": "get_current_weather",
                          "description": "Get the current weather in a given location",
                          "parameters": {
                            "type": "object",
                            "properties": {
                              "location": {
                                "type": "string",
                                "description": "The city and state, e.g. San Francisco, CA",
                              },
                              "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                            },
                            "required": ["location"],
                          },
                        }
                      }
                  ];

                  const response = await openai.chat.completions.create({
                    model: "gpt-4.1",
                    messages: messages,
                    tools: tools,
                    tool_choice: "auto",
                  });

                  console.log(response);
                }

                main();
              csharp: >
                using System;

                using System.Collections.Generic;


                using OpenAI.Chat;


                ChatClient client = new(
                    model: "gpt-4.1",
                    apiKey: Environment.GetEnvironmentVariable("OPENAI_API_KEY")
                );


                ChatTool getCurrentWeatherTool = ChatTool.CreateFunctionTool(
                    functionName: "get_current_weather",
                    functionDescription: "Get the current weather in a given location",
                    functionParameters: BinaryData.FromString("""
                        {
                            "type": "object",
                            "properties": {
                                "location": {
                                    "type": "string",
                                    "description": "The city and state, e.g. San Francisco, CA"
                                },
                                "unit": {
                                    "type": "string",
                                    "enum": [ "celsius", "fahrenheit" ]
                                }
                            },
                            "required": [ "location" ]
                        }
                    """)
                );


                List<ChatMessage> messages =

                [
                    new UserChatMessage("What's the weather like in Boston today?"),
                ];


                ChatCompletionOptions options = new()

                {
                    Tools =
                    {
                        getCurrentWeatherTool
                    },
                    ToolChoice = ChatToolChoice.CreateAutoChoice(),
                };


                ChatCompletion completion = client.CompleteChat(messages,
                options);
            response: |
              {
                "id": "chatcmpl-abc123",
                "object": "chat.completion",
                "created": 1699896916,
                "model": "gpt-4o-mini",
                "choices": [
                  {
                    "index": 0,
                    "message": {
                      "role": "assistant",
                      "content": null,
                      "tool_calls": [
                        {
                          "id": "call_abc123",
                          "type": "function",
                          "function": {
                            "name": "get_current_weather",
                            "arguments": "{\n\"location\": \"Boston, MA\"\n}"
                          }
                        }
                      ]
                    },
                    "logprobs": null,
                    "finish_reason": "tool_calls"
                  }
                ],
                "usage": {
                  "prompt_tokens": 82,
                  "completion_tokens": 17,
                  "total_tokens": 99,
                  "completion_tokens_details": {
                    "reasoning_tokens": 0,
                    "accepted_prediction_tokens": 0,
                    "rejected_prediction_tokens": 0
                  }
                }
              }
          - title: Logprobs
            request:
              curl: |
                curl https://api.openai.com/v1/chat/completions \
                  -H "Content-Type: application/json" \
                  -H "Authorization: Bearer $OPENAI_API_KEY" \
                  -d '{
                    "model": "VAR_chat_model_id",
                    "messages": [
                      {
                        "role": "user",
                        "content": "Hello!"
                      }
                    ],
                    "logprobs": true,
                    "top_logprobs": 2
                  }'
              python: |
                from openai import OpenAI
                client = OpenAI()

                completion = client.chat.completions.create(
                  model="VAR_chat_model_id",
                  messages=[
                    {"role": "user", "content": "Hello!"}
                  ],
                  logprobs=True,
                  top_logprobs=2
                )

                print(completion.choices[0].message)
                print(completion.choices[0].logprobs)
              node.js: |
                import OpenAI from "openai";

                const openai = new OpenAI();

                async function main() {
                  const completion = await openai.chat.completions.create({
                    messages: [{ role: "user", content: "Hello!" }],
                    model: "VAR_chat_model_id",
                    logprobs: true,
                    top_logprobs: 2,
                  });

                  console.log(completion.choices[0]);
                }

                main();
              csharp: >
                using System;

                using System.Collections.Generic;


                using OpenAI.Chat;


                ChatClient client = new(
                    model: "gpt-4.1",
                    apiKey: Environment.GetEnvironmentVariable("OPENAI_API_KEY")
                );


                List<ChatMessage> messages =

                [
                    new UserChatMessage("Hello!")
                ];


                ChatCompletionOptions options = new()

                {
                    IncludeLogProbabilities = true,
                    TopLogProbabilityCount = 2
                };


                ChatCompletion completion = client.CompleteChat(messages,
                options);


                Console.WriteLine(completion.Content[0].Text);
            response: |
              {
                "id": "chatcmpl-123",
                "object": "chat.completion",
                "created": 1702685778,
                "model": "gpt-4o-mini",
                "choices": [
                  {
                    "index": 0,
                    "message": {
                      "role": "assistant",
                      "content": "Hello! How can I assist you today?"
                    },
                    "logprobs": {
                      "content": [
                        {
                          "token": "Hello",
                          "logprob": -0.31725305,
                          "bytes": [72, 101, 108, 108, 111],
                          "top_logprobs": [
                            {
                              "token": "Hello",
                              "logprob": -0.31725305,
                              "bytes": [72, 101, 108, 108, 111]
                            },
                            {
                              "token": "Hi",
                              "logprob": -1.3190403,
                              "bytes": [72, 105]
                            }
                          ]
                        },
                        {
                          "token": "!",
                          "logprob": -0.02380986,
                          "bytes": [
                            33
                          ],
                          "top_logprobs": [
                            {
                              "token": "!",
                              "logprob": -0.02380986,
                              "bytes": [33]
                            },
                            {
                              "token": " there",
                              "logprob": -3.787621,
                              "bytes": [32, 116, 104, 101, 114, 101]
                            }
                          ]
                        },
                        {
                          "token": " How",
                          "logprob": -0.000054669687,
                          "bytes": [32, 72, 111, 119],
                          "top_logprobs": [
                            {
                              "token": " How",
                              "logprob": -0.000054669687,
                              "bytes": [32, 72, 111, 119]
                            },
                            {
                              "token": "<|end|>",
                              "logprob": -10.953937,
                              "bytes": null
                            }
                          ]
                        },
                        {
                          "token": " can",
                          "logprob": -0.015801601,
                          "bytes": [32, 99, 97, 110],
                          "top_logprobs": [
                            {
                              "token": " can",
                              "logprob": -0.015801601,
                              "bytes": [32, 99, 97, 110]
                            },
                            {
                              "token": " may",
                              "logprob": -4.161023,
                              "bytes": [32, 109, 97, 121]
                            }
                          ]
                        },
                        {
                          "token": " I",
                          "logprob": -3.7697225e-6,
                          "bytes": [
                            32,
                            73
                          ],
                          "top_logprobs": [
                            {
                              "token": " I",
                              "logprob": -3.7697225e-6,
                              "bytes": [32, 73]
                            },
                            {
                              "token": " assist",
                              "logprob": -13.596657,
                              "bytes": [32, 97, 115, 115, 105, 115, 116]
                            }
                          ]
                        },
                        {
                          "token": " assist",
                          "logprob": -0.04571125,
                          "bytes": [32, 97, 115, 115, 105, 115, 116],
                          "top_logprobs": [
                            {
                              "token": " assist",
                              "logprob": -0.04571125,
                              "bytes": [32, 97, 115, 115, 105, 115, 116]
                            },
                            {
                              "token": " help",
                              "logprob": -3.1089056,
                              "bytes": [32, 104, 101, 108, 112]
                            }
                          ]
                        },
                        {
                          "token": " you",
                          "logprob": -5.4385737e-6,
                          "bytes": [32, 121, 111, 117],
                          "top_logprobs": [
                            {
                              "token": " you",
                              "logprob": -5.4385737e-6,
                              "bytes": [32, 121, 111, 117]
                            },
                            {
                              "token": " today",
                              "logprob": -12.807695,
                              "bytes": [32, 116, 111, 100, 97, 121]
                            }
                          ]
                        },
                        {
                          "token": " today",
                          "logprob": -0.0040071653,
                          "bytes": [32, 116, 111, 100, 97, 121],
                          "top_logprobs": [
                            {
                              "token": " today",
                              "logprob": -0.0040071653,
                              "bytes": [32, 116, 111, 100, 97, 121]
                            },
                            {
                              "token": "?",
                              "logprob": -5.5247097,
                              "bytes": [63]
                            }
                          ]
                        },
                        {
                          "token": "?",
                          "logprob": -0.0008108172,
                          "bytes": [63],
                          "top_logprobs": [
                            {
                              "token": "?",
                              "logprob": -0.0008108172,
                              "bytes": [63]
                            },
                            {
                              "token": "?\n",
                              "logprob": -7.184561,
                              "bytes": [63, 10]
                            }
                          ]
                        }
                      ]
                    },
                    "finish_reason": "stop"
                  }
                ],
                "usage": {
                  "prompt_tokens": 9,
                  "completion_tokens": 9,
                  "total_tokens": 18,
                  "completion_tokens_details": {
                    "reasoning_tokens": 0,
                    "accepted_prediction_tokens": 0,
                    "rejected_prediction_tokens": 0
                  }
                },
                "system_fingerprint": null
              }
      x-apifox-folder: 语言模型/OpenAI
      x-apifox-status: released
      x-run-in-apifox: https://app.apifox.com/web/project/4632351/apis/api-297251415-run
components:
  schemas:
    聊天接口请求:
      allOf:
        - $ref: '#/components/schemas/CreateModelResponseProperties'
        - type: object
          properties:
            messages:
              description: 包含迄今为止对话的消息列表。根据您使用的模型，支持不同的消息类型（模态），如文本、图像和音频。
              type: array
              minItems: 1
              items:
                $ref: '#/components/schemas/ChatCompletionRequestMessage'
            model:
              type: string
              description: 用于生成响应的模型ID，如 `gpt-4o` 或 `o3`。OpenAI 提供了多种具有不同能力、性能特征和价格点的模型。
            modalities:
              $ref: '#/components/schemas/ResponseModalities'
            reasoning_effort:
              $ref: '#/components/schemas/ReasoningEffort'
            max_completion_tokens:
              description: 完成生成的最大令牌数上限，包括可见输出令牌和推理令牌。
              type: integer
              nullable: true
            frequency_penalty:
              type: number
              default: 0
              minimum: -2
              maximum: 2
              description: 介于 -2.0 和 2.0 之间的数字。正值根据文本中已有的频率惩罚新生成的标记，从而降低模型逐字重复相同行的可能性。
              nullable: true
            presence_penalty:
              type: number
              default: 0
              minimum: -2
              maximum: 2
              description: 介于 -2.0 和 2.0 之间的数字。正值会根据新标记是否出现在当前文本中进行惩罚，从而增加模型谈论新话题的可能性。
              nullable: true
            web_search_options:
              type: object
              title: Web search
              description: |
                此工具在网络上搜索相关结果，以用于响应。
              properties:
                user_location:
                  type: object
                  required:
                    - type
                    - approximate
                  description: 搜索的大致位置参数。
                  properties:
                    type:
                      type: string
                      description: 位置近似类型。总是 `approximate`。
                      enum:
                        - approximate
                      x-stainless-const: true
                    approximate:
                      $ref: '#/components/schemas/WebSearchLocation'
                  x-apifox-orders:
                    - type
                    - approximate
                  x-apifox-ignore-properties: []
                  nullable: true
                search_context_size:
                  $ref: '#/components/schemas/WebSearchContextSize'
              x-apifox-orders:
                - user_location
                - search_context_size
              x-apifox-ignore-properties: []
            top_logprobs:
              description: |-
                一个介于0到20之间的整数，指定在每个标记位置返回的最可能标记数量，每个标记都有一个相关的对数概率。

                如果使用此参数，`logprobs`必须设置为`true`。
              type: integer
              minimum: 0
              maximum: 20
              nullable: true
            response_format:
              description: >-
                一个指定模型必须输出格式的对象。


                设置为 `{ "type": "json_schema", "json_schema": {...} }`
                启用结构化输出，确保模型将匹配您提供的 JSON
                模式。更多信息请参见[结构化输出指南](/docs/guides/structured-outputs)。


                设置为 `{ "type": "json_object" }` 启用较旧的 JSON 模式，确保模型生成的消息是有效的
                JSON。支持的模型建议使用 `json_schema`。
              oneOf:
                - $ref: '#/components/schemas/ResponseFormatText'
                - $ref: '#/components/schemas/ResponseFormatJsonSchema'
                - $ref: '#/components/schemas/ResponseFormatJsonObject'
            audio:
              type: object
              description: |-
                音频输出参数。当请求音频输出时需要，参数为

                `modalities: ["audio"]`。
              required:
                - voice
                - format
              properties:
                voice:
                  type: string
                  description: >-
                    模型用来响应的声音。支持的声音有


                    `alloy`，`ash`，`ballad`，`coral`，`echo`，`fable`，`nova`，`onyx`，`sage`，和
                    `shimmer`。
                format:
                  type: string
                  enum:
                    - wav
                    - aac
                    - mp3
                    - flac
                    - opus
                    - pcm16
                  description: 指定输出音频格式。必须是 `wav`、`mp3`、`flac`、`opus` 或 `pcm16` 之一。
              x-apifox-orders:
                - voice
                - format
              x-apifox-ignore-properties: []
              nullable: true
            store:
              type: boolean
              default: false
              description: 是否存储此聊天完成请求的输出以用于我们的模型蒸馏]或评估产品。
              nullable: true
            stream:
              description: >-
                如果设置为
                true，模型响应数据将在生成时通过[服务器发送事件](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events#Event_stream_format)流式传输到客户端。
              type: boolean
              default: false
              nullable: true
            stop:
              $ref: '#/components/schemas/StopConfiguration'
            logit_bias:
              type: object
              x-oaiTypeLabel: map
              default: null
              additionalProperties:
                type: integer
              description: >-
                修改指定令牌在完成中出现的可能性。


                接受一个 JSON 对象，该对象将令牌（通过其在分词器中的令牌 ID 指定）映射到一个相关的偏置值，范围从 -100 到
                100。数学上，


                偏置值会在模型生成的 logits 采样之前被添加。确切的效果会因模型而异，但 -1 到 1 之间的值应该会


                减少或增加选择的可能性；像 -100 或 100 这样的值应该会导致相关令牌的禁止或唯一选择。
              x-apifox-orders: []
              properties: {}
              x-apifox-ignore-properties: []
              nullable: true
            logprobs:
              description: |-
                是否返回输出标记的对数概率。如果为真，

                则返回在`message`的`content`中每个输出标记的对数概率。
              type: boolean
              default: false
              nullable: true
            max_tokens:
              description: >-
                在聊天补全中可以生成的最大[令牌](/tokenizer)数量。此值可用于控制通过API生成文本的[成本](https://openai.com/api/pricing/)。


                此值现已被`max_completion_tokens`取代，并且与o系列模型不兼容。
              type: integer
              deprecated: true
              nullable: true
            'n':
              type: integer
              minimum: 1
              maximum: 128
              default: 1
              description: 为每条输入消息生成多少个聊天完成选项。请注意，您将根据所有选项生成的令牌数量收费。将 `n` 保持为 `1` 以最小化成本。
              examples:
                - 1
              nullable: true
            prediction:
              description: |-
                预测输出 的配置，

                当模型响应的大部分内容事先已知时，

                这可以大大提高响应速度。这种情况最常见于

                你只对大部分内容做了少量更改而重新生成文件时。
              oneOf:
                - $ref: '#/components/schemas/PredictionContent'
              type: 'null'
            seed:
              type: integer
              minimum: -9223372036854776000
              maximum: 9223372036854776000
              description: |-
                此功能处于测试阶段。

                如果指定，我们的系统将尽最大努力进行确定性采样，以便使用相同的 `seed` 和参数的重复请求应返回相同的结果。

                不保证确定性，您应参考 `system_fingerprint` 响应参数以监控后端的变化。
              x-oaiMeta:
                beta: true
              nullable: true
            stream_options:
              $ref: '#/components/schemas/ChatCompletionStreamOptions'
            tools:
              type: array
              description: >-
                模型可能调用的工具列表。目前，仅支持函数作为工具。使用此列表提供模型可能生成 JSON 输入的函数列表。最多支持 128
                个函数。
              items:
                $ref: '#/components/schemas/ChatCompletionTool'
            tool_choice:
              $ref: '#/components/schemas/ChatCompletionToolChoiceOption'
            parallel_tool_calls:
              $ref: '#/components/schemas/ParallelToolCalls'
            function_call:
              deprecated: true
              description: |-
                已弃用，建议使用 `tool_choice`。

                控制模型调用哪个（如果有的话）函数。

                `none` 表示模型不会调用函数，而是生成一条消息。

                `auto` 表示模型可以选择生成消息或调用函数。

                通过 `{"name": "my_function"}` 指定特定函数，强制模型调用该函数。

                当没有函数时，默认值为 `none`。当有函数时，默认值为 `auto`。
              oneOf:
                - type: string
                  description: >
                    `none` means the model will not call a function and instead
                    generates a message. `auto` means the model can pick between
                    generating a message or calling a function.
                  enum:
                    - none
                    - auto
                - $ref: '#/components/schemas/ChatCompletionFunctionCallOption'
            functions:
              deprecated: true
              description: |-
                已弃用，建议使用 `tools`。

                模型可能生成 JSON 输入的函数列表。
              type: array
              minItems: 1
              maxItems: 128
              items:
                $ref: '#/components/schemas/ChatCompletionFunctions'
          required:
            - messages
            - model
          x-apifox-orders:
            - messages
            - model
            - modalities
            - reasoning_effort
            - max_completion_tokens
            - frequency_penalty
            - presence_penalty
            - web_search_options
            - top_logprobs
            - response_format
            - audio
            - store
            - stream
            - stop
            - logit_bias
            - logprobs
            - max_tokens
            - 'n'
            - prediction
            - seed
            - stream_options
            - tools
            - tool_choice
            - parallel_tool_calls
            - function_call
            - functions
          x-apifox-ignore-properties: []
      x-apifox-folder: ''
    ChatCompletionFunctions:
      type: object
      deprecated: true
      properties:
        description:
          type: string
          description: 函数的描述，供模型选择何时以及如何调用该函数时使用。
        name:
          type: string
          description: 要调用的函数名称。必须是a-z、A-Z、0-9，或包含下划线和连字符，最大长度为64。
        parameters: &ref_0
          $ref: '#/components/schemas/FunctionParameters'
      required:
        - name
      x-apifox-orders:
        - description
        - name
        - parameters
      x-apifox-ignore-properties: []
      x-apifox-folder: ''
    FunctionParameters:
      type: object
      description: >-
        函数接受的参数，描述为一个 JSON Schema
        对象。有关示例，请参见[指南](/docs/guides/function-calling)，有关格式的文档，请参见[JSON Schema
        参考](https://json-schema.org/understanding-json-schema/)。


        省略 `parameters` 定义一个参数列表为空的函数。
      additionalProperties: true
      x-apifox-orders: []
      properties: {}
      x-apifox-ignore-properties: []
      x-apifox-folder: ''
    ChatCompletionFunctionCallOption:
      type: object
      description: >
        Specifying a particular function via `{"name": "my_function"}` forces
        the model to call that function.
      properties:
        name:
          type: string
          description: The name of the function to call.
      required:
        - name
      x-apifox-orders:
        - name
      x-apifox-ignore-properties: []
      x-apifox-folder: ''
    ParallelToolCalls:
      description: 是否在使用工具时启用并行函数调用
      type: boolean
      default: true
      x-apifox-folder: ''
    ChatCompletionToolChoiceOption:
      description: >-
        控制模型调用哪个（如果有的话）工具。


        `none` 意味着模型不会调用任何工具，而是生成一条消息。


        `auto` 意味着模型可以选择生成消息或调用一个或多个工具。


        `required` 意味着模型必须调用一个或多个工具。


        通过 `{"type": "function", "function": {"name": "my_function"}}`
        指定特定工具，强制模型调用该工具。


        当没有工具时，默认值为 `none`。当有工具时，默认值为 `auto`。
      oneOf:
        - type: string
          description: >-
            `none` 意味着模型不会调用任何工具，而是生成一条消息。`auto`
            意味着模型可以选择生成消息或调用一个或多个工具。`required` 意味着模型必须调用一个或多个工具。
          enum:
            - none
            - auto
            - required
        - $ref: '#/components/schemas/ChatCompletionNamedToolChoice'
      x-apifox-folder: ''
    ChatCompletionNamedToolChoice:
      type: object
      description: 指定模型应使用的工具。用于强制模型调用特定函数。
      properties:
        type:
          type: string
          enum:
            - function
          description: 工具的类型。目前，仅支持 `function`。
          x-stainless-const: true
        function:
          type: object
          properties:
            name:
              type: string
              description: 要调用的函数名称。
          required:
            - name
          x-apifox-orders:
            - name
          x-apifox-ignore-properties: []
      required:
        - type
        - function
      x-apifox-orders:
        - type
        - function
      x-apifox-ignore-properties: []
      x-apifox-folder: ''
    ChatCompletionTool:
      type: object
      properties:
        type:
          type: string
          enum:
            - function
          description: 工具的类型。目前仅支持`function`。
          x-stainless-const: true
        function:
          $ref: '#/components/schemas/FunctionObject'
      required:
        - type
        - function
      x-apifox-orders:
        - type
        - function
      x-apifox-ignore-properties: []
      x-apifox-folder: ''
    FunctionObject:
      type: object
      properties:
        description:
          type: string
          description: 函数的功能描述，供模型选择何时以及如何调用该函数时使用。
        name:
          type: string
          description: 要调用的函数名称。必须是a-z、A-Z、0-9，或包含下划线和连字符，最大长度为64。
        parameters: *ref_0
        strict:
          type: boolean
          default: false
          description: >-
            是否在生成函数调用时启用严格的模式遵循。如果设置为 true，模型将遵循 `parameters` 字段中定义的精确模式。当
            `strict` 为 `true` 时，仅支持 JSON Schema 的子集。
          nullable: true
      required:
        - name
      x-apifox-orders:
        - description
        - name
        - parameters
        - strict
      x-apifox-ignore-properties: []
      x-apifox-folder: ''
    ChatCompletionStreamOptions:
      description: '流式响应的选项。仅在设置 `stream: true` 时设置此项。'
      type: object
      default: null
      properties:
        include_usage:
          type: boolean
          description: >-
            如果设置了，在 `data: [DONE]` 消息之前会额外流式传输一个块。该块上的 `usage`
            字段显示整个请求的令牌使用统计信息，`choices` 字段将始终是一个空数组。


            所有其他块也将包含一个 `usage` 字段，但其值为 null。注意：如果流被中断，您可能无法收到包含请求总令牌使用量的最终使用块。
      x-apifox-orders:
        - include_usage
      x-apifox-ignore-properties: []
      nullable: true
      x-apifox-folder: ''
    PredictionContent:
      type: object
      title: Static Content
      description: >
        Static predicted output content, such as the content of a text file that
        is

        being regenerated.
      required:
        - type
        - content
      properties:
        type:
          type: string
          enum:
            - content
          description: |
            The type of the predicted content you want to provide. This type is
            currently always `content`.
          x-stainless-const: true
        content:
          description: >
            The content that should be matched when generating a model response.

            If generated tokens would match this content, the entire model
            response

            can be returned much more quickly.
          oneOf:
            - type: string
              title: Text content
              description: |
                The content used for a Predicted Output. This is often the
                text of a file you are regenerating with minor changes.
            - type: array
              description: >-
                An array of content parts with a defined type. Supported options
                differ based on the [model](/docs/models) being used to generate
                the response. Can contain text inputs.
              title: Array of content parts
              items: &ref_1
                $ref: >-
                  #/components/schemas/ChatCompletionRequestMessageContentPartText
              minItems: 1
      x-apifox-orders:
        - type
        - content
      x-apifox-ignore-properties: []
      x-apifox-folder: ''
    ChatCompletionRequestMessageContentPartText:
      type: object
      title: Text content part
      description: |
        Learn about [text inputs](/docs/guides/text-generation).
      properties:
        type:
          type: string
          enum:
            - text
          description: The type of the content part.
          x-stainless-const: true
        text:
          type: string
          description: The text content.
      required:
        - type
        - text
      x-apifox-orders:
        - type
        - text
      x-apifox-ignore-properties: []
      x-apifox-folder: ''
    StopConfiguration:
      description: |-
        不支持最新的推理模型 `o3` 和 `o4-mini`。

        最多支持4个序列，API将在这些序列处停止生成更多的标记。

        返回的文本将不包含停止序列。
      default: null
      oneOf:
        - type: string
          default: <|endoftext|>
          examples:
            - |+

          title: ''
          description: ''
          nullable: true
        - type: array
          minItems: 1
          maxItems: 4
          items:
            type: string
            examples:
              - '["\n"]'
          title: ''
          description: ''
      type: 'null'
      x-apifox-folder: ''
    ResponseFormatJsonObject:
      type: object
      title: JSON object
      description: |-
        JSON 对象响应格式。一种较旧的生成 JSON 响应的方法。

        建议对支持该功能的模型使用 `json_schema`。请注意，

        模型不会在没有系统或用户消息指示的情况下生成 JSON。
      properties:
        type:
          type: string
          description: 定义的响应格式类型。始终为 `json_object`。
          enum:
            - json_object
          x-stainless-const: true
      required:
        - type
      x-apifox-orders:
        - type
      x-apifox-ignore-properties: []
      x-apifox-folder: ''
    ResponseFormatJsonSchema:
      type: object
      title: JSON schema
      description: JSON Schema响应格式。用于生成结构化JSON响应。
      properties:
        type:
          type: string
          description: 正在定义的响应格式类型。始终为 `json_schema`。
          enum:
            - json_schema
          x-stainless-const: true
        json_schema:
          type: object
          title: JSON schema
          description: 结构化输出配置选项，包括 JSON 模式。
          properties:
            description:
              type: string
              description: 响应格式的描述，用于模型确定如何以该格式进行响应。
            name:
              type: string
              description: 响应格式的名称。必须是a-z、A-Z、0-9，或包含下划线和连字符，最大长度为64。
            schema:
              $ref: '#/components/schemas/ResponseFormatJsonSchemaSchema'
            strict:
              type: boolean
              default: false
              description: |
                是否在生成输出时启用严格的模式遵循。

                如果设置为 true，模型将始终遵循 `schema` 字段中定义的确切模式。

                当 `strict` 为 `true` 时，仅支持 JSON Schema 的子集。
              nullable: true
          required:
            - name
          x-apifox-orders:
            - description
            - name
            - schema
            - strict
          x-apifox-ignore-properties: []
      required:
        - type
        - json_schema
      x-apifox-orders:
        - type
        - json_schema
      x-apifox-ignore-properties: []
      x-apifox-folder: ''
    ResponseFormatJsonSchemaSchema:
      type: object
      title: JSON schema
      description: |-
        响应格式的模式，描述为JSON模式对象。

        了解如何构建JSON架构[此处]（https://json-schema.org/）。
      additionalProperties: true
      x-apifox-orders: []
      properties: {}
      x-apifox-ignore-properties: []
      x-apifox-folder: ''
    ResponseFormatText:
      type: object
      title: Text
      description: |
        Default response format. Used to generate text responses.
      properties:
        type:
          type: string
          description: 默认响应格式。用于生成文本响应。
          enum:
            - text
          x-stainless-const: true
      required:
        - type
      x-apifox-orders:
        - type
      x-apifox-ignore-properties: []
      x-apifox-folder: ''
    WebSearchContextSize:
      type: string
      description: 用于搜索的上下文窗口空间量的高级指导。可选值为`low`、`medium`或`high`。默认值为`medium`。
      enum:
        - low
        - medium
        - high
      default: medium
      x-apifox-folder: ''
    WebSearchLocation:
      type: object
      title: Web search location
      description: Approximate location parameters for the search.
      properties:
        country:
          type: string
          description: |-
            用户的两个字母

            [ISO国家代码](https://en.wikipedia.org/wiki/ISO_3166-1)，

            例如 `US`。
        region:
          type: string
          description: 用户所在地区的自由文本输入，例如 `California`。
        city:
          type: string
          description: 用户所在城市的自由文本输入，例如 `San Francisco`。
        timezone:
          type: string
          description: >-
            用户的 [IANA 时区](https://timeapi.io/documentation/iana-timezones)，例如
            `America/Los_Angeles`。
      x-apifox-orders:
        - country
        - region
        - city
        - timezone
      x-apifox-ignore-properties: []
      x-apifox-folder: ''
    ReasoningEffort:
      type: string
      enum:
        - low
        - medium
        - high
      default: medium
      description: |-
        仅限o系列模型

        限制推理模型的推理努力

        [推理模型](https://platform.openai.com/docs/guides/reasoning)。

        当前支持的值为`low`（低）、`medium`（中）和`high`（高）。减少推理努力可以带来更快的响应速度和在响应中使用更少的推理令牌。
      nullable: true
      x-apifox-folder: ''
    ResponseModalities:
      type: array
      description: |-
        您希望模型生成的输出类型。

        大多数模型能够生成文本，这是默认选项：

        `["text"]`

        `gpt-4o-audio-preview` 模型还可以用于生成音频。要请求该模型同时生成

        文本和音频响应，您可以使用：

        `["text", "audio"]`
      items:
        type: string
        enum:
          - text
          - audio
      nullable: true
      x-apifox-folder: ''
    ChatCompletionRequestMessage:
      oneOf:
        - $ref: '#/components/schemas/ChatCompletionRequestDeveloperMessage'
        - $ref: '#/components/schemas/ChatCompletionRequestSystemMessage'
        - $ref: '#/components/schemas/ChatCompletionRequestUserMessage'
        - $ref: '#/components/schemas/ChatCompletionRequestAssistantMessage'
        - $ref: '#/components/schemas/ChatCompletionRequestToolMessage'
        - $ref: '#/components/schemas/ChatCompletionRequestFunctionMessage'
      x-apifox-folder: ''
    ChatCompletionRequestFunctionMessage:
      type: object
      title: Function message
      deprecated: true
      properties:
        role:
          type: string
          enum:
            - function
          description: 消息作者的角色，在此情况下为 `function`。
          x-stainless-const: true
        content:
          type: string
          description: 函数消息的内容。
          nullable: true
        name:
          type: string
          description: 要调用的函数名称。
      required:
        - role
        - content
        - name
      x-apifox-orders:
        - role
        - content
        - name
      x-apifox-ignore-properties: []
      x-apifox-folder: ''
    ChatCompletionRequestToolMessage:
      type: object
      title: Tool message
      properties:
        role:
          type: string
          enum:
            - tool
          description: 消息作者的角色，在此情况下为 `tool`。
          x-stainless-const: true
        content:
          oneOf:
            - type: string
              description: 工具消息的内容。
              title: Text content
            - type: array
              description: 具有定义类型的内容部分数组。对于工具消息，仅支持类型 `text`。
              title: Array of content parts
              items:
                $ref: >-
                  #/components/schemas/ChatCompletionRequestToolMessageContentPart
              minItems: 1
          description: 工具消息的内容。
        tool_call_id:
          type: string
          description: 该消息所响应的工具调用。
      required:
        - role
        - content
        - tool_call_id
      x-apifox-orders:
        - role
        - content
        - tool_call_id
      x-apifox-ignore-properties: []
      x-apifox-folder: ''
    ChatCompletionRequestToolMessageContentPart:
      oneOf:
        - *ref_1
      x-apifox-folder: ''
    ChatCompletionRequestAssistantMessage:
      type: object
      title: Assistant message
      description: 模型对用户消息发送的回复。
      properties:
        content:
          oneOf:
            - type: string
              description: The contents of the assistant message.
              title: Text content
            - type: array
              description: >-
                An array of content parts with a defined type. Can be one or
                more of type `text`, or exactly one of type `refusal`.
              title: Array of content parts
              items:
                $ref: >-
                  #/components/schemas/ChatCompletionRequestAssistantMessageContentPart
              minItems: 1
          description: 助手消息的内容。除非指定了`tool_calls`或`function_call`，否则为必填项。
          type: 'null'
        refusal:
          type: string
          description: 助手拒绝的消息。
          nullable: true
        role:
          type: string
          enum:
            - assistant
          description: 消息作者的角色，在本例中为`assistant`。
          x-stainless-const: true
        name:
          type: string
          description: 参与者的可选名称。为模型提供信息以区分同一角色的不同参与者。
        audio:
          type: object
          description: 关于模型之前音频响应的数据。
          required:
            - id
          properties:
            id:
              type: string
              description: |
                Unique identifier for a previous audio response from the model.
          x-apifox-orders:
            - id
          x-apifox-ignore-properties: []
          nullable: true
        tool_calls: &ref_4
          $ref: '#/components/schemas/ChatCompletionMessageToolCalls'
        function_call:
          type: object
          deprecated: true
          description: 已弃用，改为使用 `tool_calls`。由模型生成的应调用函数的名称和参数。
          properties:
            arguments:
              type: string
              description: >-
                调用函数的参数，由模型以JSON格式生成。请注意，模型并不总是生成有效的JSON，可能会产生未在您的函数模式中定义的参数。在调用函数之前，请在代码中验证参数。
            name:
              type: string
              description: 要调用的函数名称。
          required:
            - arguments
            - name
          x-apifox-orders:
            - arguments
            - name
          x-apifox-ignore-properties: []
          nullable: true
      required:
        - role
      x-apifox-orders:
        - content
        - refusal
        - role
        - name
        - audio
        - tool_calls
        - function_call
      x-apifox-ignore-properties: []
      x-apifox-folder: ''
    ChatCompletionMessageToolCalls:
      type: array
      description: The tool calls generated by the model, such as function calls.
      items:
        $ref: '#/components/schemas/ChatCompletionMessageToolCall'
      x-apifox-folder: ''
    ChatCompletionMessageToolCall:
      type: object
      properties:
        id:
          type: string
          description: 工具调用的ID。
        type:
          type: string
          enum:
            - function
          description: 工具的类型。目前仅支持`function`。
          x-stainless-const: true
        function:
          type: object
          description: 模型调用的函数。
          properties:
            name:
              type: string
              description: 要调用的函数名称。
            arguments:
              type: string
              description: >-
                调用函数的参数，由模型以JSON格式生成。请注意，模型并不总是生成有效的JSON，可能会产生未在您的函数模式中定义的参数。在调用函数之前，请在代码中验证这些参数。
          required:
            - name
            - arguments
          x-apifox-orders:
            - name
            - arguments
          x-apifox-ignore-properties: []
      required:
        - id
        - type
        - function
      x-apifox-orders:
        - id
        - type
        - function
      x-apifox-ignore-properties: []
      x-apifox-folder: ''
    ChatCompletionRequestAssistantMessageContentPart:
      oneOf:
        - *ref_1
        - $ref: '#/components/schemas/ChatCompletionRequestMessageContentPartRefusal'
      x-apifox-folder: ''
    ChatCompletionRequestMessageContentPartRefusal:
      type: object
      title: Refusal content part
      properties:
        type:
          type: string
          enum:
            - refusal
          description: The type of the content part.
          x-stainless-const: true
        refusal:
          type: string
          description: The refusal message generated by the model.
      required:
        - type
        - refusal
      x-apifox-orders:
        - type
        - refusal
      x-apifox-ignore-properties: []
      x-apifox-folder: ''
    ChatCompletionRequestUserMessage:
      type: object
      title: User message
      description: 由终端用户发送的消息，包含提示或附加的上下文信息。
      properties:
        content:
          description: 用户消息的内容。
          oneOf:
            - type: string
              description: The text contents of the message.
              title: Text content
            - type: array
              description: >-
                An array of content parts with a defined type. Supported options
                differ based on the [model](/docs/models) being used to generate
                the response. Can contain text, image, or audio inputs.
              title: Array of content parts
              items:
                $ref: >-
                  #/components/schemas/ChatCompletionRequestUserMessageContentPart
              minItems: 1
       