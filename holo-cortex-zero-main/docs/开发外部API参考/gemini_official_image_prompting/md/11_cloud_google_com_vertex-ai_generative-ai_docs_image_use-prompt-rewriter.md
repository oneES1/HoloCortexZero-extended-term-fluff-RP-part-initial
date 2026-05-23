# Use prompt rewriter

> Source: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/image/use-prompt-rewriter
> Downloaded: 2026-02-05

[Try image generation (Vertex AI Studio)](https://console.cloud.google.com/vertex-ai/studio/media/generate;tab=image)

[Try Imagen in a Colab](https://colab.research.google.com/github/GoogleCloudPlatform/generative-ai/blob/main/vision/getting-started/imagen4_image_generation.ipynb)

Imagen on Vertex AI offers an LLM-based prompt rewriting tool, also known as a
prompt rewriter. The prompt rewriter helps you obtain higher quality output
images by adding more detail to your prompt.

If you disable the prompt rewriter, the quality of the images and how well the
output resembles the prompt that you supplied may be impacted. This feature is
enabled by default for the following model versions:

- `imagen-4.0-generate-001`
- `imagen-4.0-fast-generate-001`
- `imagen-4.0-ultra-generate-001`
- `imagen-3.0-generate-002`

The rewritten prompt is delivered by API response only if the original prompt
is fewer than 30 words long.

**Important:** `imagen-4.0-fast-generate-001` may generate undesireable
results if the prompt is complex and you use enhanced prompts. To fix this,
avoid using **Help me write** in Google Cloud console, or set `enhancePrompt` to
`false`.

## Use the prompt rewriter

To use the prompt rewriter, do the following:

### Console

1. In the Google Cloud console, go to the **Vertex AI > Media
   Studio** page.

   [Go to Media
   Studio](https://console.cloud.google.com/vertex-ai/studio/media/generate;tab=image)
2. Click **Imagen**. The Imagen Media Studio image generation page is
   displayed.
3. In the **Settings** panel, adjust the following options:

   - **Model**: Choose a model from the available options.

     For more information about available models, see [Imagen
     models](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models#imagen-models)
   - **Number of results**: Adjust the slider or enter a value between
     **1** and **4**.
   - In the **Negative prompt** box, enter a prompt that describes what
     you don't want generated in the image.
4. In the **Write your prompt** box, click **Help me write**.

   The **Enhance my prompt** window is displayed.
5. In the **Current prompt** box, write your prompt, and then click
   **Enhance**.

   The rewritten prompt is displayed in the **Enhanced prompt** box. You
   can edit the enhanced prompt or use it as displayed.
6. Click **Insert** to use the displayed prompt.

   The prompt is inserted into the **Write your prompt** box.
7. Click send **Generate**.

### REST

Before using any of the request data,
make the following replacements:

- PROJECT\_ID: Your Google Cloud [project ID](https://docs.cloud.google.com/resource-manager/docs/creating-managing-projects#identifiers).
- MODEL\_VERSION: The image generation model version to use.

  For more information about model versions and features, see [model versions](#model-versions).
- LOCATION: Your project's region. For example,
  `us-central1`, `europe-west2`, or `asia-northeast3`. For a list
  of available regions, see
  [Generative AI on Vertex AI locations](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/locations-genai).
- TEXT\_PROMPT: The text prompt that guides what images the model
  generates. Before images are generated, this base prompt is enhanced with
  more detail and descripitive language using the LLM-based prompt rewriting
  tool.
- IMAGE\_COUNT: An integer, describing the number of images to
  generate. The accepted values are `1`-`4`. The default
  value is `4`.
- PROMPT\_SETTING: A boolean value, `true` enables
  enhanced prompts and `false` disables enhanced prompts. The
  default value is `true`.

HTTP method and URL:

```
POST https://LOCATION-aiplatform.googleapis.com/v1/projects/PROJECT_ID/locations/LOCATION/publishers/google/models/MODEL_VERSION:predict
```

Request JSON body:

```
{
  "instances": [
    {
      "prompt": "TEXT_PROMPT"
    }
  ],
  "parameters": {
    "sampleCount": IMAGE_COUNT,
    "enhancePrompt": PROMPT_SETTING
  }
}
```

To send your request, choose one of these options:

#### curl

**Note:**
The following command assumes that you have logged in to
the `gcloud` CLI with your user account by running
[`gcloud init`](https://docs.cloud.google.com/sdk/gcloud/reference/init)
or
[`gcloud auth login`](https://docs.cloud.google.com/sdk/gcloud/reference/auth/login)
, or by using [Cloud Shell](https://docs.cloud.google.com/shell/docs),
which automatically logs you into the `gcloud` CLI
.
You can check the currently active account by running
[`gcloud auth list`](https://docs.cloud.google.com/sdk/gcloud/reference/auth/list).

Save the request body in a file named `request.json`,
and execute the following command:

```
curl -X POST \     -H "Authorization: Bearer $(gcloud auth print-access-token)" \     -H "Content-Type: application/json; charset=utf-8" \     -d @request.json \     "https://LOCATION-aiplatform.googleapis.com/v1/projects/PROJECT_ID/locations/LOCATION/publishers/google/models/MODEL_VERSION:predict"
```

#### PowerShell

**Note:**
The following command assumes that you have logged in to
the `gcloud` CLI with your user account by running
[`gcloud init`](https://docs.cloud.google.com/sdk/gcloud/reference/init)
or
[`gcloud auth login`](https://docs.cloud.google.com/sdk/gcloud/reference/auth/login)
.
You can check the currently active account by running
[`gcloud auth list`](https://docs.cloud.google.com/sdk/gcloud/reference/auth/list).

Save the request body in a file named `request.json`,
and execute the following command:

```
$cred = gcloud auth print-access-token$headers = @{ "Authorization" = "Bearer $cred" }Invoke-WebRequest `    -Method POST `    -Headers $headers `    -ContentType: "application/json; charset=utf-8" `    -InFile request.json `    -Uri "https://LOCATION-aiplatform.googleapis.com/v1/projects/PROJECT_ID/locations/LOCATION/publishers/google/models/MODEL_VERSION:predict" | Select-Object -Expand Content
```

With prompt enhancement enabled, the response includes an additional
`prompt` field that shows the enhanced prompt and its associated
generated image:

```json
  {
    "predictions": [
      {
        "mimeType": "MIME_TYPE",
        "prompt": "ENHANCED_PROMPT_1",
        "bytesBase64Encoded": "BASE64_IMG_BYTES_1"
      },
      {
        "mimeType": "MIME_TYPE",
        "prompt": "ENHANCED_PROMPT_2",
        "bytesBase64Encoded": "BASE64_IMG_BYTES_2"
      }
    ]
  }
```

For example, the following sample response is for a request with
`"sampleCount": 2` and `"prompt": "A raccoon wearing formal
clothes, wearing a top hat. Oil painting in the style of Vincent Van
Gogh."`. The response returns two prediction objects, each with their
enhanced prompt and the generated image bytes base64-encoded.

```
{
  "predictions": [
    {
      "mimeType": "image/png",
      "prompt": "An oil painting in the style of Vincent van Gogh,
        depicting a raccoon adorned in a finely tailored tuxedo, complete with a
        crisp white shirt and a bow tie. The raccoon also sports a classic top
        hat, perched jauntily on its head. The painting uses thick, swirling
        brushstrokes characteristic of van Gogh, with vibrant hues of blue,
        yellow, and green in the background, contrasting with the dark tones of
        the raccoon's attire. The light source is subtly placed, casting a
        dramatic shadow of the raccoon's attire onto the surface it sits upon,
        further enhancing the depth and dimensionality of the composition. The
        overall impression is one of a whimsical and sophisticated character, a
        raccoon elevated to a higher class through its formal attire, rendered
        in van Gogh's iconic style.",
      "bytesBase64Encoded": "BASE64_IMG_BYTES"
    },
    {
      "mimeType": "image/png",
      "prompt": "An oil painting in the style of Vincent van Gogh featuring
        a raccoon in a dapper suit, complete with a black jacket, crisp white
        shirt, and a black bow tie. The raccoon is wearing a black top hat,
        adding a touch of elegance to its ensemble. The painting is rendered
        with characteristic van Gogh brushwork, utilizing thick, impasto strokes
        of color. The background is a swirl of blues, greens, and yellows,
        creating a vibrant yet slightly chaotic atmosphere that contrasts with
        the raccoon's formal attire. The lighting is dramatic, casting sharp
        shadows and highlighting the textures of the fabric and the raccoon's
        fur, enhancing the sense of realism within the fantastical scene. The
        composition focuses on the raccoon's proud posture, highlighting the
        whimsical contrast of a wild animal dressed in formal attire, captured
        in the unique artistic language of van Gogh. ",
      "bytesBase64Encoded": "BASE64_IMG_BYTES"
    }
  ]
}
```

## What's next

- [Set text prompt language](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/image/set-text-prompt-language)
- [Configure aspect ratio](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/image/configure-aspect-ratio)
- [Omit content using a negative prompt](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/image/omit-content-using-a-negative-prompt)
- [Generate deterministic images](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/image/generate-deterministic-images)
