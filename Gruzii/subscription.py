import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum

DB_NAME = Path("database.db")


class SubscriptionType(Enum):
    """Типы подписок"""
    TRIAL = "trial"  # Пробная (24 часа)
    PAID = "paid"    # Платная (бессрочная или на длительный срок)


def init_db():
    """Инициализация базы данных и создание таблиц"""
    if not Path(DB_NAME).exists():
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
                CREATE TABLE IF NOT EXISTS Subscriptions (
                    user_id INTEGER PRIMARY KEY,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    subscription_type TEXT NOT NULL DEFAULT 'trial',
                    trial_used BOOLEAN DEFAULT 0
                )
            ''')
        conn.commit()
        conn.close()


class SubscriptionManager:
    """Класс для управления подписками пользователей"""

    TRIAL_DURATION_HOURS = 24  # Длительность пробной подписки в часах
    PAID_DURATION_DAYS = 365   # Длительность платной подписки в днях (по умолчанию 1 год)

    def __init__(self):
        """Инициализация менеджера подписок"""
        if not Path(DB_NAME).exists():
            init_db()
        self._ensure_subscription_table()

    def _ensure_subscription_table(self):
        """Создает таблицу подписок, если она не существует"""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Subscriptions (
                user_id INTEGER PRIMARY KEY,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                subscription_type TEXT NOT NULL DEFAULT 'trial',
                FOREIGN KEY (user_id) REFERENCES Users(id)
            )
        ''')
        
        # Добавляем колонку subscription_type, если её нет (для старых баз)
        try:
            cursor.execute("ALTER TABLE Subscriptions ADD COLUMN subscription_type TEXT DEFAULT 'trial'")
            conn.commit()
        except sqlite3.OperationalError:
            pass

        # Добавляем колонку trial_used, если её нет
        try:
            cursor.execute("ALTER TABLE Subscriptions ADD COLUMN trial_used BOOLEAN DEFAULT 0")
            conn.commit()
        except sqlite3.OperationalError:
            pass

        conn.close()

    def activate_trial_subscription(self, user_id: int) -> dict:
        """
        Активирует пробную подписку для пользователя на 24 часа

        Args:
            user_id: ID пользователя

        Returns:
            dict с информацией о подписке
            
        Raises:
            ValueError: если пользователь уже использовал пробную подписку
        """
        # Проверяем, использовал ли пользователь пробную подписку
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT trial_used FROM Subscriptions WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:  # trial_used = True
            raise ValueError("Пользователь уже использовал пробную подписку")
        
        subscription = self._activate_subscription(user_id, SubscriptionType.TRIAL)
        
        # Отмечаем, что пробная подписка использована
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE Subscriptions SET trial_used = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        return subscription

    def activate_paid_subscription(self, user_id: int, duration_days: int = None) -> dict:
        """
        Активирует платную подписку для пользователя
        
        Args:
            user_id: ID пользователя
            duration_days: длительность в днях (по умолчанию 365 дней = 1 год)
            
        Returns:
            dict с информацией о подписке
        """
        return self._activate_subscription(user_id, SubscriptionType.PAID, duration_days)

    def activate_subscription(self, user_id: int, sub_type: SubscriptionType = SubscriptionType.TRIAL, duration_days: int = None) -> dict:
        """
        Активирует подписку для пользователя
        
        Args:
            user_id: ID пользователя
            sub_type: тип подписки (TRIAL или PAID)
            duration_days: длительность в днях (переопределяет стандартную)
            
        Returns:
            dict с информацией о подписке
        """
        return self._activate_subscription(user_id, sub_type, duration_days)

    def _activate_subscription(self, user_id: int, sub_type: SubscriptionType = SubscriptionType.TRIAL, duration_days: int = None) -> dict:
        """Внутренний метод для активации подписки"""
        now = datetime.now()
        
        # Определяем длительность
        if sub_type == SubscriptionType.TRIAL:
            duration = timedelta(hours=self.TRIAL_DURATION_HOURS)
        else:  # PAID
            days = duration_days if duration_days else self.PAID_DURATION_DAYS
            duration = timedelta(days=days)
        
        end_time = now + duration

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Проверяем, есть ли уже подписка
        cursor.execute("SELECT user_id FROM Subscriptions WHERE user_id = ?", (user_id,))
        existing = cursor.fetchone()

        if existing:
            # Обновляем существующую подписку
            cursor.execute('''
                UPDATE Subscriptions 
                SET start_time = ?, end_time = ?, is_active = 1, subscription_type = ?
                WHERE user_id = ?
            ''', (now, end_time, sub_type.value, user_id))
        else:
            # Создаем новую подписку
            cursor.execute('''
                INSERT INTO Subscriptions (user_id, start_time, end_time, is_active, subscription_type)
                VALUES (?, ?, ?, 1, ?)
            ''', (user_id, now, end_time, sub_type.value))

        conn.commit()
        conn.close()

        return {
            "user_id": user_id,
            "start_time": now,
            "end_time": end_time,
            "is_active": True,
            "subscription_type": sub_type
        }

    def is_subscription_active(self, user_id: int) -> bool:
        """
        Проверяет, активна ли подписка у пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если подписка активна, иначе False
        """
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT is_active, end_time 
            FROM Subscriptions 
            WHERE user_id = ?
        ''', (user_id,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            return False

        is_active, end_time_str = result
        end_time = datetime.fromisoformat(end_time_str)

        # Подписка активна только если флаг is_active = 1 и время не истекло
        if not is_active:
            return False

        if datetime.now() > end_time:
            # Время подписки истекло, обновляем статус
            self._deactivate_subscription(user_id)
            return False

        return True

    def get_subscription_info(self, user_id: int) -> dict | None:
        """
        Получает информацию о подписке пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            dict с информацией о подписке или None
        """
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, start_time, end_time, is_active, subscription_type 
            FROM Subscriptions 
            WHERE user_id = ?
        ''', (user_id,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            return None

        user_id, start_time_str, end_time_str, is_active, sub_type = result
        
        return {
            "user_id": user_id,
            "start_time": datetime.fromisoformat(start_time_str),
            "end_time": datetime.fromisoformat(end_time_str),
            "is_active": is_active,
            "subscription_type": SubscriptionType(sub_type)
        }

    def deactivate_subscription(self, user_id: int) -> bool:
        """
        Деактивирует подписку пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если успешно, иначе False
        """
        return self._deactivate_subscription(user_id)

    def _deactivate_subscription(self, user_id: int) -> bool:
        """Внутренний метод для деактивации подписки"""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE Subscriptions 
            SET is_active = 0 
            WHERE user_id = ?
        ''', (user_id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()

        return affected > 0

    def get_time_remaining(self, user_id: int) -> timedelta | None:
        """
        Получает оставшееся время подписки
        
        Args:
            user_id: ID пользователя
            
        Returns:
            timedelta с оставшимся временем или None
        """
        info = self.get_subscription_info(user_id)
        if not info or not info["is_active"]:
            return None

        remaining = info["end_time"] - datetime.now()
        if remaining.total_seconds() <= 0:
            self._deactivate_subscription(user_id)
            return None

        return remaining

    def get_subscription_type(self, user_id: int) -> SubscriptionType | None:
        """
        Получает тип подписки пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            SubscriptionType или None
        """
        info = self.get_subscription_info(user_id)
        if not info:
            return None
        
        sub_type_str = info.get("subscription_type", "trial")
        return SubscriptionType(sub_type_str)

    def get_all_users_with_subscriptions(self) -> list[dict]:
        """
        Получает список всех пользователей с подписками
        
        Returns:
            list[dict] - список с информацией о подписках
        """
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.user_id, s.start_time, s.end_time, s.is_active, s.subscription_type
            FROM Subscriptions s
            ORDER BY s.user_id
        ''')
        results = []
        for row in cursor.fetchall():
            user_id, start_time_str, end_time_str, is_active, sub_type = row
            results.append({
                "user_id": user_id,
                "start_time": datetime.fromisoformat(start_time_str),
                "end_time": datetime.fromisoformat(end_time_str),
                "is_active": is_active,
                "subscription_type": SubscriptionType(sub_type),
                "time_remaining": self.get_formatted_time_remaining(user_id) if is_active else "Не активна"
            })
        conn.close()
        return results

    def delete_user(self, user_id: int) -> dict:
        """
        Полностью удаляет пользователя и его подписку из БД
        
        Args:
            user_id: ID пользователя
            
        Returns:
            dict с информацией о результате удаления
        """
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Проверяем, есть ли пользователь
        cursor.execute("SELECT user_id FROM Subscriptions WHERE user_id = ?", (user_id,))
        user_exists = cursor.fetchone() is not None
        if not user_exists:
            conn.close()
            return {"success": False, "message": "Пользователь не найден в базе"}
        
        # Удаляем подписку
        cursor.execute("DELETE FROM Subscriptions WHERE user_id = ?", (user_id,))
        subscription_deleted = cursor.rowcount > 0
        
        # Удаляем пользователя
        cursor.execute("DELETE FROM Subscriptions WHERE id = ?", (user_id,))
        user_deleted = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        return {
            "success": user_deleted,
            "subscription_deleted": subscription_deleted,
            "message": f"Пользователь {user_id} удалён" if user_deleted else "Ошибка при удалении"
        }

    def deactivate_all_user_subscriptions(self) -> int:
        """
        Деактивирует все подписки пользователей (для админа)
        
        Returns:
            Количество деактивированных подписок
        """
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE Subscriptions 
            SET is_active = 0
            WHERE is_active = 1
        ''')
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected

    def cleanup_expired(self) -> int:
        """
        Очищает все истекшие подписки
        
        Returns:
            Количество деактивированных подписок
        """
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        now = datetime.now()

        cursor.execute('''
            UPDATE Subscriptions 
            SET is_active = 0 
            WHERE is_active = 1 AND end_time < ?
        ''', (now,))
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()

        return affected

    def get_formatted_time_remaining(self, user_id: int) -> str:
        """
        Получает отформатированное оставшееся время подписки
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Строка с оставшимся временем (например "23ч 45м")
        """
        remaining = self.get_time_remaining(user_id)
        if not remaining:
            return "Подписка не активна"

        total_seconds = int(remaining.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        if hours > 0:
            return f"{hours}ч {minutes}м"
        else:
            return f"{minutes}м"


# Создаем глобальный экземпляр менеджера подписок
subscription_manager = SubscriptionManager()
