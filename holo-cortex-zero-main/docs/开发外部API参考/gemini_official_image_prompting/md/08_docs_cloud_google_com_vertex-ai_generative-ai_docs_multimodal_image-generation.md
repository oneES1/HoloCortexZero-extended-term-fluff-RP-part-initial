# Generate and edit images with Gemini

> Source: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/image-generation
> Downloaded: 2026-02-05

**Caution:** The `gemini-2.0-flash-preview-image-generation` and
`gemini-2.5-flash-image-preview`
models will be retired on October 31, 2025.
Migrate any workflows to `gemini-2.5-flash-image`
before that date to avoid service disruption.
**Note:** Image output is only supported in `gemini-3-pro-image-preview`
(preview) and `gemini-2.5-flash-image`, but not in
`gemini-3-pro` (preview) and `gemini-2.5-flash`.

To see examples of image generation with Gemini,
run the following notebooks in the environment of your choice:

- "Gemini 3 Pro Image Generation in Vertex AI":

  [![](https://docs.cloud.google.com/static/vertex-ai/images/colab-logo-32px.png)Open in Colab](https://colab.research.google.com/github/GoogleCloudPlatform/generative-ai/blob/main/gemini/getting-started/intro_gemini_3_image_gen.ipynb)
  |
  [![](https://docs.cloud.google.com/static/vertex-ai/images/colab-enterprise-logo-32px.png)Open in Colab Enterprise](https://console.cloud.google.com/vertex-ai/colab/import/https%3A%2F%2Fraw.githubusercontent.com%2FGoogleCloudPlatform%2Fgenerative-ai%2Fmain%2Fgemini%2Fgetting-started%2Fintro_gemini_3_image_gen.ipynb)
  |
  [![](https://docs.cloud.google.com/static/vertex-ai/images/vertex-ai-workbench-logo-32px.png)Open
  in Vertex AI Workbench](https://console.cloud.google.com/vertex-ai/workbench/deploy-notebook?download_url=https%3A%2F%2Fraw.githubusercontent.com%2FGoogleCloudPlatform%2Fgenerative-ai%2Fmain%2Fgemini%2Fgetting-started%2Fintro_gemini_3_image_gen.ipynb)
  |
  [![](https://docs.cloud.google.com/static/vertex-ai/images/github-logo-32px.png)View on GitHub](https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/getting-started/intro_gemini_3_image_gen.ipynb)
- "Gemini 2.5 Flash Image Generation in Vertex AI":

  [![](https://docs.cloud.google.com/static/vertex-ai/images/colab-logo-32px.png)Open in Colab](https://colab.research.google.com/github/GoogleCloudPlatform/generative-ai/blob/main/gemini/getting-started/intro_gemini_2_5_image_gen.ipynb)
  |
  [![](https://docs.cloud.google.com/static/vertex-ai/images/colab-enterprise-logo-32px.png)Open in Colab Enterprise](https://console.cloud.google.com/vertex-ai/colab/import/https%3A%2F%2Fraw.githubusercontent.com%2FGoogleCloudPlatform%2Fgenerative-ai%2Fmain%2Fgemini%2Fgetting-started%2Fintro_gemini_2_5_image_gen.ipynb)
  |
  [![](https://docs.cloud.google.com/static/vertex-ai/images/vertex-ai-workbench-logo-32px.png)Open
  in Vertex AI Workbench](https://console.cloud.google.com/vertex-ai/workbench/deploy-notebook?download_url=https%3A%2F%2Fraw.githubusercontent.com%2FGoogleCloudPlatform%2Fgenerative-ai%2Fmain%2Fgemini%2Fgetting-started%2Fintro_gemini_2_5_image_gen.ipynb)
  |
  [![](https://docs.cloud.google.com/static/vertex-ai/images/github-logo-32px.png)View on GitHub](https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/getting-started/intro_gemini_2_5_image_gen.ipynb)

The following Gemini models support the ability to generate images
in addition to text:

- Gemini 2.5 Flash Image, otherwise known as Gemini 2.5 Flash (with Nano Banana)
- Gemini 3 Pro Image (preview), otherwise known as Gemini 3 Pro (with Nano Banana)

This expands Gemini's capabilities to include the following:

- Iteratively generate images through conversation with natural language,
  adjusting images while maintaining consistency and context.
- Generate images with high-quality long text rendering.
- Generate interleaved text-image output. For example, a blog post with
  text and images in a single turn. Previously, this required stringing
  together multiple models.
- Generate images using Gemini's world knowledge and reasoning capabilities.

Gemini 2.5 Flash Image (`gemini-2.5-flash-image`) and Gemini 3 Pro Image preview (`gemini-3-pro-image-preview`) support
generating images of people and contains updated safety filters that provide a
more flexible and less restrictive user experience. Gemini 2.5 Flash Image
can generate images in 1024px. Gemini 3 Pro Image can generate images
up to 4096px.

Both models support the following modalities and capabilities:

- Text to image

  - **Example prompt:** "Generate an image of the Eiffel tower with
    fireworks in the background."
- Text to image (text rendering)

  - **Example prompt:** "generate a cinematic photo of a large
    building with this giant text projection mapped on the front of the
    building: "Gemini 3 can now generate long form text""
- Text to image(s) and text (interleaved)

  - **Example prompt:** "Generate an illustrated recipe for a
    paella. Create images alongside the text as you generate the recipe."
  - **Example prompt:** "Generate a story about a dog in a 3D
    cartoon animation style. For each scene, generate an image"
- Image(s) and text to image(s) and text (interleaved)

  - **Example prompt:** (With an image of a furnished room) "What
    other color sofas would work in my space? Can you update the image?"

**Best practices**

To improve your image generation results, follow these best practices:

- **Be specific:** More details give you more control. For example, instead of
  "fantasy armor," try "ornate elven plate armor, etched with silver leaf
  patterns, with a high collar and pauldrons shaped like falcon wings."
- **Provide context and intent:** Explain the purpose of the image to help the
  model understand the context. For example, "Create a logo for a high-end,
  minimalist skincare brand" works better than "Create a logo."
- **Iterate and refine:** Don't expect a perfect image on your first attempt.
  Use follow-up prompts to make small changes, for example, "Make the lighting
  warmer" or "Change the character's expression to be more serious."
- **Use step-by-step instructions:** For complex scenes, split your request
  into steps. For example, "First, create a background of a serene, misty
  forest at dawn. Then, in the foreground, add a moss-covered ancient stone
  altar. Finally, place a single, glowing sword on top of the altar."
- **Describe what you want, not what you don't:** Instead of saying "no cars",
  describe the scene positively by saying, "an empty, deserted street with no
  signs of traffic."
- **Control the camera:** Guide the camera view. Use photographic and
  cinematic terms to describe the composition, for example, "wide-angle shot",
  "macro shot", or "low-angle perspective".
- **Prompt for images:** Describe the intent by using phrases such as "create
  an image of" or "generate an image of". Otherwise, the multimodal model
  might respond with text instead of the image.
- **Pass [Thought Signatures](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/thought-signatures):**
  When using Gemini 3 Pro Image, we recommend that you pass thought signatures
  back to the model during multi-turn image creation and editing. This lets you preserve reasoning
  context across interactions. For code samples related to multi-turn image editing using
  Gemini 3 Pro Image, see
  [Example of multi-turn image editing using thought signatures](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/thought-signatures#multi-turn-image-editing).

**Limitations:**

- For best performance with Gemini 2.5 Flash Image, use the following
  languages: EN, es-MX, ja-JP, zh-CN, or hi-IN. For best performance with
  Gemini 3 Pro Image, use the following languages: ar-EG, de-DE, EN,
  es-MX, fr-FR, hi-IN, id-ID, it-IT, ja-JP, ko-KR, pt-BR, ru-RU, ua-UA, vi-VN,
  and zh-CN
- Image generation doesn't support audio or video inputs.
- The model might not create the exact number of images you ask for.
- For best results using Gemini 2.5 Flash Image, include a maximum of
  three images in an input. For best results using Gemini 3 Pro Image,
  include a maximum of 14 images in an input.
- When generating an image containing text, first generate the text and then
  generate an image with that text.
- Image or text generation might not work as expected in these situations:

  - The model might only create text and no image if the prompt is
    ambiguous. If you want images, clearly ask for images in your request.
    For example, "provide images as you go along."
  - The model might create text as an image. To generate text, specifically
    ask for text output. For example, "generate narrative text along with
    illustrations."
  - The model might stop generating content even when it's not finished. If
    this occurs, try again or use a different prompt.
  - If a prompt is potentially unsafe, the model might not process the request
    and returns a response indicating that it can't create unsafe images. In
    this case, the
    [`FinishReason`](https://docs.cloud.google.com/vertex-ai/docs/reference/rest/v1/GenerateContentResponse#FinishReason) is
    `STOP`.

## Generate images

The following sections cover how to generate images using either
Vertex AI Studio or using the API.

For guidance and best practices for prompting, see
[Design multimodal prompts](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/design-multimodal-prompts#fundamentals).

### Console

To use image generation:

1. Open [**Vertex AI Studio > Create prompt**](https://console.cloud.google.com/vertex-ai/studio/multimodal;mode=prompt).
2. Click **Switch model** and select one of the following models from the menu:
   - **`gemini-2.5-flash-image`**
   - **`gemini-3-pro-image-preview`**
3. In the **Outputs** panel, select **Image and text** from the
   drop-down menu.
4. Write a description of the image you want to generate in the text area of
   the **Write a prompt** text area.
5. Click the **Prompt** (send) button.

Gemini will generate an image based on your description. This
process takes a few seconds, but can be comparatively slower depending on
capacity.

### Python

#### Install

```
pip install --upgrade google-genai
```

To learn more, see the
[SDK reference documentation](https://googleapis.github.io/python-genai/).

Set environment variables to use the Gen AI SDK with Vertex AI:

```bash
# Replace the `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` values
# with appropriate values for your project.
export GOOGLE_CLOUD_PROJECT=GOOGLE_CLOUD_PROJECT
export GOOGLE_CLOUD_LOCATION=global
export GOOGLE_GENAI_USE_VERTEXAI=True
```

```python
from google import genai
from google.genai.types import GenerateContentConfig, Modality
from PIL import Image
from io import BytesIO

client = genai.Client()

response = client.models.generate_content(
    model="gemini-3-pro-image-preview",
    contents=("Generate an image of the Eiffel tower with fireworks in the background."),
    config=GenerateContentConfig(
        response_modalities=[Modality.TEXT, Modality.IMAGE],
    ),
)
for part in response.candidates[0].content.parts:
    if part.text:
        print(part.text)
    elif part.inline_data:
        image = Image.open(BytesIO((part.inline_data.data)))
        image.save("output_folder/example-image-eiffel-tower.png")
```

### Go

Learn how to install or update the [Go](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/sdks/overview).

To learn more, see the
[SDK reference documentation](https://pkg.go.dev/google.golang.org/genai).

Set environment variables to use the Gen AI SDK with Vertex AI:

```bash
# Replace the `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` values
# with appropriate values for your project.
export GOOGLE_CLOUD_PROJECT=GOOGLE_CLOUD_PROJECT
export GOOGLE_CLOUD_LOCATION=global
export GOOGLE_GENAI_USE_VERTEXAI=True
```

```python
import (
	"context"
	"fmt"
	"io"
	"os"

	"google.golang.org/genai"
)

// generateMMFlashWithText demonstrates how to generate both text and image outputs.
func generateMMFlashWithText(w io.Writer) error {
	ctx := context.Background()

	client, err := genai.NewClient(ctx, &genai.ClientConfig{
		HTTPOptions: genai.HTTPOptions{APIVersion: "v1"},
	})
	if err != nil {
		return fmt.Errorf("failed to create genai client: %w", err)
	}

	modelName := "gemini-2.5-flash-image"
	contents := []*genai.Content{
		{
			Parts: []*genai.Part{
				{Text: "Generate an image of the Eiffel tower with fireworks in the background."},
			},
			Role: genai.RoleUser,
		},
	}

	resp, err := client.Models.GenerateContent(ctx,
		modelName,
		contents,
		&genai.GenerateContentConfig{
			ResponseModalities: []string{
				string(genai.ModalityText),
				string(genai.ModalityImage),
			},
			CandidateCount: int32(1),
			SafetySettings: []*genai.SafetySetting{
				{Method: genai.HarmBlockMethodProbability},
				{Category: genai.HarmCategoryDangerousContent},
				{Threshold: genai.HarmBlockThresholdBlockMediumAndAbove},
			},
		},
	)
	if err != nil {
		return fmt.Errorf("failed to generate content: %w", err)
	}

	if len(resp.Candidates) == 0 || resp.Candidates[0].Content == nil {
		return fmt.Errorf("no candidates returned")
	}
	var fileName string
	for _, part := range resp.Candidates[0].Content.Parts {
		if part.Text != "" {
			fmt.Fprintln(w, part.Text)
		} else if part.InlineData != nil {
			fileName = "example-image-eiffel-tower.png"
			if err := os.WriteFile(fileName, part.InlineData.Data, 0o644); err != nil {
				return fmt.Errorf("failed to save image: %w", err)
			}
		}
	}
	fmt.Fprintln(w, fileName)

	// Example response:
	// I will generate an image of the Eiffel Tower at night, with a vibrant display of
	// colorful fireworks exploding in the dark sky behind it.
	// ....
	return nil
}
```

### Node.js

#### Install

```
npm install @google/genai
```

To learn more, see the
[SDK reference documentation](https://googleapis.github.io/js-genai/).

Set environment variables to use the Gen AI SDK with Vertex AI:

```bash
# Replace the `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` values
# with appropriate values for your project.
export GOOGLE_CLOUD_PROJECT=GOOGLE_CLOUD_PROJECT
export GOOGLE_CLOUD_LOCATION=global
export GOOGLE_GENAI_USE_VERTEXAI=True
```

```gdscript
const fs = require('fs');
const {GoogleGenAI, Modality} = require('@google/genai');

const GOOGLE_CLOUD_PROJECT = process.env.GOOGLE_CLOUD_PROJECT;
const GOOGLE_CLOUD_LOCATION =
  process.env.GOOGLE_CLOUD_LOCATION || 'us-central1';

async function generateImage(
  projectId = GOOGLE_CLOUD_PROJECT,
  location = GOOGLE_CLOUD_LOCATION
) {
  const client = new GoogleGenAI({
    vertexai: true,
    project: projectId,
    location: location,
  });

  const response = await client.models.generateContentStream({
    model: 'gemini-2.5-flash-image',
    contents:
      'Generate an image of the Eiffel tower with fireworks in the background.',
    config: {
      responseModalities: [Modality.TEXT, Modality.IMAGE],
    },
  });

  const generatedFileNames = [];
  let imageIndex = 0;

  for await (const chunk of response) {
    const text = chunk.text;
    const data = chunk.data;
    if (text) {
      console.debug(text);
    } else if (data) {
      const outputDir = 'output-folder';
      if (!fs.existsSync(outputDir)) {
        fs.mkdirSync(outputDir, {recursive: true});
      }
      const fileName = `${outputDir}/generate_content_streaming_image_${imageIndex++}.png`;
      console.debug(`Writing response image to file: ${fileName}.`);
      try {
        fs.writeFileSync(fileName, data);
        generatedFileNames.push(fileName);
      } catch (error) {
        console.error(`Failed to write image file ${fileName}:`, error);
      }
    }
  }

  // Example response:
  //  I will generate an image of the Eiffel Tower at night, with a vibrant display of
  //  colorful fireworks exploding in the dark sky behind it. The tower will be
  //  illuminated, standing tall as the focal point of the scene, with the bursts of
  //  light from the fireworks creating a festive atmosphere.

  return generatedFileNames;
}
```

### Java

Learn how to install or update the [Java](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/sdks/overview).

To learn more, see the
[SDK reference documentation](https://central.sonatype.com/artifact/com.google.genai/google-genai).

Set environment variables to use the Gen AI SDK with Vertex AI:

```bash
# Replace the `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` values
# with appropriate values for your project.
export GOOGLE_CLOUD_PROJECT=GOOGLE_CLOUD_PROJECT
export GOOGLE_CLOUD_LOCATION=global
export GOOGLE_GENAI_USE_VERTEXAI=True
```

```python
import com.google.genai.Client;
import com.google.genai.types.Blob;
import com.google.genai.types.Candidate;
import com.google.genai.types.Content;
import com.google.genai.types.GenerateContentConfig;
import com.google.genai.types.GenerateContentResponse;
import com.google.genai.types.Part;
import com.google.genai.types.SafetySetting;
import java.awt.image.BufferedImage;
import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import javax.imageio.ImageIO;

public class ImageGenMmFlashWithText {

  public static void main(String[] args) throws IOException {
    // TODO(developer): Replace these variables before running the sample.
    String modelId = "gemini-2.5-flash-image";
    String outputFile = "resources/output/example-image-eiffel-tower.png";
    generateContent(modelId, outputFile);
  }

  // Generates an image with text input
  public static void generateContent(String modelId, String outputFile) throws IOException {
    // Client Initialization. Once created, it can be reused for multiple requests.
    try (Client client = Client.builder().location("global").vertexAI(true).build()) {

      GenerateContentConfig contentConfig =
          GenerateContentConfig.builder()
              .responseModalities("TEXT", "IMAGE")
              .candidateCount(1)
              .safetySettings(
                  SafetySetting.builder()
                      .method("PROBABILITY")
                      .category("HARM_CATEGORY_DANGEROUS_CONTENT")
                      .threshold("BLOCK_MEDIUM_AND_ABOVE")
                      .build())
              .build();

      GenerateContentResponse response =
          client.models.generateContent(
              modelId,
              "Generate an image of the Eiffel tower with fireworks in the background.",
              contentConfig);

      // Get parts of the response
      List<Part> parts =
          response
              .candidates()
              .flatMap(candidates -> candidates.stream().findFirst())
              .flatMap(Candidate::content)
              .flatMap(Content::parts)
              .orElse(new ArrayList<>());

      // For each part print text if present, otherwise read image data if present and
      // write it to the output file
      for (Part part : parts) {
        if (part.text().isPresent()) {
          System.out.println(part.text().get());
        } else if (part.inlineData().flatMap(Blob::data).isPresent()) {
          BufferedImage image =
              ImageIO.read(new ByteArrayInputStream(part.inlineData().flatMap(Blob::data).get()));
          ImageIO.write(image, "png", new File(outputFile));
        }
      }

      System.out.println("Content written to: " + outputFile);
      // Example response:
      // Here is the Eiffel Tower with fireworks in the background...
      //
      // Content written to: resources/output/example-image-eiffel-tower.png
    }
  }
}
```

### REST

Run the following command in the terminal to create or overwrite this file in
the current directory:

```bash
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  https://${API_ENDPOINT}:generateContent \
  -d '{
    "contents": {
      "role": "USER",
      "parts": [
        {
          "text": "Create a tutorial explaining how to make a peanut butter and jelly sandwich in three easy steps."
        }
      ]
    },
    "generationConfig": {
      "responseModalities": ["TEXT", "IMAGE"],
      "imageConfig": {
        "aspectRatio": "16:9",
      },
     },
     "safetySettings": {
      "method": "PROBABILITY",
      "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
      "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
  }' 2>/dev/null >response.json
```

**Note:** Gemini 2.5 Flash Image supports the following aspect
ratios: `1:1`, `3:2`, `2:3`,
`3:4`, `4:3`, `4:5`, `5:4`,
`9:16`, `16:9`, and `21:9`.

Gemini will generate an image based on your description. This
process takes a few seconds, but can be comparatively slower depending on
capacity.

## Generate interleaved images and text

Gemini 2.5 Flash Image can generate interleaved images with its
text responses. For example, you can generate images of what each step of a
generated recipe might look like to go along with the text of that step, without
having to make separate requests to the model to do so.

### Console

To generate interleaved images with text responses:

1. Open [**Vertex AI Studio > Create prompt**](https://console.cloud.google.com/vertex-ai/studio/multimodal;mode=prompt).
2. Click **Switch model** and select one of the following models from the menu:
   - **`gemini-2.5-flash-image`**
   - **`gemini-3-pro-image-preview`**
3. In the **Outputs** panel, select **Image and text** from the
   drop-down menu.
4. Write a description of the image you want to generate in the text area of
   the **Write a prompt** text area. For example, "Create a tutorial
   explaining how to make a peanut butter and jelly sandwich in three easy
   steps. For each step, provide a title with the number of the step, an
   explanation, and also generate an image, generate each image in a 1:1 aspect
   ratio."
5. Click the **Prompt** (send) button.

Gemini will generate a response based on your description. This
process takes a few seconds, but can be comparatively slower depending on
capacity.

### Python

#### Install

```
pip install --upgrade google-genai
```

To learn more, see the
[SDK reference documentation](https://googleapis.github.io/python-genai/).

Set environment variables to use the Gen AI SDK with Vertex AI:

```bash
# Replace the `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` values
# with appropriate values for your project.
export GOOGLE_CLOUD_PROJECT=GOOGLE_CLOUD_PROJECT
export GOOGLE_CLOUD_LOCATION=global
export GOOGLE_GENAI_USE_VERTEXAI=True
```

```python
from google import genai
from google.genai.types import GenerateContentConfig, Modality
from PIL import Image
from io import BytesIO

client = genai.Client()

response = client.models.generate_content(
    model="gemini-3-pro-image-preview",
    contents=(
        "Generate an illustrated recipe for a paella."
        "Create images to go alongside the text as you generate the recipe"
    ),
    config=GenerateContentConfig(response_modalities=[Modality.TEXT, Modality.IMAGE]),
)
with open("output_folder/paella-recipe.md", "w") as fp:
    for i, part in enumerate(response.candidates[0].content.parts):
        if part.text is not None:
            fp.write(part.text)
        elif part.inline_data is not None:
            image = Image.open(BytesIO((part.inline_data.data)))
            image.save(f"output_folder/example-image-{i+1}.png")
            fp.write(f"![image](example-image-{i+1}.png)")
```

### Java

Learn how to install or update the [Java](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/sdks/overview).

To learn more, see the
[SDK reference documentation](https://central.sonatype.com/artifact/com.google.genai/google-genai).

Set environment variables to use the Gen AI SDK with Vertex AI:

```bash
# Replace the `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` values
# with appropriate values for your project.
export GOOGLE_CLOUD_PROJECT=GOOGLE_CLOUD_PROJECT
export GOOGLE_CLOUD_LOCATION=global
export GOOGLE_GENAI_USE_VERTEXAI=True
```

```python
import com.google.genai.Client;
import com.google.genai.types.Blob;
import com.google.genai.types.Candidate;
import com.google.genai.types.Content;
import com.google.genai.types.GenerateContentConfig;
import com.google.genai.types.GenerateContentResponse;
import com.google.genai.types.Part;
import java.awt.image.BufferedImage;
import java.io.BufferedWriter;
import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import javax.imageio.ImageIO;

public class ImageGenMmFlashTextAndImageWithText {

  public static void main(String[] args) throws IOException {
    // TODO(developer): Replace these variables before running the sample.
    String modelId = "gemini-2.5-flash-image";
    String outputFile = "resources/output/paella-recipe.md";
    generateContent(modelId, outputFile);
  }

  // Generates text and image with text input
  public static void generateContent(String modelId, String outputFile) throws IOException {
    // Client Initialization. Once created, it can be reused for multiple requests.
    try (Client client = Client.builder().location("global").vertexAI(true).build()) {

      GenerateContentResponse response =
          client.models.generateContent(
              modelId,
              Content.fromParts(
                  Part.fromText("Generate an illustrated recipe for a paella."),
                  Part.fromText(
                      "Create images to go alongside the text as you generate the recipe.")),
              GenerateContentConfig.builder().responseModalities("TEXT", "IMAGE").build());

      try (BufferedWriter writer = new BufferedWriter(new FileWriter(outputFile))) {

        // Get parts of the response
        List<Part> parts =
            response
                .candidates()
                .flatMap(candidates -> candidates.stream().findFirst())
                .flatMap(Candidate::content)
                .flatMap(Content::parts)
                .orElse(new ArrayList<>());

        int index = 1;
        // For each part print text if present, otherwise read image data if present and
        // write it to the output file
        for (Part part : parts) {
          if (part.text().isPresent()) {
            writer.write(part.text().get());
          } else if (part.inlineData().flatMap(Blob::data).isPresent()) {
            BufferedImage image =
                ImageIO.read(new ByteArrayInputStream(part.inlineData().flatMap(Blob::data).get()));
            ImageIO.write(
                image, "png", new File("resources/output/example-image-" + index + ".png"));
            writer.write("![image](example-image-" + index + ".png)");
          }
          index++;
        }

        System.out.println("Content written to: " + outputFile);

        // Example response:
        // A markdown page for a Paella recipe(`paella-recipe.md`) has been generated.
        // It includes detailed steps and several images illustrating the cooking process.
        //
        // Content written to:  resources/output/paella-recipe.md
      }
    }
  }
}
```

### Go

Learn how to install or update the [Go](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/sdks/overview).

To learn more, see the
[SDK reference documentation](https://pkg.go.dev/google.golang.org/genai).

Set environment variables to use the Gen AI SDK with Vertex AI:

```bash
# Replace the `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` values
# with appropriate values for your project.
export GOOGLE_CLOUD_PROJECT=GOOGLE_CLOUD_PROJECT
export GOOGLE_CLOUD_LOCATION=global
export GOOGLE_GENAI_USE_VERTEXAI=True
```

```python
import (
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"

	"google.golang.org/genai"
)

// generateMMFlashTxtImgWithText demonstrates how to generate an illustrated recipe
// combining text and image outputs into a markdown file.
func generateMMFlashTxtImgWithText(w io.Writer) error {
	ctx := context.Background()

	client, err := genai.NewClient(ctx, &genai.ClientConfig{
		HTTPOptions: genai.HTTPOptions{APIVersion: "v1"},
	})
	if err != nil {
		return fmt.Errorf("failed to create genai client: %w", err)
	}

	modelName := "gemini-2.5-flash-image"
	contents := []*genai.Content{
		{
			Parts: []*genai.Part{
				{Text: "Generate an illustrated recipe for a paella. " +
					"Create images to go alongside the text as you generate the recipe."},
			},
			Role: genai.RoleUser,
		},
	}

	resp, err := client.Models.GenerateContent(ctx,
		modelName,
		contents,
		&genai.GenerateContentConfig{
			ResponseModalities: []string{
				string(genai.ModalityText),
				string(genai.ModalityImage),
			},
			CandidateCount: int32(1),
		},
	)
	if err != nil {
		return fmt.Errorf("failed to generate content: %w", err)
	}

	if len(resp.Candidates) == 0 || resp.Candidates[0].Content == nil {
		return fmt.Errorf("no candidates returned")
	}

	outputFolder := ""

	// Create the markdown file
	mdFile := filepath.Join(outputFolder, "paella-recipe.md")
	fp, err := os.Create(mdFile)
	if err != nil {
		return fmt.Errorf("failed to create markdown file: %w", err)
	}
	defer fp.Close()

	for i, part := range resp.Candidates[0].Content.Parts {
		if part.Text != "" {
			if _, err := fp.WriteString(part.Text); err != nil {
				return fmt.Errorf("failed to write text: %w", err)
			}
		} else if part.InlineData != nil {
			imgFile := filepath.Join(outputFolder, fmt.Sprintf("example-image-%d.png", i+1))
			if err := os.WriteFile(imgFile, part.InlineData.Data, 0644); err != nil {
				return fmt.Errorf("failed to save image: %w", err)
			}
			if _, err := fp.WriteString(fmt.Sprintf("![image](%s)", filepath.Base(imgFile))); err != nil {
				return fmt.Errorf("failed to write image reference: %w", err)
			}
		}
	}

	fmt.Fprintln(w, mdFile)

	// Example response:
	//  A markdown page for a Paella recipe (`paella-recipe.md`) has been generated.
	//  It includes detailed steps and several images illustrating the cooking process.
	return nil
}
```

### Node.js

#### Install

```
npm install @google/genai
```

To learn more, see the
[SDK reference documentation](https://googleapis.github.io/js-genai/).

Set environment variables to use the Gen AI SDK with Vertex AI:

```bash
# Replace the `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` values
# with appropriate values for your project.
export GOOGLE_CLOUD_PROJECT=GOOGLE_CLOUD_PROJECT
export GOOGLE_CLOUD_LOCATION=global
export GOOGLE_GENAI_USE_VERTEXAI=True
```

```transact-sql
const fs = require('fs');
const {GoogleGenAI, Modality} = require('@google/genai');

const GOOGLE_CLOUD_PROJECT = process.env.GOOGLE_CLOUD_PROJECT;
const GOOGLE_CLOUD_LOCATION =
  process.env.GOOGLE_CLOUD_LOCATION || 'us-central1';

async function savePaellaRecipe(response) {
  const parts = response.candidates[0].content.parts;

  let mdText = '';
  const outputDir = 'output-folder';

  for (let i = 0; i < parts.length; i++) {
    const part = parts[i];

    if (part.text) {
      mdText += part.text + '\n';
    } else if (part.inlineData) {
      if (!fs.existsSync(outputDir)) {
        fs.mkdirSync(outputDir, {recursive: true});
      }
      const imageBytes = Buffer.from(part.inlineData.data, 'base64');
      const imagePath = `example-image-${i + 1}.png`;
      const saveImagePath = `${outputDir}/${imagePath}`;

      fs.writeFileSync(saveImagePath, imageBytes);
      mdText += `![image](./${imagePath})\n`;
    }
  }
  const mdFile = `${outputDir}/paella-recipe.md`;

  fs.writeFileSync(mdFile, mdText);
  console.log(`Saved recipe to: ${mdFile}`);
}

async function generateImage(
  projectId = GOOGLE_CLOUD_PROJECT,
  location = GOOGLE_CLOUD_LOCATION
) {
  const client = new GoogleGenAI({
    vertexai: true,
    project: projectId,
    location: location,
  });

  const response = await client.models.generateContent({
    model: 'gemini-2.5-flash-image',
    contents:
      'Generate an illustrated recipe for a paella. Create images to go alongside the text as you generate the recipe',
    config: {
      responseModalities: [Modality.TEXT, Modality.IMAGE],
    },
  });
  console.log(response);

  await savePaellaRecipe(response);

  return response;
}
// Example response:
//  A markdown page for a Paella recipe(`paella-recipe.md`) has been generated.
//  It includes detailed steps and several images illustrating the cooking process.
```

### REST

Run the following command in the terminal to create or overwrite this file in
the current directory:

```bash
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  https://${API_ENDPOINT}:generateContent \
  -d '{
    "contents": {
      "role": "USER",
      "parts": [
        {
          "text": "Create a tutorial explaining how to make a peanut butter and jelly sandwich in three easy steps. For each step, provide a title with the number of the step, an explanation, and also generate an image, generate each image in a 1:1 aspect ratio."
        }
      ]
    },
    "generationConfig": {
      "responseModalities": ["TEXT", "IMAGE"],
      "imageConfig": {
        "aspectRatio": "16:9",
      },
    },
    "safetySettings": {
      "method": "PROBABILITY",
      "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
      "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
  }' 2>/dev/null >response.json
```

**Note:** Gemini 2.5 Flash Image and Gemini 3 Pro Image
support the following aspect ratios: `1:1`, `3:2`,
`2:3`, `3:4`, `4:3`, `4:5`,
`5:4`, `9:16`, `16:9`, and `21:9`.

Gemini will generate an image based on your description. This
process takes a few seconds, but can be comparatively slower depending on
capacity.

## Edit images

Gemini 2.5 Flash Image for image generation
(`gemini-2.5-flash-image`) supports the ability to edit
images in addition generating them. Gemini 2.5 Flash Image supports
improved editing of images and multi-turn editing, and contains updated safety
filters that provide a more flexible and less restrictive user experience.

It supports the following modalities and capabilities:

- Image editing (text and image to image)

  - **Example prompt:** "Edit this image to make it look like a cartoon"
  - **Example prompt:** [image of a cat] + [image of a pillow] +
    "Create a cross stitch of my cat on this pillow."
- Multi-turn image editing (chat)

  - **Example prompts:** [upload an image of a blue car.] "Turn this car into a convertible."

    - [Model returns an image of a convertible in the same scene] "Now change the color to yellow."
    - [Model returns an image with a yellow convertible] "Add a spoiler."
    - [Model returns an image of the convertible with a spoiler]

### Edit an image

### Console

To edit images:

1. Open [**Vertex AI Studio > Create prompt**](https://console.cloud.google.com/vertex-ai/studio/multimodal).
2. Click **Switch model** and select one of the following models from the menu:
   - **`gemini-2.5-flash-image`**
   - **`gemini-3-pro-image-preview`**
3. In the **Outputs** panel, select **Image and text** from the
   drop-down menu.
4. Click **Insert media** (add\_photo\_alternate) and
   select a source from the menu, then follow the dialog's instructions.
5. Write what edits you want to make to the image in the **Write a prompt**
   text area.
6. Click the **Prompt** (send) button.

Gemini will generate an edited version of the provided image based on
your description. This process takes a few seconds, but can be
comparatively slower depending on capacity.

### Python

#### Install

```
pip install --upgrade google-genai
```

To learn more, see the
[SDK reference documentation](https://googleapis.github.io/python-genai/).

Set environment variables to use the Gen AI SDK with Vertex AI:

```bash
# Replace the `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` values
# with appropriate values for your project.
export GOOGLE_CLOUD_PROJECT=GOOGLE_CLOUD_PROJECT
export GOOGLE_CLOUD_LOCATION=global
export GOOGLE_GENAI_USE_VERTEXAI=True
```

```python
from google import genai
from google.genai.types import GenerateContentConfig, Modality
from PIL import Image
from io import BytesIO

client = genai.Client()

# Using an image of Eiffel tower, with fireworks in the background.
image = Image.open("test_resources/example-image-eiffel-tower.png")

response = client.models.generate_content(
    model="gemini-3-pro-image-preview",
    contents=[image, "Edit this image to make it look like a cartoon."],
    config=GenerateContentConfig(response_modalities=[Modality.TEXT, Modality.IMAGE]),
)
for part in response.candidates[0].content.parts:
    if part.text:
        print(part.text)
    elif part.inline_data:
        image = Image.open(BytesIO((part.inline_data.data)))
        image.save("output_folder/bw-example-image.png")
```

### Java

Learn how to install or update the [Java](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/sdks/overview).

To learn more, see the
[SDK reference documentation](https://central.sonatype.com/artifact/com.google.genai/google-genai).

Set environment variables to use the Gen AI SDK with Vertex AI:

```bash
# Replace the `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` values
# with appropriate values for your project.
export GOOGLE_CLOUD_PROJECT=GOOGLE_CLOUD_PROJECT
export GOOGLE_CLOUD_LOCATION=global
export GOOGLE_GENAI_USE_VERTEXAI=True
```

```python
import com.google.genai.Client;
import com.google.genai.types.Blob;
import com.google.genai.types.Candidate;
import com.google.genai.types.Content;
import com.google.genai.types.GenerateContentConfig;
import com.google.genai.types.GenerateContentResponse;
import com.google.genai.types.Part;
import java.awt.image.BufferedImage;
import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import javax.imageio.ImageIO;

public class ImageGenMmFlashEditImageWithTextAndImage {

  public static void main(String[] args) throws IOException {
    // TODO(developer): Replace these variables before running the sample.
    String modelId = "gemini-2.5-flash-image";
    String outputFile = "resources/output/bw-example-image.png";
    generateContent(modelId, outputFile);
  }

  // Edits an image with image and text input
  public static void generateContent(String modelId, String outputFile) throws IOException {
    // Client Initialization. Once created, it can be reused for multiple requests.
    try (Client client = Client.builder().location("global").vertexAI(true).build()) {

      byte[] localImageBytes =
          Files.readAllBytes(Paths.get("resources/example-image-eiffel-tower.png"));

      GenerateContentResponse response =
          client.models.generateContent(
              modelId,
              Content.fromParts(
                  Part.fromBytes(localImageBytes, "image/png"),
                  Part.fromText("Edit this image to make it look like a cartoon.")),
              GenerateContentConfig.builder().responseModalities("TEXT", "IMAGE").build());

      // Get parts of the response
      List<Part> parts =
          response
              .candidates()
              .flatMap(candidates -> candidates.stream().findFirst())
              .flatMap(Candidate::content)
              .flatMap(Content::parts)
              .orElse(new ArrayList<>());

      // For each part print text if present, otherwise read image data if present and
      // write it to the output file
      for (Part part : parts) {
        if (part.text().isPresent()) {
          System.out.println(part.text().get());
        } else if (part.inlineData().flatMap(Blob::data).isPresent()) {
          BufferedImage image =
              ImageIO.read(new ByteArrayInputStream(part.inlineData().flatMap(Blob::data).get()));
          ImageIO.write(image, "png", new File(outputFile));
        }
      }

      System.out.println("Content written to: " + outputFile);

      // Example response:
      // No problem! Here's the image in a cartoon style...
      //
      // Content written to: resources/output/bw-example-image.png
    }
  }
}
```

### Go

Learn how to install or update the [Go](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/sdks/overview).

To learn more, see the
[SDK reference documentation](https://pkg.go.dev/google.golang.org/genai).

Set environment variables to use the Gen AI SDK with Vertex AI:

```bash
# Replace the `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` values
# with appropriate values for your project.
export GOOGLE_CLOUD_PROJECT=GOOGLE_CLOUD_PROJECT
export GOOGLE_CLOUD_LOCATION=global
export GOOGLE_GENAI_USE_VERTEXAI=True
```

```python
import (
	"context"
	"fmt"
	"io"
	"os"

	"google.golang.org/genai"
)

// generateImageMMFlashEditWithTextImg demonstrates editing an image with text and image inputs.
func generateImageMMFlashEditWithTextImg(w io.Writer) error {
	// TODO(developer): Update below lines
	outputFile := "bw-example-image.png"
	inputFile := "example-image-eiffel-tower.png"
	ctx := context.Background()

	client, err := genai.NewClient(ctx, &genai.ClientConfig{
		HTTPOptions: genai.HTTPOptions{APIVersion: "v1"},
	})
	if err != nil {
		return fmt.Errorf("failed to create genai client: %w", err)
	}

	image, err := os.ReadFile(inputFile)
	if err != nil {
		return fmt.Errorf("failed to read image: %w", err)
	}

	modelName := "gemini-2.5-flash-image"
	prompt := "Edit this image to make it look like a cartoon."
	contents := []*genai.Content{
		{
			Role: "user",
			Parts: []*genai.Part{
				{Text: prompt},
				{InlineData: &genai.Blob{
					MIMEType: "image/png",
					Data:     image,
				}},
			},
		},
	}
	resp, err := client.Models.GenerateContent(ctx,
		modelName,
		contents,
		&genai.GenerateContentConfig{
			ResponseModalities: []string{
				string(genai.ModalityText),
				string(genai.ModalityImage),
			},
		},
	)
	if err != nil {
		return fmt.Errorf("failed to generate content: %w", err)
	}

	if len(resp.Candidates) == 0 || resp.Candidates[0].Content == nil {
		return fmt.Errorf("no content was generated")
	}

	for _, part := range resp.Candidates[0].Content.Parts {
		if part.Text != "" {
			fmt.Fprintln(w, part.Text)
		} else if part.InlineData != nil {
			if len(part.InlineData.Data) > 0 {
				if err := os.WriteFile(outputFile, part.InlineData.Data, 0644); err != nil {
					return fmt.Errorf("failed to save image: %w", err)
				}
				fmt.Fprintln(w, outputFile)
			}
		}
	}

	// Example response:
	// Here's the image of the Eiffel Tower and fireworks, cartoonized for you!
	// Cartoon-style edit:
	//  - Simplified the Eiffel Tower with bolder lines and slightly exaggerated proportions.
	//  - Brightened and saturated the colors of the sky, fireworks, and foliage for a more vibrant, cartoonish look.
	//  ....
	return nil
}
```

### Node.js

#### Install

```
npm install @google/genai
```

To learn more, see the
[SDK reference documentation](https://googleapis.github.io/js-genai/).

Set environment variables to use the Gen AI SDK with Vertex AI:

```bash
# Replace the `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` values
# with appropriate values for your project.
export GOOGLE_CLOUD_PROJECT=GOOGLE_CLOUD_PROJECT
export GOOGLE_CLOUD_LOCATION=global
export GOOGLE_GENAI_USE_VERTEXAI=True
```

```gdscript
const fs = require('fs');
const {GoogleGenAI, Modality} = require('@google/genai');

const GOOGLE_CLOUD_PROJECT = process.env.GOOGLE_CLOUD_PROJECT;
const GOOGLE_CLOUD_LOCATION =
  process.env.GOOGLE_CLOUD_LOCATION || 'us-central1';

const FILE_NAME = 'test-data/example-image-eiffel-tower.png';

async function generateImage(
  projectId = GOOGLE_CLOUD_PROJECT,
  location = GOOGLE_CLOUD_LOCATION
) {
  const client = new GoogleGenAI({
    vertexai: true,
    project: projectId,
    location: location,
  });

  const imageBytes = fs.readFileSync(FILE_NAME);

  const response = await client.models.generateContent({
    model: 'gemini-2.5-flash-image',
    contents: [
      {
        role: 'user',
        parts: [
          {
            inlineData: {
              mimeType: 'image/png',
              data: imageBytes.toString('base64'),
            },
          },
          {
            text: 'Edit this image to make it look like a cartoon',
          },
        ],
      },
    ],
    config: {
      responseModalities: [Modality.TEXT, Modality.IMAGE],
    },
  });

  for (const part of response.candidates[0].content.parts) {
    if (part.text) {
      console.log(`${part.text}`);
    } else if (part.inlineData) {
      const outputDir = 'output-folder';
      if (!fs.existsSync(outputDir)) {
        fs.mkdirSync(outputDir, {recursive: true});
      }
      const imageBytes = Buffer.from(part.inlineData.data, 'base64');
      const filename = `${outputDir}/bw-example-image.png`;
      fs.writeFileSync(filename, imageBytes);
    }
  }

  // Example response:
  // Okay, I will edit this image to give it a cartoonish style, with bolder outlines, simplified details, and more vibrant colors.
  return response;
}
```

### REST

Run the following command in the terminal to create or overwrite this file in
the current directory:

```bash
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  https://${API_ENDPOINT}:generateContent \
  -d '{
    "contents": {
      "role": "USER",
      "parts": [
        {"fileData": {
          "mimeType": "image/jpg",
          "fileUri": "FILE_NAME"
          }
        },
        {"text": "Convert this photo to black and white, in a cartoonish style."},
      ]

    },
    "generationConfig": {
      "responseModalities": ["TEXT", "IMAGE"],
      "imageConfig": {
        "aspectRatio": "16:9",
      },
    },
    "safetySettings": {
      "method": "PROBABILITY",
      "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
      "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
  }' 2>/dev/null >response.json
```

**Note:** Gemini 2.5 Flash Image supports the following aspect
ratios: `1:1`, `3:2`, `2:3`,
`3:4`, `4:3`, `4:5`, `5:4`,
`9:16`, `16:9`, and `21:9`.

Gemini will generate an image based on your description. This
process takes a few seconds, but can be comparatively slower depending on
capacity.

### Multi-turn image editing

Gemini 2.5 Flash Image and Gemini 3 Pro Image support
improved multi-turn editing, letting you respond to the model with changes after
receiving an edited image response. This lets you continue to make edits to the
image conversationally.

Note that it's recommended to limit the entire request file size to 50MB maximum.

To test out multi-turn image editing, try the following notebooks:

- [Gemini 3 Pro Image Generation in Vertex AI](https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/getting-started/intro_gemini_3_image_gen.ipynb),
- [Gemini 2.5 Flash Image Generation in Vertex AI](https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/getting-started/intro_gemini_2_5_image_gen.ipynb)

For code samples related to multi-turn image creation and editing using
Gemini 3 Pro Image, see
[Example of multi-turn image editing using thought signatures](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/thought-signatures#multi-turn-image-editing).

## Responsible AI

To ensure a safe and responsible experience, Vertex AI's image generation capabilities are equipped with a multi-layered safety approach. This is designed to prevent the creation of inappropriate content, including sexually explicit, dangerous, violent, hateful, or toxic material.

All users must adhere to the Generative AI Prohibited Use Policy. This policy strictly forbids the generation of content that:

- Relates to child sexual abuse or exploitation.
- Facilitates violent extremism or terrorism.
- Facilitates non-consensual intimate imagery.
  Facilitates self-harm.
- Is sexually explicit.
- Constitutes hate speech.
- Promotes harassment or bullying.

When provided with an unsafe prompt, the model might refuse to generate an image, or the prompt or generated response might be blocked by our safety filters.

- Model refusal: If a prompt is potentially unsafe, the model might refuse to process the request. If this happens, the model usually gives a text response saying it can't generate unsafe images. The `FinishReason` will be `STOP`.
- Safety filter blocking:  
  - If the prompt is identified as potentially harmful by a safety filter, the API returns `BlockedReason` in `PromptFeedback`.
  - If the response is identified as potentially harmful by a safety filter, the API response will include a `FinishReason` of `IMAGE_SAFETY`, `IMAGE_PROHIBITED_CONTENT`, or similar.

### Safety filter code categories

Depending on the safety filters you configure, your output may contain a safety
reason code similar to the following:

```scdoc
    {
      "raiFilteredReason": "ERROR_MESSAGE. Support codes: 56562880"
    }
```

The code listed corresponds to a specific harmful category. These code to
category mappings are as follows:

| Error code | Safety category | Description | Content filtered: prompt input or image output |
| --- | --- | --- | --- |
| 58061214 17301594 | Child | Detects child content where it isn't allowed due to the API request settings or allowlisting. | input (prompt): 58061214 output (image): 17301594 |
| 29310472 15236754 | Celebrity | Detects a photorealistic representation of a celebrity in the request. | input (prompt): 29310472 output (image): 15236754 |
| 62263041 | Dangerous content | Detects content that's potentially dangerous in nature. | input (prompt) |
| 57734940 22137204 | Hate | Detects hate-related topics or content. | input (prompt): 57734940 output (image): 22137204 |
| 74803281 29578790 42876398 | Other | Detects other miscellaneous safety issues with the request. | input (prompt): 42876398 output (image): 29578790, 74803281 |
| 39322892 | People/Face | Detects a person or face when it isn't allowed due to the request safety settings. | output (image) |
| 92201652 | Personal information | Detects Personally Identifiable Information (PII) in the text, such as the mentioning a credit card number, home addresses, or other such information. | input (prompt) |
| 89371032 49114662 72817394 | Prohibited content | Detects the request of prohibited content in the request. | input (prompt): 89371032 output (image): 49114662, 72817394 |
| 90789179 63429089 43188360 | Sexual | Detects content that's sexual in nature. | input (prompt): 90789179 output (image): 63429089, 43188360 |
| 78610348 | Toxic | Detects toxic topics or content in the text. | input (prompt) |
| 61493863 56562880 | Violence | Detects violence-related content from the image or text. | input (prompt): 61493863 output (image): 56562880 |
| 32635315 | Vulgar | Detects vulgar topics or content from the text. | input (prompt) |
| 64151117 | Celebrity or child | Detects photorealistic respresentation of a celebrity or of a child that violates Google's safety policies. | input (prompt) output (image) |
