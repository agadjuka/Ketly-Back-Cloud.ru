"""
Скрипт для просмотра состояния графа из PostgreSQL checkpointer
"""
import os
import sys
import json
import asyncio
from dotenv import load_dotenv

# Настройка event loop policy для Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()


async def get_state(thread_id: str):
    """Получает состояние графа для указанного thread_id"""
    import psycopg
    
    # Получаем строку подключения
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        host = os.getenv("PG_HOST", "localhost")
        port = os.getenv("PG_PORT", "5432")
        database = os.getenv("PG_DB", "ai_db")
        user = os.getenv("PG_USER", "postgres")
        password = os.getenv("PG_PASSWORD", "")
        database_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
    
    print(f"🔍 Подключение к PostgreSQL...")
    print(f"📌 Thread ID: {thread_id}\n")
    
    async with await psycopg.AsyncConnection.connect(database_url, autocommit=True) as conn:
        async with conn.cursor() as cur:
            # Получаем последний checkpoint для thread_id
            await cur.execute("""
                SELECT 
                    thread_id,
                    checkpoint_ns,
                    checkpoint_id,
                    parent_checkpoint_id,
                    type,
                    checkpoint
                FROM checkpoints 
                WHERE thread_id = %s 
                ORDER BY checkpoint_id DESC 
                LIMIT 1
            """, (thread_id,))
            
            row = await cur.fetchone()
            
            if not row:
                print(f"❌ Состояние для thread_id={thread_id} не найдено в базе данных")
                print(f"\n💡 Возможно, этот пользователь еще не взаимодействовал с ботом")
                return
            
            thread_id_db, checkpoint_ns, checkpoint_id, parent_checkpoint_id, type_field, checkpoint_data = row
            
            print("=" * 80)
            print("📊 МЕТАДАННЫЕ CHECKPOINT")
            print("=" * 80)
            print(f"Thread ID: {thread_id_db}")
            print(f"Checkpoint Namespace: {checkpoint_ns}")
            print(f"Checkpoint ID: {checkpoint_id}")
            print(f"Parent Checkpoint ID: {parent_checkpoint_id}")
            print(f"Type: {type_field}")
            
            # Декодируем checkpoint data
            if isinstance(checkpoint_data, bytes):
                # Данные в бинарном формате, декодируем
                import pickle
                try:
                    state = pickle.loads(checkpoint_data)
                except:
                    print(f"\n❌ Не удалось декодировать checkpoint_data")
                    return
            elif isinstance(checkpoint_data, dict):
                state = checkpoint_data
            else:
                print(f"\n❌ Неизвестный формат checkpoint_data: {type(checkpoint_data)}")
                return
            
            print("\n" + "=" * 80)
            print("📋 СОСТОЯНИЕ ГРАФА (ConversationState)")
            print("=" * 80)
            
            # Извлекаем channel_values (это и есть наше состояние)
            if 'channel_values' in state:
                channel_values = state['channel_values']
                
                # Основные поля
                print(f"\n🔹 ОСНОВНЫЕ ПОЛЯ:")
                print(f"  chat_id: {channel_values.get('chat_id', 'не задан')}")
                print(f"  stage: {channel_values.get('stage', 'не задан')}")
                print(f"  agent_name: {channel_values.get('agent_name', 'не задан')}")
                print(f"  answer: {channel_values.get('answer', 'не задан')[:100]}...")
                
                # Messages
                messages = channel_values.get('messages', [])
                print(f"\n💬 ИСТОРИЯ СООБЩЕНИЙ: {len(messages)} сообщений")
                if messages:
                    print("  Последние 5 сообщений:")
                    for i, msg in enumerate(messages[-5:], 1):
                        msg_type = type(msg).__name__ if hasattr(msg, '__class__') else 'dict'
                        content = ""
                        if hasattr(msg, 'content'):
                            content = str(msg.content)[:80]
                        elif isinstance(msg, dict):
                            content = str(msg.get('content', ''))[:80]
                        print(f"    {i}. [{msg_type}] {content}...")
                
                # Demo config
                demo_config = channel_values.get('demo_config')
                print(f"\n🎭 DEMO CONFIG:")
                if demo_config:
                    print(f"  ✅ Конфигурация присутствует!")
                    print(f"  Ниша: {demo_config.get('niche', 'не указана')}")
                    print(f"  Компания: {demo_config.get('company_name', 'не указана')}")
                    print(f"  Persona instruction (первые 200 символов):")
                    print(f"    {demo_config.get('persona_instruction', 'не указана')[:200]}...")
                    print(f"  Welcome message:")
                    print(f"    {demo_config.get('welcome_message', 'не указано')}")
                else:
                    print(f"  ❌ Конфигурация отсутствует")
                
                # Extracted info
                extracted_info = channel_values.get('extracted_info')
                print(f"\n📦 EXTRACTED INFO:")
                if extracted_info:
                    print(f"  {json.dumps(extracted_info, ensure_ascii=False, indent=2)}")
                else:
                    print(f"  Отсутствует")
                
                # Used tools
                used_tools = channel_values.get('used_tools', [])
                print(f"\n🔧 ИСПОЛЬЗОВАННЫЕ ИНСТРУМЕНТЫ: {used_tools}")
                
                # Manager alert
                manager_alert = channel_values.get('manager_alert')
                if manager_alert:
                    print(f"\n⚠️ ALERT ДЛЯ МЕНЕДЖЕРА:")
                    print(f"  {manager_alert}")
                
            else:
                print(f"\n❌ channel_values не найден в состоянии")
                print(f"\nДоступные ключи в состоянии: {list(state.keys())}")
            
            print("\n" + "=" * 80)
            print("📄 ПОЛНОЕ СОСТОЯНИЕ (JSON)")
            print("=" * 80)
            
            # Пытаемся сериализовать в JSON для полного просмотра
            try:
                # Преобразуем объекты в dict для JSON сериализации
                state_for_json = {}
                if 'channel_values' in state:
                    cv = state['channel_values']
                    state_for_json = {
                        'chat_id': cv.get('chat_id'),
                        'stage': cv.get('stage'),
                        'agent_name': cv.get('agent_name'),
                        'demo_config': cv.get('demo_config'),
                        'extracted_info': cv.get('extracted_info'),
                        'used_tools': cv.get('used_tools'),
                        'message_count': len(cv.get('messages', [])),
                        'answer_length': len(str(cv.get('answer', ''))) if cv.get('answer') else 0,
                    }
                
                print(json.dumps(state_for_json, ensure_ascii=False, indent=2))
            except Exception as e:
                print(f"⚠️ Не удалось сериализовать состояние в JSON: {e}")
            
            print("\n" + "=" * 80)


async def main():
    """Главная функция"""
    print("🔍 DEBUG STATE VIEWER")
    print("=" * 80)
    
    # Получаем thread_id из аргументов командной строки
    if len(sys.argv) > 1:
        thread_id = sys.argv[1]
    else:
        # Запрашиваем у пользователя
        thread_id = input("Введите Thread ID (chat_id пользователя): ").strip()
    
    if not thread_id:
        print("❌ Thread ID не указан!")
        return
    
    await get_state(thread_id)
    
    print("\n✅ Готово!")


if __name__ == "__main__":
    asyncio.run(main())

