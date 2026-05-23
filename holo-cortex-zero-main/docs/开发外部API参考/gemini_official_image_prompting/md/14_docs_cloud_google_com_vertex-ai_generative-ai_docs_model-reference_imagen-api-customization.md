# Customize images

> Source: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/imagen-api-customization
> Downloaded: 2026-02-05

The Imagen API lets you create high quality images in seconds,
using text prompts and reference images to guide subject or style generation.

[View Imagen for Editing and Customization model card](https://console.cloud.google.com/vertex-ai/publishers/google/model-garden/imagen-3.0-capability-001)

#### Supported Models

| Model | Code |
| --- | --- |
| Customization using reference images (few-shot) | imagen-3.0-capability-001 |

For more information about the features that each model supports, see
[Imagen
models](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models#imagen-models).

## HTTP method and URL

```bash
POST https://${LOCATION}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${LOCATION}/publishers/google/models/imagen-3.0-capability-001:predict
```

## Example syntax

Syntax to customize an image from a text prompt and reference images.

### Syntax

Syntax to customize an image.

### REST

```bash
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
https://${LOCATION}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${LOCATION}/publishers/google/models/imagen-3.0-capability-001:predict \
-d '{
    "instances": [
      {
        // Use [1] to refer to the reference images with referenceId=1
        // [2] to refer to the reference images with referenceId=2,
        // following the same format for all reference IDs that you provide.
        "prompt": "${TEXT_PROMPT}",
        "referenceImages": [
          // A list of at most 4 reference image objects.
          [...]
        ]
      }
    ],
    "parameters": {
        [...]
    }
}'
```

**Sample request body**:

This request is for person customization with a face mesh control image and
three reference images.

```
{
  "instances": [
    {
      "prompt": "Create an image about a man with short hair [1] in the pose of
       control image [2] to match the description: A pencil style sketch of a
       full-body portrait of a man with short hair [1] with hatch-cross drawing,
       hatch drawing of portrait with 6B and graphite pencils, white background,
       pencil drawing, high quality, pencil stroke, looking at camera, natural
       human eyes",
      "referenceImages": [
        {
          "referenceType": "REFERENCE_TYPE_CONTROL",
          "referenceId": 2,
          "referenceImage": {
            "bytesBase64Encoded": "${IMAGE_BYTES_1}"
          },
          "controlImageConfig": {
            "controlType": "CONTROL_TYPE_FACE_MESH",
            "enableControlImageComputation": true
          }
        },
        {
          "referenceType": "REFERENCE_TYPE_SUBJECT",
          "referenceId": 1,
          "referenceImage": {
            "bytesBase64Encoded": "${IMAGE_BYTES_2}"
          },
          "subjectImageConfig": {
            "subjectDescription": "a man with short hair",
            "subjectType": "SUBJECT_TYPE_PERSON"
          }
        },
        {
          "referenceType": "REFERENCE_TYPE_SUBJECT",
          "referenceId": 1,
          "referenceImage": {
            "bytesBase64Encoded": "${IMAGE_BYTES_3}"
          },
          "subjectImageConfig": {
            "subjectDescription": "a man with short hair",
            "subjectType": "SUBJECT_TYPE_PERSON"
          }
        },
        {
          "referenceType": "REFERENCE_TYPE_SUBJECT",
          "referenceId": 1,
          "referenceImage": {
            "bytesBase64Encoded": "${IMAGE_BYTES_4}"
          },
          "subjectImageConfig": {
            "subjectDescription": "a man with short hair",
            "subjectType": "SUBJECT_TYPE_PERSON"
          }
        }
      ]
    }
  ],
  "parameters": {
    "negativePrompt": "wrinkles, noise, Low quality, dirty, low res, multi face,
      rough texture, messy, messy background, color background, photo realistic,
      photo, super realistic, signature, autograph, sign, text, characters,
      alphabet, letter",
    "seed": 1,
    "language": "en",
    "sampleCount": 4
  }
}
```

## Parameter list

See [examples](#examples) for implementation details.

#### Customize images

### REST

| Parameters |  |
| --- | --- |
| referenceType | Required enumeration: REFERENCE_TYPE_RAW A raw reference image is required for editing use cases. A raw reference image isn't needed for other use cases. At most one raw reference image exists in one request. The output image has the same size as the raw reference input image. REFERENCE_TYPE_MASK A mask reference image is required for masked editing use cases. A mask reference image isn't required for other use cases. If a raw reference image is present, the mask image has to be in the same size as the raw reference image. The user can either provide their own mask, or let Imagen compute the mask for them from the provided reference image. If mask reference image is empty and maskMode is not set to MASK_MODE_USER_PROVIDED , the mask is computed based on the raw reference image. REFERENCE_TYPE_CONTROL If a raw reference image is provided, then the control image's size must have the same dimensions as the raw reference image. If you don't provide an image with type `REFERENCE_TYPE_CONTROL` in `bytesBase64Encoded` format, then the model computes the control image from the image provided as `REFERENCE_TYPE_RAW`. REFERENCE_TYPE_SUBJECT The user can provide multiple reference images with the same reference ID. For example, multiple images for the same subject can have the same reference ID. This could potentially improve the output quality. REFERENCE_TYPE_STYLE A style reference image that the model uses to guide the style of the generated image. |
| referenceId | Required integer The reference ID. Use this reference ID in the prompt. For example, use [1] to refer to the reference images with referenceId=1, [2] to refer to the reference images with referenceId=2. |
| referenceImage.bytesBase64Encoded | Required string A Base64 string for the encoded reference image. |
| maskImageConfig.maskMode | Optional enumeration: MASK_MODE_USER_PROVIDED , if the reference image is a mask image. MASK_MODE_BACKGROUND , to automatically generate a mask using background segmentation. MASK_MODE_FOREGROUND , to automatically generate a mask using foreground segmentation. MASK_MODE_SEMANTIC , to automatically generate a mask using semantic segmentation, and the given mask class . Specified when referenceType is set as REFERENCE_TYPE_MASK . |
| maskImageConfig.dilation | Optional float . Range: [0, 1] The percentage of image width to dilate this mask by. Specified when referenceType is set as REFERENCE_TYPE_MASK . |
| maskImageConfig.maskClasses | Optional list[Integer] . Mask classes for MASK_MODE_SEMANTIC mode. Specified when referenceType is set as REFERENCE_TYPE_MASK . |
| controlImageConfig.controlType | Required enumeration: CONTROL_TYPE_FACE_MESH for face mesh (person customization). CONTROL_TYPE_CANNY for canny edge . CONTROL_TYPE_SCRIBBLE for scribble. Specified when referenceType is set as REFERENCE_TYPE_CONTROL . |
| controlImageConfig.enableControlImageComputation | Optional bool . Default: false . Set to false if you provide your own control image. Set to true if you want to let Imagen compute the control image from the reference image. Specified when referenceType is set as REFERENCE_TYPE_CONTROL . |
| language | Optional: string ( imagen-3.0-capability-001 , imagen-3.0.generate-001 , and imagegeneration@006 only) The language code that corresponds to your text prompt language. The following values are supported: auto : Automatic detection. If Imagen detects a supported language, the prompt and an optional negative prompt are translated to English. If the language detected isn't supported, Imagen uses the input text verbatim, which might result in an unexpected output. No error code is returned. en : English (if omitted, the default value) es : Spanish hi : Hindi ja : Japanese ko : Korean pt : Portuguese zh-TW : Chinese (traditional) zh or zh-CN : Chinese (simplified) |
| subjectImageConfig.subjectDescription | Required string . A short description of the subject in the image. For example, a woman with short brown hair . Specified when referenceType is set as REFERENCE_TYPE_SUBJECT . |
| subjectImageConfig.subjectType | Required enumeration: SUBJECT_TYPE_PERSON : Person subject type. SUBJECT_TYPE_ANIMAL : Animal subject type. SUBJECT_TYPE_PRODUCT : Product subject type. SUBJECT_TYPE_DEFAULT : Default subject type. Specified when referenceType is set as REFERENCE_TYPE_SUBJECT . |
| styleImageConfig.styleDescription | Optional string . A short description for the style. Specified when referenceType is set as REFERENCE_TYPE_STYLE . |

#### Response

The response body from the REST request.

| Parameter |  |
| --- | --- |
| predictions | An array of VisionGenerativeModelResult objects , one for each requested sampleCount . If any images are filtered by responsible AI, they are not included. |

### Vision generative model result object

Information about the model result.

| Parameter |  |
| --- | --- |
| bytesBase64Encoded | The base64 encoded generated image. Not present if the output image did not pass responsible AI filters. |
| mimeType | The type of the generated image. Not present if the output image did not pass responsible AI filters. |

## Examples

The following examples show how to use the Imagen model
to customize images.

### Customize images

### REST

Before using any of the request data,
make the following replacements:

- PROJECT\_ID: Your Google Cloud [project ID](https://docs.cloud.google.com/resource-manager/docs/creating-managing-projects#identifiers).
- LOCATION: Your project's region. For example,
  `us-central1`, `europe-west2`, or `asia-northeast3`. For a list
  of available regions, see
  [Generative AI on Vertex AI locations](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/locations-genai).
- TEXT\_PROMPT: The text prompt guides what images the model
  generates. To use Imagen 3 Customization, include the `referenceId` of
  the reference image or images
  you provide in the format [$referenceId]. For example:
  - The following text prompt is for a request that has two reference images with
    `"referenceId": 1`. Both images have an optional
    description of `"subjectDescription": "man with short hair"`:
    *Create an image about a man with short hair to match the description: A
    pencil style sketch of a full-body portrait of a man with short hair [1] with
    hatch-cross
    drawing, hatch drawing of portrait with 6B and graphite pencils, white background, pencil
    drawing, high quality, pencil stroke, looking at camera, natural human eyes*
- `"referenceId"`: The ID of the reference image, or the ID for a series of reference
  images that correspond to the same subject or style. In this example the two reference images
  are of the same person, so they share the same `referenceId` (`1`).
- BASE64\_REFERENCE\_IMAGE: A reference image to guide image generation. The
  image must be specified as a [base64-encoded](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/image/base64-encode) byte
  string.
- SUBJECT\_DESCRIPTION: Optional. A text description of the reference image you can
  then use in the `prompt` field. For example:

```
      "prompt": "a full-body portrait of a man with short hair [1] with hatch-cross
      drawing",
      [...],
      "subjectDescription": "man with short hair"
```

- IMAGE\_COUNT: The number of generated images.
  Accepted integer values: 1-4. Default value: 4.

HTTP method and URL:

```
POST https://LOCATION-aiplatform.googleapis.com/v1/projects/PROJECT_ID/locations/LOCATION/publishers/google/models/imagen-3.0-capability-001:predict
```

Request JSON body:

```
{
  "instances": [
    {
      "prompt": "TEXT_PROMPT",
      "referenceImages": [
        {
          "referenceType": "REFERENCE_TYPE_SUBJECT",
          "referenceId": 1,
          "referenceImage": {
            "bytesBase64Encoded": "BASE64_REFERENCE_IMAGE"
          },
          "subjectImageConfig": {
            "subjectDescription": "SUBJECT_DESCRIPTION",
            "subjectType": "SUBJECT_TYPE_PERSON"
          }
        },
        {
          "referenceType": "REFERENCE_TYPE_SUBJECT",
          "referenceId": 1,
          "referenceImage": {
            "bytesBase64Encoded": "BASE64_REFERENCE_IMAGE"
          },
          "subjectImageConfig": {
            "subjectDescription": "SUBJECT_DESCRIPTION",
            "subjectType": "SUBJECT_TYPE_PERSON"
          }
        }
      ]
    }
  ],
  "parameters": {
    "sampleCount": IMAGE_COUNT
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
curl -X POST \     -H "Authorization: Bearer $(gcloud auth print-access-token)" \     -H "Content-Type: application/json; charset=utf-8" \     -d @request.json \     "https://LOCATION-aiplatform.googleapis.com/v1/projects/PROJECT_ID/locations/LOCATION/publishers/google/models/imagen-3.0-capability-001:predict"
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
$cred = gcloud auth print-access-token$headers = @{ "Authorization" = "Bearer $cred" }Invoke-WebRequest `    -Method POST `    -Headers $headers `    -ContentType: "application/json; charset=utf-8" `    -InFile request.json `    -Uri "https://LOCATION-aiplatform.googleapis.com/v1/projects/PROJECT_ID/locations/LOCATION/publishers/google/models/imagen-3.0-capability-001:predict" | Select-Object -Expand Content
```

The following sample response is for a request with
`"sampleCount": 2`. The response returns two prediction objects, with
the generated image bytes base64-encoded.

```
{
  "predictions": [
    {
      "bytesBase64Encoded": "BASE64_IMG_BYTES",
      "mimeType": "image/png"
    },
    {
      "mimeType": "image/png",
      "bytesBase64Encoded": "BASE64_IMG_BYTES"
    }
  ]
}
```

## Class IDs

Use the following object class IDs to
automatically create an image mask based on specific objects.

| Class ID ( class_ id ) | Object |
| --- | --- |
| 0 | backpack |
| 1 | umbrella |
| 2 | bag |
| 3 | tie |
| 4 | suitcase |
| 5 | case |
| 6 | bird |
| 7 | cat |
| 8 | dog |
| 9 | horse |
| 10 | sheep |
| 11 | cow |
| 12 | elephant |
| 13 | bear |
| 14 | zebra |
| 15 | giraffe |
| 16 | animal (other) |
| 17 | microwave |
| 18 | radiator |
| 19 | oven |
| 20 | toaster |
| 21 | storage tank |
| 22 | conveyor belt |
| 23 | sink |
| 24 | refrigerator |
| 25 | washer dryer |
| 26 | fan |
| 27 | dishwasher |
| 28 | toilet |
| 29 | bathtub |
| 30 | shower |
| 31 | tunnel |
| 32 | bridge |
| 33 | pier wharf |
| 34 | tent |
| 35 | building |
| 36 | ceiling |
| 37 | laptop |
| 38 | keyboard |
| 39 | mouse |
| 40 | remote |
| 41 | cell phone |
| 42 | television |
| 43 | floor |
| 44 | stage |
| 45 | banana |
| 46 | apple |
| 47 | sandwich |
| 48 | orange |
| 49 | broccoli |
| 50 | carrot |
| 51 | hot dog |
| 52 | pizza |
| 53 | donut |
| 54 | cake |
| 55 | fruit (other) |
| 56 | food (other) |
| 57 | chair (other) |
| 58 | armchair |
| 59 | swivel chair |
| 60 | stool |
| 61 | seat |
| 62 | couch |
| 63 | trash can |
| 64 | potted plant |
| 65 | nightstand |
| 66 | bed |
| 67 | table |
| 68 | pool table |
| 69 | barrel |
| 70 | desk |
| 71 | ottoman |
| 72 | wardrobe |
| 73 | crib |
| 74 | basket |
| 75 | chest of drawers |
| 76 | bookshelf |
| 77 | counter (other) |
| 78 | bathroom counter |
| 79 | kitchen island |
| 80 | door |
| 81 | light (other) |
| 82 | lamp |
| 83 | sconce |
| 84 | chandelier |
| 85 | mirror |
| 86 | whiteboard |
| 87 | shelf |
| 88 | stairs |
| 89 | escalator |
| 90 | cabinet |
| 91 | fireplace |
| 92 | stove |
| 93 | arcade machine |
| 94 | gravel |
| 95 | platform |
| 96 | playingfield |
| 97 | railroad |
| 98 | road |
| 99 | snow |
| 100 | sidewalk pavement |
| 101 | runway |
| 102 | terrain |
| 103 | book |
| 104 | box |
| 105 | clock |
| 106 | vase |
| 107 | scissors |
| 108 | plaything (other) |
| 109 | teddy bear |
| 110 | hair dryer |
| 111 | toothbrush |
| 112 | painting |
| 113 | poster |
| 114 | bulletin board |
| 115 | bottle |
| 116 | cup |
| 117 | wine glass |
| 118 | knife |
| 119 | fork |
| 120 | spoon |
| 121 | bowl |
| 122 | tray |
| 123 | range hood |
| 124 | plate |
| 125 | person |
| 126 | rider (other) |
| 127 | bicyclist |
| 128 | motorcyclist |
| 129 | paper |
| 130 | streetlight |
| 131 | road barrier |
| 132 | mailbox |
| 133 | cctv camera |
| 134 | junction box |
| 135 | traffic sign |
| 136 | traffic light |
| 137 | fire hydrant |
| 138 | parking meter |
| 139 | bench |
| 140 | bike rack |
| 141 | billboard |
| 142 | sky |
| 143 | pole |
| 144 | fence |
| 145 | railing banister |
| 146 | guard rail |
| 147 | mountain hill |
| 148 | rock |
| 149 | frisbee |
| 150 | skis |
| 151 | snowboard |
| 152 | sports ball |
| 153 | kite |
| 154 | baseball bat |
| 155 | baseball glove |
| 156 | skateboard |
| 157 | surfboard |
| 158 | tennis racket |
| 159 | net |
| 160 | base |
| 161 | sculpture |
| 162 | column |
| 163 | fountain |
| 164 | awning |
| 165 | apparel |
| 166 | banner |
| 167 | flag |
| 168 | blanket |
| 169 | curtain (other) |
| 170 | shower curtain |
| 171 | pillow |
| 172 | towel |
| 173 | rug floormat |
| 174 | vegetation |
| 175 | bicycle |
| 176 | car |
| 177 | autorickshaw |
| 178 | motorcycle |
| 179 | airplane |
| 180 | bus |
| 181 | train |
| 182 | truck |
| 183 | trailer |
| 184 | boat ship |
| 185 | slow wheeled object |
| 186 | river lake |
| 187 | sea |
| 188 | water (other) |
| 189 | swimming pool |
| 190 | waterfall |
| 191 | wall |
| 192 | window |
| 193 | window blind |

## What's next

- For more information, see [Imagen on Vertex AI](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/image/overview).
