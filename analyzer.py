import json
import os
from datetime import datetime
import ollama

# Карта сопоставления ID сотрудников и их реальных имен (Дополни по мере необходимости)
USERS_MAP = {
    "278": "Артур Силиверстов",
    "567": "Екатерина Кособокова",
    "584": "Юрий Литвин", 
    "322": "Роман Шишков",
    "1": "Администратор"
}

# Карта сопоставления ID рабочих групп/проектов (Дополни по мере необходимости)
GROUPS_MAP = {
    "27": "Биобанк (Оборудование)",
    "42": "МедТех (Стартап)"
}

def load_advanced_context(file_path="tasks.json"):
    """Считывание, обогащение имен и расчет сквозной статистики бэклога"""
    if not os.path.exists(file_path):
        print(f"❌ Ошибка: Файл {file_path} не найден!")
        return None, None
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        tasks = data.get("result", data)
        if not isinstance(tasks, list):
            tasks = tasks.get("tasks", [tasks])
            
        # 1. РАСЧЕТ ДЕТЕРМИНИРОВАННОЙ СТАТИСТИКИ ПРОЕКТА (Без ИИ)
        total_tasks = len(tasks)
        no_deadline_count = 0
        tasks_by_user = {}
        tasks_by_project = {}
        
        context_lines = []
        for t in tasks:
            t_id = t.get("ID")
            title = t.get("TITLE")
            desc = t.get("DESCRIPTION", "Нет описания")
            
            # Обогащаем ID исполнителя реальным именем
            resp_id = str(t.get("RESPONSIBLE_ID"))
            user_name = USERS_MAP.get(resp_id, f"Сотрудник ID {resp_id}")
            
            # Обогащаем ID группы понятным названием стартапа
            group_id = str(t.get("GROUP_ID"))
            project_name = GROUPS_MAP.get(group_id, f"Проект ID {group_id}")
            
            # Обработка дедлайнов
            deadline_raw = t.get("DEADLINE")
            if deadline_raw:
                try:
                    # Приводим ISO-дату Битрикса к красивому русскому формату
                    dt = datetime.fromisoformat(deadline_raw.replace("Z", "+00:00"))
                    deadline = dt.strftime("%d.%m.%Y %H:%M")
                except:
                    deadline = deadline_raw
            else:
                deadline = "НЕ УСТАНОВЛЕН"
                no_deadline_count += 1
                
            # Собираем метрики для статистики
            tasks_by_user[user_name] = tasks_by_user.get(user_name, 0) + 1
            tasks_by_project[project_name] = tasks_by_project.get(project_name, 0) + 1
            
            # Формируем расширенную карточку для контекста LLM
            context_lines.append(
                f"Задача №: {t_id}\n"
                f"Название: {title}\n"
                f"Описание: {desc}\n"
                f"Проект: {project_name}\n"
                f"Ответственный исполнитель: {user_name}\n"
                f"Дедлайн (Срок сдачи): {deadline}\n"
                f"Теги: {t.get('TAGS', 'Нет тегов')}\n"
                f"----------------------------------------"
            )
            
        # Формируем блок жесткой математической сводки для ИИ
        stats_summary = (
            f"ОБЩАЯ СТАТИСТИКА БЭКЛОГА НА СЕГОДНЯ:\n"
            f"Всего активных задач в работе: {total_tasks}\n"
            f"Задач без указания дедлайна (в зоне риска): {no_deadline_count}\n"
            f"Распределение задач по сотрудникам: {json.dumps(tasks_by_user, ensure_ascii=False)}\n"
            f"Распределение задач по проектам/стартапам: {json.dumps(tasks_by_project, ensure_ascii=False)}\n"
        )
        
        return stats_summary, "\n".join(context_lines)
    except Exception as e:
        print(f"❌ Ошибка обработки данных: {str(e)}")
        return None, None

def main():
    print("⏳ Загрузка расширенного бэклога задач Битрикс24 в оперативную память ИИ...")
    stats, context = load_advanced_context()
    if not context:
        return

    # Обновленный системный промпт: ИИ теперь видит картину целиком и знает имена сотрудников
    system_prompt = (
        "Ты — аналитический ИИ-координатор кросс-функциональной платформы Open Claw. "
        "В нашей системе нет деления на Руководителей и Подчиненных — все участники имеют равный доступ к бэклогу. "
        "Тебе предоставлена точная сухая статистика и полный список активных задач из Bitrix24 On-Premise.\n\n"
        "Твоя задача — формировать сквозную аналитику по движению проектов, собирать статистику "
        "как по конкретным сотрудникам (например, Роман, Юрий), так и по направлениям (Биобанк, МедТех).\n"
        "Выявляй просрочки, подсвечивай задачи без дедлайнов и группируй информацию по первому требованию. "
        "Отвечай коротко, профессионально, на понятном русском языке.\n\n"
        f"{stats}\n\n"
        f"ПОДРОБНЫЙ РЕЕСТР КАРТОЧЕК ЗАДАЧ:\n\n{context}"
    )

    print("✔ Сквозной ИИ-анализатор бэклога успешно запущен!")
    print("🤖 Задавай вопросы по задачам проекта (для выхода введи 'выход'):\n")

    while True:
        user_query = input("Юрий 👤 > ")
        if user_query.lower() in ["exit", "выход", "quit"]:
            print("🤖 До связи, Юрий!")
            break
            
        if not user_query.strip():
            continue

        print("🤖 ИИ вычисляет метрики...")
        try:
            response = ollama.chat(
                model="llama3",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query}
                ]
            )
            print(f"\nАссистент 🤖 > {response['message']['content']}\n")
        except Exception as e:
            print(f"❌ Ошибка ИИ-генерации: {str(e)}\n")

if __name__ == "__main__":
    main()

