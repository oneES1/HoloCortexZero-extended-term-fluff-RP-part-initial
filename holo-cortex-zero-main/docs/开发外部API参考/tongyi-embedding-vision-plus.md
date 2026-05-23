多模态独立向量化功能需要通过 DashScope SDK 或 API 来调用，不支持OpenAI兼容接口调用或在控制台直接使用。可为文本、图片、视频等不同模态的内容分别生成独立的向量，适用于需要单独处理每种内容类型的场景。

最多 8 张且单张大小不超过3 MB

中文与英文
JPG, PNG, BMP (支持URL或Base64)



import dashscope
import json
import os
from http import HTTPStatus

# 输入可以是视频
# video = "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250107/lbcemt/new+video.mp4"
# input = [{'video': video}]
# 或图片
image = "https://dashscope.oss-cn-beijing.aliyuncs.com/images/256_1.png"
input = [{'image': image}]
resp = dashscope.MultiModalEmbedding.call(
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="<API_KEY>",
    api_key=os.getenv('DASHSCOPE_API_KEY'),
    model="tongyi-embedding-vision-plus",
    input=input
)

print(json.dumps(resp.output, indent=4))