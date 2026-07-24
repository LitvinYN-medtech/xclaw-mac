import json
import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import ollama

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("X-Claw-Local-AI")

app = FastAPI(title="X-Claw AI Brain (Mac Mini)", version="2.0.0")

TASKS_FILE = "tasks.json"

# Контракт данных между VPS-шлюзом и Mac Mini
class IncomingQuery(BaseModel):
    query: str = Field(..., description="Текст вопроса сотрудника")
    user_id: int = Field(..., description="Динамический ID сотрудника из Битрикс24")

def filter_tasks_by_user(b24_user_id: int) -> str:
    """Динамическая фильтрация бэклога: ИИ получит только задачи этого конкретного пользователя"""
    if not os.path.exists(TASKS_FILE):
        return "В базе данных системы Битрикс24 пока нет активных задач."
        
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        tasks = data.get("result", data)
        if not isinstance(tasks, list):
            tasks = tasks.get("tasks", [tasks])
            
        user_tasks = []
        for t in tasks:
            # Сверяем ID ответственного из Битрикса с ID того, кто написал боту
            if str(t.get("RESPONSIBLE_ID")) == str(b24_user_id):
                user_tasks.append(
                    f"ID задачи: {t.get('ID')} | "
                    f"Название: {t.get('TITLE')} | "
                    f"Описание: {t.get('DESCRIPTION', 'Нет описания')} | "
                    f"Дедлайн: {t.get('DEADLINE', 'Не установлен')} | "
                    f"Теги: {t.get('TAGS', 'Нет')}"
                )
                
        if not user_tasks:
            return f"За пользователем с ID {b24_user_id} сейчас не закреплено активных задач в бэклоге."
            
        return "\n----------------------------------------\n".join(user_tasks)
    except Exception as e:
        logger.error(f"Ошибка при чтении или парсинге файла задач: {str(e)}")
        return "Ошибка обработки базы знаний."

@app.post("/api/analyze")
async def analyze_user_backlog(data: IncomingQuery):
    try:
        logger.info(f"Получен запрос от шлюза VPS для пользователя Б24 ID: {data.user_id}")
        
        # 1. ДИНАМИЧЕСКИЙ ФИЛЬТР: Вырезаем задачи ТОЛЬКО для автора запроса
        personal_context = filter_tasks_by_user(data.user_id)
        
        # 2. ФОРМИРОВАНИЕ СИСТЕМНОГО ПРОМПТА БЕЗ ЖЕСТКИХ ИМЕН И РОЛЕЙ
        system_prompt = (
            "Ты — аналитический ИИ-помощник платформы Open Claw, интегрированный в мессенджер Битрикс24.\n"
            "Перед тобой список активных задач, которые закреплены в таск-трекере за сотрудником, "
            "который в данный момент вызвал тебя. Отвечай на его вопрос строго на основе этих данных.\n"
            "ПРАВИЛО: Формулируйте ответы четко, профессионально, на русском языке. Не выдумывай факты, "
            "которых нет в предоставленном контексте.\n\n"
            f"СПИСОК ЛИЧНЫХ ЗАДАЧ СОТРУДНИКА:\n{personal_context}"
        )
        
        # 3. ЗАПРОС К ЛОКАЛЬНОЙ OLLAMA (Llama 3)
        response = ollama.chat(
            model="llama3",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": data.query}
            ]
        )
        
        return {"response": response['message']['content']}
        
    except Exception as e:
        logger.error(f"Критическая ошибка ИИ-модуля: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Запускаем локальный ИИ-сервер на Mac Mini
    uvicorn.run(app, host="0.0.0.0", port=8000)

