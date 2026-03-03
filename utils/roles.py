"""Модуль для проверки ролей и прав доступа."""

import logging
from functools import wraps
from typing import List, Callable, Any
from telegram import Update
from telegram.ext import ContextTypes

from database import Database, get_db_pool

logger = logging.getLogger(__name__)

# Словарь для красивого отображения ролей
ROLE_NAMES = {
    'superadmin': '👑 Суперадмин',
    'admin': '📊 УМСиИ',
    'manager': '📋 Начальник отдела',
    'engineer': '🔧 Инженер',
    'viewer': '👁️ Наблюдатель'
}

# Матрица прав (какие роли имеют доступ к каким функциям)
ROLE_PERMISSIONS = {
    'admin_panel': ['superadmin'],
    'assign': ['superadmin', 'admin', 'manager'],
    'create_task': ['superadmin', 'admin', 'manager'],
    'view_stats': ['superadmin', 'admin', 'manager'],
    'manage_users': ['superadmin'],
    'manage_auditories': ['superadmin', 'manager'],
}


class RoleError(Exception):
    """Исключение для ошибок доступа."""
    pass


async def get_user_role(user_id: int) -> str:
    """
    Получает роль пользователя из БД.
    
    Args:
        user_id: Telegram ID пользователя
        
    Returns:
        str: роль пользователя (по умолчанию 'engineer')
    """
    user = await Database.get_user(user_id)
    return user.get('role', 'engineer') if user else 'engineer'


def require_roles(allowed_roles: List[str]):
    """
    Декоратор для проверки роли пользователя.
    
    Args:
        allowed_roles: список разрешённых ролей
        
    Returns:
        декорированная функция
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs) -> Any:
            # Определяем user_id из разных типов объектов
            if update.callback_query:
                user_id = update.callback_query.from_user.id
            elif update.message:
                user_id = update.effective_user.id
            else:
                user_id = None
            
            if not user_id:
                logger.error("Не удалось определить user_id")
                return
            
            # Получаем роль пользователя
            user_role = await get_user_role(user_id)
            
            # Проверяем, есть ли роль в списке разрешённых
            if user_role not in allowed_roles:
                role_names = [ROLE_NAMES.get(r, r) for r in allowed_roles]
                message = f"⛔ У вас нет прав для выполнения этого действия.\n"
                message += f"Требуются права: {', '.join(role_names)}"
                
                # Отправляем сообщение в зависимости от типа update
                if update.callback_query:
                    await update.callback_query.answer(message, show_alert=True)
                elif update.message:
                    await update.message.reply_text(message)
                
                logger.warning(f"Пользователь {user_id} с ролью {user_role} попытался вызвать {func.__name__}")
                return None
            
            # Если проверка пройдена, вызываем функцию
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator


def check_permission(permission: str):
    """
    Декоратор для проверки конкретного права.
    
    Args:
        permission: название права из ROLE_PERMISSIONS
        
    Returns:
        декорированная функция
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs) -> Any:
            # Определяем user_id
            if update.callback_query:
                user_id = update.callback_query.from_user.id
            elif update.message:
                user_id = update.effective_user.id
            else:
                user_id = None
            
            if not user_id:
                logger.error("Не удалось определить user_id")
                return
            
            # Получаем роль пользователя
            user_role = await get_user_role(user_id)
            
            # Проверяем, есть ли у роли это право
            allowed_roles = ROLE_PERMISSIONS.get(permission, [])
            
            if user_role not in allowed_roles:
                logger.warning(f"Пользователь {user_id} с ролью {user_role} не имеет права {permission}")
                if update.callback_query:
                    await update.callback_query.answer("⛔ Недостаточно прав", show_alert=True)
                elif update.message:
                    await update.message.reply_text("⛔ У вас нет прав для этого действия.")
                return None
            
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator


async def set_user_role(admin_id: int, target_user_id: int, new_role: str) -> bool:
    """
    Устанавливает роль пользователю (только для superadmin).
    
    Args:
        admin_id: ID администратора, выполняющего действие
        target_user_id: ID целевого пользователя
        new_role: новая роль
        
    Returns:
        bool: успешно ли выполнено
    """
    # Проверяем, что админ действительно superadmin
    admin_role = await get_user_role(admin_id)
    if admin_role != 'superadmin':
        logger.warning(f"Пользователь {admin_id} с ролью {admin_role} пытался изменить роль")
        return False
    
    # Проверяем допустимость роли
    valid_roles = ['superadmin', 'admin', 'manager', 'engineer', 'viewer']
    if new_role not in valid_roles:
        logger.error(f"Недопустимая роль: {new_role}")
        return False
    
    # Обновляем роль в БД
    pool = get_db_pool()
    await pool.execute(
        "UPDATE users SET role = $1 WHERE telegram_id = $2",
        new_role,
        target_user_id,
    )
    
    logger.info(f"Роль пользователя {target_user_id} изменена на {new_role}")
    return True