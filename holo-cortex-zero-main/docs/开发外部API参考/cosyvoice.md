CosyVoice声音复刻服务基于生成式语音大模型，使用10~20秒音频样本即可生成高度相似且自然的定制声音，无需传统训练过程。声音复刻与语音合成是前后关联的两个步骤。本文档聚焦于介绍声音复刻的参数和接口细节，语音合成请参见[实时语音合成-CosyVoice/Sambert](https://help.aliyun.com/zh/model-studio/text-to-speech)。

**用户指南：**关于模型介绍和选型建议请参见[实时语音合成-CosyVoice/Sambert](https://help.aliyun.com/zh/model-studio/text-to-speech)。

**重要**

本文档专用于CosyVoice声音复刻接口；若您使用的是千问模型，请参见[声音复刻（Qwen）](https://help.aliyun.com/zh/model-studio/qwen-tts-voice-cloning)。

## **音频要求**

高质量的输入音频是获得优质复刻效果的基础。

| **项目** | **要求** |
| --- | --- |
| **支持格式** | WAV (16bit), MP3, M4A |
| **音频时长** | 推荐10~20秒，最长不得超过60秒 |
| **文件大小** | ≤ 10 MB |
| **采样率** | ≥ 16 kHz |
| **声道** | 单声道 / 双声道，双声道音频仅处理首声道，请确保首声道包含有效人声 |
| **内容** | 音频必须包含至少5秒连续清晰朗读（无背景音），其余部分仅允许短暂停顿（≤2秒）；整段音频应避免背景音乐、噪音或其他人声，确保核心朗读内容质量；请使用正常说话音频作为输入，不要上传歌曲或唱歌音频，以确保复刻效果准确和可用。 |
| **语言** | 因驱动音色的语音合成模型（通过`target_model`/`targetModel`参数指定）而异： - cosyvoice-v1、cosyvoice-v2：中文（普通话）、英文 - cosyvoice-v3-flash、cosyvoice-v3-plus：中文（普通话、广东话、东北话、甘肃话、贵州话、河南话、湖北话、江西话、闽南话、宁夏话、山西话、陕西话、山东话、上海话、四川话、天津话、云南话）、英文、法语、德语、日语、韩语、俄语 当前声音复刻仅支持上述列出的语言（中文普通话及表中列出的方言、英文、法语、德语、日语、韩语、俄语），暂不支持西班牙语、意大利语等其他语种的声音复刻。 |

## 快速开始：从复刻到合成

![image](https://help-static-aliyun-doc.aliyuncs.com/assets/img/zh-CN/3881370771/CAEQYxiBgMCNsMj91BkiIDdiMWQyMmQ0MzMzNjRjNGU4OGViYTU2MTE1OTExNTg05899512_20251120114927.389.svg)

### 1\. 工作流程

声音复刻与语音合成是紧密关联的两个独立步骤，遵循“先创建，后使用”的流程：

1.  创建音色
    
    调用[创建音色](#1eaa57d82did9)接口，上传一段音频。系统会分析该音频，创建一个专属的复刻音色。**此步骤必须指定**`**target_model**`**/**`**targetModel**`**，声明创建的音色将由哪个语音合成模型驱动。**
    
    若已有创建好的音色（调用[查询音色列表](#401d33226330i)接口查看），可跳过这一步直接进行下一步。
    
2.  使用音色进行语音合成
    
    使用[创建音色](#1eaa57d82did9)接口创建音色成功后，系统会返回一个`voice_id`/`voiceID`：
    
    -   该 `voice_id`/`voiceID` 可直接作为语音合成接口或各语言 SDK 中的 `voice` 参数使用，用于后续的文本转语音。
        
    -   支持多种调用形态，包括非流式、单向流式以及双向流式合成。
        
    -   合成时指定的语音合成模型必须与创建音色时的 `target_model`/`targetModel` 保持一致，否则合成会失败。
        

### 2\. 模型配置与准备工作

选择合适的模型并完成准备工作。

#### 模型配置

**重要**

在[国际部署模式](https://help.aliyun.com/zh/model-studio/regions/#080da663a75xh)（新加坡地域）下，cosyvoice-v3-plus和cosyvoice-v3-flash不支持声音复刻功能，请选择其他模型。

声音复刻时需要指定以下两个模型：

-   声音复刻模型：voice-enrollment
    
-   驱动音色的语音合成模型：
    
    在资源与预算允许的情况下，推荐使用`cosyvoice-v3-plus`以获得最佳效果。
    
    | **版本** | **适用场景** |
    | --- | --- |
    | **cosyvoice-v3-plus** | 追求最佳音质与表现力，预算充足 |
    | **cosyvoice-v3-flash** | 平衡效果与成本，综合性价比高 |
    | **cosyvoice-v2** | 兼容旧版或低要求场景 |
    | **cosyvoice-v1** | 兼容旧版或低要求场景 |
    

#### 准备工作

1.  **获取API Key**：[获取API Key](https://help.aliyun.com/zh/model-studio/get-api-key)，为安全起见，推荐将API Key配置到环境变量。
    
2.  **安装SDK**：确保已[安装最新版DashScope SDK](https://help.aliyun.com/zh/model-studio/install-sdk)。
    
3.  **准备音频URL**：将符合[音频要求](#音频要求与最佳实践)的音频文件上传至公网可访问的位置，如[阿里云对象存储OSS](https://help.aliyun.com/zh/oss/user-guide/simple-upload#a632b50f190j8)，并确保URL可公开访问。
    

### 3\. 端到端示例：从复刻到合成

以下示例演示了如何在语音合成中使用声音复刻生成的专属音色，实现与原音高度相似的输出效果。

-   **关键原则**：声音复刻时，`target_model`（驱动音色的语音合成模型）必须与后续调用语音合成接口时指定的语音合成模型一致，否则会合成失败。
    
-   注意将示例中的`AUDIO_URL`替换为实际的音频URL。
    

```
import os
import time
import dashscope
from dashscope.audio.tts_v2 import VoiceEnrollmentService, SpeechSynthesizer

# 1. 环境准备
# 推荐通过环境变量配置API Key
# export DASHSCOPE_API_KEY="<API_KEY>"
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
if not dashscope.api_key:
    raise ValueError("DASHSCOPE_API_KEY environment variable not set.")

# 2. 定义复刻参数
TARGET_MODEL = "cosyvoice-v3-plus" 
# 为音色起一个有意义的前缀
VOICE_PREFIX = "myvoice" # 仅允许数字和小写字母，小于十个字符
# 公网可访问音频URL
AUDIO_URL = "https://dashscope.oss-cn-beijing.aliyuncs.com/samples/audio/cosyvoice/cosyvoice-zeroshot-sample.wav" # 示例URL，请替换为自己的

# 3. 创建音色 (异步任务)
print("--- Step 1: Creating voice enrollment ---")
service = VoiceEnrollmentService()
try:
    voice_id = service.create_voice(
        target_model=TARGET_MODEL,
        prefix=VOICE_PREFIX,
        url=AUDIO_URL
    )
    print(f"Voice enrollment submitted successfully. Request ID: {service.get_last_request_id()}")
    print(f"Generated Voice ID: {voice_id}")
except Exception as e:
    print(f"Error during voice creation: {e}")
    raise e
# 4. 轮询查询音色状态
print("\n--- Step 2: Polling for voice status ---")
max_attempts = 30
poll_interval = 10 # 秒
for attempt in range(max_attempts):
    try:
        voice_info = service.query_voice(voice_id=voice_id)
        status = voice_info.get("status")
        print(f"Attempt {attempt + 1}/{max_attempts}: Voice status is '{status}'")
        
        if status == "OK":
            print("Voice is ready for synthesis.")
            break
        elif status == "UNDEPLOYED":
            print(f"Voice processing failed with status: {status}. Please check audio quality or contact support.")
            raise RuntimeError(f"Voice processing failed with status: {status}")
        # 对于 "DEPLOYING" 等中间状态，继续等待
        time.sleep(poll_interval)
    except Exception as e:
        print(f"Error during status polling: {e}")
        time.sleep(poll_interval)
else:
    print("Polling timed out. The voice is not ready after several attempts.")
    raise RuntimeError("Polling timed out. The voice is not ready after several attempts.")

# 5. 使用复刻音色进行语音合成
print("\n--- Step 3: Synthesizing speech with the new voice ---")
try:
    synthesizer = SpeechSynthesizer(model=TARGET_MODEL, voice=voice_id)
    text_to_synthesize = "恭喜，已成功复刻并合成了属于自己的声音！"
    
    # call()方法返回二进制音频数据
    audio_data = synthesizer.call(text_to_synthesize)
    print(f"Speech synthesis successful. Request ID: {synthesizer.get_last_request_id()}")

    # 6. 保存音频文件
    output_file = "my_custom_voice_output.mp3"
    with open(output_file, "wb") as f:
        f.write(audio_data)
    print(f"Audio saved to {output_file}")

except Exception as e:
    print(f"Error during speech synthesis: {e}")
```

## **API参考**

使用不同 API 时，请确保使用同一账号进行操作。

### **创建音色**

上传用于复刻的音频，创建自定义音色。

## Python SDK

#### **接口说明**

```
def create_voice(self, target_model: str, prefix: str, url: str, language_hints: List[str] = None) -> str:
    '''
    创建一个新的定制音色。
    param: target_model 驱动音色的语音合成模型，必须与后续调用语音合成接口时使用的语音合成模型一致，否则合成会失败。推荐 cosyvoice-v3-flash 或 cosyvoice-v3-plus。
    param: prefix 为音色指定一个便于识别的名称（仅允许数字、大小写字母和下划线，不超过10个字符）。建议选用与角色、场景相关的标识。该关键字会在复刻的音色名中出现，生成的音色名格式为：模型名-前缀-唯一标识，如cosyvoice-v3-plus-myvoice-xxxxxxxx。
    param: url 用于复刻音色的音频文件URL，要求公网可访问。
    param: language_hints 指定用于提取目标音色特征的样本音频语种，仅适用于 cosyvoice-v3-flash 和 cosyvoice-v3-plus 模型。
            该参数用于辅助模型识别样本音频（原始参考音频）的语种，从而更准确地提取音色特征，提升复刻效果。
            若设置的语言提示与实际音频语言不符（例如为中文音频设置 en），系统将忽略此提示，并依据音频内容自动检测语言。
            取值范围：zh（默认值）、en、fr、de、ja、ko、ru。此参数为数组，但当前版本仅处理第一个元素，建议只传入一个值。
    return: voice_id 音色ID，可直接用于语音合成接口的voice参数。
    '''
```

**重要**

-   `target_model`：驱动音色的语音合成模型，须和后续调用语音合成接口时使用的语音合成模型一致，否则合成会失败
    
-   `language_hints`：指定用于提取目标音色特征的样本音频语种，仅适用于cosyvoice-v3-flash和cosyvoice-v3-plus模型
    
    功能说明：该参数用于辅助模型识别样本音频（原始参考音频）的语种，从而更准确地提取音色特征，提升复刻效果。若设置的语言提示与实际音频语言不符（例如为中文音频设置 `en`），系统将忽略此提示，并依据音频内容自动检测语言。
    
    取值范围：
    
    -   zh：中文（默认值）
        
    -   en：英文
        
    -   fr：法语
        
    -   de：德语
        
    -   ja：日语
        
    -   ko：韩语
        
    -   ru：俄语
        
    
    对于中文方言（例如东北话、粤语等），建议仍将 `language_hints` 设置为 `zh`，方言风格应在后续语音合成调用中通过文本内容或 `instruct` 等参数进行控制。
    
    **注意**：此参数为数组，但当前版本仅处理第一个元素，因此建议只传入一个值。
    

#### **请求示例**

```
from dashscope.audio.tts_v2 import VoiceEnrollmentService

service = VoiceEnrollmentService()

# 避免频繁调用。每次调用都会创建新音色，达到配额上限后将无法创建。
voice_id = service.create_voice(
    target_model='cosyvoice-v3-plus',
    prefix='myvoice',
    url='https://your-audio-file-url',
    language_hints=['zh']
)

print(f"Request ID: {service.get_last_request_id()}")
print(f"Voice ID: {voice_id}")
```

## Java SDK

#### **接口说明**

```
/**
 * 创建一个新的定制音色。
 *
 * @param targetModel 驱动音色的语音合成模型，必须与后续调用语音合成接口时使用的语音合成模型一致，否则合成会失败。推荐 cosyvoice-v3-flash 或 cosyvoice-v3-plus。
 * @param prefix 为音色指定一个便于识别的名称（仅允许数字、大小写字母和下划线，不超过10个字符）。建议选用与角色、场景相关的标识。该关键字会在复刻的音色名中出现，生成的音色名格式为：模型名-前缀-唯一标识，如cosyvoice-v3-plus-myvoice-xxxxxxxx。
 * @param url 用于复刻音色的音频文件URL，要求公网可访问。
 * @param customParam 自定义参数。可在此处指定languageHints。
 *                  languageHints指定用于提取目标音色特征的样本音频语种，仅适用于 cosyvoice-v3-flash 和 cosyvoice-v3-plus 模型。
 *                  该参数用于辅助模型识别样本音频（原始参考音频）的语种，从而更准确地提取音色特征，提升复刻效果。
 *                  若设置的语言提示与实际音频语言不符（例如为中文音频设置 en），系统将忽略此提示，并依据音频内容自动检测语言。
 *                  取值范围：zh（默认值）、en、fr、de、ja、ko、ru。此参数为数组，但当前版本仅处理第一个元素，建议只传入一个值。
 * @return Voice 新创建的音色，通过Voice的getVoiceId方法能够获取音色ID，可直接用于语音合成接口的voice参数。
 * @throws NoApiKeyException 如果apikey为空。
 * @throws InputRequiredException 如果必须参数为空。
 */
public Voice createVoice(String targetModel, String prefix, String url, VoiceEnrollmentParam customParam) throws NoApiKeyException, InputRequiredException
```

**重要**

-   `targetModel`：驱动音色的语音合成模型，须和后续调用语音合成接口时使用的语音合成模型一致，否则合成会失败
    
-   `languageHints`：指定用于提取目标音色特征的样本音频语种，仅适用于cosyvoice-v3-flash和cosyvoice-v3-plus模型
    
    功能说明：该参数用于辅助模型识别样本音频（原始参考音频）的语种，从而更准确地提取音色特征，提升复刻效果。若设置的语言提示与实际音频语言不符（例如为中文音频设置 `en`），系统将忽略此提示，并依据音频内容自动检测语言。
    
    取值范围：
    
    -   zh：中文（默认值）
        
    -   en：英文
        
    -   fr：法语
        
    -   de：德语
        
    -   ja：日语
        
    -   ko：韩语
        
    -   ru：俄语
        
    
    对于中文方言（例如东北话、粤语等），建议仍将 `language_hints` 设置为 `zh`，方言风格应在后续语音合成调用中通过文本内容或 `instruct` 等参数进行控制。
    
    **注意**：此参数为数组，但当前版本仅处理第一个元素，因此建议只传入一个值。
    

#### **请求示例**

```
import com.alibaba.dashscope.audio.ttsv2.enrollment.Voice;
import com.alibaba.dashscope.audio.ttsv2.enrollment.VoiceEnrollmentParam;
import com.alibaba.dashscope.audio.ttsv2.enrollment.VoiceEnrollmentService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Collections;

public class Main {
    private static final Logger logger = LoggerFactory.getLogger(Main.class);

    public static void main(String[] args) {
        String apiKey = System.getenv("DASHSCOPE_API_KEY");
        String targetModel = "cosyvoice-v3-plus";
        String prefix = "myvoice";
        String fileUrl = "https://your-audio-file-url";
        String cloneModelName = "voice-enrollment";

        try {
            VoiceEnrollmentService service = new VoiceEnrollmentService(apiKey);
            Voice myVoice = service.createVoice(
                    targetModel,
                    prefix,
                    fileUrl,
                    VoiceEnrollmentParam.builder()
                    .model(cloneModelName)
                    .languageHints(Collections.singletonList("zh")).build());

            logger.info("Voice creation submitted. Request ID: {}", service.getLastRequestId());
            logger.info("Generated Voice ID: {}", myVoice.getVoiceId());
        } catch (Exception e) {
            logger.error("Failed to create voice", e);
        }
    }
}
```

## RESTful API

#### **基本信息**

| URL | 中国内地： ``` https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization ``` 国际： ``` https://dashscope-intl.aliyuncs.com/api/v1/services/audio/tts/customization ``` |
| --- | --- |
| 请求方法 | POST |
| 请求头 | ``` Authorization: Bearer {api-key} // 需替换为您自己的API Key Content-Type: application/json ``` |
| 消息体 | 包含所有请求参数的消息体如下，对于可选字段，在实际业务中可根据需求省略： **重要** - `model`：声音复刻模型，固定为`voice-enrollment` - `target_model`：驱动音色的语音合成模型，须和后续调用语音合成接口时使用的语音合成模型一致，否则合成会失败 - `language_hints`：指定用于提取目标音色特征的样本音频语种，仅适用于cosyvoice-v3-flash和cosyvoice-v3-plus模型 功能说明：该参数用于辅助模型识别样本音频（原始参考音频）的语种，从而更准确地提取音色特征，提升复刻效果。若设置的语言提示与实际音频语言不符（例如为中文音频设置 `en`），系统将忽略此提示，并依据音频内容自动检测语言。 取值范围： - zh：中文（默认值） - en：英文 - fr：法语 - de：德语 - ja：日语 - ko：韩语 - ru：俄语 对于中文方言（例如东北话、粤语等），建议仍将 `language_hints` 设置为 `zh`，方言风格应在后续语音合成调用中通过文本内容或 `instruct` 等参数进行控制。 **注意**：此参数为数组，但当前版本仅处理第一个元素，因此建议只传入一个值。 ``` { "model": "voice-enrollment", "input": { "action": "create_voice", "target_model": "cosyvoice-v3-plus", "prefix": "myvoice", "url": "https://yourAudioFileUrl", "language_hints": ["zh"] } } ``` |

#### **请求参数**

**点击查看请求示例**

**重要**

-   `model`：声音复刻模型，固定为`voice-enrollment`
    
-   `target_model`：驱动音色的语音合成模型，须和后续调用语音合成接口时使用的语音合成模型一致，否则合成会失败
    
-   `language_hints`：指定用于提取目标音色特征的样本音频语种，仅适用于cosyvoice-v3-flash和cosyvoice-v3-plus模型
    
    功能说明：该参数用于辅助模型识别样本音频（原始参考音频）的语种，从而更准确地提取音色特征，提升复刻效果。若设置的语言提示与实际音频语言不符（例如为中文音频设置 `en`），系统将忽略此提示，并依据音频内容自动检测语言。
    
    取值范围：
    
    -   zh：中文（默认值）
        
    -   en：英文
        
    -   fr：法语
        
    -   de：德语
        
    -   ja：日语
        
    -   ko：韩语
        
    -   ru：俄语
        
    
    对于中文方言（例如东北话、粤语等），建议仍将 `language_hints` 设置为 `zh`，方言风格应在后续语音合成调用中通过文本内容或 `instruct` 等参数进行控制。
    
    **注意**：此参数为数组，但当前版本仅处理第一个元素，因此建议只传入一个值。
    

```
curl -X POST https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization \
-H "Authorization: Bearer $DASHSCOPE_API_KEY" \
-H "Content-Type: application/json" \
-d '{
    "model": "voice-enrollment",
    "input": {
        "action": "create_voice",
        "target_model": "cosyvoice-v3-plus",
        "prefix": "myvoice",
        "url": "https://yourAudioFileUrl",
        "language_hints": ["zh"]
    }
}'
```

| **参数** | **类型** | **默认值** | **是否必须** | **说明** |
| --- | --- | --- | --- | --- |
| model | string | \\- | 是   | 声音复刻模型，固定为`voice-enrollment`。 |
| action | string | \\- | 是   | 操作类型，固定为`create_voice`。 |
| target\\_model | string | \\- | 是   | 驱动音色的语音合成模型，推荐 cosyvoice-v3-flash 或 cosyvoice-v3-plus。 必须与后续调用语音合成接口时使用的语音合成模型一致，否则合成会失败。 |
| prefix | string | \\- | 是   | 为音色指定一个便于识别的名称（仅允许数字、大小写字母和下划线，不超过10个字符）。建议选用与角色、场景相关的标识。 > 该关键字会在复刻的音色名中出现，生成的音色名格式为：`模型名-前缀-唯一标识`，如`cosyvoice-v3-plus-myvoice-xxxxxxxx`。 |
| url | string | \\- | 是   | 用于复刻音色的音频文件URL，要求公网可访问。 |
| language\\_hints | array\\[string\\] | \\["zh"\\] | 否   | 指定用于提取目标音色特征的样本音频语种，仅适用于 cosyvoice-v3-flash 和 cosyvoice-v3-plus 模型。 功能说明：该参数用于辅助模型识别样本音频（原始参考音频）的语种，从而更准确地提取音色特征，提升复刻效果。若设置的语言提示与实际音频语言不符（例如为中文音频设置 `en`），系统将忽略此提示，并依据音频内容自动检测语言。 取值范围： - zh：中文（默认值） - en：英文 - fr：法语 - de：德语 - ja：日语 - ko：韩语 - ru：俄语 对于中文方言（例如东北话、粤语等），建议仍将 `language_hints` 设置为 `zh`，方言风格应在后续语音合成调用中通过文本内容或 `instruct` 等参数进行控制。 **注意**：此参数为数组，但当前版本仅处理第一个元素，因此建议只传入一个值。 |

#### **响应参数**

**点击查看响应示例**

```
{
    "output": {
        "voice_id": "yourVoiceId"
    },
    "usage": {
        "count": 1
    },
    "request_id": "yourRequestId"
}
```

| **参数** | **类型** | **说明** |
| --- | --- | --- |
| voice\\_id | string | 音色ID，可直接用于语音合成接口的`voice`参数。 |

### **查询音色列表**

分页查询已创建的音色列表。

## Python SDK

#### **接口说明**

```
def list_voices(self, prefix=None, page_index: int = 0, page_size: int = 10) -> List[dict]:
    '''
    查询已创建的所有音色
    param: prefix 音色自定义前缀，仅允许数字和小写字母，长度小于10个字符。
    param: page_index 查询的页索引
    param: page_size 查询页大小
    return: List[dict] 音色列表，包含每个音色的id，创建时间，修改时间，状态。格式为：[{'gmt_create': '2025-10-09 14:51:01', 'gmt_modified': '2025-10-09 14:51:07', 'status': 'OK', 'voice_id': 'cosyvoice-v3-myvoice-xxx'}]
    音色状态有三种：
        DEPLOYING： 审核中
        OK：审核通过，可调用
        UNDEPLOYED：审核不通过，不可调用
    '''
```

#### **请求示例**

```
from dashscope.audio.tts_v2 import VoiceEnrollmentService

service = VoiceEnrollmentService()

# 按前缀筛选，或设为None查询所有
voices = service.list_voices(prefix='myvoice', page_index=0, page_size=10)

print(f"Request ID: {service.get_last_request_id()}")
print(f"Found voices: {voices}")
```

#### **响应示例**

```
[
    {
        "gmt_create": "2024-09-13 11:29:41",
        "voice_id": "yourVoiceId",
        "gmt_modified": "2024-09-13 11:29:41",
        "status": "OK"
    },
    {
        "gmt_create": "2024-09-13 13:22:38",
        "voice_id": "yourVoiceId",
        "gmt_modified": "2024-09-13 13:22:38",
        "status": "OK"
    }
]
```

#### **响应参数**

| **参数** | **类型** | **说明** |
| --- | --- | --- |
| voice\\_id | string | 音色ID。 |
| gmt\\_create | string | 创建音色的时间。 |
| gmt\\_modified | string | 修改音色的时间。 |
| status | string | 音色状态： - DEPLOYING： 审核中 - OK：审核通过，可调用 - UNDEPLOYED：审核不通过，不可调用 |

## Java SDK

#### **接口说明**

```
// 音色状态有三种：
//        DEPLOYING： 审核中
//        OK：审核通过，可调用
//        UNDEPLOYED：审核不通过，不可调用
/**
 * 查询已创建的所有音色 默认的页索引为0，默认的页大小为10
 *
 * @param prefix 音色自定义前缀，仅允许数字和小写字母，长度小于10个字符。可以为null。
 * @return Voice[] 音色对象数组。Voice封装了音色的id，创建时间，修改时间，状态。
 * @throws NoApiKeyException 如果apikey为空。
 * @throws InputRequiredException 如果必须参数为空。
 */
public Voice[] listVoice(String prefix) throws NoApiKeyException, InputRequiredException 

/**
 * 查询已创建的所有音色
 *
 * @param prefix 音色自定义前缀，仅允许数字和小写字母，长度小于10个字符。
 * @param pageIndex 查询的页索引。
 * @param pageSize 查询的页大小。
 * @return Voice[] 音色对象数组。Voice封装了音色的id，创建时间，修改时间，状态。
 * @throws NoApiKeyException 如果apikey为空。
 * @throws InputRequiredException 如果必须参数为空。
 */
public Voice[] listVoice(String prefix, int pageIndex, int pageSize) throws NoApiKeyException, InputRequiredException
```

#### **请求示例**

需要引入第三方库`com.google.gson.Gson`。

```
import com.alibaba.dashscope.audio.ttsv2.enrollment.Voice;
import com.alibaba.dashscope.audio.ttsv2.enrollment.VoiceEnrollmentService;
import com.alibaba.dashscope.exception.InputRequiredException;
import com.alibaba.dashscope.exception.NoApiKeyException;
import com.google.gson.Gson;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class Main {
    public static String apiKey = System.getenv("DASHSCOPE_API_KEY");  // 如果您没有配置环境变量，请在此处用您的API-KEY进行替换
    private static String prefix = "myvoice"; // 请按实际情况进行替换
    private static final Logger logger = LoggerFactory.getLogger(Main.class);

    public static void main(String[] args)
            throws NoApiKeyException, InputRequiredException {
        VoiceEnrollmentService service = new VoiceEnrollmentService(apiKey);
        // 查询音色
        Voice[] voices = service.listVoice(prefix, 0, 10);
        logger.info("List successful. Request ID: {}", service.getLastRequestId());
        logger.info("Voices Details: {}", new Gson().toJson(voices));
    }
}
```

### **响应示例**

```
[
    {
        "gmt_create": "2024-09-13 11:29:41",
        "voice_id": "yourVoiceId",
        "gmt_modified": "2024-09-13 11:29:41",
        "status": "OK"
    },
    {
        "gmt_create": "2024-09-13 13:22:38",
        "voice_id": "yourVoiceId",
        "gmt_modified": "2024-09-13 13:22:38",
        "status": "OK"
    }
]
```

### **响应参数**

| **参数** | **类型** | **说明** |
| --- | --- | --- |
| voice\\_id | string | 音色ID。 |
| gmt\\_create | string | 创建音色的时间。 |
| gmt\\_modified | string | 修改音色的时间。 |
| status | string | 音色状态： - DEPLOYING： 审核中 - OK：审核通过，可调用 - UNDEPLOYED：审核不通过，不可调用 |

## RESTful API

#### **基本信息**

| URL | 中国内地： ``` https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization ``` 国际： ``` https://dashscope-intl.aliyuncs.com/api/v1/services/audio/tts/customization ``` |
| --- | --- |
| 请求方法 | POST |
| 请求头 | ``` Authorization: Bearer {api-key} // 需替换为您自己的API Key Content-Type: application/json ``` |
| 消息体 | 包含所有请求参数的消息体如下，对于可选字段，在实际业务中可根据需求省略： **重要** `model`为声音复刻模型，固定为`voice-enrollment`。 ``` { "model": "voice-enrollment", "input": { "action": "list_voice", "prefix": "myvoice", "page_index": 0, "page_size": 10 } } ``` |

#### **请求参数**

**点击查看请求示例**

**重要**

`model`为声音复刻模型，固定为`voice-enrollment`。

```
curl -X POST https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization \
-H "Authorization: Bearer $DASHSCOPE_API_KEY" \
-H "Content-Type: application/json" \
-d '{
    "model": "voice-enrollment",
    "input": {
        "action": "list_voice",
        "prefix": "myvoice",
        "page_index": 0,
        "page_size": 10
    }
}'
```

| **参数** | **类型** | **默认值** | **是否必须** | **说明** |
| --- | --- | --- | --- | --- |
| model | string | \\- | 是   | 声音复刻模型，固定为`voice-enrollment`。 |
| action | string | \\- | 是   | 操作类型，固定为`list_voice`。 |
| prefix | string | null | 否   | 音色自定义前缀，仅允许数字和小写字母，长度小于10个字符。 |
| page\\_index | integer | 0   | 否   | 页码索引，从0开始计数。 |
| page\\_size | integer | 10  | 否   | 每页包含数据条数。 |

#### **响应参数**

**点击查看响应示例**

```
{
    "output": {
        "voice_list": [
            {
                "gmt_create": "2024-12-11 13:38:02",
                "voice_id": "yourVoiceId",
                "gmt_modified": "2024-12-11 13:38:02",
                "status": "OK"
            }
        ]
    },
    "usage": {
        "count": 1
    },
    "request_id": "yourRequestId"
}
```

| **参数** | **类型** | **说明** |
| --- | --- | --- |
| voice\\_id | string | 音色ID。 |
| gmt\\_create | string | 创建音色的时间。 |
| gmt\\_modified | string | 修改音色的时间。 |
| status | string | 音色状态： - DEPLOYING： 审核中 - OK：审核通过，可调用 - UNDEPLOYED：审核不通过，不可调用 |

### **查询指定音色**

获取特定音色的详细信息

## Python SDK

#### **接口说明**

```
def query_voice(self, voice_id: str) -> List[str]:
    '''
    查询指定音色的详细信息
    param: voice_id 需要查询的音色ID
    return: List[str] 音色详细信息，包含状态、创建时间、音频链接等
    '''
```

#### **请求示例**

```
from dashscope.audio.tts_v2 import VoiceEnrollmentService

service = VoiceEnrollmentService()
voice_id = 'cosyvoice-v3-plus-myvoice-xxxxxxxx'

voice_details = service.query_voice(voice_id=voice_id)

print(f"Request ID: {service.get_last_request_id()}")
print(f"Voice Details: {voice_details}")
```

#### **响应示例**

```
{
    "gmt_create": "2024-09-13 11:29:41",
    "resource_link": "https://yourAudioFileUrl",
    "target_model": "cosyvoice-v3-plus",
    "gmt_modified": "2024-09-13 11:29:41",
    "status": "OK"
}
```

#### **响应参数**

| **参数** | **类型** | **说明** |
| --- | --- | --- |
| resource\\_link | string | 被复刻的音频的URL。 |
| target\\_model | string | 驱动音色的语音合成模型，推荐 cosyvoice-v3-flash 或 cosyvoice-v3-plus。 必须与后续调用语音合成接口时使用的语音合成模型一致，否则合成会失败。 |
| gmt\\_create | string | 创建音色的时间。 |
| gmt\\_modified | string | 修改音色的时间。 |
| status | string | 音色状态： - DEPLOYING： 审核中 - OK：审核通过，可调用 - UNDEPLOYED：审核不通过，不可调用 |

## Java SDK

#### **接口说明**

```
/**
 * 查询指定音色的详细信息
 *
 * @param voiceId 需要查询的音色ID
 * @return Voice 音色详细信息，包含状态、创建时间、音频链接等
 * @throws NoApiKeyException 如果apikey为空
 * @throws InputRequiredException 如果必须参数为空
 */
public Voice queryVoice(String voiceId) throws NoApiKeyException, InputRequiredException
```

#### **请求示例**

需要引入第三方库`com.google.gson.Gson`。

```
import com.alibaba.dashscope.audio.ttsv2.enrollment.Voice;
import com.alibaba.dashscope.audio.ttsv2.enrollment.VoiceEnrollmentService;
import com.alibaba.dashscope.exception.InputRequiredException;
import com.alibaba.dashscope.exception.NoApiKeyException;
import com.google.gson.Gson;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class Main {
    public static String apiKey = System.getenv("DASHSCOPE_API_KEY");  // 如果您没有配置环境变量，请在此处用您的API-KEY进行替换
    private static String voiceId = "cosyvoice-v3-plus-myvoice-xxx"; // 请按实际情况进行替换
    private static final Logger logger = LoggerFactory.getLogger(Main.class);

    public static void main(String[] args)
            throws NoApiKeyException, InputRequiredException {
        VoiceEnrollmentService service = new VoiceEnrollmentService(apiKey);
        Voice voice = service.queryVoice(voiceId);
        
        logger.info("Query successful. Request ID: {}", service.getLastRequestId());
        logger.info("Voice Details: {}", new Gson().toJson(voice));
    }
}
```

### **响应示例**

```
{
    "gmt_create": "2024-09-13 11:29:41",
    "resource_link": "https://yourAudioFileUrl",
    "target_model": "cosyvoice-v3-plus",
    "gmt_modified": "2024-09-13 11:29:41",
    "status": "OK"
}
```

### **响应参数**

| **参数** | **类型** | **说明** |
| --- | --- | --- |
| resource\\_link | string | 被复刻的音频的URL。 |
| target\\_model | string | 驱动音色的语音合成模型，推荐 cosyvoice-v3-flash 或 cosyvoice-v3-plus。 必须与后续调用语音合成接口时使用的语音合成模型一致，否则合成会失败。 |
| gmt\\_create | string | 创建音色的时间。 |
| gmt\\_modified | string | 修改音色的时间。 |
| status | string | 音色状态： - DEPLOYING： 审核中 - OK：审核通过，可调用 - UNDEPLOYED：审核不通过，不可调用 |

## RESTful API

#### **基本信息**

| URL | 中国内地： ``` https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization ``` 国际： ``` https://dashscope-intl.aliyuncs.com/api/v1/services/audio/tts/customization ``` |
| --- | --- |
| 请求方法 | POST |
| 请求头 | ``` Authorization: Bearer {api-key} // 需替换为您自己的API Key Content-Type: application/json ``` |
| 消息体 | 包含所有请求参数的消息体如下，对于可选字段，在实际业务中可根据需求省略： **重要** `model`为声音复刻模型，固定为`voice-enrollment`。 ``` { "model": "voice-enrollment", "input": { "action": "query_voice", "voice_id": "yourVoiceId" } } ``` |

#### **请求参数**

**点击查看请求示例**

**重要**

`model`为声音复刻模型，固定为`voice-enrollment`。

```
curl -X POST https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization \
-H "Authorization: Bearer $DASHSCOPE_API_KEY" \
-H "Content-Type: application/json" \
-d '{
    "model": "voice-enrollment",
    "input": {
        "action": "query_voice",
        "voice_id": "yourVoiceId"
    }
}'
```

| **参数** | **类型** | **默认值** | **是否必须** | **说明** |
| --- | --- | --- | --- | --- |
| model | string | \\- | 是   | 声音复刻模型，固定为`voice-enrollment`。 |
| action | string | \\- | 是   | 操作类型，固定为`query_voice`。 |
| voice\\_id | string | \\- | 是   | 需要查询的音色ID。 |

#### **响应参数**

**点击查看响应示例**

```
{
    "output": {
        "gmt_create": "2024-12-11 13:38:02",
        "resource_link": "https://yourAudioFileUrl",
        "target_model": "cosyvoice-v3-plus",
        "gmt_modified": "2024-12-11 13:38:02",
        "status": "OK"
    },
    "usage": {
        "count": 1
    },
    "request_id": "2450f969-d9ea-9483-bafc-************"
}
```

| **参数** | **类型** | **说明** |
| --- | --- | --- |
| resource\\_link | string | 被复刻的音频的URL。 |
| target\\_model | string | 驱动音色的语音合成模型，推荐 cosyvoice-v3-flash 或 cosyvoice-v3-plus。 必须与后续调用语音合成接口时使用的语音合成模型一致，否则合成会失败。 |
| gmt\\_create | string | 创建音色的时间。 |
| gmt\\_modified | string | 修改音色的时间。 |
| status | string | 音色状态： - DEPLOYING： 审核中 - OK：审核通过，可调用 - UNDEPLOYED：审核不通过，不可调用 |

### **更新音色**

使用新的音频文件更新一个已存在的音色。

## Python SDK

#### **接口说明**

```
def update_voice(self, voice_id: str, url: str) -> None:
    '''
    更新音色
    param: voice_id 音色id
    param: url 用于声音复刻的音频文件url
    '''
```

#### **请求示例**

```
from dashscope.audio.tts_v2 import VoiceEnrollmentService

service = VoiceEnrollmentService()
service.update_voice(
    voice_id='cosyvoice-v3-plus-myvoice-xxxxxxxx',
    url='https://your-new-audio-file-url'
)
print(f"Update submitted. Request ID: {service.get_last_request_id()}")
```

## Java SDK

#### **接口说明**

```
/**
 * 更新音色
 *
 * @param voiceId 需要更新的音色
 * @param url 用于声音复刻的音频文件url
 * @throws NoApiKeyException 如果apikey为空
 * @throws InputRequiredException 如果必须参数为空
 */
public void updateVoice(String voiceId, String url)
    throws NoApiKeyException, InputRequiredException
```

#### **请求示例**

```
import com.alibaba.dashscope.audio.ttsv2.enrollment.VoiceEnrollmentService;
import com.alibaba.dashscope.exception.InputRequiredException;
import com.alibaba.dashscope.exception.NoApiKeyException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class Main {
    public static String apiKey = System.getenv("DASHSCOPE_API_KEY");  // 如果您没有配置环境变量，请在此处用您的API-KEY进行替换
    private static String fileUrl = "https://your-audio-file-url";  // 请按实际情况进行替换
    private static String voiceId = "cosyvoice-v3-plus-myvoice-xxx"; // 请按实际情况进行替换
    private static final Logger logger = LoggerFactory.getLogger(Main.class);
    
    public static void main(String[] args)
            throws NoApiKeyException, InputRequiredException {
        VoiceEnrollmentService service = new VoiceEnrollmentService(apiKey);
        // 更新音色
        service.updateVoice(voiceId, fileUrl);
        logger.info("Update submitted. Request ID: {}", service.getLastRequestId());
    }
}
```

## RESTful API

#### **基本信息**

| URL | 中国内地： ``` https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization ``` 国际： ``` https://dashscope-intl.aliyuncs.com/api/v1/services/audio/tts/customization ``` |
| --- | --- |
| 请求方法 | POST |
| 请求头 | ``` Authorization: Bearer {api-key} // 需替换为您自己的API Key Content-Type: application/json ``` |
| 消息体 | 包含所有请求参数的消息体如下，对于可选字段，在实际业务中可根据需求省略： **重要** `model`为声音复刻模型，固定为`voice-enrollment`。 ``` { "model": "voice-enrollment", "input": { "action": "update_voice", "voice_id": "yourVoiceId", "url": "https://yourAudioFileUrl" } } ``` |

#### **请求参数**

**点击查看请求示例**

**重要**

`model`为声音复刻模型，固定为`voice-enrollment`。

```
curl -X POST https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization \
-H "Authorization: Bearer $DASHSCOPE_API_KEY" \
-H "Content-Type: application/json" \
-d '{
    "model": "voice-enrollment",
    "input": {
        "action": "update_voice",
        "voice_id": "yourVoiceId",
        "url": "https://yourAudioFileUrl"
    }
}'
```

| **参数** | **类型** | **默认值** | **是否必须** | **说明** |
| --- | --- | --- | --- | --- |
| model | string | \\- | 是   | 声音复刻模型，固定为`voice-enrollment`。 |
| action | string | \\- | 是   | 操作类型，固定为`update_voice`。 |
| voice\\_id | string | \\- | 是   | 待更新的音色ID。 |
| url | string | \\- | 是   | 用于更新音色的音频文件URL。该URL要求公网可访问。 如何录制音频请参见[录音操作指南](https://help.aliyun.com/zh/model-studio/recording-guide)。 |

**点击查看响应示例**

```
{
    "output": {},
    "usage": {
        "count": 1
    },
    "request_id": "yourRequestId"
}
```

### **删除音色**

删除一个不再需要的音色以释放配额。此操作不可逆。

## Python SDK

#### **接口说明**

```
def delete_voice(self, voice_id: str) -> None:
    '''
    删除音色
    param: voice_id 需要删除的音色
    '''
```

#### **请求示例**

```
from dashscope.audio.tts_v2 import VoiceEnrollmentService

service = VoiceEnrollmentService()
service.delete_voice(voice_id='cosyvoice-v3-plus-myvoice-xxxxxxxx')
print(f"Deletion submitted. Request ID: {service.get_last_request_id()}")
```

## Java SDK

#### **接口说明**

```
/**
 * 删除音色
 *
 * @param voiceId 需要删除的音色
 * @throws NoApiKeyException 如果apikey为空
 * @throws InputRequiredException 如果必须参数为空
 */
public void deleteVoice(String voiceId) throws NoApiKeyException, InputRequiredException 
```

#### **请求示例**

```
import com.alibaba.dashscope.audio.ttsv2.enrollment.VoiceEnrollmentService;
import com.alibaba.dashscope.exception.InputRequiredException;
import com.alibaba.dashscope.exception.NoApiKeyException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class Main {
    public static String apiKey = System.getenv("DASHSCOPE_API_KEY");  // 如果您没有配置环境变量，请在此处用您的API-KEY进行替换
    private static String voiceId = "cosyvoice-v3-plus-myvoice-xxx"; // 请按实际情况进行替换
    private static final Logger logger = LoggerFactory.getLogger(Main.class);
    
    public static void main(String[] args)
            throws NoApiKeyException, InputRequiredException {
        VoiceEnrollmentService service = new VoiceEnrollmentService(apiKey);
        // 删除音色
        service.deleteVoice(voiceId);
        logger.info("Deletion submitted. Request ID: {}", service.getLastRequestId());
    }
}
```

## RESTful API

#### **基本信息**

| URL | 中国内地： ``` https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization ``` 国际： ``` https://dashscope-intl.aliyuncs.com/api/v1/services/audio/tts/customization ``` |
| --- | --- |
| 请求方法 | POST |
| 请求头 | ``` Authorization: Bearer {api-key} // 需替换为您自己的API Key Content-Type: application/json ``` |
| 消息体 | 包含所有请求参数的消息体如下，对于可选字段，在实际业务中可根据需求省略： **重要** `model`为声音复刻模型，固定为`voice-enrollment`。 ``` { "model": "voice-enrollment", "input": { "action": "delete_voice", "voice_id": "yourVoiceId" } } ``` |

#### **请求参数**

**点击查看请求示例**

**重要**

`model`为声音复刻模型，固定为`voice-enrollment`。

```
curl -X POST https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization \
-H "Authorization: Bearer $DASHSCOPE_API_KEY" \
-H "Content-Type: application/json" \
-d '{
    "model": "voice-enrollment",
    "input": {
        "action": "delete_voice",
        "voice_id": "yourVoiceId"
    }
}'
```

| **参数** | **类型** | **默认值** | **是否必须** | **说明** |
| --- | --- | --- | --- | --- |
| model | string | \\- | 是   | 声音复刻模型，固定为`voice-enrollment`。 |
| action | string | \\- | 是   | 操作类型，固定为`delete_voice`。 |
| voice\\_id | string | \\- | 是   | 待删除的音色ID。 |

**点击查看响应示例**

```
{
    "output": {},
    "usage": {
        "count": 1
    },
    "request_id": "yourRequestId"
}
```

## **音色配额与自动清理规则**

-   **总数限制**：1000个音色/账号
    
    > 当前接口不提供音色数量查询功能，可通过调用[查询音色列表](#401d33226330i)接口自行统计音色数目
    
-   **自动清理**：若单个音色在过去一年内未被用于任何语音合成请求，系统将自动将其删除
    

## **计费说明**

-   声音复刻：创建、查询、更新、删除音色免费
    
-   使用复刻生成的专属音色进行语音合成：按量（文本字符数）计费，参见[实时语音合成-CosyVoice/Sambert](https://help.aliyun.com/zh/model-studio/text-to-speech#992f46b0f4ha2)
    

## **版权与合法性**

您需对所提供声音的所有权及合法使用权负责，请注意阅读[服务协议](https://terms.alicdn.com/legal-agreement/terms/b_platform_service_agreement/20240229113512917/20240229113512917.html)。

## **错误码**

如遇报错问题，请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)进行排查。

## **常见问题**

### **功能特性**

#### **Q：如何**调节自定义音色的语速、音量**？**

与使用预置音色完全相同。在调用语音合成API时，传入相应的参数即可，例如 `speech_rate` (Python) / `speechRate` (Java) 用于调节语速，`volume` 用于调节音量。详情请参见语音合成API文档（[Java SDK](https://help.aliyun.com/zh/model-studio/cosyvoice-java-sdk)/[Python SDK](https://help.aliyun.com/zh/model-studio/cosyvoice-python-sdk)/[WebSocket API](https://help.aliyun.com/zh/model-studio/cosyvoice-websocket-api)）

#### **Q：除了Java和Python，其他语言（如Go, C#, Node.js）如何调用？**

对于音色管理，请直接使用文档中提供的RESTful API。对于语音合成，请使用[WebSocket API](https://help.aliyun.com/zh/model-studio/cosyvoice-websocket-api)，并将复刻得到的 `voice_id` 作为 `voice` 参数传入。

### **故障排查**

如遇代码报错问题，请根据[错误码](#fe96688bd1l3n)中的信息进行排查。

#### **Q：使用复刻音色合成时音频中出现额外内容如何处理？**

若使用复刻音色合成音频时，发现输出的音频中包含输入文本以外的额外字符或杂音，请按以下步骤排查：

1.  **检查源音频质量**
    
    复刻音频质量直接影响合成效果。确保源音频满足以下要求：
    
    -   无背景噪音和杂音
        
    -   音质清晰（建议采样率≥16kHz）
        
    -   音频格式：WAV格式优于MP3（避免有损压缩）
        
    -   单声道（立体声可能引入干扰）
        
    -   无静音段或过长停顿
        
    -   语速适中（过快的语速影响特征提取）
        
2.  **检查输入文本**
    
    确认输入文本中不包含特殊符号或标记：
    
    -   避免使用 `**`、`""`、`''` 等特殊符号
        
    -   若非用于LaTeX公式包裹，建议预处理过滤特殊符号
        
3.  **验证音色复刻参数**
    
    确保[创建音色](#1eaa57d82did9)时，语言参数（`language_hints`/`languageHints`）设置正确
    
4.  **尝试重新复刻**
    
    使用质量更高的源音频重新进行复刻，并测试合成效果。
    
5.  **对比系统音色**
    
    使用系统预置音色测试相同文本，确认是否为复刻音色特定问题。
    

#### **Q：使用复刻音色生成的音频无声音如何排查**？

1.  **确认音色状态**
    
    调用[查询指定音色](#e1d4d6ee81482)接口，查看音色`status`是否为`OK`。
    
2.  **检查模型版本一致性**
    
    确保复刻音色时使用的`target_model`参数与语音合成时的`model`参数完全一致。例如：
    
    -   复刻时使用`cosyvoice-v3-plus`
        
    -   合成时也必须使用`cosyvoice-v3-plus`
        
3.  **验证源音频质量**
    
    检查复刻音色时使用的源音频是否符合[音频要求](#音频要求与最佳实践)：
    
    -   音频时长：10-20秒
        
    -   音质清晰
        
    -   无背景噪音
        
4.  **检查请求参数**
    
    确认语音合成时请求参数`voice`设置为复刻音色的ID。
    

#### **Q：声音复刻后合成效果不稳定或语音不完整如何处理？**

如果复刻音色后合成的语音出现以下问题：

-   语音播放不完整，只读出部分文字
    
-   合成效果不稳定，时好时坏
    
-   语音中包含异常停顿或静音段
    

可能原因：源音频质量不符合要求

解决方案：检查源音频是否符合如下要求，建议按照[录音操作指南](https://help.aliyun.com/zh/model-studio/recording-guide)重新录制

-   检查音频连续性：确保源音频中语音内容连续，避免长时间停顿或静音段（超过2秒）。如果音频中存在明显的空白段，会导致模型将静音或噪声作为音色特征的一部分，影响生成效果
    
-   检查语音活动比例：确保有效语音占音频总时长的60%以上。如果背景噪声、非语音段过多，会干扰音色特征提取
    
-   验证音频质量细节：
    
    -   音频时长：10-20秒（推荐15秒左右）
        
    -   发音清晰，语速平稳
        
    -   无背景噪音、回音、杂音
        
    -   语音能量集中，无长时间静音段
        

#### **Q：**为什么找不到 VoiceEnrollmentService 类？

SDK版本过低。请[安装最新版SDK](https://help.aliyun.com/zh/model-studio/install-sdk)。

#### **Q：**声音复刻效果不佳，有杂音或不清晰怎么办**？**

这通常是由于输入音频质量不高导致的。请严格遵循[录音操作指南](https://help.aliyun.com/zh/model-studio/recording-guide)重新录制并上传音频。

#### **Q：**为什么使用复刻音色合成很短的文本（例如单个词语）时，前面会出现较长的静音或音频整体时长异常？

声音复刻模型会学习样本音频中的停顿与节奏，如果原始录音中包含较长的起始静音或停顿，合成结果也可能保留类似模式。对于单字或极短文本，这种静音比例会被放大，看起来像“音频很长但几乎都是静音”。建议在录制样本音频时避免长时间静音，合成时尽量使用完整句子或较长文本；如必须对单个词语进行合成，可在前后补充少量上下文或使用同音替换词以规避极端情况。

### **权限与认证**

#### **Q：使用子业务空间的API Key是否可以进行声音复刻？**

需要为API Key对应的子业务空间进行[模型授权](https://help.aliyun.com/zh/model-studio/model-authentication-instructions)后方才支持，详情请参见[子业务空间的模型调用](https://help.aliyun.com/zh/model-studio/model-calling-in-sub-workspace)。

本文介绍语音合成CosyVoice Python SDK的参数和接口细节。

**用户指南：**关于模型介绍和选型建议请参见[实时语音合成-CosyVoice/Sambert](https://help.aliyun.com/zh/model-studio/text-to-speech)。

## **前提条件**

-   已开通服务并[获取API Key](https://help.aliyun.com/zh/model-studio/get-api-key)。请[配置API Key到环境变量](https://help.aliyun.com/zh/model-studio/configure-api-key-through-environment-variables)，而非硬编码在代码中，防范因代码泄露导致的安全风险。
    
    **说明**
    
    当您需要为第三方应用或用户提供临时访问权限，或者希望严格控制敏感数据访问、删除等高风险操作时，建议使用[临时鉴权Token](https://help.aliyun.com/zh/model-studio/generate-temporary-api-key)。
    
    与长期有效的 API Key 相比，临时鉴权 Token 具备时效性短（60秒）、安全性高的特点，适用于临时调用场景，能有效降低API Key泄露的风险。
    
    使用方式：在代码中，将原本用于鉴权的 API Key 替换为获取到的临时鉴权 Token 即可。
    
-   [安装最新版DashScope SDK](https://help.aliyun.com/zh/model-studio/install-sdk)。
    

## **模型与价格**

参见[实时语音合成-CosyVoice/Sambert](https://help.aliyun.com/zh/model-studio/text-to-speech)

## **语音合成文本限制与格式规范**

### **文本长度限制**

-   [非流式调用](#8341058094tc3)或[单向流式调用](#cc2a504f344s2)：单次发送文本长度不得超过 20000 字符。
    
-   [双向流式调用](#ba023aacfbr84)：单次发送文本长度不得超过 20000 字符，且累计发送文本总长度不得超过 20 万字符。
    

### **字符计算规则**

-   汉字（包括简/繁体汉字、日文汉字和韩文汉字）按2个字符计算，其他所有字符（如标点符号、字母、数字、日韩文假名/谚文等）均按 1个字符计算
    
-   计算文本长度时，不包含SSML 标签内容
    
-   示例：
    
    -   `"你好"` → 2(你)+2(好)=4字符
        
    -   `"中A文123"` → 2(中)+1(A)+2(文)+1(1)+1(2)+1(3)=8字符
        
    -   `"中文。"` → 2(中)+2(文)+1(。)=5字符
        
    -   `"中 文。"` → 2(中)+1(空格)+2(文)+1(。)=6字符
        
    -   `"<speak>你好</speak>"` → 2(你)+2(好)=4字符
        

### **编码格式**

需采用UTF-8编码。

### **数学表达式支持说明**

当前数学表达式解析功能仅适用于`cosyvoice-v2`、`cosyvoice-v3-flash`和`cosyvoice-v3-plus`模型，支持识别中小学常见的数学表达式，包括但不限于基础运算、代数、几何等内容。

详情请参见[LaTeX 公式转语音](https://help.aliyun.com/zh/model-studio/latex-capability-support-description)。

### [SSML](https://help.aliyun.com/zh/model-studio/introduction-to-cosyvoice-ssml-markup-language)**标记语言支持说明**

当前SSML（Speech Synthesis Markup Language，语音合成标记语言）功能仅适用于cosyvoice-v3-flash、cosyvoice-v3-plus和cosyvoice-v2模型的复刻音色，以及[音色列表](https://help.aliyun.com/zh/model-studio/cosyvoice-voice-list)中标记为支持的系统音色，使用时需满足以下条件：

-   使用[DashScope SDK](https://help.aliyun.com/zh/model-studio/install-sdk) 1.23.4 或更高版本
    
-   仅支持[非流式调用](#8341058094tc3)和[单向流式调用](#cc2a504f344s2)（即[SpeechSynthesizer类](#d6bc1f133f871)的`call`方法），不支持[双向流式调用](#ba023aacfbr84)（即[SpeechSynthesizer类](#d6bc1f133f871)的`streaming_call`方法）
    
-   使用方法与普通语音合成一致：将包含SSML的文本传入[SpeechSynthesizer类](#d6bc1f133f871)的`call`方法即可
    

## **快速开始**

[SpeechSynthesizer类](#d6bc1f133f871)提供了语音合成的关键接口，支持以下几种调用方式：

-   非流式调用：阻塞式，一次性发送完整文本，直接返回完整音频。适合短文本语音合成场景。
    
-   单向流式调用：非阻塞式，一次性发送完整文本，通过回调函数接收音频数据（可能分片）。适用于对实时性要求高的短文本语音合成场景。
    
-   双向流式调用：非阻塞式，可分多次发送文本片段，通过回调函数实时接收增量合成的音频流。适合实时性要求高的长文本语音合成场景。
    

### **非流式调用**

提交单个语音合成任务，无需调用回调函数，进行语音合成（无流式输出中间结果），最终一次性获取完整结果。

![image](https://help-static-aliyun-doc.aliyuncs.com/assets/img/zh-CN/8971370771/CAEQURiBgMDRr9T4phkiIGNmYzBiZjFkZjQ4MDQzZGU4NDIyZDU2NWJjYjkyZTQ04709861_20241015153444.149.svg)

实例化[SpeechSynthesizer类](#d6bc1f133f871)绑定[请求参数](#2fe363ace1l4k)，调用`call`方法进行合成并获取二进制音频数据。

发送的文本长度不得超过20000字符（详情请参见[SpeechSynthesizer类](#d6bc1f133f871)的`call`方法）。

**重要**

每次调用`call`方法前，需要重新初始化`SpeechSynthesizer`实例。

点击查看完整示例

```
# coding=utf-8

import dashscope
from dashscope.audio.tts_v2 import *
import os

# 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
# 若没有配置环境变量，请用百炼API Key将下行替换为：dashscope.api_key = "<API_KEY>"
dashscope.api_key = os.environ.get('DASHSCOPE_API_KEY')

# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference
dashscope.base_websocket_api_url='wss://dashscope.aliyuncs.com/api-ws/v1/inference'

# 模型
model = "cosyvoice-v3-flash"
# 音色
voice = "longanyang"

# 实例化SpeechSynthesizer，并在构造方法中传入模型（model）、音色（voice）等请求参数
synthesizer = SpeechSynthesizer(model=model, voice=voice)
# 发送待合成文本，获取二进制音频
audio = synthesizer.call("今天天气怎么样？")
# 首次发送文本时需建立 WebSocket 连接，因此首包延迟会包含连接建立的耗时
print('[Metric] requestId为：{}，首包延迟为：{}毫秒'.format(
    synthesizer.get_last_request_id(),
    synthesizer.get_first_package_delay()))

# 将音频保存至本地
with open('output.mp3', 'wb') as f:
    f.write(audio)
```

### **单向流式调用**

提交单个语音合成任务，通过回调的方式流式输出中间结果，合成结果通过`ResultCallback`中的回调函数流式获取。

![image](https://help-static-aliyun-doc.aliyuncs.com/assets/img/zh-CN/9971370771/CAEQVRiBgIDv9fShrBkiIDhmNTk5YmQ1ZDgwNzRjZjRiN2VlMTU5YzI1ZGMwMTlm4709861_20241015153444.149.svg)

实例化[SpeechSynthesizer类](#d6bc1f133f871)绑定[请求参数](#2fe363ace1l4k)和[回调接口（ResultCallback）](#85d698b9f9g8s)，调用`call`方法进行合成并通过[回调接口（ResultCallback）](#85d698b9f9g8s)的`on_data`方法实时获取合成结果。

发送的文本长度不得超过20000字符（详情请参见[SpeechSynthesizer类](#d6bc1f133f871)的`call`方法）。

**重要**

每次调用`call`方法前，需要重新初始化`SpeechSynthesizer`实例。

点击查看完整示例

```
# coding=utf-8

import os
import dashscope
from dashscope.audio.tts_v2 import *

from datetime import datetime

def get_timestamp():
    now = datetime.now()
    formatted_timestamp = now.strftime("[%Y-%m-%d %H:%M:%S.%f]")
    return formatted_timestamp

# 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
# 若没有配置环境变量，请用百炼API Key将下行替换为：dashscope.api_key = "<API_KEY>"
dashscope.api_key = os.environ.get('DASHSCOPE_API_KEY')

# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference
dashscope.base_websocket_api_url='wss://dashscope.aliyuncs.com/api-ws/v1/inference'

# 模型
model = "cosyvoice-v3-flash"
# 音色
voice = "longanyang"


# 定义回调接口
class Callback(ResultCallback):
    _player = None
    _stream = None

    def on_open(self):
        self.file = open("output.mp3", "wb")
        print("连接建立：" + get_timestamp())

    def on_complete(self):
        print("语音合成完成，所有合成结果已被接收：" + get_timestamp())
        # 当任务完成（on_complete 回调触发）后，才可调用 get_first_package_delay 获取延迟
        # 首次发送文本时需建立 WebSocket 连接，因此首包延迟会包含连接建立的耗时
        print('[Metric] requestId为：{}，首包延迟为：{}毫秒'.format(
            synthesizer.get_last_request_id(),
            synthesizer.get_first_package_delay()))

    def on_error(self, message: str):
        print(f"语音合成出现异常：{message}")

    def on_close(self):
        print("连接关闭：" + get_timestamp())
        self.file.close()

    def on_event(self, message):
        pass

    def on_data(self, data: bytes) -> None:
        print(get_timestamp() + " 二进制音频长度为：" + str(len(data)))
        self.file.write(data)


callback = Callback()

# 实例化SpeechSynthesizer，并在构造方法中传入模型（model）、音色（voice）等请求参数
synthesizer = SpeechSynthesizer(
    model=model,
    voice=voice,
    callback=callback,
)

# 发送待合成文本，在回调接口的on_data方法中实时获取二进制音频
synthesizer.call("今天天气怎么样？")
```

### **双向流式调用**

在同一个语音合成任务中分多次提交文本，并通过回调的方式实时获取合成结果。

**说明**

-   流式输入时可多次调用`streaming_call`按顺序提交文本片段。服务端接收文本片段后自动进行分句：
    
    -   完整语句立即合成
        
    -   不完整语句缓存至完整后合成
        
    
    调用 `streaming_complete` 时，服务端会强制合成所有已接收但未处理的文本片段（包括未完成的句子）。
    
-   发送文本片段的间隔不得超过23秒，否则触发“request timeout after 23 seconds”异常。
    
    若无待发送文本，需及时调用 `streaming_complete`结束任务。
    
    > 服务端强制设定23秒超时机制，客户端无法修改该配置。
    

![image](https://help-static-aliyun-doc.aliyuncs.com/assets/img/zh-CN/9971370771/CAEQVRiBgMDb7PahrBkiIDVkNjEwOTMxYjEwOTRmOWFhMmI1OTRiY2Q3ZDgzZmE54709861_20241015153444.149.svg)

1.  实例化SpeechSynthesizer类
    
    实例化[SpeechSynthesizer类](#d6bc1f133f871)绑定[请求参数](#2fe363ace1l4k)和[回调接口（ResultCallback）](#85d698b9f9g8s)。
    
2.  流式传输
    
    多次调用[SpeechSynthesizer类](#d6bc1f133f871)的`streaming_call`方法分片提交待合成文本，将待合成文本分段发送至服务端。
    
    在发送文本的过程中，服务端会通过[回调接口（ResultCallback）](#85d698b9f9g8s)的`on_data`方法，将合成结果实时返回给客户端。
    
    每次调用`streaming_call`方法发送的文本片段（即`text`）长度不得超过20000字符，累计发送的文本总长度不得超过20万字符。
    
3.  结束处理
    
    调用[SpeechSynthesizer类](#d6bc1f133f871)的`streaming_complete`方法结束语音合成。
    
    该方法会阻塞当前线程，直到[回调接口（ResultCallback）](#85d698b9f9g8s)的`on_complete`或者`on_error`回调触发后才会释放线程阻塞。
    
    请务必确保调用该方法，否则可能会导致结尾部分的文本无法成功转换为语音。
    

点击查看完整示例

```
# coding=utf-8
#
# pyaudio安装说明：
# 如果是macOS操作系统，执行如下命令：
#   brew install portaudio
#   pip install pyaudio
# 如果是Debian/Ubuntu操作系统，执行如下命令：
#   sudo apt-get install python-pyaudio python3-pyaudio
#   或者
#   pip install pyaudio
# 如果是CentOS操作系统，执行如下命令：
#   sudo yum install -y portaudio portaudio-devel && pip install pyaudio
# 如果是Microsoft Windows，执行如下命令：
#   python -m pip install pyaudio

import os
import time
import pyaudio
import dashscope
from dashscope.api_entities.dashscope_response import SpeechSynthesisResponse
from dashscope.audio.tts_v2 import *

from datetime import datetime

def get_timestamp():
    now = datetime.now()
    formatted_timestamp = now.strftime("[%Y-%m-%d %H:%M:%S.%f]")
    return formatted_timestamp

# 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
# 若没有配置环境变量，请用百炼API Key将下行替换为：dashscope.api_key = "<API_KEY>"
dashscope.api_key = os.environ.get('DASHSCOPE_API_KEY')

# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference
dashscope.base_websocket_api_url='wss://dashscope.aliyuncs.com/api-ws/v1/inference'

# 模型
model = "cosyvoice-v3-flash"
# 音色
voice = "longanyang"


# 定义回调接口
class Callback(ResultCallback):
    _player = None
    _stream = None

    def on_open(self):
        print("连接建立：" + get_timestamp())
        self._player = pyaudio.PyAudio()
        self._stream = self._player.open(
            format=pyaudio.paInt16, channels=1, rate=22050, output=True
        )

    def on_complete(self):
        print("语音合成完成，所有合成结果已被接收：" + get_timestamp())

    def on_error(self, message: str):
        print(f"语音合成出现异常：{message}")

    def on_close(self):
        print("连接关闭：" + get_timestamp())
        # 停止播放器
        self._stream.stop_stream()
        self._stream.close()
        self._player.terminate()

    def on_event(self, message):
        pass

    def on_data(self, data: bytes) -> None:
        print(get_timestamp() + " 二进制音频长度为：" + str(len(data)))
        self._stream.write(data)


callback = Callback()

test_text = [
    "流式文本语音合成SDK，",
    "可以将输入的文本",
    "合成为语音二进制数据，",
    "相比于非流式语音合成，",
    "流式合成的优势在于实时性",
    "更强。用户在输入文本的同时",
    "可以听到接近同步的语音输出，",
    "极大地提升了交互体验，",
    "减少了用户等待时间。",
    "适用于调用大规模",
    "语言模型（LLM），以",
    "流式输入文本的方式",
    "进行语音合成的场景。",
]

# 实例化SpeechSynthesizer，并在构造方法中传入模型（model）、音色（voice）等请求参数
synthesizer = SpeechSynthesizer(
    model=model,
    voice=voice,
    format=AudioFormat.PCM_22050HZ_MONO_16BIT,  
    callback=callback,
)


# 流式发送待合成文本。在回调接口的on_data方法中实时获取二进制音频
for text in test_text:
    synthesizer.streaming_call(text)
    time.sleep(0.1)
# 结束流式语音合成
synthesizer.streaming_complete()

# 首次发送文本时需建立 WebSocket 连接，因此首包延迟会包含连接建立的耗时
print('[Metric] requestId为：{}，首包延迟为：{}毫秒'.format(
    synthesizer.get_last_request_id(),
    synthesizer.get_first_package_delay()))
```

## **请求参数**

请求参数通过[SpeechSynthesizer类](#d6bc1f133f871)的构造方法进行设置。

| **参数** | **类型** | **是否必须** | **说明** |
| --- | --- | --- | --- |
| model | str | 是   | 语音合成[模型](https://help.aliyun.com/zh/model-studio/models#7a960cc042zwt)。 不同模型版本需要使用对应版本的音色： - cosyvoice-v3-flash/cosyvoice-v3-plus：使用longanyang等音色。 - cosyvoice-v2：使用longxiaochun\\_v2等音色。 - cosyvoice-v1：使用longwan等音色。 - 完整音色列表请参见[音色列表](https://help.aliyun.com/zh/model-studio/cosyvoice-voice-list)。 |
| voice | str | 是   | 语音合成所使用的音色。 支持系统音色和复刻音色： - **系统音色**：参见[音色列表](https://help.aliyun.com/zh/model-studio/cosyvoice-voice-list)。 - **复刻音色**：通过[声音复刻](https://help.aliyun.com/zh/model-studio/voice-replica-1/)功能定制。使用复刻音色时，请确保声音复刻与语音合成使用同一账号。详细操作步骤请参见[CosyVoice声音复刻API](https://help.aliyun.com/zh/model-studio/cosyvoice-clone-api#da30eeebc4uwk)。 使用声音复刻生成的复刻音色时，本请求的`model`参数值，必须与创建该音色时所用的模型版本（即`target_model`参数）完全一致。 |
| format | enum | 否   | 指定音频编码格式及采样率。 若未指定`format`，则合成音频采样率为22.05kHz，格式为mp3。 **说明** 默认采样率代表当前音色的最佳采样率，缺省条件下默认按照该采样率输出，同时支持降采样或升采样。 可指定的音频编码格式及采样率如下： - 所有模型均支持的音频编码格式及采样率： - AudioFormat.WAV\\_8000HZ\\_MONO\\_16BIT，代表音频格式为wav，采样率为8kHz - AudioFormat.WAV\\_16000HZ\\_MONO\\_16BIT，代表音频格式为wav，采样率为16kHz - AudioFormat.WAV\\_22050HZ\\_MONO\\_16BIT，代表音频格式为wav，采样率为22.05kHz - AudioFormat.WAV\\_24000HZ\\_MONO\\_16BIT，代表音频格式为wav，采样率为24kHz - AudioFormat.WAV\\_44100HZ\\_MONO\\_16BIT，代表音频格式为wav，采样率为44.1kHz - AudioFormat.WAV\\_48000HZ\\_MONO\\_16BIT，代表音频格式为wav，采样率为48kHz - AudioFormat.MP3\\_8000HZ\\_MONO\\_128KBPS，代表音频格式为mp3，采样率为8kHz - AudioFormat.MP3\\_16000HZ\\_MONO\\_128KBPS，代表音频格式为mp3，采样率为16kHz - AudioFormat.MP3\\_22050HZ\\_MONO\\_256KBPS，代表音频格式为mp3，采样率为22.05kHz - AudioFormat.MP3\\_24000HZ\\_MONO\\_256KBPS，代表音频格式为mp3，采样率为24kHz - AudioFormat.MP3\\_44100HZ\\_MONO\\_256KBPS，代表音频格式为mp3，采样率为44.1kHz - AudioFormat.MP3\\_48000HZ\\_MONO\\_256KBPS，代表音频格式为mp3，采样率为48kHz - AudioFormat.PCM\\_8000HZ\\_MONO\\_16BIT，代表音频格式为pcm，采样率为8kHz - AudioFormat.PCM\\_16000HZ\\_MONO\\_16BIT，代表音频格式为pcm，采样率为16kHz - AudioFormat.PCM\\_22050HZ\\_MONO\\_16BIT，代表音频格式为pcm，采样率为22.05kHz - AudioFormat.PCM\\_24000HZ\\_MONO\\_16BIT，代表音频格式为pcm，采样率为24kHz - AudioFormat.PCM\\_44100HZ\\_MONO\\_16BIT，代表音频格式为pcm，采样率为44.1kHz - AudioFormat.PCM\\_48000HZ\\_MONO\\_16BIT，代表音频格式为pcm，采样率为48kHz - 除`cosyvoice-v1`外，其他模型支持的音频编码格式及采样率： 音频格式为opus时，支持通过`bit_rate`参数调整码率。仅对1.24.0及之后版本的DashScope适用。 - AudioFormat.OGG\\_OPUS\\_8KHZ\\_MONO\\_32KBPS，代表音频格式为opus，采样率为8kHz，码率为32kbps - AudioFormat.OGG\\_OPUS\\_16KHZ\\_MONO\\_16KBPS，代表音频格式为opus，采样率为16kHz，码率为16kbps - AudioFormat.OGG\\_OPUS\\_16KHZ\\_MONO\\_32KBPS，代表音频格式为opus，采样率为16kHz，码率为32kbps - AudioFormat.OGG\\_OPUS\\_16KHZ\\_MONO\\_64KBPS，代表音频格式为opus，采样率为16kHz，码率为64kbps - AudioFormat.OGG\\_OPUS\\_24KHZ\\_MONO\\_16KBPS，代表音频格式为opus，采样率为24kHz，码率为16kbps - AudioFormat.OGG\\_OPUS\\_24KHZ\\_MONO\\_32KBPS，代表音频格式为opus，采样率为24kHz，码率为32kbps - AudioFormat.OGG\\_OPUS\\_24KHZ\\_MONO\\_64KBPS，代表音频格式为opus，采样率为24kHz，码率为64kbps - AudioFormat.OGG\\_OPUS\\_48KHZ\\_MONO\\_16KBPS，代表音频格式为opus，采样率为48kHz，码率为16kbps - AudioFormat.OGG\\_OPUS\\_48KHZ\\_MONO\\_32KBPS，代表音频格式为opus，采样率为48kHz，码率为32kbps - AudioFormat.OGG\\_OPUS\\_48KHZ\\_MONO\\_64KBPS，代表音频格式为opus，采样率为48kHz，码率为64kbps |
| volume | int | 否   | 音量。 默认值：50。 取值范围：\\[0, 100\\]。50代表标准音量。音量大小与该值呈线性关系，0为静音，100为最大音量。 **重要** 该字段在不同版本的DashScope SDK中有所不同： - 1.20.10及以后版本的SDK：volume - 1.20.10以前版本的SDK：volumn |
| speech\\_rate | float | 否   | 语速。 默认值：1.0。 取值范围：\\[0.5, 2.0\\]。1.0为标准语速，小于1.0则减慢，大于1.0则加快。 |
| pitch\\_rate | float | 否   | 音高。该值作为音高调节的乘数，但其与听感上的音高变化并非严格的线性或对数关系，建议通过测试选择合适的值。 默认值：1.0。 取值范围：\\[0.5, 2.0\\]。1.0为音色自然音高。大于1.0则音高变高，小于1.0则音高变低。 |
| bit\\_rate | int | 否   | 音频码率（单位kbps）。音频格式为opus时，支持通过`bit_rate`参数调整码率。 默认值：32。 取值范围：\\[6, 510\\]。 `cosyvoice-v1`模型不支持该参数。 **说明** `bit_rate`需要通过`additional_params`参数进行设置： ``` synthesizer = SpeechSynthesizer(model="cosyvoice-v3-flash", voice="longanyang", format=AudioFormat.OGG_OPUS_16KHZ_MONO_16KBPS, additional_params={"bit_rate": 32}) ``` |
| word\\_timestamp\\_enabled | bool | 否   | 是否开启字级别时间戳。 默认值：False。 - True：开启。 - False：关闭。 该功能仅适用于cosyvoice-v3-flash、cosyvoice-v3-plus和cosyvoice-v2模型的复刻音色，以及[音色列表](https://help.aliyun.com/zh/model-studio/cosyvoice-voice-list)中标记为支持的系统音色。 > 时间戳结果仅能通过回调接口获取 **说明** `word_timestamp_enabled`需要通过`additional_params`参数进行设置： ``` synthesizer = SpeechSynthesizer(model="cosyvoice-v3-flash", voice="longyingjing_v3", callback=callback, # 时间戳结果仅能通过回调接口获取 additional_params={'word_timestamp_enabled': True}) ``` **点击查看完整示例代码** ``` # coding=utf-8 import dashscope from dashscope.audio.tts_v2 import * import json from datetime import datetime def get_timestamp(): now = datetime.now() formatted_timestamp = now.strftime("[%Y-%m-%d %H:%M:%S.%f]") return formatted_timestamp # 若没有将API Key配置到环境变量中，需将<API_KEY>替换为自己的API Key # dashscope.api_key = "<API_KEY>" model = "cosyvoice-v3-flash" # 音色 voice = "longyingjing_v3" # 定义回调接口 class Callback(ResultCallback): _player = None _stream = None def on_open(self): self.file = open("output.mp3", "wb") print("连接建立：" + get_timestamp()) def on_complete(self): print("语音合成完成，所有合成结果已被接收：" + get_timestamp()) def on_error(self, message: str): print(f"语音合成出现异常：{message}") def on_close(self): print("连接关闭：" + get_timestamp()) self.file.close() def on_event(self, message): json_data = json.loads(message) if json_data['payload'] and json_data['payload']['output'] and json_data['payload']['output']['sentence']: sentence = json_data['payload']['output']['sentence'] print(f'sentence: {sentence}') # 获取句子的编号 # index = sentence['index'] words = sentence['words'] if words: for word in words: print(f'word: {word}') # 示例值：word: {'text': '今', 'begin_index': 0, 'end_index': 1, 'begin_time': 80, 'end_time': 200} def on_data(self, data: bytes) -> None: print(get_timestamp() + " 二进制音频长度为：" + str(len(data))) self.file.write(data) callback = Callback() # 实例化SpeechSynthesizer，并在构造方法中传入模型（model）、音色（voice）等请求参数 synthesizer = SpeechSynthesizer( model=model, voice=voice, callback=callback, additional_params={'word_timestamp_enabled': True} ) # 发送待合成文本，在回调接口的on_data方法中实时获取二进制音频 synthesizer.call("今天天气怎么样？") # 首次发送文本时需建立 WebSocket 连接，因此首包延迟会包含连接建立的耗时 print('[Metric] requestId为：{}，首包延迟为：{}毫秒'.format( synthesizer.get_last_request_id(), synthesizer.get_first_package_delay())) ``` |
| seed | int | 否   | 生成时使用的随机数种子，使合成的效果产生变化。在模型版本、文本、音色及其他参数均相同的前提下，使用相同的seed可复现相同的合成结果。 默认值0。 取值范围：\\[0, 65535\\]。 cosyvoice-v1不支持该功能。 |
| language\\_hints | list\\[str\\] | 否   | 指定语音合成的目标语言，提升合成效果。cosyvoice-v1不支持该功能。 当数字、缩写、符号等朗读方式或者小语种合成效果不符合预期时使用，例如： - 数字朗读方式不符合预期，“hello, this is 110”读成“hello, this is one one zero”而非“hello, this is 幺幺零” - 符号朗读不准确，“@”读成“艾特”而非“at” - 小语种合成效果差，合成不自然 取值范围： - zh：中文 - en：英文 - fr：法语 - de：德语 - ja：日语 - ko：韩语 - ru：俄语 **注意**：此参数为数组，但当前版本仅处理第一个元素，因此建议只传入一个值。 **重要** 此参数用于指定语音合成的目标语言，该设置与声音复刻时的样本音频的语种无关。如果您需要设置复刻任务的源语言，请参见[CosyVoice声音复刻API](https://help.aliyun.com/zh/model-studio/cosyvoice-clone-api)。 |
| instruction | str | 否   | 设置指令，用于控制方言、情感或角色等合成效果。该功能仅适用于cosyvoice-v3-flash模型的复刻音色，以及[音色列表](https://help.aliyun.com/zh/model-studio/cosyvoice-voice-list)中标记为支持Instruct的系统音色。 **使用要求**： - 指令必须使用固定格式和内容（见下方说明） - 不设置时不生效（无默认值） **支持的功能**： - 指定方言 - 适用音色：仅复刻音色 - 格式：“`请用<方言>表达。`”（注意，结尾一定不要遗漏句号，使用时将“`<方言>`”替换为具体的`方言`，例如替换为`广东话`）。 - 示例：“`请用广东话表达。`” - 支持的方言：广东话、东北话、甘肃话、贵州话、河南话、湖北话、江西话、闽南话、宁夏话、山西话、陕西话、山东话、上海话、四川话、天津话、云南话。 - 指定情感 - 适用音色 - 复刻音色 - [音色列表](https://help.aliyun.com/zh/model-studio/cosyvoice-voice-list)中标记为支持Instruct的系统音色 - 格式： - 复刻音色： 点击查看复刻音色指令格式 - `请尽可能非常大声地说一句话。` - `请用尽可能慢地语速说一句话。` - `请用尽可能快地语速说一句话。` - `请非常轻声地说一句话。` - `你可以慢一点说吗` - `你可以非常快一点说吗` - `你可以非常慢一点说吗` - `你可以快一点说吗` - `请非常生气地说一句话。` - `请非常开心地说一句话。` - `请非常恐惧地说一句话。` - `请非常伤心地说一句话。` - `请非常惊讶地说一句话。` - `请尽可能表现出坚定的感觉。` - `请尽可能表现出愤怒的感觉。` - `请尝试一下亲和的语调。` - `请用冷酷的语调讲话。` - `请用威严的语调讲话。` - `我想体验一下自然的语气。` - `我想看看你如何表达威胁。` - `我想看看你怎么表现智慧。` - `我想看看你怎么表现诱惑。` - `我想听听用活泼的方式说话。` - `我想听听你用激昂的感觉说话。` - `我想听听用沉稳的方式说话的样子。` - `我想听听你用自信的感觉说话。` - `你能用兴奋的感觉和我交流吗？` - `你能否展示狂傲的情绪表达？` - `你能展现一下优雅的情绪吗？` - `你可以用幸福的方式回答问题吗？` - `你可以做一个温柔的情感演示吗？` - `能用冷静的语调和我谈谈吗？` - `能用深沉的方法回答我吗？` - `能用粗犷的情绪态度和我对话吗？` - `用阴森的声音告诉我这个答案。` - `用坚韧的声音告诉我这个答案。` - `用自然亲切的闲聊风格叙述。` - `用广播剧博客主的语气讲话。` - 系统音色：系统音色和复刻音色的情感指令格式不同，详情请参见[音色列表](https://help.aliyun.com/zh/model-studio/cosyvoice-voice-list) - 指定场景、角色或身份等 - 适用音色：[音色列表](https://help.aliyun.com/zh/model-studio/cosyvoice-voice-list)中标记为支持Instruct的系统音色 - 格式：请参见[音色列表](https://help.aliyun.com/zh/model-studio/cosyvoice-voice-list) |
| enable\\_aigc\\_tag | bool | 否   | 是否在生成的音频中添加AIGC隐性标识。设置为True时，会将隐性标识嵌入到支持格式（wav/mp3/opus）的音频中。 默认值：False。 仅cosyvoice-v3-flash、cosyvoice-v3-plus、cosyvoice-v2支持该功能。 **说明** `enable_aigc_tag`需要通过`additional_params`参数进行设置： ``` synthesizer = SpeechSynthesizer(model="cosyvoice-v3-flash", voice="longanyang", format=AudioFormat.OGG_OPUS_16KHZ_MONO_16KBPS, additional_params={"enable_aigc_tag": True}) ``` |
| aigc\\_propagator | str | 否   | 设置AIGC隐性标识中的 `ContentPropagator` 字段，用于标识内容的传播者。仅在 `enable_aigc_tag` 为 `True` 时生效。 默认值：阿里云UID。 仅cosyvoice-v3-flash、cosyvoice-v3-plus、cosyvoice-v2支持该功能。 **说明** `aigc_propagator`需要通过`additional_params`参数进行设置： ``` synthesizer = SpeechSynthesizer(model="cosyvoice-v3-flash", voice="longanyang", format=AudioFormat.OGG_OPUS_16KHZ_MONO_16KBPS, additional_params={"enable_aigc_tag": True, "aigc_propagator": "xxxx"}) ``` |
| aigc\\_propagate\\_id | str | 否   | 设置AIGC隐性标识中的 `PropagateID` 字段，用于唯一标识一次具体的传播行为。仅在 `enable_aigc_tag` 为 `True` 时生效。 默认值：本次语音合成请求Request ID。 仅cosyvoice-v3-flash、cosyvoice-v3-plus、cosyvoice-v2支持该功能。 **说明** `aigc_propagate_id`需要通过`additional_params`参数进行设置： ``` synthesizer = SpeechSynthesizer(model="cosyvoice-v3-flash", voice="longanyang", format=AudioFormat.OGG_OPUS_16KHZ_MONO_16KBPS, additional_params={"enable_aigc_tag": True, "aigc_propagate_id": "xxxx"}) ``` |
| callback | ResultCallback | 否   | [回调接口（ResultCallback）](#85d698b9f9g8s). |

## **关键接口**

### `SpeechSynthesizer`类

`SpeechSynthesizer`通过“`from dashscope.audio.tts_v2 import *`”方式引入，提供语音合成的关键接口。

| **方法** | **参数** | **返回值** | **描述** |
| ``` def call(self, text: str, timeout_millis=None) ``` | - `text`：待合成文本 - `timeout_millis`：阻塞线程的超时时间，单位为毫秒，不设置或值为0时不生效 | 没有指定`ResultCallback`时返回二进制音频数据，否则返回None | 将整段文本（无论是纯文本还是包含[SSML](https://help.aliyun.com/zh/model-studio/introduction-to-cosyvoice-ssml-markup-language)的文本）转换为语音。 在创建`SpeechSynthesizer`实例时，存在以下两种情况： - 没有指定`ResultCallback`：`call`方法会阻塞当前线程直到语音合成完成并返回二进制音频数据。使用方法请参见[非流式调用](#8341058094tc3)。 - 指定了`ResultCallback`：`call`方法会立刻返回None，并通过[回调接口（ResultCallback）](#85d698b9f9g8s)的`on_data`方法返回语音合成的结果。使用方法请参见[单向流式调用](#cc2a504f344s2)。 **重要** 每次调用`call`方法前，需要重新初始化`SpeechSynthesizer`实例。 |
| ``` def streaming_call(self, text: str) ``` | `text`：待合成文本片段 | 无   | 流式发送待合成文本（不支持包含SSML的文本）。 您可以多次调用该接口，将待合成文本分多次发送给服务端。合成结果通过[回调接口（ResultCallback）](#85d698b9f9g8s)的`on_data`方法获取。 使用方法请参见[双向流式调用](#ba023aacfbr84)。 |
| ``` def streaming_complete(self, complete_timeout_millis=600000) ``` | `complete_timeout_millis`：等待时间，单位为毫秒 | 无   | 结束流式语音合成。 该方法阻塞当前线程N毫秒（具体时长由`complete_timeout_millis`决定），直到任务结束。如果`completeTimeoutMillis`设置为0，则无限期等待。 默认情况下，如果等待时间超过10分钟，则停止等待。 使用方法请参见[双向流式调用](#ba023aacfbr84)。 **重要** 在[双向流式调用](#ba023aacfbr84)时，请务必确保调用该方法，否则可能会出现合成语音缺失的问题。 |
| ``` def get_last_request_id(self) ``` | 无   | 上一个任务的request\\_id | 获取上一个任务的request\\_id。 |
| ``` def get_first_package_delay(self) ``` | 无   | 首包延迟 | 获取当前任务的首包延迟，任务结束后使用。首包延迟是开始发送文本和接收第一个音频包之间的时间，单位为毫秒。 **影响首包延迟的因素：** - WebSocket连接建立耗时（首次调用） - 音色加载时间（不同音色加载时间不同） - 服务承载量（高峰期可能出现排队等待） - 网络延迟 **典型延迟范围：** - 复用连接且音色已加载：500ms左右 - 首次连接或切换音色：可能达到1500~2000ms 若首包延迟持续过高（>2000ms），建议： 1. 使用高并发场景下的连接池功能提前建立连接 2. 检查网络连接质量 3. 避免在高峰时段调用 |
| ``` def get_response(self) ``` | 无   | 最后一次报文 | 获取最后一次报文（为JSON格式的数据），可以用于获取task-failed报错。 |

### **回调接口（**`ResultCallback`）

[单向流式调用](#cc2a504f344s2)或[双向流式调用](#ba023aacfbr84)时，服务端会通过回调的方式，将关键流程信息和数据返回给客户端。您需要实现回调方法，处理服务端返回的信息或者数据。

通过“`from dashscope.audio.tts_v2 import *`”方式引入。

点击查看示例

```
class Callback(ResultCallback):
    def on_open(self) -> None:
        print('连接成功')
    
    def on_data(self, data: bytes) -> None:
        # 实现接收合成二进制音频结果的逻辑

    def on_complete(self) -> None:
        print('合成完成')

    def on_error(self, message) -> None:
        print('出现异常：', message)

    def on_close(self) -> None:
        print('连接关闭')


callback = Callback()
```

| **方法** | **参数** | **返回值** | **描述** |
| --- | --- | --- | --- |
| ``` def on_open(self) -> None ``` | 无   | 无   | 当和服务端建立连接完成后，该方法立刻被回调。 |
| ``` def on_event( self, message: str) -> None ``` | `message`：服务端返回的信息 | 无   | 当服务有回复时会被回调。`message`为JSON字符串，解析可获取Task ID（`task_id`参数）、本次请求中计费的有效字符数（`characters`参数）等信息。 |
| ``` def on_complete(self) -> None ``` | 无   | 无   | 当所有合成数据全部返回（语音合成完成）后被回调。 |
| ``` def on_error(self, message) -> None ``` | `message`：异常信息 | 无   | 发生异常时该方法被回调。 |
| ``` def on_data(self, data: bytes) -> None ``` | `data`：服务器返回的二进制音频数据 | 无   | 当服务器有合成音频返回时被回调。 您可以将二进制音频数据合成为一个完整的音频文件后使用播放器播放，也可以通过支持流式播放的播放器实时播放。 **重要** - 流式语音合成中，对于mp3/opus等压缩格式，音频分段传输需使用流式播放器，不可逐帧播放，避免解码失败。 > 支持流式播放的播放器：ffmpeg、pyaudio (Python)、AudioFormat (Java)、MediaSource (Javascript)等。 - 将音频数据合成完整的音频文件时，应以追加模式写入同一文件。 - 流式语音合成的wav/mp3 格式音频仅首帧包含头信息，后续帧为纯音频数据。 |
| ``` def on_close(self) -> None ``` | 无   | 无   | 当服务已经关闭连接后被回调。 |

## **响应结果**

服务器返回二进制音频数据：

-   [非流式调用](#8341058094tc3)：对[SpeechSynthesizer类](#d6bc1f133f871)的`call`方法返回的二进制音频数据进行处理。
    
-   [单向流式调用](#cc2a504f344s2)或[双向流式调用](#ba023aacfbr84)：对[回调接口（ResultCallback）](#85d698b9f9g8s)的`on_data`方法的参数（bytes类型数据）进行处理。
    

## **错误码**

如遇报错问题，请参见[错误信息](https://help.aliyun.com/zh/model-studio/error-code)进行排查。

## **更多示例**

更多示例，请参见[GitHub](https://github.com/aliyun/alibabacloud-bailian-speech-demo)。

## **常见问题**

### **功能特性/计量计费/限流**

#### **Q：当遇到发音不准的情况时，有什么解决方案可以尝试？**

通过[SSML](https://help.aliyun.com/zh/model-studio/introduction-to-cosyvoice-ssml-markup-language)可以对语音合成效果进行个性化定制。

#### **Q：**语音合成是按文本字符数计费的，要如何查看或获取每次合成的文本长度？

根据是否开启日志，有不同的获取方式：

1.  未开启日志
    
    -   [非流式调用](#8341058094tc3)：需要按照字符计算规则自行计算。
        
    -   其他调用方式：通过[回调接口（ResultCallback）](#85d698b9f9g8s)`on_event`方法的`message`参数获取。`message`为JSON字符串，解析可获取本次请求中计费的有效字符数（`characters`参数）。请以收到的最后一个`message`为准。
        
2.  开启日志
    
    在控制台会打印如下日志，`characters`即为本次请求中计费的有效字符数。请以打印的最后一个日志为准。
    
    ```
    2025-08-27 11:02:09,429 - dashscope - speech_synthesizer.py - on_message - 454 - DEBUG - <<<recv {"header":{"task_id":"62ebb7d6cb0a4080868f0edb######","event":"result-generated","attributes":{}},"payload":{"output":{"sentence":{"words":[]}},"usage":{"characters":15}}}
    ```
    

**点击查看如何开启日志**

通过在命令行设置环境变量开启日志：

-   Windows系统：`$env:DASHSCOPE_LOGGING_LEVEL="debug"`
    
-   Linux/macOS系统：`export DASHSCOPE_LOGGING_LEVEL=debug`
    

### **故障排查**

如遇代码报错问题，请根据[错误码](#ca4936efd2bim)中的信息进行排查。

#### **Q：如何获取**Request ID**？**

通过以下两种方式可以获取：

-   在[回调接口（ResultCallback）](#85d698b9f9g8s)的`on_event`方法中对JSON字符串`message`进行解析。
    
-   调用[SpeechSynthesizer](#d6bc1f133f871)的`get_last_request_id`方法。
    

#### **Q：使用SSML功能失败是什么原因？**

请按以下步骤排查：

1.  确保[限制与约束](https://help.aliyun.com/zh/model-studio/introduction-to-cosyvoice-ssml-markup-language#923300b3e9a3z)正确
    
2.  [安装最新版本 DashScope SDK](https://help.aliyun.com/zh/model-studio/install-sdk)
    
3.  确保使用正确的接口：只有[SpeechSynthesizer类](#d6bc1f133f871)的`call`方法支持SSML
    
4.  确保待合成文本为纯文本格式且符合格式要求，详情请参见[SSML标记语言介绍](https://help.aliyun.com/zh/model-studio/introduction-to-cosyvoice-ssml-markup-language)
    

#### **Q：为什么音频无法播放？**

请根据以下场景逐一排查：

1.  音频保存为完整文件（如xx.mp3）的情况
    
    1.  音频格式一致性：确保请求参数中设置的音频格式与文件后缀一致。例如，如果请求参数设置的音频格式为wav，但文件后缀为mp3，可能会导致播放失败。
        
    2.  播放器兼容性：确认使用的播放器是否支持该音频文件的格式和采样率。例如，某些播放器可能不支持高采样率或特定编码的音频文件。
        
2.  流式播放音频的情况
    
    1.  将音频流保存为完整文件，尝试使用播放器播放。如果文件无法播放，请参考场景 1 的排查方法。
        
    2.  如果文件可以正常播放，则问题可能出在流式播放的实现上。请确认使用的播放器是否支持流式播放。
        
        常见的支持流式播放的工具和库包括：ffmpeg、pyaudio (Python)、AudioFormat (Java)、MediaSource (Javascript)等。
        

#### **Q：为什么音频播放卡顿？**

请根据以下场景逐一排查：

1.  检查文本发送速度： 确保发送文本的间隔合理，避免前一句音频播放完毕后，下一句文本未能及时发送。
    
2.  检查回调函数性能：
    
    -   检查回调函数中是否存在过多业务逻辑，导致阻塞。
        
    -   回调函数运行在 WebSocket 线程中，若被阻塞，可能会影响 WebSocket 接收网络数据包，进而导致音频接收卡顿。
        
    -   建议将音频数据写入一个独立的音频缓冲区（audio buffer），然后在其他线程中读取并处理，避免阻塞 WebSocket 线程。
        
3.  检查网络稳定性： 确保网络连接稳定，避免因网络波动导致音频传输中断或延迟。
    

#### **Q：语音合成慢（合成时间长）是什么原因？**

请按以下步骤排查：

1.  检查输入间隔
    
    如果是流式语音合成，请确认文字发送间隔是否过长（如上段发出后延迟数秒才发送下段），过久间隔会导致合成总时长增加。
    
2.  分析性能指标
    
    -   首包延迟：正常500ms左右。
        
    -   RTF（RTF = 合成总耗时/音频时长）：正常小于1.0。
        

#### **Q：合成的语音发音错误如何处理？**

请使用SSML的[<phoneme>标签](https://help.aliyun.com/zh/model-studio/introduction-to-cosyvoice-ssml-markup-language#title-m9h-7yc-48k)指定正确的发音。

#### **Q：为什么没有返回语音？为什么结尾部分的文本没能成功转换成语音？（合成语音缺失）**

请检查是否遗漏了调用[SpeechSynthesizer类](#d6bc1f133f871)的`streaming_complete`方法。在语音合成过程中，服务端会在缓存足够文本后才开始合成。如果未调用`streaming_complete`方法，可能会导致缓存中的结尾部分文本未能被合成为语音。

#### **Q：SSL证书校验失败如何处理？**

1.  安装系统根证书
    
    ```
    sudo yum install -y ca-certificates
    sudo update-ca-trust enable
    ```
    
2.  代码中添加如下内容
    
    ```
    import os
    os.environ["SSL_CERT_FILE"] = "/etc/ssl/certs/ca-bundle.crt"
    ```
    

#### **Q：Mac环境下出现“**SSL: CERTIFICATE\_VERIFY\_FAILED**”异常是什么原因？（**websocket closed due to \[SSL: CERTIFICATE\_VERIFY\_FAILED\] certificate verify failed: unable to get local issuer certificate (\_ssl.c:1000)）

在连接 WebSocket 时，可能会遇到 OpenSSL 验证证书失败的问题，提示找不到证书。这通常是由于 Python 环境的证书配置不正确导致的。可以通过以下步骤手动定位并修复证书问题：

1.  导出系统证书并设置环境变量 执行以下命令，将 macOS 系统中的所有证书导出到一个文件，并将其设置为 Python 和相关库的默认证书路径：
    
    ```
    security find-certificate -a -p > ~/all_mac_certs.pem
    export SSL_CERT_FILE=~/all_mac_certs.pem
    export REQUESTS_CA_BUNDLE=~/all_mac_certs.pem
    ```
    
2.  创建符号链接以修复 Python 的 OpenSSL 配置 如果 Python 的 OpenSSL 配置缺失证书，可以通过以下命令手动创建符号链接。请确保替换命令中的路径为本地 Python 版本的实际安装目录：
    
    ```
    # 3.9是示例版本号，请根据您本地安装的 Python 版本调整路径
    ln -s /etc/ssl/* /Library/Frameworks/Python.framework/Versions/3.9/etc/openssl
    ```
    
3.  重新启动终端并清除缓存 完成上述操作后，请关闭并重新打开终端，以确保环境变量生效。清除可能的缓存后重试连接 WebSocket。
    

通过以上步骤，可以解决因证书配置错误导致的连接问题。如果问题仍未解决，请检查目标服务器的证书配置是否正确。

#### **Q：运行代码提示“**AttributeError: module 'websocket' has no attribute 'WebSocketApp'. Did you mean: 'WebSocket'?**”是什么原因？**

原因是没有安装websocket-client或websocket-client版本不匹配，请依次执行以下命令：

```
pip uninstall websocket-client
pip uninstall websocket
pip install websocket-client
```

### **权限与认证**

#### **Q：**我希望我的 API Key 仅用于 CosyVoice 语音合成服务，而不被百炼其他模型使用（权限隔离），我该如何做**？**

可以通过新建业务空间并只授权特定模型来限制API Key的使用范围。详情请参见[业务空间管理](https://help.aliyun.com/zh/model-studio/use-workspace)。

##### **Q：使用子业务空间的API Key是否可以调用CosyVoice模型？**

对于默认业务空间，模型均可调用。

对于子业务空间：需要为API Key对应的子业务空间进行[模型授权](https://help.aliyun.com/zh/model-studio/model-authentication-instructions)，详情请参见[子业务空间的模型调用](https://help.aliyun.com/zh/model-studio/model-calling-in-sub-workspace)。

### **更多问题**

请参见GitHub [QA](https://github.com/aliyun/alibabacloud-bailian-speech-demo/blob/master/docs/QA/cosyvoice.md)。

SSML（Speech Synthesis Markup Language） 是一种基于 XML 的语音合成标记语言。它不仅能让语音合成大模型读出更丰富的文本内容，还支持对语速、语调、停顿、音量等语音特征进行精细控制，甚至可以添加背景音乐，带来更具表现力的语音效果。本文介绍CosyVoice的SSML功能及使用。

## **限制与约束**

-   **模型：**仅cosyvoice-v3-flash、cosyvoice-v3-plus和cosyvoice-v2模型支持SSML功能
    
-   **音色：**仅复刻音色，以及[音色列表](https://help.aliyun.com/zh/model-studio/cosyvoice-voice-list)中标记为支持SSML的系统音色支持SSML功能
    
-   **接口：**仅部分接口支持SSML功能
    
    -   Java SDK（不低于2.20.3版本）：仅非流式调用和单向流式调用支持SSML（详情请参见：[SSML标记语言支持说明-Java SDK](https://help.aliyun.com/zh/model-studio/cosyvoice-java-sdk#99f13f3817ptm)）
        
    -   Python SDK（不低于1.23.4版本）：仅非流式调用和单向流式调用支持SSML（详情请参见：[SSML标记语言支持说明-Python SDK](https://help.aliyun.com/zh/model-studio/cosyvoice-python-sdk#99f13f3817ptm)）
        
    -   WebSocket API：在发送[run-task指令](https://help.aliyun.com/zh/model-studio/cosyvoice-websocket-api#12d8a57443dmz)时，必须将参数`enable_ssml`设置为`true`，且只允许发送一次[continue-task指令](https://help.aliyun.com/zh/model-studio/cosyvoice-websocket-api#974b0beb59ob5)（详情请参见：[SSML标记语言支持说明-WebSocket API](https://help.aliyun.com/zh/model-studio/cosyvoice-websocket-api#99f13f3817ptm)）。
        

## **快速开始**

运行代码前，请完成以下准备工作：

1.  [获取API Key](https://help.aliyun.com/zh/model-studio/get-api-key)
    
2.  [安装SDK](https://help.aliyun.com/zh/model-studio/install-sdk)（如需运行Java/Python SDK示例）
    

## Java SDK

## 非流式调用

```
import com.alibaba.dashscope.audio.ttsv2.SpeechSynthesisParam;
import com.alibaba.dashscope.audio.ttsv2.SpeechSynthesizer;
import com.alibaba.dashscope.utils.Constants;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;

/**
 * SSML功能说明：
 *     1. 只有非流式调用和单向流式调用支持SSML功能
 *     2. 只有cosyvoice-v3-flash、cosyvoice-v3-plus和cosyvoice-v2模型的复刻音色以及音色列表中标记为支持SSML的系统音色支持SSML功能（例如cosyvoice-v3-flash模型的longanyang音色）
 */
public class Main {
    private static String model = "cosyvoice-v3-flash";
    private static String voice = "longanyang";

    public static void main(String[] args) {
        // 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference
        Constants.baseWebsocketApiUrl = "wss://dashscope.aliyuncs.com/api-ws/v1/inference";
        streamAudioDataToSpeaker();
        System.exit(0);
    }

    public static void streamAudioDataToSpeaker() {
        SpeechSynthesisParam param =
                SpeechSynthesisParam.builder()
                        // 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
                        // 若没有配置环境变量，请用百炼API Key将下行替换为：.apiKey("<API_KEY>")
                        .apiKey(System.getenv("DASHSCOPE_API_KEY"))
                        .model(model)
                        .voice(voice)
                        .build();

        SpeechSynthesizer synthesizer = new SpeechSynthesizer(param, null);
        ByteBuffer audio = null;
        try {
            // 非流式调用，阻塞直至音频返回
            // 特殊字符需要进行转义
            audio = synthesizer.call("<speak rate=\"2\">我的语速比正常人快。</speak>");
        } catch (Exception e) {
            throw new RuntimeException(e);
        } finally {
            // 任务结束关闭websocket连接
            synthesizer.getDuplexApi().close(1000, "bye");
        }
        if (audio != null) {
            // 将音频数据保存到本地文件“output.mp3”中
            File file = new File("output.mp3");
            try (FileOutputStream fos = new FileOutputStream(file)) {
                fos.write(audio.array());
            } catch (IOException e) {
                throw new RuntimeException(e);
            }
        }

        // 首次发送文本时需建立 WebSocket 连接，因此首包延迟会包含连接建立的耗时
        System.out.println(
                "[Metric] requestId为："
                        + synthesizer.getLastRequestId()
                        + "首包延迟（毫秒）为："
                        + synthesizer.getFirstPackageDelay());
    }
}
```

## 单向流式调用

```
import com.alibaba.dashscope.audio.tts.SpeechSynthesisResult;
import com.alibaba.dashscope.audio.ttsv2.SpeechSynthesisAudioFormat;
import com.alibaba.dashscope.audio.ttsv2.SpeechSynthesisParam;
import com.alibaba.dashscope.audio.ttsv2.SpeechSynthesizer;
import com.alibaba.dashscope.common.ResultCallback;
import com.alibaba.dashscope.utils.Constants;

import java.io.FileOutputStream;
import java.io.IOException;
import java.util.concurrent.CountDownLatch;

/**
 * SSML功能说明：
 *     1. 只有非流式调用和单向流式调用支持SSML功能
 *     2. 只有cosyvoice-v3-flash、cosyvoice-v3-plus和cosyvoice-v2模型的复刻音色以及音色列表中标记为支持SSML的系统音色支持SSML功能（例如cosyvoice-v3-flash模型的longanyang音色）
 */
public class Main {
    private static String model = "cosyvoice-v3-flash";
    private static String voice = "longanyang";

    public static void main(String[] args) {
        // 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference
        Constants.baseWebsocketApiUrl = "wss://dashscope.aliyuncs.com/api-ws/v1/inference";
        streamAudioDataToSpeaker();
        System.out.println("音频已保存到 output.mp3 文件中");
        System.exit(0);
    }

    public static void streamAudioDataToSpeaker() {
        CountDownLatch latch = new CountDownLatch(1);
        final FileOutputStream[] fileOutputStream = new FileOutputStream[1];

        try {
            fileOutputStream[0] = new FileOutputStream("output.mp3");
        } catch (IOException e) {
            System.err.println("无法创建输出文件: " + e.getMessage());
            return;
        }

        // 实现回调接口ResultCallback
        ResultCallback<SpeechSynthesisResult> callback = new ResultCallback<SpeechSynthesisResult>() {
            @Override
            public void onEvent(SpeechSynthesisResult result) {
                if (result.getAudioFrame() != null) {
                    // 将音频数据写入本地文件
                    try {
                        byte[] audioData = result.getAudioFrame().array();
                        fileOutputStream[0].write(audioData);
                        fileOutputStream[0].flush();
                    } catch (IOException e) {
                        System.err.println("写入音频数据失败: " + e.getMessage());
                    }
                }
            }

            @Override
            public void onComplete() {
                System.out.println("收到Complete，语音合成结束");
                closeFileOutputStream(fileOutputStream[0]);
                latch.countDown();
            }

            @Override
            public void onError(Exception e) {
                System.out.println("出现异常：" + e.toString());
                closeFileOutputStream(fileOutputStream[0]);
                latch.countDown();
            }
        };

        SpeechSynthesisParam param =
                SpeechSynthesisParam.builder()
                        // 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
                        // 若没有配置环境变量，请用百炼API Key将下行替换为：.apiKey("<API_KEY>")
                        .apiKey(System.getenv("DASHSCOPE_API_KEY"))
                        .model(model)
                        .voice(voice)
                        .format(SpeechSynthesisAudioFormat.MP3_22050HZ_MONO_256KBPS)
                        .build();

        SpeechSynthesizer synthesizer = new SpeechSynthesizer(param, callback);

        try {
            // 单向流式调用，立即返回null（实际结果通过回调接口异步传递），在回调接口的onEvent方法中实时获取二进制音频
            // 特殊字符需要进行转义
            synthesizer.call("<speak rate=\"2\">我的语速比正常人快。</speak>");
            // 等待合成完成
            latch.await();
        } catch (Exception e) {
            throw new RuntimeException(e);
        } finally {
            // 任务结束后关闭websocket连接
            try {
                synthesizer.getDuplexApi().close(1000, "bye");
            } catch (Exception e) {
                System.err.println("关闭WebSocket连接失败: " + e.getMessage());
            }

            // 确保文件流被关闭
            closeFileOutputStream(fileOutputStream[0]);
        }

        // 首次发送文本时需建立 WebSocket 连接，因此首包延迟会包含连接建立的耗时
        System.out.println(
                "[Metric] requestId为："
                        + synthesizer.getLastRequestId()
                        + "，首包延迟（毫秒）为："
                        + synthesizer.getFirstPackageDelay());
    }

    private static void closeFileOutputStream(FileOutputStream fileOutputStream) {
        try {
            if (fileOutputStream != null) {
                fileOutputStream.close();
            }
        } catch (IOException e) {
            System.err.println("关闭文件流失败: " + e.getMessage());
        }
    }
}
```

## Python SDK

## 非流式调用

```
# coding=utf-8
# SSML功能说明：
#     1. 只有非流式调用和单向流式调用支持SSML功能
#     2. 只有cosyvoice-v3-flash、cosyvoice-v3-plus和cosyvoice-v2模型的复刻音色以及音色列表中标记为支持SSML的系统音色支持SSML功能（例如cosyvoice-v3-flash模型的longanyang音色）

import dashscope
from dashscope.audio.tts_v2 import *
import os

# 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
# 若没有配置环境变量，请用百炼API Key将下行替换为：dashscope.api_key = "<API_KEY>"
dashscope.api_key = os.environ.get('DASHSCOPE_API_KEY')

# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference
dashscope.base_websocket_api_url='wss://dashscope.aliyuncs.com/api-ws/v1/inference'

# 模型
model = "cosyvoice-v3-flash"
# 音色
voice = "longanyang"

# 实例化SpeechSynthesizer，并在构造方法中传入模型（model）、音色（voice）等请求参数
synthesizer = SpeechSynthesizer(model=model, voice=voice)
# 非流式调用，阻塞直至音频返回
# 特殊字符需要进行转义
audio = synthesizer.call("<speak rate=\"2\">我的语速比正常人快。</speak>")

# 将音频保存至本地
with open('output.mp3', 'wb') as f:
    f.write(audio)

# 首次发送文本时需建立 WebSocket 连接，因此首包延迟会包含连接建立的耗时
print('[Metric] requestId为：{}，首包延迟为：{}毫秒'.format(
    synthesizer.get_last_request_id(),
    synthesizer.get_first_package_delay()))
```

## 单向流式调用

```
# coding=utf-8
# SSML功能说明：
#     1. 只有非流式调用和单向流式调用支持SSML功能
#     2. 只有cosyvoice-v3-flash、cosyvoice-v3-plus和cosyvoice-v2模型的复刻音色以及音色列表中标记为支持SSML的系统音色支持SSML功能（例如cosyvoice-v3-flash模型的longanyang音色）

import dashscope
from dashscope.audio.tts_v2 import *
import os
from datetime import datetime

def get_timestamp():
    now = datetime.now()
    formatted_timestamp = now.strftime("[%Y-%m-%d %H:%M:%S.%f]")
    return formatted_timestamp

# 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
# 若没有配置环境变量，请用百炼API Key将下行替换为：dashscope.api_key = "<API_KEY>"
dashscope.api_key = os.environ.get('DASHSCOPE_API_KEY')

# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference
dashscope.base_websocket_api_url='wss://dashscope.aliyuncs.com/api-ws/v1/inference'

# 模型
model = "cosyvoice-v3-flash"
# 音色
voice = "longanyang"

# 定义回调接口
class Callback(ResultCallback):
    _player = None
    _stream = None

    def on_open(self):
        # 打开输出文件，准备写入音频数据
        self.file = open("output.mp3", "wb")
        print("连接建立：" + get_timestamp())

    def on_complete(self):
        print("语音合成完成，所有合成结果已被接收：" + get_timestamp())
        if hasattr(self, 'file') and self.file:
            self.file.close()
        self
        # 首次发送文本时需建立 WebSocket 连接，因此首包延迟会包含连接建立的耗时
        print('[Metric] requestId为：{}，首包延迟为：{}毫秒'.format(
            self.synthesizer.get_last_request_id(),
            self.synthesizer.get_first_package_delay()))

    def on_error(self, message: str):
        print(f"语音合成出现异常：{message}")
        if hasattr(self, 'file') and self.file:
            self.file.close()

    def on_close(self):
        print("连接关闭：" + get_timestamp())
        if hasattr(self, 'file') and self.file:
            self.file.close()

    def on_event(self, message):
        pass

    def on_data(self, data: bytes) -> None:
        print(get_timestamp() + " 二进制音频长度为：" + str(len(data)))
        # 将音频数据写入文件
        self.file.write(data)

callback = Callback()

# 实例化SpeechSynthesizer，并在构造方法中传入模型（model）、音色（voice）等请求参数
synthesizer = SpeechSynthesizer(
    model=model,
    voice=voice,
    callback=callback,
)

# 将synthesizer实例赋值给callback，以便在on_complete中使用
callback.synthesizer = synthesizer

# 单向流式调用，发送待合成文本，在回调接口的on_data方法中实时获取二进制音频
# 特殊字符需要进行转义
synthesizer.call("<speak rate=\"2\">我的语速比正常人快。</speak>")
```

## WebSocket API

## Go

```
// SSML功能说明：
//     1. 在发送run-task指令时，将参数enable_ssml设置为true，以开启SSML支持
//     2. 通过continue-task指令发送包含SSML的文本，且只允许发送一次continue-task指令
//     3. 只有cosyvoice-v3-flash、cosyvoice-v3-plus和cosyvoice-v2模型的复刻音色以及音色列表中标记为支持SSML的系统音色支持SSML功能（例如cosyvoice-v3-flash模型的longanyang音色）

package main

import (
    "encoding/json"
    "fmt"
    "net/http"
    "os"
    "strings"
    "time"

    "github.com/google/uuid"
    "github.com/gorilla/websocket"
)

const (
    // 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference/
    wsURL      = "wss://dashscope.aliyuncs.com/api-ws/v1/inference/"
    outputFile = "output.mp3"
)

func main() {
    // 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
    // 若没有配置环境变量，请用百炼API Key将下行替换为：apiKey := "<API_KEY>"
    apiKey := os.Getenv("DASHSCOPE_API_KEY")

    // 清空输出文件
    os.Remove(outputFile)
    os.Create(outputFile)

    // 连接WebSocket
    header := make(http.Header)
    header.Add("X-DashScope-DataInspection", "enable")
    header.Add("Authorization", fmt.Sprintf("bearer %s", apiKey))

    conn, resp, err := websocket.DefaultDialer.Dial(wsURL, header)
    if err != nil {
        if resp != nil {
            fmt.Printf("连接失败 HTTP状态码: %d\n", resp.StatusCode)
        }
        fmt.Println("连接失败:", err)
        return
    }
    defer conn.Close()

    // 生成任务ID
    taskID := uuid.New().String()
    fmt.Printf("生成任务ID: %s\n", taskID)

    // 发送run-task指令
    runTaskCmd := map[string]interface{}{
        "header": map[string]interface{}{
            "action":    "run-task",
            "task_id":   taskID,
            "streaming": "duplex",
        },
        "payload": map[string]interface{}{
            "task_group": "audio",
            "task":       "tts",
            "function":   "SpeechSynthesizer",
            "model":      "cosyvoice-v3-flash",
            "parameters": map[string]interface{}{
                "text_type":   "PlainText",
                "voice":       "longanyang",
                "format":      "mp3",
                "sample_rate": 22050,
                "volume":      50,
                "rate":        1,
                "pitch":       1,
                // 如果enable_ssml设为true，只允许发送一次continue-task指令，否则会报错“Text request limit violated, expected 1.”
                "enable_ssml": true,
            },
            "input": map[string]interface{}{},
        },
    }

    runTaskJSON, _ := json.Marshal(runTaskCmd)
    fmt.Printf("发送run-task指令: %s\n", string(runTaskJSON))

    err = conn.WriteMessage(websocket.TextMessage, runTaskJSON)
    if err != nil {
        fmt.Println("发送run-task失败:", err)
        return
    }

    textSent := false

    // 处理消息
    for {
        messageType, message, err := conn.ReadMessage()
        if err != nil {
            fmt.Println("读取消息失败:", err)
            break
        }

        // 处理二进制消息
        if messageType == websocket.BinaryMessage {
            fmt.Printf("收到二进制消息，长度: %d\n", len(message))
            file, _ := os.OpenFile(outputFile, os.O_APPEND|os.O_WRONLY|os.O_CREATE, 0644)
            file.Write(message)
            file.Close()
            continue
        }

        // 处理文本消息
        messageStr := string(message)
        fmt.Printf("收到文本消息: %s\n", strings.ReplaceAll(messageStr, "\n", ""))

        // 简单解析JSON获取event类型
        var msgMap map[string]interface{}
        if json.Unmarshal(message, &msgMap) == nil {
            if header, ok := msgMap["header"].(map[string]interface{}); ok {
                if event, ok := header["event"].(string); ok {
                    fmt.Printf("事件类型: %s\n", event)

                    switch event {
                    case "task-started":
                        fmt.Println("=== 收到task-started事件 ===")

                        if !textSent {
                            // 发送 continue-task 指令，使用SSML功能时，该指令只允许发送一次
                            continueTaskCmd := map[string]interface{}{
                                "header": map[string]interface{}{
                                    "action":    "continue-task",
                                    "task_id":   taskID,
                                    "streaming": "duplex",
                                },
                                "payload": map[string]interface{}{
                                    "input": map[string]interface{}{
                                        // 特殊字符需要进行转义
                                        "text": "<speak rate=\"2\">我的语速比正常人快。</speak>",
                                    },
                                },
                            }

                            continueTaskJSON, _ := json.Marshal(continueTaskCmd)
                            fmt.Printf("发送continue-task指令: %s\n", string(continueTaskJSON))

                            err = conn.WriteMessage(websocket.TextMessage, continueTaskJSON)
                            if err != nil {
                                fmt.Println("发送continue-task失败:", err)
                                return
                            }

                            textSent = true

                            // 延迟发送finish-task
                            time.Sleep(500 * time.Millisecond)

                            // 发送finish-task指令
                            finishTaskCmd := map[string]interface{}{
                                "header": map[string]interface{}{
                                    "action":    "finish-task",
                                    "task_id":   taskID,
                                    "streaming": "duplex",
                                },
                                "payload": map[string]interface{}{
                                    "input": map[string]interface{}{},
                                },
                            }

                            finishTaskJSON, _ := json.Marshal(finishTaskCmd)
                            fmt.Printf("发送finish-task指令: %s\n", string(finishTaskJSON))

                            err = conn.WriteMessage(websocket.TextMessage, finishTaskJSON)
                            if err != nil {
                                fmt.Println("发送finish-task失败:", err)
                                return
                            }
                        }

                    case "task-finished":
                        fmt.Println("=== 任务完成 ===")
                        return

                    case "task-failed":
                        fmt.Println("=== 任务失败 ===")
                        if header["error_message"] != nil {
                            fmt.Printf("错误信息: %s\n", header["error_message"])
                        }
                        return

                    case "result-generated":
                        fmt.Println("收到result-generated事件")
                    }
                }
            }
        }
    }
}
```

## C#

```
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;

// SSML功能说明：
//     1. 在发送run-task指令时，将参数enable_ssml设置为true，以开启SSML支持
//     2. 通过continue-task指令发送包含SSML的文本，且只允许发送一次continue-task指令
//     3. 只有cosyvoice-v3-flash、cosyvoice-v3-plus和cosyvoice-v2模型的复刻音色以及音色列表中标记为支持SSML的系统音色支持SSML功能（例如cosyvoice-v3-flash模型的longanyang音色）
class Program {
    // 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
    // 若没有配置环境变量，请用百炼API Key将下行替换为：private static readonly string ApiKey = "<API_KEY>"
    private static readonly string ApiKey = Environment.GetEnvironmentVariable("DASHSCOPE_API_KEY") ?? throw new InvalidOperationException("DASHSCOPE_API_KEY environment variable is not set.");

    // 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference/
    private const string WebSocketUrl = "wss://dashscope.aliyuncs.com/api-ws/v1/inference/";
    // 输出文件路径
    private const string OutputFilePath = "output.mp3";

    // WebSocket客户端
    private static ClientWebSocket _webSocket = new ClientWebSocket();
    // 取消令牌源
    private static CancellationTokenSource _cancellationTokenSource = new CancellationTokenSource();
    // 任务ID
    private static string? _taskId;
    // 任务是否已启动
    private static TaskCompletionSource<bool> _taskStartedTcs = new TaskCompletionSource<bool>();

    static async Task Main(string[] args) {
        try {
            // 清空输出文件
            ClearOutputFile(OutputFilePath);

            // 连接WebSocket服务
            await ConnectToWebSocketAsync(WebSocketUrl);

            // 启动接收消息的任务
            Task receiveTask = ReceiveMessagesAsync();

            // 发送run-task指令
            _taskId = GenerateTaskId();
            await SendRunTaskCommandAsync(_taskId);

            // 等待task-started事件
            await _taskStartedTcs.Task;

            // 发送 continue-task 指令，使用SSML功能时，该指令只允许发送一次
            // 特殊字符需要进行转义
            await SendContinueTaskCommandAsync("<speak rate=\"2\">我的语速比正常人快。</speak>");

            // 发送finish-task指令
            await SendFinishTaskCommandAsync(_taskId);

            // 等待接收任务完成
            await receiveTask;

            Console.WriteLine("任务完成，连接已关闭。");
        } catch (OperationCanceledException) {
            Console.WriteLine("任务被取消。");
        } catch (Exception ex) {
            Console.WriteLine($"发生错误：{ex.Message}");
        } finally {
            _cancellationTokenSource.Cancel();
            _webSocket.Dispose();
        }
    }

    private static void ClearOutputFile(string filePath) {
        if (File.Exists(filePath)) {
            File.WriteAllText(filePath, string.Empty);
            Console.WriteLine("输出文件已清空。");
        } else {
            Console.WriteLine("输出文件不存在，无需清空。");
        }
    }

    private static async Task ConnectToWebSocketAsync(string url) {
        var uri = new Uri(url);
        if (_webSocket.State == WebSocketState.Connecting || _webSocket.State == WebSocketState.Open) {
            return;
        }

        // 设置WebSocket连接的头部信息
        _webSocket.Options.SetRequestHeader("Authorization", $"bearer {ApiKey}");
        _webSocket.Options.SetRequestHeader("X-DashScope-DataInspection", "enable");

        try {
            await _webSocket.ConnectAsync(uri, _cancellationTokenSource.Token);
            Console.WriteLine("已成功连接到WebSocket服务。");
        } catch (OperationCanceledException) {
            Console.WriteLine("WebSocket连接被取消。");
        } catch (Exception ex) {
            Console.WriteLine($"WebSocket连接失败: {ex.Message}");
            throw;
        }
    }

    private static async Task SendRunTaskCommandAsync(string taskId) {
        var command = CreateCommand("run-task", taskId, "duplex", new {
            task_group = "audio",
            task = "tts",
            function = "SpeechSynthesizer",
            model = "cosyvoice-v3-flash",
            parameters = new
            {
                text_type = "PlainText",
                voice = "longanyang",
                format = "mp3",
                sample_rate = 22050,
                volume = 50,
                rate = 1,
                pitch = 1,
                // 如果enable_ssml设为true，只允许发送一次continue-task指令，否则会报错“Text request limit violated, expected 1.”
                enable_ssml = true
            },
            input = new { }
        });

        await SendJsonMessageAsync(command);
        Console.WriteLine("已发送run-task指令。");
    }

    private static async Task SendContinueTaskCommandAsync(string text) {
        if (_taskId == null) {
            throw new InvalidOperationException("任务ID未初始化。");
        }

        var command = CreateCommand("continue-task", _taskId, "duplex", new {
            input = new {
                text
            }
        });

        await SendJsonMessageAsync(command);
        Console.WriteLine("已发送continue-task指令。");
    }

    private static async Task SendFinishTaskCommandAsync(string taskId) {
        var command = CreateCommand("finish-task", taskId, "duplex", new {
            input = new { }
        });

        await SendJsonMessageAsync(command);
        Console.WriteLine("已发送finish-task指令。");
    }

    private static async Task SendJsonMessageAsync(string message) {
        var buffer = Encoding.UTF8.GetBytes(message);
        try {
            await _webSocket.SendAsync(new ArraySegment<byte>(buffer), WebSocketMessageType.Text, true, _cancellationTokenSource.Token);
        } catch (OperationCanceledException) {
            Console.WriteLine("消息发送被取消。");
        }
    }

    private static async Task ReceiveMessagesAsync() {
        while (_webSocket.State == WebSocketState.Open) {
            var response = await ReceiveMessageAsync();
            if (response != null) {
                var eventStr = response.RootElement.GetProperty("header").GetProperty("event").GetString();
                switch (eventStr) {
                    case "task-started":
                        Console.WriteLine("任务已启动。");
                        _taskStartedTcs.TrySetResult(true);
                        break;
                    case "task-finished":
                        Console.WriteLine("任务已完成。");
                        _cancellationTokenSource.Cancel();
                        break;
                    case "task-failed":
                        Console.WriteLine("任务失败：" + response.RootElement.GetProperty("header").GetProperty("error_message").GetString());
                        _cancellationTokenSource.Cancel();
                        break;
                    default:
                        // result-generated可在此处理
                        break;
                }
            }
        }
    }

    private static async Task<JsonDocument?> ReceiveMessageAsync() {
        var buffer = new byte[1024 * 4];
        var segment = new ArraySegment<byte>(buffer);

        try {
            WebSocketReceiveResult result = await _webSocket.ReceiveAsync(segment, _cancellationTokenSource.Token);

            if (result.MessageType == WebSocketMessageType.Close) {
                await _webSocket.CloseAsync(WebSocketCloseStatus.NormalClosure, "Closing", _cancellationTokenSource.Token);
                return null;
            }

            if (result.MessageType == WebSocketMessageType.Binary) {
                // 处理二进制数据
                Console.WriteLine("接收到二进制数据...");

                // 将二进制数据保存到文件
                using (var fileStream = new FileStream(OutputFilePath, FileMode.Append)) {
                    fileStream.Write(buffer, 0, result.Count);
                }

                return null;
            }

            string message = Encoding.UTF8.GetString(buffer, 0, result.Count);
            return JsonDocument.Parse(message);
        } catch (OperationCanceledException) {
            Console.WriteLine("消息接收被取消。");
            return null;
        }
    }

    private static string GenerateTaskId() {
        return Guid.NewGuid().ToString("N").Substring(0, 32);
    }

    private static string CreateCommand(string action, string taskId, string streaming, object payload) {
        var command = new {
            header = new {
                action,
                task_id = taskId,
                streaming
            },
            payload
        };

        return JsonSerializer.Serialize(command);
    }
}
```

## PHP

示例代码目录结构为：

my-php-project/

├── composer.json

├── vendor/

└── index.php

composer.json内容如下，相关依赖的版本号请根据实际情况自行决定：

```
{
    "require": {
        "react/event-loop": "^1.3",
        "react/socket": "^1.11",
        "react/stream": "^1.2",
        "react/http": "^1.1",
        "ratchet/pawl": "^0.4"
    },
    "autoload": {
        "psr-4": {
            "App\\": "src/"
        }
    }
}
```

index.php内容如下：

```
<!-- SSML功能说明： -->
<!--     1. 在发送run-task指令时，将参数enable_ssml设置为true，以开启SSML支持 -->
<!--     2. 通过continue-task指令发送包含SSML的文本，且只允许发送一次continue-task指令 -->
<!--     3. 只有cosyvoice-v3-flash、cosyvoice-v3-plus和cosyvoice-v2模型的复刻音色以及音色列表中标记为支持SSML的系统音色支持SSML功能（例如cosyvoice-v3-flash模型的longanyang音色） -->

<?php

require __DIR__ . '/vendor/autoload.php';

use Ratchet\Client\Connector;
use React\EventLoop\Loop;
use React\Socket\Connector as SocketConnector;

// 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
// 若没有配置环境变量，请用百炼API Key将下行替换为：$api_key = "<API_KEY>"
$api_key = getenv("DASHSCOPE_API_KEY");
// 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference/
$websocket_url = 'wss://dashscope.aliyuncs.com/api-ws/v1/inference/'; // WebSocket服务器地址
$output_file = 'output.mp3'; // 输出文件路径

$loop = Loop::get();

if (file_exists($output_file)) {
    // 清空文件内容
    file_put_contents($output_file, '');
}

// 创建自定义的连接器
$socketConnector = new SocketConnector($loop, [
    'tcp' => [
        'bindto' => '0.0.0.0:0',
    ],
    'tls' => [
        'verify_peer' => false,
        'verify_peer_name' => false,
    ],
]);

$connector = new Connector($loop, $socketConnector);

$headers = [
    'Authorization' => 'bearer ' . $api_key,
    'X-DashScope-DataInspection' => 'enable'
];

$connector($websocket_url, [], $headers)->then(function ($conn) use ($loop, $output_file) {
    echo "连接到WebSocket服务器\n";

    // 生成任务ID
    $taskId = generateTaskId();

    // 发送 run-task 指令
    sendRunTaskMessage($conn, $taskId);

    // 定义发送 continue-task 指令的函数
    $sendContinueTask = function() use ($conn, $loop, $taskId) {
        // 发送 continue-task 指令，使用SSML功能时，该指令只允许发送一次
        $continueTaskMessage = json_encode([
            "header" => [
                "action" => "continue-task",
                "task_id" => $taskId,
                "streaming" => "duplex"
            ],
            "payload" => [
                "input" => [
                    // 特殊字符需要进行转义
                    "text" => "<speak rate=\"2\">我的语速比正常人快。</speak>"
                ]
            ]
        ]);
        $conn->send($continueTaskMessage);

        // 发送 finish-task 指令
        sendFinishTaskMessage($conn, $taskId);
    };

    // 标记是否收到 task-started 事件
    $taskStarted = false;

    // 监听消息
    $conn->on('message', function($msg) use ($conn, $sendContinueTask, $loop, &$taskStarted, $taskId, $output_file) {
        if ($msg->isBinary()) {
            // 写入二进制数据到本地文件
            file_put_contents($output_file, $msg->getPayload(), FILE_APPEND);
        } else {
            // 处理非二进制消息
            $response = json_decode($msg, true);

            if (isset($response['header']['event'])) {
                handleEvent($conn, $response, $sendContinueTask, $loop, $taskId, $taskStarted);
            } else {
                echo "未知的消息格式\n";
            }
        }
    });

    // 监听连接关闭
    $conn->on('close', function($code = null, $reason = null) {
        echo "连接已关闭\n";
        if ($code !== null) {
            echo "关闭代码: " . $code . "\n";
        }
        if ($reason !== null) {
            echo "关闭原因：" . $reason . "\n";
        }
    });
}, function ($e) {
    echo "无法连接：{$e->getMessage()}\n";
});

$loop->run();

/**
 * 生成任务ID
 * @return string
 */
function generateTaskId(): string {
    return bin2hex(random_bytes(16));
}

/**
 * 发送 run-task 指令
 * @param $conn
 * @param $taskId
 */
function sendRunTaskMessage($conn, $taskId) {
    $runTaskMessage = json_encode([
        "header" => [
            "action" => "run-task",
            "task_id" => $taskId,
            "streaming" => "duplex"
        ],
        "payload" => [
            "task_group" => "audio",
            "task" => "tts",
            "function" => "SpeechSynthesizer",
            "model" => "cosyvoice-v3-flash",
            "parameters" => [
                "text_type" => "PlainText",
                "voice" => "longanyang",
                "format" => "mp3",
                "sample_rate" => 22050,
                "volume" => 50,
                "rate" => 1,
                "pitch" => 1,
                // 如果enable_ssml设为true，只允许发送一次continue-task指令，否则会报错“Text request limit violated, expected 1.”
                "enable_ssml" => true
            ],
            "input" => (object) []
        ]
    ]);
    echo "准备发送run-task指令: " . $runTaskMessage . "\n";
    $conn->send($runTaskMessage);
    echo "run-task指令已发送\n";
}

/**
 * 读取音频文件
 * @param string $filePath
 * @return bool|string
 */
function readAudioFile(string $filePath) {
    $voiceData = file_get_contents($filePath);
    if ($voiceData === false) {
        echo "无法读取音频文件\n";
    }
    return $voiceData;
}

/**
 * 分割音频数据
 * @param string $data
 * @param int $chunkSize
 * @return array
 */
function splitAudioData(string $data, int $chunkSize): array {
    return str_split($data, $chunkSize);
}

/**
 * 发送 finish-task 指令
 * @param $conn
 * @param $taskId
 */
function sendFinishTaskMessage($conn, $taskId) {
    $finishTaskMessage = json_encode([
        "header" => [
            "action" => "finish-task",
            "task_id" => $taskId,
            "streaming" => "duplex"
        ],
        "payload" => [
            "input" => (object) []
        ]
    ]);
    echo "准备发送finish-task指令: " . $finishTaskMessage . "\n";
    $conn->send($finishTaskMessage);
    echo "finish-task指令已发送\n";
}

/**
 * 处理事件
 * @param $conn
 * @param $response
 * @param $sendContinueTask
 * @param $loop
 * @param $taskId
 * @param $taskStarted
 */
function handleEvent($conn, $response, $sendContinueTask, $loop, $taskId, &$taskStarted) {
    switch ($response['header']['event']) {
        case 'task-started':
            echo "任务开始，发送continue-task指令...\n";
            $taskStarted = true;
            // 发送 continue-task 指令
            $sendContinueTask();
            break;
        case 'result-generated':
            // 忽略result-generated事件
            break;
        case 'task-finished':
            echo "任务完成\n";
            $conn->close();
            break;
        case 'task-failed':
            echo "任务失败\n";
            echo "错误代码：" . $response['header']['error_code'] . "\n";
            echo "错误信息：" . $response['header']['error_message'] . "\n";
            $conn->close();
            break;
        case 'error':
            echo "错误：" . $response['payload']['message'] . "\n";
            break;
        default:
            echo "未知事件：" . $response['header']['event'] . "\n";
            break;
    }

    // 如果任务已完成，关闭连接
    if ($response['header']['event'] == 'task-finished') {
        // 等待1秒以确保所有数据都已传输完毕
        $loop->addTimer(1, function() use ($conn) {
            $conn->close();
            echo "客户端关闭连接\n";
        });
    }

    // 如果没有收到 task-started 事件，关闭连接
    if (!$taskStarted && in_array($response['header']['event'], ['task-failed', 'error'])) {
        $conn->close();
    }
}
```

## Node.js

需安装相关依赖：

```
npm install ws
npm install uuid
```

示例代码如下：

```
// SSML功能说明：
//     1. 在发送run-task指令时，将参数enable_ssml设置为true，以开启SSML支持
//     2. 通过continue-task指令发送包含SSML的文本，且只允许发送一次continue-task指令
//     3. 只有cosyvoice-v3-flash、cosyvoice-v3-plus和cosyvoice-v2模型的复刻音色以及音色列表中标记为支持SSML的系统音色支持SSML功能（例如cosyvoice-v3-flash模型的longanyang音色）

import fs from 'fs';
import WebSocket from 'ws';
import { v4 as uuid } from 'uuid'; // 用于生成UUID

// 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
// 若没有配置环境变量，请用百炼API Key将下行替换为：const apiKey = "<API_KEY>"
const apiKey = process.env.DASHSCOPE_API_KEY;
// 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference/
const url = 'wss://dashscope.aliyuncs.com/api-ws/v1/inference/';
// 输出文件路径
const outputFilePath = 'output.mp3';

// 清空输出文件
fs.writeFileSync(outputFilePath, '');

// 创建WebSocket客户端
const ws = new WebSocket(url, {
  headers: {
    Authorization: `bearer ${apiKey}`,
    'X-DashScope-DataInspection': 'enable'
  }
});

let taskStarted = false;
let taskId = uuid();

ws.on('open', () => {
  console.log('已连接到WebSocket服务器');

  // 发送run-task指令
  const runTaskMessage = JSON.stringify({
    header: {
      action: 'run-task',
      task_id: taskId,
      streaming: 'duplex'
    },
    payload: {
      task_group: 'audio',
      task: 'tts',
      function: 'SpeechSynthesizer',
      model: 'cosyvoice-v3-flash',
      parameters: {
        text_type: 'PlainText',
        voice: 'longanyang', // 音色
        format: 'mp3', // 音频格式
        sample_rate: 22050, // 采样率
        volume: 50, // 音量
        rate: 1, // 语速
        pitch: 1, // 音调
        enable_ssml: true // 是否开启SSML功能。如果enable_ssml设为true，只允许发送一次continue-task指令，否则会报错“Text request limit violated, expected 1.”
      },
      input: {}
    }
  });
  ws.send(runTaskMessage);
  console.log('已发送run-task消息');
});

const fileStream = fs.createWriteStream(outputFilePath, { flags: 'a' });
ws.on('message', (data, isBinary) => {
  if (isBinary) {
    // 写入二进制数据到文件
    fileStream.write(data);
  } else {
    const message = JSON.parse(data);

    switch (message.header.event) {
      case 'task-started':
        taskStarted = true;
        console.log('任务已开始');
        // 发送continue-task指令
        sendContinueTasks(ws);
        break;
      case 'task-finished':
        console.log('任务已完成');
        ws.close();
        fileStream.end(() => {
          console.log('文件流已关闭');
        });
        break;
      case 'task-failed':
        console.error('任务失败：', message.header.error_message);
        ws.close();
        fileStream.end(() => {
          console.log('文件流已关闭');
        });
        break;
      default:
        // 可以在这里处理result-generated
        break;
    }
  }
});

function sendContinueTasks(ws) {
  
  if (taskStarted) {
    // 发送 continue-task 指令，使用SSML功能时，该指令只允许发送一次
    const continueTaskMessage = JSON.stringify({
      header: {
        action: 'continue-task',
        task_id: taskId,
        streaming: 'duplex'
      },
      payload: {
        input: {
          // 特殊字符需要进行转义
          text: '<speak rate="2">我的语速比正常人快。</speak>'
        }
      }
    });
    ws.send(continueTaskMessage);
    
    // 发送finish-task指令
    const finishTaskMessage = JSON.stringify({
      header: {
        action: 'finish-task',
        task_id: taskId,
        streaming: 'duplex'
      },
      payload: {
        input: {}
      }
    });
    ws.send(finishTaskMessage);
  }
}

ws.on('close', () => {
  console.log('已断开与WebSocket服务器的连接');
});
```

## Java

如您使用Java编程语言，建议采用Java DashScope SDK进行开发，详情请参见[Java SDK](https://help.aliyun.com/zh/model-studio/cosyvoice-java-sdk)。

以下是Java WebSocket的调用示例。在运行示例前，请确保已导入以下依赖：

-   `Java-WebSocket`
    
-   `jackson-databind`
    

推荐您使用Maven或Gradle管理依赖包，其配置如下：

## pom.xml

```
<dependencies>
    <!-- WebSocket Client -->
    <dependency>
        <groupId>org.java-websocket</groupId>
        <artifactId>Java-WebSocket</artifactId>
        <version>1.5.3</version>
    </dependency>

    <!-- JSON Processing -->
    <dependency>
        <groupId>com.fasterxml.jackson.core</groupId>
        <artifactId>jackson-databind</artifactId>
        <version>2.13.0</version>
    </dependency>
</dependencies>
```

## build.gradle

```
// 省略其它代码
dependencies {
  // WebSocket Client
  implementation 'org.java-websocket:Java-WebSocket:1.5.3'
  // JSON Processing
  implementation 'com.fasterxml.jackson.core:jackson-databind:2.13.0'
}
// 省略其它代码
```

Java代码如下：

```
import com.fasterxml.jackson.databind.ObjectMapper;

import org.java_websocket.client.WebSocketClient;
import org.java_websocket.handshake.ServerHandshake;

import java.io.FileOutputStream;
import java.io.IOException;
import java.net.URI;
import java.nio.ByteBuffer;
import java.util.*;

/**
 * SSML功能说明：
 *     1. 在发送run-task指令时，将参数enable_ssml设置为true，以开启SSML支持
 *     2. 通过continue-task指令发送包含SSML的文本，且只允许发送一次continue-task指令
 *     3. 只有cosyvoice-v3-flash、cosyvoice-v3-plus和cosyvoice-v2模型的复刻音色以及音色列表中标记为支持SSML的系统音色支持SSML功能（例如cosyvoice-v3-flash模型的longanyang音色）
 */
public class TTSWebSocketClient extends WebSocketClient {
    private final String taskId = UUID.randomUUID().toString();
    private final String outputFile = "output_" + System.currentTimeMillis() + ".mp3";
    private boolean taskFinished = false;

    public TTSWebSocketClient(URI serverUri, Map<String, String> headers) {
        super(serverUri, headers);
    }

    @Override
    public void onOpen(ServerHandshake serverHandshake) {
        System.out.println("连接成功");

        // 发送run-task指令
        // 如果enable_ssml设为true，只允许发送一次continue-task指令，否则会报错“Text request limit violated, expected 1.”
        String runTaskCommand = "{ \"header\": { \"action\": \"run-task\", \"task_id\": \"" + taskId + "\", \"streaming\": \"duplex\" }, \"payload\": { \"task_group\": \"audio\", \"task\": \"tts\", \"function\": \"SpeechSynthesizer\", \"model\": \"cosyvoice-v3-flash\", \"parameters\": { \"text_type\": \"PlainText\", \"voice\": \"longanyang\", \"format\": \"mp3\", \"sample_rate\": 22050, \"volume\": 50, \"rate\": 1, \"pitch\": 1, \"enable_ssml\": true }, \"input\": {} }}";
        send(runTaskCommand);
    }

    @Override
    public void onMessage(String message) {
        System.out.println("收到服务端返回的消息：" + message);
        try {
            // Parse JSON message
            Map<String, Object> messageMap = new ObjectMapper().readValue(message, Map.class);

            if (messageMap.containsKey("header")) {
                Map<String, Object> header = (Map<String, Object>) messageMap.get("header");

                if (header.containsKey("event")) {
                    String event = (String) header.get("event");

                    if ("task-started".equals(event)) {
                        System.out.println("收到服务端返回的task-started事件");

                        // 发送 continue-task 指令，使用SSML功能时，该指令只允许发送一次
                        // 特殊字符需要进行转义
                        sendContinueTask("<speak rate=\\\"2\\\">我的语速比正常人快。</speak>");

                        // 发送finish-task指令
                        sendFinishTask();
                    } else if ("task-finished".equals(event)) {
                        System.out.println("收到服务端返回的task-finished事件");
                        taskFinished = true;
                        closeConnection();
                    } else if ("task-failed".equals(event)) {
                        System.out.println("任务失败：" + message);
                        closeConnection();
                    }
                }
            }
        } catch (Exception e) {
            System.err.println("出现异常：" + e.getMessage());
        }
    }

    @Override
    public void onMessage(ByteBuffer message) {
        System.out.println("收到的二进制音频数据大小为：" + message.remaining());

        try (FileOutputStream fos = new FileOutputStream(outputFile, true)) {
            byte[] buffer = new byte[message.remaining()];
            message.get(buffer);
            fos.write(buffer);
            System.out.println("音频数据已写入本地文件" + outputFile + "中");
        } catch (IOException e) {
            System.err.println("音频数据写入本地文件失败：" + e.getMessage());
        }
    }

    @Override
    public void onClose(int code, String reason, boolean remote) {
        System.out.println("连接关闭：" + reason + " (" + code + ")");
    }

    @Override
    public void onError(Exception ex) {
        System.err.println("报错：" + ex.getMessage());
        ex.printStackTrace();
    }

    private void sendContinueTask(String text) {
        String command = "{ \"header\": { \"action\": \"continue-task\", \"task_id\": \"" + taskId + "\", \"streaming\": \"duplex\" }, \"payload\": { \"input\": { \"text\": \"" + text + "\" } }}";
        send(command);
    }

    private void sendFinishTask() {
        String command = "{ \"header\": { \"action\": \"finish-task\", \"task_id\": \"" + taskId + "\", \"streaming\": \"duplex\" }, \"payload\": { \"input\": {} }}";
        send(command);
    }

    private void closeConnection() {
        if (!isClosed()) {
            close();
        }
    }

    public static void main(String[] args) {
        try {
            // 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
            // 若没有配置环境变量，请用百炼API Key将下行替换为：String apiKey = "<API_KEY>"
            String apiKey = System.getenv("DASHSCOPE_API_KEY");
            if (apiKey == null || apiKey.isEmpty()) {
                System.err.println("请设置 DASHSCOPE_API_KEY 环境变量");
                return;
            }

            Map<String, String> headers = new HashMap<>();
            headers.put("Authorization", "bearer " + apiKey);
            // 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference/
            TTSWebSocketClient client = new TTSWebSocketClient(new URI("wss://dashscope.aliyuncs.com/api-ws/v1/inference/"), headers);

            client.connect();

            while (!client.isClosed() && !client.taskFinished) {
                Thread.sleep(1000);
            }
        } catch (Exception e) {
            System.err.println("连接WebSocket服务失败：" + e.getMessage());
            e.printStackTrace();
        }
    }
}
```

## Python

如您使用Python编程语言，建议采用Python DashScope SDK进行开发，详情请参见[Python SDK](https://help.aliyun.com/zh/model-studio/cosyvoice-python-sdk)。

以下是Python WebSocket的调用示例。在运行示例前，请确保通过如下方式导入依赖：

```
pip uninstall websocket-client
pip uninstall websocket
pip install websocket-client
```

**重要**

请不要将运行示例代码的Python文件命名为“websocket.py”，否则会报错（AttributeError: module 'websocket' has no attribute 'WebSocketApp'. Did you mean: 'WebSocket'?）。

```
# SSML功能说明：
#     1. 在发送run-task指令时，将参数enable_ssml设置为true，以开启SSML支持
#     2. 通过continue-task指令发送包含SSML的文本，且只允许发送一次continue-task指令
#     3. 只有cosyvoice-v3-flash、cosyvoice-v3-plus和cosyvoice-v2模型的复刻音色以及音色列表中标记为支持SSML的系统音色支持SSML功能（例如cosyvoice-v3-flash模型的longanyang音色）

import websocket
import json
import uuid
import os
import time


class TTSClient:
    def __init__(self, api_key, uri):
        """
    初始化 TTSClient 实例

    参数:
        api_key (str): 鉴权用的 API Key
        uri (str): WebSocket 服务地址
    """
        self.api_key = api_key  # 替换为你的 API Key
        self.uri = uri  # 替换为你的 WebSocket 地址
        self.task_id = str(uuid.uuid4())  # 生成唯一任务 ID
        self.output_file = f"output_{int(time.time())}.mp3"  # 输出音频文件路径
        self.ws = None  # WebSocketApp 实例
        self.task_started = False  # 是否收到 task-started
        self.task_finished = False  # 是否收到 task-finished / task-failed

    def on_open(self, ws):
        """
    WebSocket 连接建立时回调函数
    发送 run-task 指令开启语音合成任务
    """
        print("WebSocket 已连接")

        # 构造 run-task 指令
        run_task_cmd = {
            "header": {
                "action": "run-task",
                "task_id": self.task_id,
                "streaming": "duplex"
            },
            "payload": {
                "task_group": "audio",
                "task": "tts",
                "function": "SpeechSynthesizer",
                "model": "cosyvoice-v3-flash",
                "parameters": {
                    "text_type": "PlainText",
                    "voice": "longanyang",
                    "format": "mp3",
                    "sample_rate": 22050,
                    "volume": 50,
                    "rate": 1,
                    "pitch": 1,
                    # 如果enable_ssml设为True，只允许发送一次continue-task指令，否则会报错“Text request limit violated, expected 1.”
                    "enable_ssml": True
                },
                "input": {}
            }
        }

        # 发送 run-task 指令
        ws.send(json.dumps(run_task_cmd))
        print("已发送 run-task 指令")

    def on_message(self, ws, message):
        """
    接收到消息时的回调函数
    区分文本和二进制消息处理
    """
        if isinstance(message, str):
            # 处理 JSON 文本消息
            try:
                msg_json = json.loads(message)
                print(f"收到 JSON 消息: {msg_json}")

                if "header" in msg_json:
                    header = msg_json["header"]

                    if "event" in header:
                        event = header["event"]

                        if event == "task-started":
                            print("任务已启动")
                            self.task_started = True

                            # 发送 continue-task 指令，使用SSML功能时，该指令只允许发送一次
                            # 特殊字符需要进行转义
                            self.send_continue_task("<speak rate=\"2\">我的语速比正常人快。</speak>")

                            # continue-task 发送完成后发送 finish-task
                            self.send_finish_task()

                        elif event == "task-finished":
                            print("任务已完成")
                            self.task_finished = True
                            self.close(ws)

                        elif event == "task-failed":
                            error_msg = msg_json.get("error_message", "未知错误")
                            print(f"任务失败: {error_msg}")
                            self.task_finished = True
                            self.close(ws)

            except json.JSONDecodeError as e:
                print(f"JSON 解析失败: {e}")
        else:
            # 处理二进制消息（音频数据）
            print(f"收到二进制消息，大小: {len(message)} 字节")
            with open(self.output_file, "ab") as f:
                f.write(message)
            print(f"已将音频数据写入本地文件{self.output_file}中")

    def on_error(self, ws, error):
        """发生错误时的回调"""
        print(f"WebSocket 出错: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        """连接关闭时的回调"""
        print(f"WebSocket 已关闭: {close_msg} ({close_status_code})")

    def send_continue_task(self, text):
        """发送 continue-task 指令，附带要合成的文本内容"""
        cmd = {
            "header": {
                "action": "continue-task",
                "task_id": self.task_id,
                "streaming": "duplex"
            },
            "payload": {
                "input": {
                    "text": text
                }
            }
        }

        self.ws.send(json.dumps(cmd))
        print(f"已发送 continue-task 指令，文本内容: {text}")

    def send_finish_task(self):
        """发送 finish-task 指令，结束语音合成任务"""
        cmd = {
            "header": {
                "action": "finish-task",
                "task_id": self.task_id,
                "streaming": "duplex"
            },
            "payload": {
                "input": {}
            }
        }

        self.ws.send(json.dumps(cmd))
        print("已发送 finish-task 指令")

    def close(self, ws):
        """主动关闭连接"""
        if ws and ws.sock and ws.sock.connected:
            ws.close()
            print("已主动关闭连接")

    def run(self):
        """启动 WebSocket 客户端"""
        # 设置请求头部（鉴权）
        header = {
            "Authorization": f"bearer {self.api_key}",
            "X-DashScope-DataInspection": "enable"
        }

        # 创建 WebSocketApp 实例
        self.ws = websocket.WebSocketApp(
            self.uri,
            header=header,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )

        print("正在监听 WebSocket 消息...")
        self.ws.run_forever()  # 启动长连接监听


# 示例使用方式
if __name__ == "__main__":
    # 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
    # 若没有配置环境变量，请用百炼API Key将下行替换为：API_KEY = "<API_KEY>"
    API_KEY = os.environ.get("DASHSCOPE_API_KEY")
    # 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference/
    SERVER_URI = "wss://dashscope.aliyuncs.com/api-ws/v1/inference/"

    client = TTSClient(API_KEY, SERVER_URI)
    client.run()
```

## 标签

**说明**

阿里巴巴语音合成服务在实现 SSML 时参考了 [W3C](https://www.w3.org/TR/speech-synthesis/) SSML 1.0 规范，但在设计上更注重业务适配性。因此，并未完整支持所有标准标签，而是结合实际使用场景，实现了最具实用价值的标签集合。

-   所有使用 SSML 功能的文本内容必须包含在 `<speak></speak>` 标签内。
    
-   支持多个 `<speak>` 标签并列使用（如：`<speak></speak><speak></speak>`），但不支持嵌套结构（如：`<speak><speak></speak></speak>`）。
    
-   编码时，若标签内的文本内容包含 XML 特殊字符，需进行相应的字符转义。常见特殊字符及其转义形式如下：
    
    -   `"`（双引号） → `&quot;`
        
    -   `'`（单引号/撇号） → `&apos;`
        
    -   `&`（表示“和”的符号） → `&amp;`
        
    -   `<`（小于号） → &lt;
        
    -   `>`（大于号） → &gt;
        

### `<**speak**>`**：根节点**

-   描述
    
    `<speak>` 标签是所有 SSML 标签的根节点，任何使用 SSML 功能的文本内容都必须包含在 `<speak></speak>` 标签之间。
    
-   语法
    
    ```
     <speak>需要使用SSML功能的文本</speak>
    ```
    
-   属性
    
    | **属性名称** | **属性类型** | **是否必选** | **描述** |
    | --- | --- | --- | --- |
    | voice | String | 否   | 指定发音人（音色）。 优先级高于接口请求参数`voice`指定的发音人。 - 取值范围：具体的音色，详情请参见[cosyvoice-v2音色](https://help.aliyun.com/zh/model-studio/cosyvoice-java-sdk#da9ae03e5ek7b)。 - 示例： ``` <speak voice="longcheng_v2"> 我是男声。 </speak> ``` |
    | rate | String | 否   | 指定语速。优先级高于接口请求参数`speech_rate`指定的语速。 - 取值范围：\\[0.5,2\\]之间的小数 - 默认值：1 - 大于1表示加快语速 - 小于1表示减慢语速 - 示例： ``` <speak rate="2"> 我的语速比正常人快。 </speak> ``` |
    | pitch | String | 否   | 指定音高（语调）。优先级高于接口请求参数`pitch_rate`指定的音高（语调）。 - 取值范围：\\[0.5,2\\]之间的小数 - 默认值：1 - 大于1表示升高音高 - 小于1表示降低音高 - 示例： ``` <speak pitch="0.5"> 我的音高却比别人低。 </speak> ``` |
    | volume | String | 否   | 指定音量。优先级高于接口请求参数`volume`指定的音量。 - 取值范围：\\[0,100\\]之间的整数 - 默认值：50 - 大于50表示增大音量 - 小于50表示减小音量 - 示例： ``` <speak volume="80"> 我的音量也很大。 </speak> ``` |
    | effect | String | 否   | 指定音效。 - 取值范围： - robot：机器人音效 - lolita：萝莉音效 - lowpass：低通音效 - echo：回声音效 - eq：均衡器（高级） - lpfilter：低通滤波器（高级） - hpfilter：高通滤波器（高级） **说明** - eq、lpfilter、hpfilter是高级音效类型，您可以通过`effectValue`参数自定义其具体效果。 - 每个 SSML 标签仅支持配置一种音效，不允许多个 `effect` 属性共存。 - 使用音效功能会增加系统延时。 - 示例： ``` <speak effect="robot"> 你喜欢机器人瓦力吗？ </speak> ``` |
    | effectValue | String | 否   | 指定音效（`effect`参数）的具体效果。 - 取值范围： - `eq`（均衡器）：系统默认支持8个频率等级，对应频率如下： \\[“40 Hz”,“100 Hz”, “200 Hz”, “400 Hz”, “800 Hz”, “1600 Hz”, “4000 Hz”, “12000 Hz”\\]。 每个频段带宽均为1.0q。 使用时需通过 `effectValue` 参数指定每个频段的增益值，该参数为一个由 8 个整数组成的字符串，数值范围为 \\[-20, 20\\]，数字之间用空格分隔，数值为 `0` 表示不调整对应频率的增益。 例如：`effectValue="1 1 1 1 1 1 1 1"` - `lpfilter`（低通滤波器）：输入低通滤波器的频率值。取值为(0, 目标采样率/2\\]之间的整数。例如effectValue="800"。 - `hpfilter`（高通滤波器）：输入高通滤波器的频率值。取值为(0, 目标采样率/2\\]之间的整数。例如effectValue="1200"。 - 示例： ``` <speak effect="eq" effectValue="1 -20 1 1 1 1 20 1"> 你喜欢机器人瓦力吗？ </speak> <speak effect="lpfilter" effectValue="1200"> 你喜欢机器人瓦力吗？ </speak> <speak effect="hpfilter" effectValue="1200"> 你喜欢机器人瓦力吗？ </speak> ``` |
    | bgm | String | 否   | 为合成的语音添加指定的背景音乐。背景音文件需存储在阿里云 OSS 上（请参见[上传文件](https://help.aliyun.com/zh/oss/getting-started/upload-objects-16#concept-zx1-4p4-tdb)），且所在存储空间（Bucket）应至少具有公共读权限。 背景音乐URL中若包含 XML 特殊字符（如 `&`, `<`, `>` 等），需进行字符转义处理。 - 音频要求： 音频文件大小无上限，但较大的文件可能会增加下载耗时；若合成内容的时长超过背景音时长，背景音将自动循环播放以匹配合成音频长度。 - 采样率：16kHz - 声道数：单声道 - 文件格式：WAV 若原始音频非 WAV 格式，可使用 `ffmpeg` 工具进行转换： ``` ffmpeg -i 输入音频 -acodec pcm_s16le -ac 1 -ar 16000 输出.wav ``` - 位深度：16位 - 示例： ``` <speak bgm="http://nls.alicdn.com/bgm/2.wav" backgroundMusicVolume="30" rate="-500" volume="40"> <break time="2s"/> 阴崖老木苍苍烟 <break time="700ms"/> 雨声犹在竹林间 <break time="700ms"/> 绵蕝固知裨国计 <break time="700ms"/> 绵州风物总堪怜 <break time="2s"/> </speak> ``` **重要** 您需要对上传的音频版权承担相应的法律责任。 |
    | backgroundMusicVolume | String | 否   | 指定背景音乐的音量。和`backgroundMusicVolume`属性搭配使用。 |
    
-   标签关系
    
    <speak>标签可以包含文本和其他标签：
    
    -   [控制停顿时间](#title-722-sn2-4x8)
        
    -   [替换文本](#title-4jk-q1t-jwz)
        
    -   [指定发音（拼音/音标）](#title-m9h-7yc-48k)
        
    -   [插入一段外部声音（铃声、猫叫等）](#title-al9-xs8-oer)
        
    -   [设置文本的读法（数字、日期、电话号码等）](#title-xt2-m52-1uk)
        
-   更多示例
    
    -   空属性
        
        ```
        <speak>
          需要调用SSML标签的文本
        </speak>
        ```
        
    -   属性组合（空格分隔）
        
        ```
        <speak rate="200" pitch="-100" volume="80">
          所以放在一起，我的声音是这样的。
        </speak>
        ```
        

### <break>：控制停顿时间

-   描述
    
    在语音合成过程中添加一段静默时间，模拟自然说话中的停顿效果。支持秒（s）或毫秒（ms）单位设置。该标签是可选标签。
    
-   语法
    
    ```
    # 空属性
    <break/>
    # 带time属性
    <break time="string"/>
    ```
    
-   属性
    
    **说明**
    
    使用无属性的<break>标签时，停顿时长为“1s”。
    
    | **属性名称** | **属性类型** | **是否必选** | **描述** |
    | --- | --- | --- | --- |
    | time | String | 否   | 以秒/毫秒为单位设置停顿的时长 （如“2s”、“50ms”）。 - 取值范围： - 以秒（s）为单位，取值范围为\\[1, 10\\]之间的整数 - 以毫秒（ms）为单位，取值范围为\\[50, 10000\\]之间的整数 - 示例： ``` <speak> 请闭上眼睛休息一下<break time="500ms"/>好了，请睁开眼睛。 </speak> ``` **重要** 当连续使用多个 `<break>` 标签时，总的停顿时长为各个标签指定时间的累加。若总时长超过 10 秒，则仅生效前 10 秒。 如下所示，该段 SSML 中 `<break>` 标签累计时长为 15 秒，超过 10 秒限制，最终停顿时长将被截断为 10 秒： ``` <speak> 请闭上眼睛休息一下<break time="5s"/><break time="5s"/><break time="5s"/>好了，请睁开眼睛。 </speak> ``` |
    
-   标签关系
    
    <break>是空标签，不能包含任何标签。
    

### <sub>：替换文本

-   描述
    
    将某段文本替换为指定的更适合朗读的文本。例如将 “W3C” 读成 “网络协议标准”。该标签是可选标签。
    
-   语法
    
    ```
    <sub alias="string"></sub>
    ```
    
-   属性
    
    | **属性名称** | **属性类型** | **是否必选** | **描述** |
    | --- | --- | --- | --- |
    | alias | String | 是   | 将某段文本替换为更适合朗读的文本。 示例： ``` <speak> <sub alias="网络协议标准">W3C</sub> </speak> ``` |
    
-   标签关系
    
    <sub>标签仅可以包括文本。
    

### <phoneme>：指定发音（拼音/音标）

-   描述
    
    控制某段文本的具体发音方式，中文可用拼音，英文可用音标（如 CMU），适用于需要精准发音的场景。该标签是可选标签。
    
-   语法
    
    ```
    <phoneme alphabet="string" ph="string">文本</phoneme>
    ```
    
-   属性
    
    | **属性名称** | **属性类型** | **是否必选** | **描述** |
    | --- | --- | --- | --- |
    | alphabet | String | 是   | 指定发音类型：拼音（对应中文）或音标（对应英文）。 取值范围： - "py"：拼音 - "cmu"：音标，参见[The CMU Pronouncing Dictionary](http://www.speech.cs.cmu.edu/cgi-bin/cmudict) |
    | ph  | String | 是   | 指定具体的拼音或音标： - 字与字的拼音用空格分隔，拼音的数目必须与字数一致。 - 每个拼音由发音部分和音调组成，其中音调为 `1` 到 `5` 的整数，`5` 表示轻声。 - 示例： ``` <speak> 去<phoneme alphabet="py" ph="dian3 dang4 hang2">典当行</phoneme>把这个玩意<phoneme alphabet="py" ph="dang4 diao4">当掉</phoneme> </speak> <speak> How to spell <phoneme alphabet="cmu" ph="S AY N">sin</phoneme>? </speak> ``` |
    
-   标签关系
    
    <phoneme>标签仅包括文本。
    

### <soundEvent>：插入一段外部声音（铃声、猫叫等）

-   描述
    
    支持在语音中插入音效文件，如提示音、环境音等，增强语音表达的丰富性。该标签是可选标签。
    
-   语法
    
    ```
     <soundEvent src="URL"/>
    ```
    
-   属性
    
    | **属性名称** | **属性类型** | **是否必选** | **描述** |
    | --- | --- | --- | --- |
    | src | String | 是   | 设置外部音频URL。 音频文件需存储在阿里云 OSS 上（请参见[上传文件](https://help.aliyun.com/zh/oss/getting-started/upload-objects-16#concept-zx1-4p4-tdb)），且所在存储空间（Bucket）应至少具有公共读权限。URL中若包含 XML 特殊字符（如 `&`, `<`, `>` 等），需进行字符转义处理。 - 音频要求： - 采样率：16kHz - 声道数：单声道 - 文件格式：WAV 若原始音频非 WAV 格式，可使用 `ffmpeg` 工具进行转换： ``` ffmpeg -i 输入音频 -acodec pcm_s16le -ac 1 -ar 16000 输出.wav ``` - 文件大小：不超过2MB - 位深度：16位 - 示例： ``` <speak> 一匹马受了惊吓<soundEvent src="http://nls.alicdn.com/sound-event/horse-neigh.wav"/>人们四散躲避 </speak> ``` **重要** 您需要对上传的音频版权承担相应的法律责任。 |
    
-   标签关系
    
    <soundEvent>是空标签，不可以包含任何标签。
    

### <say-as>：设置文本的读法（数字、日期、电话号码等）

-   描述
    
    告诉大模型文本是什么类型，并按该类型的常规读法进行朗读。该标签是可选标签。
    
-   语法
    
    ```
     <say-as interpret-as="string">文本</say-as>
    ```
    
-   属性
    
    | **属性名称** | **属性类型** | **是否必选** | **描述** |
    | --- | --- | --- | --- |
    | interpret-as | String | 是   | 指示出标签内文本的信息类型。 取值范围： - cardinal：按整数或小数的常见读法朗读 - digits：按数字逐个读出（如：123 → 一二三） - telephone：按电话号码的常用方式读出 - name：按人名的常规读法朗读 - address：按地址的常见方式读出 - id：适用于账户名、昵称等，按常规读法处理 - characters：将标签内的文本按字符一一读出 - punctuation：将标签内的文本按标点符号的方式读出来 - date：按日期格式的常见读法朗读 - time：按时间格式的常见方式读出 - currency：按金额的常见读法处理 - measure：按计量单位的常见方式读出 |
    
-   各<say-as>类型支持范围
    
    -   cardinal
        
        | **格式** | **示例** | **中文输出** | **说明** |
        | --- | --- | --- | --- |
        | 数字串 | 145 | 一百四十五 | 整数输入范围：20位以内的正负整数，\\[-99999999999999999999,99999999999999999999\\]。 小数输入范围：对小数点后小数的位数没有特殊限制，建议不超过10位。 |
        | 负号+数字串 | \\-145 | 负一百四十五 |
        | 以逗号分隔3位数字串 | 10,000 | 一万  |
        | 负号+以逗号分隔3位数字串 | \\-10,124 | 负一万一百二十四 |
        | 数字串+小数点+2个零 | 10.00 | 十   |
        | 负号+数字串+小数点+2个零 | \\-110.00 | 负一百一十 |
        | 数字串+小数点+数字串 | 79.090 | 七十九点零九零 |
        | 负号+数字串+小数点+数字串 | \\-79.001 | 负七十九点零零一 |
        
        | **格式** | **示例** | **英文输出** | **说明** |
        | --- | --- | --- | --- |
        | 数字串 | 145 | one hundred forty five | 整数输入范围：13位以内的正负整数，\\[-999999999999,999999999999\\]。 小数输入范围：对小数点后小数的位数没有特殊限制，建议不超过10位。 |
        | 以零开头的数字串 | 0145 | one hundred forty five |
        | 负号+数字串 | \\-145 | minus hundred forty five |
        | 以逗号分隔三位数字串 | 60,000 | sixty thousand |
        | 负号+以逗号分隔三位数字串 | \\-208,000 | minus two hundred eight thousand |
        | 数字串+小数点+零 | 12.00 | twelve |
        | 数字串+小数点+数字串 | 12.34 | twelve point three four |
        | 以逗号分隔三位数字串+小数点+数字串 | 1,000.1 | one thousand point one |
        | 负号+数字串+小数点+数字串 | \\-12.34 | minus twelve point three four |
        | 负号+以逗号分隔三位数字串+小数点+数字串 | \\-1,000.1 | minus one thousand point one |
        | （以逗号分隔三位）数字串+连词符+（以逗号分隔三位）数字 | 1-1,000 | one to one thousand |
        | 其他默认读法 | 012.34 | twelve point three four | 无   |
        | 1/2 | one half |
        | \\-3/4 | minus three quarters |
        | 5.1/6 | five point one over six |
        | \\-3 1/2 | minus three and a half |
        | 1,000.3^3 | one thousand point three to the power of three |
        | 3e9.1 | three times ten to the power of nine point one |
        | 23.10% | twenty three point one percent |
        
    -   digits
        
        | **格式** | **示例** | **中文输出** | **说明** |
        | --- | --- | --- | --- |
        | 数字串 | 129090909 | 一二九零九零九零九 | 对数字串的长度没有特殊限制，建议不超过20位。 当数字串超过10位时，每个数字后插入停顿。 |
        
        | **格式** | **示例** | **英文输出** | **说明** |
        | --- | --- | --- | --- |
        | 数字串 | 12034 | one two zero three four | 对数字串的长度没有特殊限制，建议不超过20位。 当数字串以空格或连词符分组时，分组之间会插入逗号而产生适当停顿，支持最长5个分组。 |
        | 数字串+空格或连词符+数字串+空格或连词符+数字串+空格或连词符+数字串 | 1-23-456 7890 | one, two three, four five six, seven eight nine zero |
        
    -   telephone
        
        | **格式** | **示例** | **中文输出** | **说明** |
        | --- | --- | --- | --- |
        | 座机号 | 4930286 | 四九三 零二八六 | 支持7~8位座机号，支持空格和“-”作为分隔符。 其中，7位座机号支持“3-4”的数字分隔方式；8位座机号支持“4-4”的数字分隔方式。 |
        | 493 0286 | 四九三 零二八六 |
        | 493-0286 | 四九三 零二八六 |
        | 62552560 | 六二五五 二五六零 |
        | 6255 2560 | 六二五五 二五六零 |
        | 6255-2560 | 六二五五 二五六零 |
        | 座机号+分机号 | 4930286-109 | 四九三 零二八六 转幺零九 | 支持1~4位分机号。 |
        | 4930286转109 | 四九三 零二八六 转幺零九 |
        | 4930286分机109 | 四九三 零二八六 分机幺零九 |
        | 4930286分机号109 | 四九三 零二八六 分机号幺零九 |
        | 区号+座机号 | 01062552560 | 零幺零 六二五五 二五六零 | 支持区号：010、02x、03xx、04xx、05xx、07xx、08xx、09xx。 |
        | 010 62552560 | 零幺零 六二五五 二五六零 |
        | 010 6255 2560 | 零幺零 六二五五 二五六零 |
        | 010 6255-2560 | 零幺零 六二五五 二五六零 |
        | 010-62552560 | 零幺零 六二五五 二五六零 |
        | 010-6255-2560 | 零幺零 六二五五 二五六零 |
        | (010)62552560 | 零幺零 六二五五 二五六零 |
        | 03198907098 | 零三幺九 八九零 七零九八 |
        | 0319-8907098 | 三幺九 八九零 七零九八 |
        | 区号+座机号+分机号 | 010 62552560-109 | 零幺零 六二五五 二五六零 转幺零九 | 无   |
        | 010-62552560-109 | 零幺零 六二五五 二五六零 转幺零九 |
        | (010)62552560-109 | 零幺零 六二五五 二五六零 转幺零九 |
        | (010)62552560转109 | 零幺零 六二五五 二五六零 转幺零九 |
        | (010)62552560分机109 | 零幺零 六二五五 二五六零 分机幺零九 |
        | (010)62552560分机号109 | 零幺零 六二五五 二五六零 分机号幺零九 |
        | 国家代码+区号+座机号 | 86-010-62791627 | 八六 零幺零 六二七九 幺六二七 | 支持国家代码：86、 (86)、+86、(+86)、0086。并统一读为“八六”。 |
        | (86)10-62791627 | 八六 幺零 六二七九 幺六二七 |
        | +86-010-62791627 | 八六 零幺零 六二七九 幺六二七 |
        | 0086-10-62791627 | 八六 幺零 六二七九 幺六二七 |
        | (+86)-10-6279 1627 | 八六 幺零 六二七九 幺六二七 |
        | 国家代码+区号+座机号+分机号 | (86)21-58118818-207 | 八六 二幺 五八幺幺 八八幺八 转二零七 | 无   |
        | (86)021-5811-8818-207 | 八六 零二幺 五八幺幺 八八幺八 转二零七 |
        | (86)021-58118818转207 | 八六 零二幺 五八幺幺 八八幺八 转二零七 |
        | (86)21-5811-8818分机207 | 八六 二幺 五八幺幺 八八幺八 分机二零七 |
        | +86-021-58118818分机号207 | 八六 零二幺 五八幺幺 八八幺八分机号二零七 |
        | 手机号 | 139 0000 5678 | 幺三九 零零零零 五六七八 | 支持11位手机号，支持3-3-5、3-4-4两种数字分隔方式 |
        | 139-000-05678 | 幺三九 零零零 零五六七八 |
        | 139 000 05678 | 幺三九 零零零 零五六七八 |
        | 国家代码+手机号 | +86-13900005678 | 八六 幺三九 零零零零 五六七八 | 无   |
        | (+86)-139-0000-5678 | 八六 幺三九 零零零零 五六七八 |
        | +8613900005678 | 八六 幺三九 零零零零 五六七八 |
        | 0086-139 000 05678 | 八六 幺三九 零零零 零五六七八 |
        | 服务号 | 123 | 幺二三 | - 支持常用的服务号。 - 支持以400/800开头的10位服务号，支持以“3-3-4”的数字分隔方式。 - 支持以12530/17951/12593开头的16位号码。 |
        | 95678 | 九五六七八 |
        | 4008110510 | 四零零 八幺幺 零五幺零 |
        | 800-810-8888 | 八零零 八幺零 八八八八 |
        | 1253013520638377 | 幺二五三零 幺三五 二零六三 八三七七 |
        | 其他  | (86)(21)9899-80800-0909 | 八六 二幺 九八九九 八零八零零 零九零九 | 支持“数字串+分隔符（左右括号、-）”方式。 |
        
        | **格式** | **示例** | **英文输出** | **说明** |
        | --- | --- | --- | --- |
        | 数字串 | 12034 | one two oh three four | 对数字串的长度没有特殊限制，建议不超过20位。当数字串以空格或连词符分组时，分组之间会插入逗号而产生适当停顿，支持最长5个分组。 |
        | 数字串+空格或连词符+数字串+空格或连词符+数字串 | 1-23-456 7890 | one, two three, four five six, seven eight nine oh |
        | 加号+数字串+空格或连词符+数字串 | +43-211-0567 | plus four three, two one one, oh five six seven |
        | 左括号+数字串+右括号+空格+数字串+空格或连词符+数字串 | (21) 654-3210 | (two one) six five four, three two one oh |
        
    -   address
        
        | **格式** | **示例** | **中文输出** | **说明** |
        | --- | --- | --- | --- |
        | 常用地址格式 | 元和镇嘉元30-9 | 元和镇嘉元三十杠九 | 支持常用地址格式。此处地址指标准的邮寄地址。 |
        | 市台路388弄1107-1108号 | 市台路三八八弄幺幺零七杠幺幺零八号 |
        | 华润二十四城六期锦云府3-1-3205 | 华润二十四城六期锦云府三杠一杠三二零五 |
        | 圣华名都大厦2幢2006室 | 圣华名都大厦二幢二零零六室 |
        | 五常街道庭院5幢4单元201 | 五常街道庭院五幢四单元二零幺 |
        | 芙蓉江路150弄19号 | 芙蓉江路幺五零弄十九号 |
        
        英文文本不支持该标签。
        
    -   id
        
        | **格式** | **示例** | **输出** | **说明** |
        | --- | --- | --- | --- |
        | 字符串 | dell0101 | D E L L 零 一 零 一 | 大小写英文字符、阿拉伯数字0~9、下划线。 输出的空格表示每个字符之间插入停顿，即字符一个一个地读。 |
        | myid\\_1998 | M Y I D 下划线 一 九 九 八 |
        | AiTest | A I T E S T |
        
        英文文本该标签功能同标签characters。
        
    -   characters
        
        | **格式** | **示例** | **中文输出** | **说明** |
        | --- | --- | --- | --- |
        | 字符串 | ISBN 1-001-099098-1 | I S B N 一 杠 零 零 一 杠 零 九 九 零 九 八 杠 一 | 支持中文汉字、大小写英文字符、阿拉伯数字0~9以及部分全角和半角字符。 输出的空格表示每个字符之间插入停顿，即字符一个一个地读。标签内的文本如果包含XML的特殊字符，需要做字符转义。 |
        | x10b2345\\_u | x 一 零 b 二 三 四 五 下划线 u |
        | v1.0.1 | v 一 点 零 点 一 |
        | 版本号2.0 | 版本号二 点 零 |
        | 苏M MA000 | 苏M M A 零 零 零 |
        | 空中客车A330 | 空中客车A 三 三 零 |
        | 型号s01 s02和s03 | 型号s 零 一 s 零二 和s 零 三 |
        | 空中客车A330 | 空中客车A 三 三 零 |
        | αβγ | 阿尔法 贝塔 伽玛 |
        
        | **格式** | **示例** | **英文输出** | **说明** |
        | --- | --- | --- | --- |
        | 字符串 | \\*b+3$.c-0'=α | asterisk B plus three dollar dot C dash zero apostrophe equals alpha | 支持中文汉字、大小写英文字符、阿拉伯数字0~9以及部分全角和半角字符。 输出的空格表示每个字符之间插入停顿，即字符一个一个地读。 标签内的文本如果包含XML的特殊字符，需要做字符转义。 |
        
    -   punctuation
        
        | **格式** | **示例** | **中文输出** | **说明** |
        | --- | --- | --- | --- |
        | 标点符号 | …   | 省略号 | 支持常见中英文标点。输出的空格表示每个字符之间插入停顿，即字符一个一个地读。 标签内的文本如果包含XML的特殊字符，需要做字符转义。 |
        | ……  | 省略号 |
        | !"#$%& | 叹号 双引号 井号 dollar 百分号 and |
        | ‘()\\*+ | 单引号 左括号 右括号 星号 加号 |
        | ,-./:; | 逗号 杠 点 斜杠 冒号 分号 |
        | <=>?@ | 小于 等号 大于 问号 at |
        | \\[\\\\\\]^\\_ | 左方括号 反斜线 右方括号 脱字符 下划线 |
        
        英文文本该标签功能同标签characters。
        
    -   date
        
        | **格式** | **示例** | **中文输出** | **说明** |
        | --- | --- | --- | --- |
        | xx年 | 71年 | 七一年 | 支持2位和4位年份。其中： - 2位年份支持60年~99年、00年~09年、10年~19年。 - 4位年份支持1000年~1999年、2000年~2099年。 |
        | 04年 | 零四年 |
        | 19年 | 一九年 |
        | 1011年 | 一零一一年 |
        | 1998年 | 一九九八年 |
        | 2008年 | 二零零八年 |
        | xx年xx月 | 98年4月 | 九八年四月 | 当月份为1到9月时，支持开头带“0”和不带“0”两种写法。例如“1908年4月”和“1908年04月”。 |
        | 1998年04月 | 一九九八年四月 |
        | 08年8月 | 零八年八月 |
        | 2008年8月 | 二零零八年八月 |
        | xx年xx月xx日xx年xx月xx号 | 98年4月23日 | 九八年四月二十三日 | 当日期为1到9日时，支持开头带“0”和不带“0”两种写法。例如“1908年4月8日”和“1908年04月08日”。 |
        | 1998年04月23日 | 一九九八年四月二十三日 |
        | 08年8月8号 | 零八年八月八号 |
        | 2008年08月08号 | 二零零八年八月八号 |
        | xx年xx月xx日xx年xx月xx号 | 98年4月23日 | 九八年四月二十三日 | 当日期为1到9日时，支持开头带“0”和不“0”两种写法。例如“1908年4月8日”和“1908年04月08日”。 |
        | 1998年04月23日 | 一九九八年四月二十三日 |
        | 08年8月8号 | 零八年八月八号 |
        | 2008年08月08号 | 二零零八年八月八号 |
        | xx月xx号 | 3月20日 | 三月二十日 | 无   |
        | 08月07号 | 八月七号 |
        | 年月缩写 | 2018/08 | 二零一八年八月 | 支持“/”、“-”、“.”作为缩写的分隔符。 |
        | 2018-08 | 二零一八年八月 |
        | 2018.08 | 二零一八年八月 |
        | 年月日缩写 | 2018/08/08 | 二零一八年八月八日 |
        | 2018-8-8 | 二零一八年八月八日 |
        | 2018.08.08 | 二零一八年八月八日 |
        | xx年xx月xx日~xx年xx月xx日xx年xx月xx号~xx年xx月xx号 | 04年9月1日~30日 | 零四年九月一日至三十日 | 支持“~”、“-”作为“至”的缩写标志。 |
        | 2004年09月01号-2008年06月08号 | 二零零四年九月一号至二零零八年六月八号 |
        | xx年xx月xx日~xx日xx年xx月xx号~xx号 | 04年9月1日~30日 | 零四年九月一日至三十日 |
        | 2004年09月01号-2008年06月08号 | 二零零四年九月一号至二零零八年六月八号 |
        | xx年xx月~xx年xx月 | 01年04月~10年04月 | 零一年四月至一零年四月 |
        | 2001年04月~2010年04月 | 二零零一年四月至二零一零年四月 |
        | xx月xx日~xx月xx日xx月xx号~xx月xx号 | 10月1日~10月7日 | 十月一日至十月七日 |
        | 10月01号~10月07号 | 十月一号至十月七号 |
        | xx月xx日~xx日xx月xx号~xx号 | 10月1日~7日 | 十月一日至七日 |
        | 10月01号~07号 | 十月一号至七号 |
        | 年月日缩写~年月日缩写 | 2018/03/03~2019/01/01 | 二零一八年三月三日至二零一九年一月一日 | 支持“/”、“.”作为缩写的分隔符，支持“~”、“-”作为“至”的缩写标志。 |
        | 1997.9.9~1998.9.9 | 一九九七年九月九日至一九九八年九月九日 |
        | 月日缩写~月日缩写 | 10/20~10/31 | 十月二十日至十月三十一日 |
        | xx~xx月xx月~xx月 | 1~10月 | 一至十月 |
        | 1月~10月 | 一月至十月 |
        | 月日年缩写 | 10/20/2018 | 二零一八年十月二十日 | 仅支持4位的年份，仅支持“/”作为日期的分隔符，仅支持“月/日/年”的书写方式。 |
        
        | **格式** | **示例** | **英文输出** | **说明** |
        | --- | --- | --- | --- |
        | 四位数字/两位数字或四位数字-两位数字 | 2000/01 | two thousand, oh one | 跨年度。 |
        | 1900-01 | nineteen hundred, oh one |
        | 2001-02 | twenty oh one, oh two |
        | 2019-20 | twenty nineteen, twenty |
        | 1998-99 | nineteen ninety eight, ninety nine |
        | 1999-00 | nineteen ninety nine, oh oh |
        | 以1或2开头的四位数字 | 2000 | two thousand | 四位数字年份。 |
        | 1900 | nineteen hundred |
        | 1905 | nineteen oh five |
        | 2021 | twenty twenty one |
        | 星期几-星期几 或 星期几~星期几 或 星期几&星期几 | mon-wed | monday to wednesday | 星期几的范围标签内的文本如果包含XML的特殊字符，需要做字符转义。 |
        | tue~fri | tuesday to friday |
        | sat&sun | saturday and sunday |
        | DD-DD MMM, YYYY 或 DD~DD MMM, YYYY 或 DD&DD MMM, YYYY | 19-20 Jan, 2000 | the nineteen to the twentieth of january two thousand | DD表示两位数字日期，MMM表示月份的三字母缩写或完整单词，YYYY表示以1或2开头的四位数字年份。 |
        | 01 ~ 10 Jul, 2020 | the first to the tenth of july twenty twenty |
        | 05&06 Apr, 2009 | the fifth and the sixth of april two thousand nine |
        | MMM DD-DD 或 MMM DD~DD 或 MMM DD&DD | Feb 01 - 03 | feburary the first to the third | MMM表示月份的三字母缩写或完整单词，DD表示两位数字日期。 |
        | Aug 10~20 | august the tenth to the twentieth |
        | Dec 11&12 | december the eleventh and the twelfth |
        | MMM-MMM 或 MMM~MMM 或 MMM&MMM | Jan-Jun | january to june | MMM表示月份的三字母缩写或完整单词。 |
        | jul ~ dec | july to december |
        | sep&oct | september and october |
        | YYYY-YYYY 或 YYYY~YYYY | 1990 - 2000 | nineteen ninety to two thousand | YYYY表示以1或2开头的四位数字年份。 |
        | 2001~2021 | two thousand one to twenty twenty one |
        | WWW DD MMM YYYY | Sun 20 Nov 2011 | sunday the twentieth of november twenty eleven | WWW表示星期几的三字母缩写或完整单词，DD表示两位数字日期，MMM表示月份的三字母缩写或完整单词，MM表示两位数字月份（或三字母缩写或完整单词），YYYY表示以1或2开头的四位数字年份。 |
        | WWW DD MMM | Sun 20 Nov | sunday the twentieth of november |
        | WWW MMM DD YYYY | Sun Nov 20 2011 | sunday november the twentieth twenty eleven |
        | WWW MMM DD | Sun Nov 20 | sunday november the twentieth |
        | WWW YYYY-MM-DD | Sat 2010-10-01 | aturday october the first twenty ten |
        | WWW YYYY/MM/DD | Sat 2010/10/01 | saturday october the first twenty ten |
        | WWW MM/DD/YYYY | Sun 11/20/2011 | sunday november the twentieth twenty eleven |
        | MM/DD/YYYY | 11/20/2011 | november the twentieth twenty eleven |
        | YYYY | 1998 | nineteen ninety eight |
        | 其他默认读法 | 10 Mar, 2001 | the tenth of march two thousand one | 无   |
        | 10 Mar | the tenth of march |
        | Mar 2001 | march two thousand one |
        | Fri. 10/Mar/2001 | friday the tenth of march two thousand one |
        | Mar 10th, 2001 | march the tenth two thousand one |
        | Mar 10 | march the tenth |
        | 2001/03/10 | march the tenth two thousand one |
        | 2001-03-10 | march the tenth two thousand one |
        | 2000s | two thousands |
        | 2010's | twenty tens |
        | 1900's | nineteen hundreds |
        | 1990s | nineteen nineties |
        
    -   time
        
        | **格式** | **示例** | **中文输出** | **说明** |
        | --- | --- | --- | --- |
        | 时刻  | 12:00 | 十二点 | 支持常用时间和时间范围格式。 |
        | 12:00:00点 | 十二点 |
        | 10:20分 | 十点二十分 |
        | 10:20:30 | 十点二十分三十秒 |
        | 09:18:14 | 九点十八分十四秒 |
        | 时刻~时刻 | 11:00~12:00 | 十一点到十二点 |
        | 09:00-14:00 | 九点到十四点 |
        | 11:00~11:30 | 十一点到十一点三十分 |
        | 11:00-12:18 | 十一点到十二点十八分 |
        | 10:30~11:00 | 十点三十分到十一点 |
        | 09:28-10:00 | 九点二十八分到十点 |
        | 10:20~11:20 | 十点二十分到十一点二十分 |
        | 06:00~08:00 | 六点到八点 |
        | 上午10:20~下午13:30 | 上午十点二十分到下午十三点三十分 |
        | 时间缩写 | 5:00 am | 凌晨五点整 |
        | 5:30 am | 凌晨五点半 |
        | 5:20:12 am | 凌晨五点二十分十二秒 |
        | 7:00 am | 上午七点整 |
        | 7:30 AM | 上午七点半 |
        | 7:20:12 a.m. | 上午七点二十分十二秒 |
        | 07:08:12 A.M. | 上午七点零八分十二秒 |
        | 5:00 pm | 下午五点整 |
        | 5:30 PM | 下午五点半 |
        | 5:20:12 p.m. | 下午五点二十分十二秒 |
        | 05:09:12 P.M. | 下午五点零九分十二秒 |
        | 9:00 pm | 晚上九点整 |
        | 9:30 pm | 晚上九点半 |
        | 9:20:12 PM | 晚上九点二十分十二秒 |
        | 9:02:12 P.M. | 晚上九点零二分十二秒 |
        | 12:00 pm | 中午十二点整 |
        | 12:30 p.m. | 中午十二点半 |
        | 12:20:12 PM | 中午十二点二十分十二秒 |
        
        | **格式** | **示例** | **英文输出** | **说明** |
        | --- | --- | --- | --- |
        | HH:MM AM或PM | 09:00 AM | nine A M | HH表示一或两位数字小时，MM表示两位数字分钟，AM/PM表示上/下午。 |
        | 09:03 PM | nine oh three P M |
        | 09:13 p.m. | nine thirteen p m |
        | HH:MM | 21:00 | twenty one hundred |
        | HHMM | 100 | one oclock |
        | 时刻-时刻 | 8:00 am - 05:30 pm | eight a m to five p m | 支持常见时间格式和范围。 |
        | 7:05~10:15 AM | seven oh five to ten fifteen A M |
        | 09:00-13:00 | nine oclock to thirteen hundred |
        
    -   currency
        
        | **格式** | **示例** | **中文输出** | **说明** |
        | --- | --- | --- | --- |
        | 数字+金额标识符 | 12.00 RMB | 十二人民币 | 支持AUD（澳元） 、CAD（加元）、 HKD（港币）、JPY（日元）、USD（美元）、CHF（瑞士法郎）、NOK（挪威克朗）、SEK（瑞典克朗）、GBP（英镑）、 RMB（人民币）、CNY（元）和EUR（欧元）。 支持的数字格式包括：整数、小数以及以逗号分隔的国际写法。 |
        | 12.50 RMB | 十二点五零人民币 |
        | 12,000,000 RMB | 一千二百万人民币 |
        | 12,000,000.00 RMB | 一千二百万人民币 |
        | 12,000.35 RMB | 一万两千点三五人民币 |
        | 金额标识符+数字 | $12 | 十二美元 | 支持 CAD（加元）、 $（美元）、Fr（法郎）、kr（丹麦克朗）、 £（英镑）、¥（元）和 €（欧元）。 支持的数字格式包括：整数、小数以及以逗号分隔的国际写法。 |
        | $12.00 | 十二美元 |
        | $12.12 | 二点一二美元 |
        | $12,000 | 一万两千美元 |
        | $12,000.00 | 一万两千美元 |
        | $12,000.99 | 一万两千点九九美元 |
        | 其他默认读法 | 1213 | 一千二百一十三 | 无   |
        | 1213 KML | 一千二百一十三K M L |
        | 1213.00 KML | 一千二百一十三K M L |
        | 1213.9 KML | 一千二百一十三点九K M L |
        | 1,000 KML | 一千K M L |
        | 1,000.00 KML | 一千K M L |
        | 1,000.98 KML | 一千点九八K M L |
        | 12,000 | 一万两千 |
        
        | **格式** | **示例** | **英文输出** | **说明** |
        | --- | --- | --- | --- |
        | 数字+金额识别符 | 1.00 RMB | one yuan | 支持的数字格式：整数、小数以及以逗号分隔的国际写法。 支持的金额识别符： CN¥ (yuan) CNY (yuan) RMB (yuan) AUD (australian dollar) CAD (canadian dollar) CHF (swiss franc) DKK (danish krone) EUR (euro) GBP (british pound) HKD (Hong Kong(China) dollar) JPY (japanese yen) NOK (norwegian krone) SEK (swedish krona) SGD (singapore dollar) USD (united states dollar) |
        | 2.02 CNY | two point zero two yuan |
        | 1,000.23 CN¥ | one thousand point two three yuan |
        | 1.01 SGD | one singapore dollar and one cent |
        | 2.01 CAD | two canadian dollars and one cent |
        | 3.1 HKD | three hong kong dollars and ten cents |
        | 1,000.00 EUR | one thousand euros |
        | 金额识别符+数字 | US$ 1.00 | one US dollar | 支持的数字格式：整数、小数以及以逗号分隔的国际写法。 支持的金额识别符： US$ (US dollar) CA$ (Canadian dollar) AU$ (Australian dollar) SG$ (Singapore dollar) HK$ (Hong Kong dollar) C$ (Canadian dollar) A$ (Australian dollar) $ (dollar) £ (pound) € (euro) CN¥ (yuan) CNY (yuan) RMB (yuan) AUD (australian dollar) CAD (canadian dollar) CHF (swiss franc) DKK (danish krone) EUR (euro) GBP (british pound) HKD (Hong Kong(China) dollar) JPY (japanese yen) NOK (norwegian krone) SEK (swedish krona) SGD (singapore dollar) USD (united states dollar) |
        | $0.01 | one cent |
        | JPY 1.01 | one japanese yen and one sen |
        | £1.1 | one pound and ten pence |
        | €2.01 | two euros and one cent |
        | USD 1,000 | one thousand united states dollars |
        | 数字+量词+金额识别符 或 金额识别符+数字+量词 | 1.23 Tn RMB | one point two three trillion yuan | 支持的量词格式包括： thousand million billion trillion Mil (million) mil (million) Bil (billion) bil (billion) MM (million) Bn (billion) bn (billion) Tn (trillion) tn (trillion) K(thousand) k (thousand) M (million) m (million) |
        | $1.2 K | one point two thousand dollars |
        
    -   measure
        
        | **格式** | **示例** | **中文输出** | **说明** |
        | --- | --- | --- | --- |
        | 数字+中文单位 | 2片  | 两片  | 支持常见中文单位及单位缩写。 |
        | 120公顷 | 一百二十公顷 |
        | 100多毫克 | 一百多毫克 |
        | 100来米 | 一百来米 |
        | 100余人 | 一百余人 |
        | 1厘米20毫米 | 一厘米二十毫米 |
        | 120.00平方公里 | 一百二十平方公里 |
        | 数字+单位缩写 | 120.56 cm² | 一百二十点五六平方厘米 |
        | 120 ㎡ 56 cm² | 一百二十平方米五十六平方厘米 |
        | 100 m 12 cm 6 mm | 一百米十二厘米六毫米 |
        | 范围  | 10~15 kg | 十至十五千克 |
        | 10.24~789.82亩 | 十点二四至七百八十九点八二亩 |
        | 10米~15米 | 十米至十五米 |
        | 10.24 cm~19.08 cm | 十点二四厘米至十九点零八厘米 |
        | 数字+单位+"/"+单位 | 10元/斤 | 十元每斤 |
        | 199~299元/件 | 一百九十九至二百九十九元每件 |
        | 299.99元/g~399.99元/g | 二百九十九点九九元每克至三百九十九点九九元每克 |
        | 其他默认读法 | 12扎 | 十二扎 |
        | 30 rm | 三十r m |
        | 4万万同胞 | 四万万同胞 |
        | 12.897微克 | 十二点八九七微克 |
        
        | **格式** | **示例** | **英文输出** | **说明** |
        | --- | --- | --- | --- |
        | 数字+计量单位 | 1.0 kg | one kilogram | 支持的数字格式：整数、小数以及以逗号分隔的国际写法。 支持常见单位缩写。 |
        | 1,234.01 km | one thousand two hundred thirty four point zero one kilometres. |
        | 计量单位 | mm2 | square millimetre |
        
    -   <say-as>常见符号读法如下表所示。
        
        | **符号** | **中文读法** | **英文读法** |
        | --- | --- | --- |
        | !   | 叹号  | exclamation mark |
        | “   | 双引号 | double quote |
        | #   | 井号  | pound |
        | $   | dollar | dollar |
        | %   | 百分号 | percent |
        | &   | and | and |
        | ‘   | 单引号 | left quote |
        | （   | 左括号 | left parenthesis |
        | ）   | 右括号 | right parenthesis |
        | \\* | 星   | asterisk |
        | +   | 加   | plus |
        | ,   | 逗号  | comma |
        | \\- | 杠   | dash |
        | .   | 点   | dot |
        | /   | 斜杠  | slash |
        | ：   | 零冒号 | solon |
        | ；   | 分号  | semicolon |
        | <   | 小于  | less than |
        | \\= | 等号  | equals |
        | \\> | 大于  | greater than |
        | ?   | 问号  | question mark |
        | @   | at  | at  |
        | \\[ | 左方括号 | left bracket |
        | \\\\ | 反斜线 | back slash |
        | \\] | 右方括号 | right bracket |
        | ^   | 脱字符 | caret |
        | \\_ | 下划线 | underscore |
        | \\` | 反引号 | back quote |
        | {   | 左花括号 | left brace |
        | \\| | 竖线  | vertical bar |
        | }   | 右花括号 | right brace |
        | ~   | 波浪线 | tilde |
        | ！   | 叹号  | exclamation mark |
        | “   | 左双引号 | left double quote |
        | ”   | 右双引号 | right double qute |
        | ‘   | 左单引号 | left quote |
        | ’   | 右单引号 | right quote |
        | （   | 左括号 | left parenthesis |
        | ）   | 右括号 | right parenthesis |
        | ，   | 逗号  | comma |
        | 。   | 句号  | full stop |
        | —   | 杠   | em dash |
        | ：   | 冒号  | colon |
        | ；   | 分号  | semicolon |
        | ？   | 问号  | question mark |
        | 、   | 顿号  | enumeration comma |
        | …   | 省略号 | ellipsis |
        | ……  | 省略号 | ellipsis |
        | 《   | 左书名号 | left guillemet |
        | 》   | 右书名号 | right guillemet |
        | ￥   | 人民币符号 | yuan |
        | ≥   | 大于等于 | greater than or equal to |
        | ≤   | 小于等于 | less than or equal to |
        | ≠   | 不等于 | not equal |
        | ≈   | 约等于 | approximately equal |
        | ±   | 加减  | plus or minus |
        | ×   | 乘   | times |
        | π   | 派   | pi  |
        | Α   | 阿尔法 | alpha |
        | Β   | 贝塔  | beta |
        | Γ   | 伽玛  | gamma |
        | Δ   | 德尔塔 | delta |
        | Ε   | 艾普西龙 | epsilon |
        | Ζ   | 捷塔  | zeta |
        | Θ   | 西塔  | theta |
        | Ι   | 艾欧塔 | iota |
        | Κ   | 喀帕  | kappa |
        | ∧   | 拉姆达 | lambda |
        | Μ   | 缪   | mu  |
        | Ν   | 拗   | nu  |
        | Ξ   | 克西  | ksi |
        | Ο   | 欧麦克轮 | omicron |
        | ∏   | 派   | pi  |
        | Ρ   | 柔   | rho |
        | ∑   | 西格玛 | sigma |
        | Τ   | 套   | tau |
        | Υ   | 宇普西龙 | upsilon |
        | Φ   | fai | phi |
        | Χ   | 器   | chi |
        | Ψ   | 普赛  | psi |
        | Ω   | 欧米伽 | omega |
        | α   | 阿尔法 | alpha |
        | β   | 贝塔  | beta |
        | γ   | 伽玛  | gamma |
        | δ   | 德尔塔 | delta |
        | ε   | 艾普西龙 | epsilon |
        | ζ   | 捷塔  | zeta |
        | η   | 依塔  | eta |
        | θ   | 西塔  | theta |
        | ι   | 艾欧塔 | iota |
        | κ   | 喀帕  | kappa |
        | λ   | 拉姆达 | lambda |
        | μ   | 缪   | mu  |
        | ν   | 拗   | nu  |
        | ξ   | 克西  | ksi |
        | ο   | 欧麦克轮 | omicron |
        | π   | 派   | pi  |
        | ρ   | 柔   | rho |
        | σ   | 西格玛 | sigma |
        | τ   | 套   | tau |
        | υ   | 宇普西龙 | upsilon |
        | φ   | fai | phi |
        | χ   | 器   | chi |
        | ψ   | 普赛  | psi |
        | ω   | 欧米伽 | omega |
        
    -   <say-as>常见计量单位如下表所示。
        
        | **格式** | **类别** | **中文示例** | **英文示例** |
        | --- | --- | --- | --- |
        | 缩写  | 长度  | nm（纳米）、μm（微米）、 mm（毫米）、cm（厘米）、m（米）、km（千米）、ft（英尺）、in（英寸） | nm (nanometre), μm (micrometre), mm (millimetre), cm (centimetre), m (metre), km (kilometre), ft (foot), in (inch) |
        | 面积  | cm²（平方厘米）、㎡（平方米）、km²（平方千米）、SqFt（平方英尺） | cm² (square centimetre), ㎡ (square metre), km2 (square kilometre), SqFt (square foot) |
        | 体积  | cm³（立方厘米）、m³（立方米）、km³（立方千米）、mL（毫升）、L（升）、gallon（加仑） | cm³ (cubic centimetre), m³ (cubic metre), km3 (cubic kilometre), mL (millilitre), L (millilitre), gal (gallon) |
        | 重量  | μg（微克）、mg（毫克）、g（克）、kg（千克） | μg (microgram), mg (microgram), g (gram), kg (kilogram) |
        | 时间  | min（分）、sec（秒）、ms（毫秒） | min (minute), sec (second), ms (millisecond) |
        | 电磁  | μA（微安）、mA（毫安）、Ω（欧姆）、Hz（赫兹）、kHz（千赫兹）、MHz（兆赫兹）、GHz（吉赫兹）、V（伏）、kV（千伏）、kWh（千瓦时） | μA (microamp), mA (milliamp), Hz (hertz), kHz (kilohertz), MHz (megahertz), GHz (gigahertz), V (volt), kV (kilovolt), kWh (kilowatt hour) |
        | 声音  | dB（分贝） | dB (decibel) |
        | 气压  | Pa（帕）、kPa（千帕）、Mpa（兆帕） | Pa (pascal), kPa (kilopascal), MPa (megapascal) |
        | 其他常见单位 |   | 支持不限于上述类别的中文单位，例如“米”、“秒”、“美元”、“毫升每瓶”等。以及中文量词，例如“架”、“场”、“头”、“部”、“盆”等。 | 支持不限于上述类别的计量单位，例如 tsp (teaspoon), rpm (round per minute), KB (kilobyte), mmHg (milimetre of mercury) 等。 |
        
-   标签关系
    
    <say-as>标签可以包括文本及<vhml/>。
    
-   示例
    
    -   cardinal
        
        ```
        <speak>
          <say-as interpret-as="cardinal">12345</say-as>
        </speak>
        ```
        
        ```
        <speak>
          <say-as interpret-as="cardinal">10234</say-as>
        </speak>
        ```
        
    -   digits
        
        ```
        <speak>
          <say-as interpret-as="digits">12345</say-as>
        </speak>
        ```
        
        ```
        <speak>
          <say-as interpret-as="digits">10234</say-as>
        </speak>
        ```
        
    -   telephone
        
        ```
        <speak>
          <say-as interpret-as="telephone">12345</say-as>
        </speak>
        ```
        
        ```
        <speak>
          <say-as interpret-as="telephone">10234</say-as>
        </speak>
        ```
        
    -   name
        
        ```
        <speak>
          她的曾用名是<say-as interpret-as="name">曾小凡</say-as>
        </speak>
        ```
        
    -   address
        
        ```
        <speak>
          <say-as interpret-as="address">富路国际1号楼3单元304</say-as>
        </speak>
        ```
        
    -   id
        
        ```
        <speak>
          <say-as interpret-as="id">myid_1998</say-as>
        </speak>
        ```
        
    -   characters
        
        ```
        <speak>
          <say-as interpret-as="characters">希腊字母αβ</say-as>
        </speak>
        ```
        
        ```
        <speak>
          <say-as interpret-as="characters">*b+3.c$=α</say-as>
        </speak>
        ```
        
    -   punctuation
        
        ```
        <speak>
          <say-as interpret-as="punctuation"> -./:;</say-as>
        </speak>
        ```
        
    -   date
        
        ```
        <speak>
          <say-as interpret-as="date">1000-10-10</say-as>
        </speak>
        ```
        
        ```
        <speak>
          <say-as interpret-as="date">10-01-2020</say-as>
        </speak>
        ```
        
    -   time
        
        ```
        <speak>
          <say-as interpret-as="time">5:00am</say-as>
        </speak>
        ```
        
        ```
        <speak>
          <say-as interpret-as="time">0500</say-as>
        </speak>
        ```
        
    -   currency
        
        ```
        <speak>
          <say-as interpret-as="currency">13,000,000.00RMB</say-as>
        </speak>
        ```
        
        ```
        <speak>
          <say-as interpret-as="currency">$1,000.01</say-as>
        </speak>
        ```
        
    -   measure
        
        ```
        <speak>
          <say-as interpret-as="measure">100m12cm6mm</say-as>
        </speak>
        ```
        
        ```
        <speak>
          <say-as interpret-as="measure">1,000.01kg</say-as>
        </speak>
        ```

CosyVoice支持的系统音色如下表所示。若需要更加个性化的音色，可通过声音复刻功能免费定制专属音色，详情请参见[使用复刻的音色进行语音合成](https://help.aliyun.com/zh/model-studio/cosyvoice-clone-api#b6d3449fb336v)。

进行语音合成时：

-   每个模型（`model`）仅支持一组特定的音色（`voice`），不能将一个模型的音色与另一个模型混用
    
-   待合成文本（`text`）必须在所选音色支持的语言范围内，否则可能出现发音错误或不自然
    
-   对于支持SSML的音色，如需使用SSML功能，请参见[SSML标记语言介绍](https://help.aliyun.com/zh/model-studio/introduction-to-cosyvoice-ssml-markup-language)，在请求参数`text`中填写符合SSML规范的内容
    
-   对于支持Instruct的音色，如需使用Instruct功能，请在请求参数`instruction`中填写符合Instruct格式要求的文本
    
-   对于支持时间戳的音色，如需使用时间戳功能，请通过请求参数`word_timestamp_enabled`（Java SDK中为`enableWordTimestamp`）开启该功能
    

## **cosyvoice-v3-flash音色列表**

| **适用场景** | **音色信息** | **特性支持** | **音频试听（右键保存音频）** |
| --- | --- | --- | --- |
| 社交陪伴（标杆音色） | **名称**：龙安洋 **voice参数**：longanyang **特质**：阳光大男孩 **年龄**：20~30岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：支持 时间戳：支持 **点击查看Instruct设置** 1. 设置情感 - 格式：“`你说话的情感是<情感值>。`”（注意，结尾一定不要遗漏句号，使用时将“`<情感值>`”替换为具体的情感值，例如替换为`neutral`）。 - 示例：“`你说话的情感是neutral。`” - 支持的情感值：`neutral`、`fearful`、`angry`、`sad`、`surprised`、`happy`、`disgusted`。 2. 设置场景+情感 - 格式：“`你正在进行<场景>，你说话的情感是<情感值>。`”（注意，结尾一定不要遗漏句号，使用时将“场景”替换为具体的场景，将“`<情感值>`”替换为具体的情感值，例如替换为`neutral`）。 - 示例：“`你正在进行闲聊互动，你说话的情感是neutral。`” - 支持的场景：`闲聊互动`、`新闻播报`、`广告促销`、`比赛解说`、`一些儿童内容解说`、`语音导航`、`脱口秀表演`。 - 支持的情感值：`neutral`、`fearful`、`angry`、`sad`、`surprised`、`happy`、`disgusted`。 3. 设置角色+情感 - 格式：“`你现在说话的角色是<角色>，你说话的情感是<情感值>。`”（注意，结尾一定不要遗漏句号，使用时将“`角色`”替换为具体的角色，将“`<情感值>`”替换为具体的情感值，例如替换为`neutral`）。 - 示例：“`你现在说话的角色是一个旁白，你说话的情感是neutral。`” - 支持的角色：`一个旁白`。 - 支持的情感值：`neutral`、`fearful`、`angry`、`sad`、`surprised`、`happy`、`disgusted`。 4. 设置身份+情感 - 格式：“`你正在以一个<身份>的身份说话，你说话的情感是<情感值>。`”（注意，结尾一定不要遗漏句号，使用时将“身份”替换为具体的身份，将“`<情感值>`”替换为具体的情感值，例如替换为`neutral`）。 - 示例：“`你正在以一个故事机的身份说话，你说话的情感是neutral。`” - 支持的身份：`故事机`。 - 支持的情感值：`neutral`、`fearful`、`angry`、`sad`、`surprised`、`happy`、`disgusted`。 |     |
| **名称**：龙安欢 **voice参数**：longanhuan **特质**：欢脱元气女 **年龄**：20~30岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：支持 时间戳：支持 **点击查看Instruct设置** 1. 设置情感 - 格式：“`你说话的情感是<情感值>。`”（注意，结尾一定不要遗漏句号，使用时将“`<情感值>`”替换为具体的情感值，例如替换为`neutral`）。 - 示例：“`你说话的情感是neutral。`” - 支持的情感值：`neutral`、`fearful`、`angry`、`sad`、`surprised`、`happy`、`disgusted`。 2. 设置场景+情感 - 格式：“`你正在进行<场景>，你说话的情感是<情感值>。`”（注意，结尾一定不要遗漏句号，使用时将“场景”替换为具体的场景，将“`<情感值>`”替换为具体的情感值，例如替换为`neutral`）。 - 示例：“`你正在进行闲聊对话，你说话的情感是neutral。`” - 支持的场景：`闲聊对话`、`比赛解说`、`深夜电台广播`、`剧情解说`、`诗歌朗诵`、`科普知识推广`、`产品推广`、`脱口秀表演`。 - 支持的情感值：`neutral`、`fearful`、`angry`、`sad`、`surprised`、`happy`、`disgusted`。 3. 设置角色+情感 - 格式：“`你说话的角色是<角色>，你说话的情感是<情感值>。`”（注意，结尾一定不要遗漏句号，使用时将“`角色`”替换为具体的角色，将“`<情感值>`”替换为具体的情感值，例如替换为`neutral`）。 - 示例：“`你说话的角色是温和客服，你说话的情感是neutral。`” - 支持的角色：`温和客服`。 - 支持的情感值：`neutral`、`fearful`、`angry`、`sad`、`surprised`、`happy`、`disgusted`。 |     |
| 童声（标杆音色） | **名称**：龙呼呼 **voice参数**：longhuhu\\_v3 **特质**：天真烂漫女童 **年龄**：6~10岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：支持 时间戳：支持 **点击查看Instruct设置** 1. 设置情感 - 格式：“`你说话的情感是<情感值>。`”（注意，结尾一定不要遗漏句号，使用时将“`<情感值>`”替换为具体的情感值，例如替换为`neutral`）。 - 示例：“`你说话的情感是neutral。`” - 支持的情感值：`neutral`、`fearful`、`angry`、`sad`、`surprised`、`happy`、`disgusted`。 2. 设置场景+情感 - 格式：“`你正在进行<场景>，你说话的情感是<情感值>。`”（注意，结尾一定不要遗漏句号，使用时将“场景”替换为具体的场景，将“`<情感值>`”替换为具体的情感值，例如替换为`neutral`）。 - 示例：“`你正在进行自由对话，你说话的情感是neutral。`” - 支持的场景：`自由对话`、`广告促销`。 - 支持的情感值：`neutral`、`fearful`、`angry`、`sad`、`surprised`、`happy`、`disgusted`。 3. 设置角色+情感 - 格式：“`你说话的角色是<角色>，你说话的情感是<情感值>。`”（注意，结尾一定不要遗漏句号，使用时将“`角色`”替换为具体的角色，将“`<情感值>`”替换为具体的情感值，例如替换为`neutral`）。 - 示例：“`你说话的角色是傲娇公主，你说话的情感是neutral。`” - 支持的角色：`傲娇公主`、`元气少女`、`可爱孩童`、`机器人`、`小猪佩奇`。 - 支持的情感值：`neutral`、`fearful`、`angry`、`sad`、`surprised`、`happy`、`disgusted`。 4. 设置身份+情感 - 格式：“`你正在以一个<身份>的身份说话，你说话的情感是<情感值>。`”（注意，结尾一定不要遗漏句号，使用时将“身份”替换为具体的身份，将“`<情感值>`”替换为具体的情感值，例如替换为`neutral`）。 - 示例：“`你正在以一个故事机的身份说话，你说话的情感是neutral。`” - 支持的身份：`故事机`、`儿童玩具`。 - 支持的情感值：`neutral`、`fearful`、`angry`、`sad`、`surprised`、`happy`、`disgusted`。 |     |
| 智能玩具/儿童故事机 | **名称**：龙泡泡 **voice参数**：longpaopao\\_v3 **特质**：飞天泡泡音 **年龄**：6~15岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙杰力豆 **voice参数**：longjielidou\\_v3 **特质**：阳光顽皮男 **年龄**：10岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙仙 **voice参数**：longxian\\_v3 **特质**：豪放可爱女 **年龄**：12岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙铃 **voice参数**：longling\\_v3 **特质**：稚气呆板女 **年龄**：10岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 消费电子-儿童有声书 | **名称**：龙闪闪 **voice参数**：longshanshan\\_v3 **特质**：戏剧化童声 **年龄**：6~15岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙牛牛 **voice参数**：longniuniu\\_v3 **特质**：阳光男童声 **年龄**：6~15岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 方言  | **名称**：龙嘉欣 **voice参数**：longjiaxin\\_v3 **特质**：优雅粤语女 **年龄**：30~35岁 **语言**：中文（粤语）、英 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙嘉怡 **voice参数**：longjiayi\\_v3 **特质**：知性粤语女 **年龄**：25~30岁 **语言**：中文（粤语）、英 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙安粤 **voice参数**：longanyue\\_v3 **年龄**：25~35岁 **特质**：欢脱粤语男 **语言**：中文（粤语）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙老铁 **voice参数**：longlaotie\\_v3 **特质**：东北直率男 **年龄**：25~30岁 **语言**：中文（东北话）、英 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙陕哥 **voice参数**：longshange\\_v3 **年龄**：25~35岁 **特质**：原味陕北男 **语言**：中文（陕西话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙安闽 **voice参数**：longanmin\\_v3 **年龄**：18~25岁 **特质**：清纯萝莉女 **语言**：中文（闽南话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 出海营销 | **名称**：loongkyong **voice参数**：loongkyong\\_v3 **特质**：韩语女 **年龄**：25~30岁 **语言**：韩语 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：Riko **voice参数**：loongriko\\_v3 **特质**：二次元霓虹女 **年龄**：18~25岁 **语言**：日语 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：loongtomoka **voice参数**：loongtomoka\\_v3 **特质**：日语女 **年龄**：30~35岁 **语言**：日语 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 诗词朗诵 | **名称**：龙飞 **voice参数**：longfei\\_v3 **特质**：热血磁性男 **年龄**：30~35岁 **语言**：中文（普通话）、英 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 电话销售 | **名称**：龙应笑 **voice参数**：longyingxiao\\_v3 **年龄**：20~25岁 **特质**：清甜推销女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 客服  | **名称**：龙应询 **voice参数**：longyingxun\\_v3 **年龄**：20~25岁 **特质**：年轻青涩男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙应静 **voice参数**：longyingjing\\_v3 **年龄**：25~35岁 **特质**：低调冷静女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙应聆 **voice参数**：longyingling\\_v3 **年龄**：25~30岁 **特质**：温和共情女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙应桃 **voice参数**：longyingtao\\_v3 **年龄**：25~30岁 **特质**：温柔淡定女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 语音助手 | **名称**：龙小淳 **voice参数**：longxiaochun\\_v3 **特质**：知性积极女 **年龄**：25~30岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙小夏 **voice参数**：longxiaoxia\\_v3 **特质**：沉稳权威女 **年龄**：25~30岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：YUMI **voice参数**：longyumi\\_v3 **特质**：正经青年女 **年龄**：20~25岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙安昀 **voice参数**：longanyun\\_v3 **特质**：居家暖男 **年龄**：30~35岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙安温 **voice参数**：longanwen\\_v3 **特质**：优雅知性女 **年龄**：25~35岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙安莉 **voice参数**：longanli\\_v3 **特质**：利落从容女 **年龄**：25~35岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙安朗 **voice参数**：longanlang\\_v3 **特质**：清爽利落男 **年龄**：20~25岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙应沐 **voice参数**：longyingmu\\_v3 **特质**：优雅知性女 **年龄**：25~30岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 社交陪伴 | **名称**：龙安台 **voice参数**：longantai\\_v3 **特质**：嗲甜台湾女 **年龄**：20~25岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙华 **voice参数**：longhua\\_v3 **特质**：元气甜美女 **年龄**：20~25岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙橙 **voice参数**：longcheng\\_v3 **特质**：智慧青年男 **年龄**：20~25岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙泽 **voice参数**：longze\\_v3 **特质**：温暖元气男 **年龄**：25~30岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙哲 **voice参数**：longzhe\\_v3 **特质**：呆板大暖男 **年龄**：25~30岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙颜 **voice参数**：longyan\\_v3 **特质**：温暖春风女 **年龄**：30~35岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙星 **voice参数**：longxing\\_v3 **特质**：温婉邻家女 **年龄**：20~25岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙天 **voice参数**：longtian\\_v3 **特质**：磁性理智男 **年龄**：30~35岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙婉 **voice参数**：longwan\\_v3 **特质**：细腻柔声女 **年龄**：20~30岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙嫱 **voice参数**：longqiang\\_v3 **特质**：浪漫风情女 **年龄**：30~35岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙菲菲 **voice参数**：longfeifei\\_v3 **特质**：甜美娇气女 **年龄**：20~25岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙浩 **voice参数**：longhao\\_v3 **特质**：多情忧郁男 **年龄**：30~35岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙安柔 **voice参数**：longanrou\\_v3 **特质**：温柔闺蜜女 **年龄**：20~35岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙寒 **voice参数**：longhan\\_v3 **特质**：温暖痴情男 **年龄**：30~35岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙安智 **voice参数**：longanzhi\\_v3 **特质**：睿智轻熟男 **年龄**：25~35岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙安灵 **voice参数**：longanling\\_v3 **特质**：思维灵动女 **年龄**：20~30岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙安雅 **voice参数**：longanya\\_v3 **特质**：高雅气质女 **年龄**：25~35岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙安亲 **voice参数**：longanqin\\_v3 **特质**：亲和活泼女 **年龄**：20~25岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 有声书 | **名称**：龙妙 **voice参数**：longmiao\\_v3 **特质**：抑扬顿挫女 **年龄**：25~30岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙三叔 **voice参数**：longsanshu\\_v3 **特质**：沉稳质感男 **年龄**：25~45岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙媛 **voice参数**：longyuan\\_v3 **特质**：温暖治愈女 **年龄**：35~40岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙悦 **voice参数**：longyue\\_v3 **特质**：温暖磁性女 **年龄**：30~35岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙修 **voice参数**：longxiu\\_v3 **特质**：博才说书男 **年龄**：25~35岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙楠 **voice参数**：longnan\\_v3 **特质**：睿智青年男 **年龄**：25~30岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙婉君 **voice参数**：longwanjun\\_v3 **特质**：细腻柔声女 **年龄**：20~30岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙逸尘 **voice参数**：longyichen\\_v3 **特质**：洒脱活力男 **年龄**：20~30岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙老伯 **voice参数**：longlaobo\\_v3 **特质**：沧桑岁月爷 **年龄**：60岁以上 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙老姨 **voice参数**：longlaoyi\\_v3 **特质**：烟火从容阿姨 **年龄**：60岁以上 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 短视频配音 | **名称**：龙机器 **voice参数**：longjiqi\\_v3 **特质**：呆萌机器人 **年龄**：20~30岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙猴哥 **voice参数**：longhouge\\_v3 **特质**：经典猴哥 **年龄**：20~25岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙黛玉 **voice参数**：longdaiyu\\_v3 **特质**：娇率才女音 **年龄**：15~25岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 直播带货 | **名称**：龙安燃 **voice参数**：longanran\\_v3 **特质**：活泼质感女 **年龄**：30~40岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙安宣 **voice参数**：longanxuan\\_v3 **特质**：经典直播女 **年龄**：30~40岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 新闻播报 | **名称**：龙硕 **voice参数**：longshuo\\_v3 **特质**：博才干练男 **年龄**：25~30岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙书 **voice参数**：longshu\\_v3 **特质**：沉稳青年男 **年龄**：20~25岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：Bella3.0 **voice参数**：loongbella\\_v3 **特质**：精准干练女 **年龄**：25~30岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |

## **cosyvoice-v3-plus音色列表**

| **适用场景** | **音色信息** | **特性支持** | **音频试听（右键保存音频）** |
| --- | --- | --- | --- |
| 社交陪伴（标杆音色） | **名称**：龙安洋 **voice参数**：longanyang **特质**：阳光大男孩 **年龄**：20~30岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：支持 时间戳：支持 **点击查看Instruct设置** 1. 设置情感 - 格式：“`你说话的情感是<情感值>。`”（注意，结尾一定不要遗漏句号，使用时将“`<情感值>`”替换为具体的情感值，例如替换为`neutral`）。 - 示例：“`你说话的情感是neutral。`” - 支持的情感值：`neutral`、`fearful`、`angry`、`sad`、`surprised`、`happy`、`disgusted`。 2. 设置场景+情感 - 格式：“`你正在进行<场景>，你说话的情感是<情感值>。`”（注意，结尾一定不要遗漏句号，使用时将“场景”替换为具体的场景，将“`<情感值>`”替换为具体的情感值，例如替换为`neutral`）。 - 示例：“`你正在进行闲聊互动，你说话的情感是neutral。`” - 支持的场景：`闲聊互动`、`新闻播报`、`广告促销`、`比赛解说`、`一些儿童内容解说`、`语音导航`、`脱口秀表演`。 - 支持的情感值：`neutral`、`fearful`、`angry`、`sad`、`surprised`、`happy`、`disgusted`。 3. 设置角色+情感 - 格式：“`你现在说话的角色是<角色>，你说话的情感是<情感值>。`”（注意，结尾一定不要遗漏句号，使用时将“`角色`”替换为具体的角色，将“`<情感值>`”替换为具体的情感值，例如替换为`neutral`）。 - 示例：“`你现在说话的角色是一个旁白，你说话的情感是neutral。`” - 支持的角色：`一个旁白`。 - 支持的情感值：`neutral`、`fearful`、`angry`、`sad`、`surprised`、`happy`、`disgusted`。 4. 设置身份+情感 - 格式：“`你正在以一个<身份>的身份说话，你说话的情感是<情感值>。`”（注意，结尾一定不要遗漏句号，使用时将“身份”替换为具体的身份，将“`<情感值>`”替换为具体的情感值，例如替换为`neutral`）。 - 示例：“`你正在以一个故事机的身份说话，你说话的情感是neutral。`” - 支持的身份：`故事机`。 - 支持的情感值：`neutral`、`fearful`、`angry`、`sad`、`surprised`、`happy`、`disgusted`。 |     |
| **名称**：龙安欢 **voice参数**：longanhuan **特质**：欢脱元气女 **年龄**：20~30岁 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：支持 时间戳：支持 **点击查看Instruct设置** 1. 设置情感 - 格式：“`你说话的情感是<情感值>。`”（注意，结尾一定不要遗漏句号，使用时将“`<情感值>`”替换为具体的情感值，例如替换为`neutral`）。 - 示例：“`你说话的情感是neutral。`” - 支持的情感值：`neutral`、`fearful`、`angry`、`sad`、`surprised`、`happy`、`disgusted`。 2. 设置场景+情感 - 格式：“`你正在进行<场景>，你说话的情感是<情感值>。`”（注意，结尾一定不要遗漏句号，使用时将“场景”替换为具体的场景，将“`<情感值>`”替换为具体的情感值，例如替换为`neutral`）。 - 示例：“`你正在进行闲聊互动，你说话的情感是neutral。`” - 支持的场景：`闲聊对话`、`比赛解说`、`深夜电台广播`、`诗歌朗诵`、`科普知识推广`、`产品推广`、`脱口秀表演`。 - 支持的情感值：`neutral`、`fearful`、`angry`、`sad`、`surprised`、`happy`、`disgusted`。 3. 设置角色+情感 - 格式：“`你说话的角色是<角色>，你说话的情感是<情感值>。`”（注意，结尾一定不要遗漏句号，使用时将“`角色`”替换为具体的角色，将“`<情感值>`”替换为具体的情感值，例如替换为`neutral`）。 - 示例：“`你说话的角色是温和客服，你说话的情感是neutral。`” - 支持的角色：`温和客服`。 - 支持的情感值：`neutral`、`fearful`、`angry`、`sad`、`surprised`、`happy`、`disgusted`。 |     |

## **cosyvoice-v2音色列表**

| **适用场景** | **音色信息** | **特性支持** | **音频试听（右键保存音频）** |
| --- | --- | --- | --- |
| 电话销售 | **名称**：龙应笑 **voice参数**：longyingxiao **特质**：清甜推销女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 短视频配音 | **名称**：龙机器 **voice参数**：longjiqi **特质**：呆萌机器人 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙猴哥 **voice参数**：longhouge **特质**：经典猴哥 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙机心 **voice参数**：longjixin **特质**：毒舌心机女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙安粤 **voice参数**：longanyue **特质**：欢脱粤语男 **语言**：中文（粤语）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙陕哥 **voice参数**：longshange **特质**：原味陕北男 **语言**：中文（陕西话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙安敏 **voice参数**：longanmin **特质**：甜美闽南女 **语言**：中文（闽南话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙黛玉 **voice参数**：longdaiyu **特质**：娇率才女音 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙高僧 **voice参数**：longgaoseng **特质**：得道高僧音 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 语音助手 | **名称**：龙安莉 **voice参数**：longanli **特质**：利落从容女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙安朗 **voice参数**：longanlang **特质**：清爽利落男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙安温 **voice参数**：longanwen **特质**：优雅知性女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙安昀 **voice参数**：longanyun **特质**：居家暖男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：YUMI **voice参数**：longyumi\\_v2 **特质**：正经青年女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙小淳 **voice参数**：longxiaochun\\_v2 **特质**：知性积极女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙小夏 **voice参数**：longxiaoxia\\_v2 **特质**：沉稳权威女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 有声书 | **名称**：龙逸尘 **voice参数**：longyichen **特质**：洒脱活力男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙婉君 **voice参数**：longwanjun **特质**：细腻柔声女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙老伯 **voice参数**：longlaobo **特质**：沧桑岁月爷 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙老姨 **voice参数**：longlaoyi **特质**：烟火从容阿姨 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙白芷 **voice参数**：longbaizhi **特质**：睿气旁白女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙三叔 **voice参数**：longsanshu **特质**：沉稳质感男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙修 **voice参数**：longxiu\\_v2 **特质**：博才说书男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙妙 **voice参数**：longmiao\\_v2 **特质**：抑扬顿挫女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙悦 **voice参数**：longyue\\_v2 **特质**：温暖磁性女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙楠 **voice参数**：longnan\\_v2 **特质**：睿智青年男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙媛 **voice参数**：longyuan\\_v2 **特质**：温暖治愈女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 社交陪伴 | **名称**：龙安亲 **voice参数**：longanqin **特质**：亲和活泼女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙安雅 **voice参数**：longanya **特质**：高雅气质女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙安朔 **voice参数**：longanshuo **特质**：干净清爽男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙安灵 **voice参数**：longanling **特质**：思维灵动女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙安智 **voice参数**：longanzhi **特质**：睿智轻熟男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙安柔 **voice参数**：longanrou **特质**：温柔闺蜜女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙嫱 **voice参数**：longqiang\\_v2 **特质**：浪漫风情女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙寒 **voice参数**：longhan\\_v2 **特质**：温暖痴情男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙星 **voice参数**：longxing\\_v2 **特质**：温婉邻家女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙华 **voice参数**：longhua\\_v2 **特质**：元气甜美女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙婉 **voice参数**：longwan\\_v2 **特质**：积极知性女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙橙 **voice参数**：longcheng\\_v2 **特质**：智慧青年男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙菲菲 **voice参数**：longfeifei\\_v2 **特质**：甜美娇气女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙小诚 **voice参数**：longxiaocheng\\_v2 **特质**：磁性低音男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙哲 **voice参数**：longzhe\\_v2 **特质**：呆板大暖男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙颜 **voice参数**：longyan\\_v2 **特质**：温暖春风女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙天 **voice参数**：longtian\\_v2 **特质**：磁性理智男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙泽 **voice参数**：longze\\_v2 **特质**：温暖元气男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙邵 **voice参数**：longshao\\_v2 **特质**：积极向上男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙浩 **voice参数**：longhao\\_v2 **特质**：多情忧郁男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙深 **voice参数**：kabuleshen\\_v2 **特质**：实力歌手男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 童声（标杆音色） | **名称**：龙呼呼 **voice参数**：longhuhu **特质**：天真烂漫女童 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 消费电子-教育培训 | **名称**：龙安培 **voice参数**：longanpei **特质**：青少年教师女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 消费电子-儿童陪伴 | **名称**：龙汪汪 **voice参数**：longwangwang **特质**：台湾少年音 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙泡泡 **voice参数**：longpaopao **特质**：飞天泡泡音 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 消费电子-儿童有声书 | **名称**：龙闪闪 **voice参数**：longshanshan **特质**：戏剧化童声 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙牛牛 **voice参数**：longniuniu **特质**：阳光男童声 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 客服  | **名称**：龙应沐 **voice参数**：longyingmu **特质**：优雅知性女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙应询 **voice参数**：longyingxun **特质**：年轻青涩男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙应催 **voice参数**：longyingcui **特质**：严肃催收男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙应答 **voice参数**：longyingda **特质**：开朗高音女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙应静 **voice参数**：longyingjing **特质**：低调冷静女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙应严 **voice参数**：longyingyan **特质**：义正严辞女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙应甜 **voice参数**：longyingtian **特质**：温柔甜美女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙应冰 **voice参数**：longyingbing **特质**：尖锐强势女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙应桃 **voice参数**：longyingtao **特质**：温柔淡定女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙应聆 **voice参数**：longyingling **特质**：温和共情女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 直播带货 | **名称**：龙安燃 **voice参数**：longanran **特质**：活泼质感女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙安宣 **voice参数**：longanxuan **特质**：经典直播女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙安冲 **voice参数**：longanchong **特质**：激情推销男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙安萍 **voice参数**：longanping **特质**：高亢直播女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 童声  | **名称**：龙杰力豆 **voice参数**：longjielidou\\_v2 **特质**：阳光顽皮男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙铃 **voice参数**：longling\\_v2 **特质**：稚气呆板女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙可 **voice参数**：longke\\_v2 **特质**：懵懂乖乖女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙仙 **voice参数**：longxian\\_v2 **特质**：豪放可爱女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 方言  | **名称**：龙老铁 **voice参数**：longlaotie\\_v2 **特质**：东北直率男 **语言**：中文（东北话）、英 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙嘉怡 **voice参数**：longjiayi\\_v2 **特质**：知性粤语女 **语言**：中文（粤语）、英 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙桃 **voice参数**：longtao\\_v2 **特质**：积极粤语女 **语言**：中文（粤语）、英 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 诗词朗诵 | **名称**：龙飞 **voice参数**：longfei\\_v2 **特质**：热血磁性男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：李白 **voice参数**：libai\\_v2 **特质**：古代诗仙男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙津 **voice参数**：longjin\\_v2 **特质**：优雅温润男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 新闻播报 | **名称**：龙书 **voice参数**：longshu\\_v2 **特质**：沉稳青年男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：Bella2.0 **voice参数**：loongbella\\_v2 **特质**：精准干练女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙硕 **voice参数**：longshuo\\_v2 **特质**：博才干练男 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙小白 **voice参数**：longxiaobai\\_v2 **特质**：沉稳播报女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：龙婧 **voice参数**：longjing\\_v2 **特质**：典型播音女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| **名称**：loongstella **voice参数**：loongstella\\_v2 **特质**：飒爽利落女 **语言**：中文（普通话）、英文 | SSML：支持 Instruct：不支持 时间戳：支持 |     |
| 出海营销 | **名称**：loongyuuna **voice参数**：loongyuuna\\_v2 **特质**：元气霓虹女 **语言**：日语 | SSML：支持 Instruct：不支持 时间戳：不支持 |     |
| **名称**：loongyuuma **voice参数**：loongyuuma\\_v2 **特质**：干练霓虹男 **语言**：日语 | SSML：支持 Instruct：不支持 时间戳：不支持 |     |
| **名称**：loongjihun **voice参数**：loongjihun\\_v2 **特质**：阳光韩国男 **语言**：韩语 | SSML：支持 Instruct：不支持 时间戳：不支持 |     |
| **名称**：loongeva **voice参数**：loongeva\\_v2 **特质**：知性英文女 **语言**：英式英文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| **名称**：loongbrian **voice参数**：loongbrian\\_v2 **特质**：沉稳英文男 **语言**：英式英文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| **名称**：loongluna **voice参数**：loongluna\\_v2 **特质**：英式英文女 **语言**：英式英文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| **名称**：loongluca **voice参数**：loongluca\\_v2 **特质**：英式英文男 **语言**：英式英文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| **名称**：loongemily **voice参数**：loongemily\\_v2 **特质**：英式英文女 **语言**：英式英文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| **名称**：loongeric **voice参数**：loongeric\\_v2 **特质**：英式英文男 **语言**：英式英文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| **名称**：loongabby **voice参数**：loongabby\\_v2 **特质**：美式英文女 **语言**：美式英文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| **名称**：loongannie **voice参数**：loongannie\\_v2 **特质**：美式英文女 **语言**：美式英文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| **名称**：loongandy **voice参数**：loongandy\\_v2 **特质**：美式英文男 **语言**：美式英文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| **名称**：loongava **voice参数**：loongava\\_v2 **特质**：美式英文女 **语言**：美式英文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| **名称**：loongbeth **voice参数**：loongbeth\\_v2 **特质**：美式英文女 **语言**：美式英文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| **名称**：loongbetty **voice参数**：loongbetty\\_v2 **特质**：美式英文女 **语言**：美式英文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| **名称**：loongcindy **voice参数**：loongcindy\\_v2 **特质**：美式英文女 **语言**：美式英文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| **名称**：loongcally **voice参数**：loongcally\\_v2 **特质**：美式英文女 **语言**：美式英文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| **名称**：loongdavid **voice参数**：loongdavid\\_v2 **特质**：美式英文男 **语言**：美式英文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| **名称**：loongdonna **voice参数**：loongdonna\\_v2 **特质**：美式英文女 **语言**：美式英文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| **名称**：loongkyong **voice参数**：loongkyong\\_v2 **特质**：韩语女 **语言**：韩语 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| **名称**：loongtomoka **voice参数**：loongtomoka\\_v2 **特质**：日语女 **语言**：日语 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| **名称**：loongtomoya **voice参数**：loongtomoya\\_v2 **特质**：日语男 **语言**：日语 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |

## cosyvoice-v1音色列表

cosyvoice-v1音色不支持方言。

| **适用场景** | **音色信息** | **特性支持** | **音频试听（右键保存音频）** |
| --- | --- | --- | --- |
| 语音助手、 导航播报、 聊天数字人 | **名称**：龙婉 **voice参数**：longwan **语言**：中文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| 语音助手、 导航播报、 聊天数字人 | **名称**：龙橙 **voice参数**：longcheng **语言**：中文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| 语音助手、 导航播报、 聊天数字人 | **名称**：龙华 **voice参数**：longhua **语言**：中文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| 语音助手、 导航播报、 聊天数字人 | **名称**：龙小淳 **voice参数**：longxiaochun **语言**：中文、英文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| 语音助手、聊天数字人 | **名称**：龙小夏 **voice参数**：longxiaoxia **语言**：中文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| 语音助手、导航播报、聊天数字人 | **名称**：龙小诚 **voice参数**：longxiaocheng **语言**：中文、英文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| 聊天数字人、有声书、语音助手 | **名称**：龙小白 **voice参数**：longxiaobai **语言**：中文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| 新闻播报、有声书、语音助手、直播带货、导航播报 | **名称**：龙老铁 **voice参数**：longlaotie **语言**：中文东北口音 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| 有声书、语音助手、导航播报、新闻播报、智能客服 | **名称**：龙书 **voice参数**：longshu **语言**：中文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| 语音助手、导航播报、新闻播报、客服催收 | **名称**：龙硕 **voice参数**：longshuo **语言**：中文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| 语音助手、导航播报、新闻播报、客服催收 | **名称**：龙婧 **voice参数**：longjing **语言**：中文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| 客服催收、导航播报、有声书、语音助手 | **名称**：龙妙 **voice参数**：longmiao **语言**：中文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| 语音助手、诗词朗诵、有声书朗读、导航播报、新闻播报、客服催收 | **名称**：龙悦 **voice参数**：longyue **语言**：中文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| 有声书、语音助手、聊天数字人 | **名称**：龙媛 **voice参数**：longyuan **语言**：中文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| 会议播报、新闻播报、有声书 | **名称**：龙飞 **voice参数**：longfei **语言**：中文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| 新闻播报、有声书、聊天助手 | **名称**：龙杰力豆 **voice参数**：longjielidou **语言**：中文、英文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| 有声书、导航播报、聊天数字人 | **名称**：龙彤 **voice参数**：longtong **语言**：中文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| 新闻播报、有声书、导航播报 | **名称**：龙祥 **voice参数**：longxiang **语言**：中文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| 语音助手、直播带货、导航播报、客服催收、有声书 | **名称**：Stella **voice参数**：loongstella **语言**：中文、英文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |
| 语音助手、客服催收、新闻播报、导航播报 | **名称**：Bella **voice参数**：loongbella **语言**：中文 | SSML：不支持 Instruct：不支持 时间戳：不支持 |     |

 span.aliyun-docs-icon { color: transparent !important; font-size: 0 !important; } span.aliyun-docs-icon:before { color: black; font-size: 16px; } span.aliyun-docs-icon.icon-size-20:before { font-size: 20px; } span.aliyun-docs-icon.icon-size-22:before { font-size: 22px; } span.aliyun-docs-icon.icon-size-24:before { font-size: 24px; } span.aliyun-docs-icon.icon-size-26:before { font-size: 26px; } span.aliyun-docs-icon.icon-size-28:before { font-size: 28px; }

/\* 当设备显示尺寸宽度过小时，让当做卡片的表格横向单元格改变方向，变成垂直方向显示，类似钉钉文档的分栏效果。 使用时需要为对应的 table 设置 class=column-layout。\*/ @media (max-width: 1590px) { .aliyun-docs-content table.column-layout tr, .aliyun-docs-content table.column-layout td, .aliyun-docs-content table.column-layout th { display: flex !important; flex-direction: column !important; height: auto !important; padding: 0 ; } .aliyun-docs-content table.column-layout colgroup { display: none; } }