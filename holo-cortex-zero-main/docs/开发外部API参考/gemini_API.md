# 聊天接口(非流)

## OpenAPI Specification

```yaml
openapi: 3.0.1
info:
  title: ''
  description: ''
  version: 1.0.0
paths:
  /gemini/v1beta/models/{mode}:generateContent:
    post:
      summary: 聊天接口(非流)
      deprecated: false
      description: ''
      tags:
        - 语言模型/Gemini
      parameters:
        - name: mode
          in: path
          description: 模型名称
          required: true
          schema:
            type: string
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                system_instruction:
                  type: object
                  properties:
                    parts:
                      type: object
                      properties:
                        text:
                          type: string
                          description: 提示词内容
                      required:
                        - text
                      x-apifox-orders:
                        - text
                  required:
                    - parts
                  x-apifox-orders:
                    - parts
                  description: 系统提示词
                generationConfig:
                  type: object
                  properties:
                    responseModalities:
                      type: array
                      items:
                        type: string
                        enum:
                          - Text
                          - Image
                          - AUDIO
                        x-apifox-enum:
                          - value: Text
                            name: ''
                            description: 文本
                          - value: Image
                            name: ''
                            description: 图像
                          - value: AUDIO
                            name: ''
                            description: 音频
                      description: 输出多模态设置
                    speechConfig:
                      type: object
                      properties:
                        multiSpeakerVoiceConfig:
                          type: object
                          properties:
                            speakerVoiceConfigs:
                              type: array
                              items:
                                type: object
                                properties:
                                  speaker:
                                    type: string
                                    description: 要使用的说话人名称。应与提示中的名称相同。
                                  voiceConfig:
                                    type: object
                                    properties:
                                      prebuiltVoiceConfig:
                                        type: object
                                        properties:
                                          voiceName:
                                            type: string
                                            description: 要使用的预设语音名称。
                                        required:
                                          - voiceName
                                        x-apifox-orders:
                                          - voiceName
                                    required:
                                      - prebuiltVoiceConfig
                                    x-apifox-orders:
                                      - prebuiltVoiceConfig
                                    description: 声音设置
                                required:
                                  - speaker
                                  - voiceConfig
                                x-apifox-orders:
                                  - speaker
                                  - voiceConfig
                              description: 所有启用的扬声器声音。
                          required:
                            - speakerVoiceConfigs
                          x-apifox-orders:
                            - speakerVoiceConfigs
                          description: 多人说话配置 与单人说话配置互斥
                        voiceConfig:
                          type: object
                          properties:
                            prebuiltVoiceConfig:
                              type: object
                              properties:
                                voiceName:
                                  type: string
                                  description: 要使用的预设语音名称。
                              x-apifox-orders:
                                - voiceName
                              description: 预构建语音的配置
                              required:
                                - voiceName
                          x-apifox-orders:
                            - prebuiltVoiceConfig
                          description: 单人说话配置 与多人说话配置互斥
                          required:
                            - prebuiltVoiceConfig
                        languageCode:
                          type: string
                          description: >-
                            用于语音合成的语言代码

                            有效值包括：de-DE、en-AU、en-GB、en-IN、en-US、es-US、fr-FR、hi-IN、pt-BR、ar-XA、es-ES、fr-CA、id-ID、it-IT、ja-JP、tr-TR、vi-VN、bn-IN、gu-IN、kn-IN、ml-IN、mr-IN、ta-IN、te-IN、nl-NL、ko-KR、cmn-CN、pl-PL、ru-RU
                            和 th-TH。
                      required:
                        - voiceConfig
                      x-apifox-orders:
                        - multiSpeakerVoiceConfig
                        - voiceConfig
                        - languageCode
                      description: 音频设置
                    stopSequences:
                      type: array
                      items:
                        type: string
                      description: 停止序列
                    temperature:
                      type: integer
                      description: 温度
                    maxOutputTokens:
                      type: integer
                      description: 最大输出tokens
                    topP:
                      type: number
                    topK:
                      type: integer
                    thinkingConfig:
                      type: object
                      properties:
                        includeThoughts:
                          type: boolean
                          description: 是否包含推理过程
                        thinkingBudget:
                          type: integer
                          description: 推理tokens
                      required:
                        - includeThoughts
                        - thinkingBudget
                      x-apifox-orders:
                        - includeThoughts
                        - thinkingBudget
                      description: 推理设置
                    responseMimeType:
                      type: string
                      description: 结构化输出设置，application/json
                    responseSchema:
                      type: object
                      properties:
                        type:
                          type: string
                        items:
                          type: object
                          properties:
                            type:
                              type: string
                            properties:
                              type: object
                              properties:
                                recipe_name:
                                  type: object
                                  properties:
                                    type:
                                      type: string
                                  required:
                                    - type
                                  x-apifox-orders:
                                    - type
                              required:
                                - recipe_name
                              x-apifox-orders:
                                - recipe_name
                          required:
                            - type
                            - properties
                          x-apifox-orders:
                            - type
                            - properties
                      required:
                        - type
                        - items
                      x-apifox-orders:
                        - type
                        - items
                      description: 生成的候选文本的输出模式。模式必须是 OpenAPI 模式的子集，可以是对象、原始类型或数组。
                  required:
                    - responseModalities
                    - responseMimeType
                    - responseSchema
                    - stopSequences
                    - temperature
                    - maxOutputTokens
                    - topP
                    - topK
                    - thinkingConfig
                  x-apifox-orders:
                    - responseModalities
                    - speechConfig
                    - responseMimeType
                    - responseSchema
                    - stopSequences
                    - temperature
                    - maxOutputTokens
                    - topP
                    - topK
                    - thinkingConfig
                  description: |-
                    生成设置。

                    **注意不是所有的配置都能同时存在，请查看官方文档**
                tools:
                  type: array
                  items:
                    type: object
                    properties:
                      codeExecution:
                        type: object
                        properties: {}
                        x-apifox-orders: []
                        description: 代码执行工具
                      googleSearch:
                        type: object
                        properties: {}
                        x-apifox-orders: []
                        description: 联网搜索工具
                      functionDeclarations:
                        type: array
                        items:
                          type: object
                          properties:
                            name:
                              type: string
                            description:
                              type: string
                            parameters:
                              type: object
                              properties:
                                type:
                                  type: string
                                properties:
                                  type: object
                                  properties:
                                    rgb_hex:
                                      type: object
                                      properties:
                                        type:
                                          type: string
                                        description:
                                          type: string
                                      required:
                                        - type
                                        - description
                                      x-apifox-orders:
                                        - type
                                        - description
                                  required:
                                    - rgb_hex
                                  x-apifox-orders:
                                    - rgb_hex
                                required:
                                  type: array
                                  items:
                                    type: string
                              required:
                                - type
                                - properties
                                - required
                              x-apifox-orders:
                                - type
                                - properties
                                - required
                          required:
                            - name
                            - description
                          x-apifox-orders:
                            - name
                            - description
                            - parameters
                        description: 自定义工具
                    x-apifox-orders:
                      - functionDeclarations
                      - codeExecution
                      - googleSearch
                  description: 工具
                tool_config:
                  type: object
                  properties:
                    functionCallingConfig:
                      type: object
                      properties:
                        mode:
                          type: string
                          description: 指定函数调用的执行模式。如果未指定，则默认值将设置为 AUTO。
                        allowedFunctionNames:
                          type: array
                          items:
                            type: string
                          description: >-
                            一组函数名称，提供时会限制模型将调用的函数。


                            仅当 Mode 为 ANY 或 VALIDATED 时才应设置此项。函数名称应与
                            [FunctionDeclaration.name]
                            匹配。设置后，模型将仅根据允许的函数名称预测函数调用。
                      required:
                        - mode
                        - allowedFunctionNames
                      x-apifox-orders:
                        - mode
                        - allowedFunctionNames
                      description: 函数调用配置
                  required:
                    - functionCallingConfig
                  x-apifox-orders:
                    - functionCallingConfig
                  description: 工具配置
                contents:
                  type: array
                  items:
                    type: object
                    properties:
                      role:
                        type: string
                        description: 角色名称
                      parts:
                        type: array
                        properties:
                          text:
                            type: string
                        required:
                          - text
                        items:
                          type: object
                          properties:
                            functionCall:
                              type: object
                              properties:
                                name:
                                  type: string
                              required:
                                - name
                              x-apifox-orders:
                                - name
                              description: 需要请求的函数
                            functionResponse:
                              type: object
                              properties:
                                name:
                                  type: string
                                response:
                                  type: object
                                  properties:
                                    name:
                                      type: string
                                    content:
                                      type: string
                                  required:
                                    - name
                                    - content
                                  x-apifox-orders:
                                    - name
                                    - content
                              required:
                                - name
                                - response
                              x-apifox-orders:
                                - name
                                - response
                              description: 函数回复数据
                            text:
                              type: string
                              description: 文本内容
                            executableCode:
                              type: object
                              properties: {}
                              x-apifox-orders: []
                              description: 需要执行的代码
                            codeExecutionResult:
                              type: object
                              properties: {}
                              x-apifox-orders: []
                              description: 代码执行结果
                            inlineData:
                              type: object
                              properties:
                                mime_type:
                                  type: string
                                  description: >-
                                    媒体类型


                                    文档类型对应的MIME类型列表：


                                    - PDF - application/pdf

                                    - JavaScript -
                                    application/x-javascript、text/javascript

                                    - Python -
                                    application/x-python、text/x-python

                                    - TXT - text/plain

                                    - HTML - text/html

                                    - CSS - text/css

                                    - Markdown - text/md

                                    - CSV - text/csv

                                    - XML - text/xml

                                    - RTF - text/rtf


                                    音频类型对应的MIME类型列表：

                                    - WAV - audio/wav

                                    - MP3 - audio/mp3

                                    - AIFF - audio/aiff

                                    - AAC - audio/aac

                                    - OGG Vorbis - audio/ogg

                                    - FLAC - audio/flac


                                    视频类型对应的MIME类型列表：

                                    - video/mp4

                                    - video/mpeg

                                    - video/mov

                                    - video/avi

                                    - video/x-flv

                                    - video/mpg

                                    - video/webm

                                    - video/wmv

                                    - video/3gpp


                                    图片类型对应的MIME类型列表：

                                    - PNG - image/png

                                    - JPEG - image/jpeg

                                    - WEBP - image/webp

                                    - HEIC - image/heic

                                    - HEIF - image/heif
                                data:
                                  type: string
                                  description: base64数据
                              required:
                                - mime_type
                                - data
                              x-apifox-orders:
                                - mime_type
                                - data
                              description: 媒体数据
                          x-apifox-orders:
                            - functionCall
                            - functionResponse
                            - text
                            - inlineData
                            - executableCode
                            - codeExecutionResult
                        description: 内容
                    required:
                      - role
                      - parts
                    x-apifox-orders:
                      - role
                      - parts
                  description: 内容数组
                systemInstruction:
                  type: string
              required:
                - tools
                - contents
                - systemInstruction
              x-apifox-orders:
                - system_instruction
                - generationConfig
                - tools
                - tool_config
                - contents
                - systemInstruction
            examples:
              '1':
                value:
                  contents:
                    - parts:
                        - text: Write a story about a magic backpack.
                summary: 文本
              '2':
                value:
                  contents:
                    - parts:
                        - text: Tell me about this instrument
                        - inline_data:
                            mime_type: image/jpeg
                            data: Base64 data.....
                summary: 图像理解
              '3':
                value:
                  contents:
                    - parts:
                        - text: Tell me about this audio
                        - inline_data:
                            mime_type: audio/wav
                            data: Base64 data.....
                summary: 音频理解
              '4':
                value: |-
                  {
                      "contents": [
                          {
                              "parts": [
                                  {
                                      "text": "List 5 popular cookie recipes"
                                  }
                              ]
                          }
                      ],
                      "generationConfig": {
                          "response_mime_type": "application/json",
                          "response_schema": {
                              "type": "ARRAY",
                              "items": {
                                  "type": "OBJECT",
                                  "properties": {
                                      "recipe_name": {
                                          "type": "STRING"
                                      },
                                  }
                              }
                          }
                      }
                  }
                summary: 结构化输出
              '5':
                value:
                  system_instruction:
                    parts:
                      text: >-
                        You are a helpful lighting system bot. You can turn
                        lights on and off, and you can set the color. Do not
                        perform any other tasks.
                  tools:
                    - function_declarations:
                        - name: enable_lights
                          description: Turn on the lighting system.
                        - name: set_light_color
                          description: >-
                            Set the light color. Lights must be enabled for this
                            to work.
                          parameters:
                            type: object
                            properties:
                              rgb_hex:
                                type: string
                                description: >-
                                  The light color as a 6-digit hex string, e.g.
                                  ff0000 for red.
                            required:
                              - rgb_hex
                        - name: stop_lights
                          description: Turn off the lighting system.
                  tool_config:
                    function_calling_config:
                      mode: auto
                  contents:
                    - role: user
                      parts:
                        text: Turn on the lights please.
                    - role: model
                      parts:
                        - functionCall:
                            name: enable_lights
                    - parts:
                        - functionResponse:
                            name: enable_lights
                            response:
                              name: enable_lights
                              content: Lights have been turned on.
                summary: 函数调用
              '6':
                value:
                  contents:
                    - parts:
                        - text: >-
                            TTS the following conversation between Joe and Jane:
                            Joe: Hows it going today Jane? Jane: Not too bad,
                            how about you?
                  generationConfig:
                    responseModalities:
                      - AUDIO
                    speechConfig:
                      multiSpeakerVoiceConfig:
                        speakerVoiceConfigs:
                          - speaker: Joe
                            voiceConfig:
                              prebuiltVoiceConfig:
                                voiceName: Kore
                          - speaker: Jane
                            voiceConfig:
                              prebuiltVoiceConfig:
                                voiceName: Puck
                  model: gemini-2.5-flash-preview-tts
                summary: TTS/音频生成
                description: ⚠️该请求需要使用tts模型请求
              '7':
                value:
                  generationConfig:
                    responseModalities:
                      - Text
                      - Image
                  contents:
                    - role: user
                      parts:
                        - text: 画一只可爱的猫
                summary: 图像生成
                description: 注意需要使用image模型，例如gemini-2.5-flash-image
      responses:
        '200':
          description: ''
          content:
            application/json:
              schema:
                type: object
                properties: {}
          headers: {}
          x-apifox-name: 成功
      security:
        - bearer: []
      x-apifox-folder: 语言模型/Gemini
      x-apifox-status: developing
      x-run-in-apifox: https://app.apifox.com/web/project/4632351/apis/api-366719812-run
components:
  schemas: {}
  securitySchemes:
    MJ:
      type: apikey
      in: header
      name: mj-api-secret
    BFL:
      type: apikey
      in: header
      name: x-key
    bearer:
      type: http
      scheme: bearer
servers:
  - url: https://api.uniapi.io
    description: 正式环境
security:
  - bearer: []
```
