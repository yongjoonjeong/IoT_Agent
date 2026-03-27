import os
import re
import json
from ollama import AsyncClient

# 샌드박스 경로 설정
SANDBOX_DIR = "@coder_sandbox"
if not os.path.exists(SANDBOX_DIR):
    os.makedirs(SANDBOX_DIR)

class AICoder:
    def __init__(self, model="qwen2.5-coder:3b"):
        self.model = model
        self.client = AsyncClient()

    async def generate_code(self, prompt):
        """사용자의 요청을 바탕으로 파이썬 코드를 생성하고 파일로 저장함"""
        
        system_instructions = (
            "당신은 파이썬 전문 개발자입니다. 사용자의 요청에 맞는 파이썬 코드를 작성하세요.\n"
            "반드시 다음 형식을 지키세요:\n"
            "1. 설명 없이 오직 코드만 작성할 것.\n"
            "2. 파일명은 코드의 목적에 맞게 'snake_case.py' 형식으로 추천할 것.\n"
            "3. 응답은 반드시 아래 JSON 형식으로만 대답할 것:\n"
            "{\"filename\": \"suggested_name.py\", \"code\": \"python_code_here\"}"
        )

        try:
            response = await self.client.chat(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': system_instructions},
                    {'role': 'user', 'content': prompt}
                ]
            )
            
            content = response['message']['content'].strip()
            # JSON만 추출 (가끔 LLM이 설명 문구를 붙일 때를 대비)
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            
            if json_match:
                data = json.loads(json_match.group(0))
                filename = data.get("filename", "generated_code.py")
                code = data.get("code", "")
                
                # 샌드박스에 저장
                save_path = os.path.join(SANDBOX_DIR, filename)
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(code)
                
                return True, filename, code
            else:
                return False, "JSON 형식을 파싱할 수 없습니다.", content

        except Exception as e:
            return False, str(e), None

    def list_sandbox_files(self):
        """샌드박스 내의 파일 목록 반환"""
        return os.listdir(SANDBOX_DIR)