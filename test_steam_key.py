"""
Быстрый тест Steam API ключа.
"""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()


async def test_steam_key():
    """Тестирует Steam API ключ."""
    from src.services.opendota_service import OpenDotaService
    
    steam_key = os.getenv("STEAM_API_KEY")
    
    print("="*60)
    print("🔑 ТЕСТ STEAM API КЛЮЧА")
    print("="*60)
    
    if not steam_key:
        print("❌ STEAM_API_KEY не найден в .env")
        return
    
    print(f"✅ Ключ найден: {steam_key[:8]}...{steam_key[-8:]}")
    print()
    
    # Создаём сервис с ключом
    service = OpenDotaService(steam_api_key=steam_key)
    await service.init()
    
    # Тестируем vanity URL
    test_url = "https://steamcommunity.com/id/Lord9000/"
    
    print(f"📝 Тестируем: {test_url}")
    print("-"*60)
    
    try:
        account_id = await service.parse_account_id(test_url)
        
        if account_id:
            print(f"\n✅ УСПЕХ!")
            print(f"   Account ID: {account_id}")
            print(f"   OpenDota: https://www.opendota.com/players/{account_id}")
            print(f"   Dotabuff: https://www.dotabuff.com/players/{account_id}")
            
            # Проверяем профиль
            print(f"\n📊 Проверяем профиль...")
            profile = await service.get_profile(account_id)
            if profile:
                print(f"   Имя: {profile.persona_name}")
                print(f"   Ранг: {profile.rank_name}")
        else:
            print(f"\n❌ Не удалось распарсить")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await service.close()
    
    print("\n" + "="*60)


if __name__ == "__main__":
    asyncio.run(test_steam_key())
