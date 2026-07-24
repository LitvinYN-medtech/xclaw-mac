import os
import json
import logging
import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("X-Claw-NotebookLM")

app = FastAPI(title="X-Claw AI Brain (Claude Sonnet)", version="3.0.0")

# Конфигурация инфраструктуры
ZARUBEZH_VPS_URL = "http://176.12.73" # Порт прокси Claude на зарубежной VPS
TASKS_FILE = "/Users/admin/xclaw_analyzer/tasks.json"

USERS_MAP = {
    "278": "Артур Силиверстов", "567": "Екатерина Кособокова",
    "584": "Юрий Литвин", "322": "Роман Шишков", "1": "Администратор"
}
GROUPS_MAP = {
    "27": "Биобанк (Оборудование)", "42": "МедТех (Стартап)"
}

class IncomingQuery(BaseModel):
    query: str = Field(..., description="Текст вопроса сотрудника")
    user_id: int = Field(..., description="ID сотрудника из Битрикс24")

def build_notebooklm_context() -> str:
    """Генерирует полную аналитическую базу знаний (NotebookLM) из бэклога"""
    if not os.path.exists(TASKS_FILE):
        return "Данные бэклога Bitrix24 временно недоступны."
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        tasks = data.get("result", data)
        if not isinstance(tasks, list):
            tasks = tasks.get("tasks", [tasks])

        total_tasks = len(tasks)
        no_deadline_count = 0
        tasks_by_user = {}
        context_lines = []

        for t in tasks:
            user_name = USERS_MAP.get(str(t.get("RESPONSIBLE_ID")), f"Сотрудник ID {t.get('RESPONSIBLE_ID')}")
            project_name = GROUPS_MAP.get(str(t.get("GROUP_ID")), f"Проект ID {t.get('GROUP_ID')}")
            
            deadline_raw = t.get("DEADLINE")
            if deadline_raw:
                try:
                    dt = datetime.fromisoformat(deadline_raw.replace("Z", "+00:00"))
                    deadline = dt.strftime("%d.%m.%Y %H:%M")
                except:
                    deadline = deadline_raw
            else:
                deadline = "НЕ УСТАНОВЛЕН"
                no_deadline_count += 1

            tasks_by_user[user_name] = tasks_by_user.get(user_name, 0) + 1
            context_lines.append(
                f"Задача №{t.get('ID')} | {t.get('TITLE')}\n"
                f"Проект: {project_name} | Исполнитель: {user_name} | Дедлайн: {deadline}\n"
                f"Описание: {t.get('DESCRIPTION', 'Нет')}\n"
                f"----------------------------------------"
            )

        stats = f"Всего задач: {total_tasks}, Без дедлайна: {no_deadline_count}. Распределение: {json.dumps(tasks_by_user, ensure_ascii=False)}"
        return f"СТАТИСТИКА:\n{stats}\n\nРЕЕСТР ЗАДАЧ:\n" + "\n".join(context_lines)
    except Exception as e:
        logger.error(f"Ошибка парсинга контекста: {e}")
        return "Ошибка сборки базы знаний."

@app.post("/api/analyze")
async def analyze_request(data: IncomingQuery):
    logger.info(f"🧠 Запрос к Claude Sonnet для пользователя ID: {data.user_id}")
    
    # Собираем актуальную сквозную память всех проектов (NotebookLM)
    full_knowledge_base = build_notebooklm_context()
    author_name = USERS_MAP.get(str(data.user_id), f"Сотрудник с ID {data.user_id}")

    system_prompt = (
        "Ты — Цифровой двойник и ИИ-координатор платформы Open Claw, интегрированный в Битрикс24.\n"
        "Перед тобой полная база знаний и бэклог всех активных проектов (NotebookLM).\n"
        f"Сейчас к тебе обращается сотрудник: {author_name}.\n"
        "Твоя задача — сопоставлять его вопросы со сквозной аналитикой, находить скрытые риски, "
        "просрочки и пересечения задач. Отвечай экспертно, лаконично, строго на русском языке. "
        "Не придумывай задачи, которых нет в реестре."
    )

    # Формируем payload для Claude 3.5 Sonnet
    claude_payload = {
        "model": "claude-3-5-sonnet",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"База знаний проектов:\n{full_knowledge_base}\n\nВопрос от {author_name}: {data.query}"}
        ],
        "temperature": 0.3
    }

    # Отправляем запрос на зарубежную VPS
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(ZARUBEZH_VPS_URL, json=claude_payload, timeout=30.0)
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail=f"Зарубежная VPS вернула ошибку: {response.text}")
            
            result = response.json()
            # Извлекаем ответ Claude (совместимо со стандартом OpenAI API)
            ai_text = result['choices'][0]['message']['content']
            return {"status": "success", "response": ai_text}
        except Exception as e:
            logger.error(f"Ошибка вызова Claude через VPS: {e}")
            raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

