get_user_notifications = """ select * FROM (
                            SELECT NotificationId, FromUserEmail, Title, Message, NotificationType, NotificationParams,
                                    IsRead, IsAccepted, CreatedAt
                            FROM S_UserNotifications
                            WHERE ToUserEmail = ?
                            AND   CreatedAt > datetime('now', '-7 days')
                            AND IsAccepted = 0
                            ) ORDER BY 1 DESC
                            """

get_all_user_notifications = """ select * FROM (
                            SELECT NotificationId, FromUserEmail, Title, Message, NotificationType, NotificationParams,
                                    IsRead, IsAccepted, CreatedAt
                                FROM S_UserNotifications
                                WHERE ToUserEmail = ?
                            ) ORDER BY 1 DESC LIMIT 1000
                            """

mark_notification_read = """
        UPDATE S_UserNotifications SET IsRead = 1, ReadAt = CURRENT_TIMESTAMP
        WHERE NotificationId = ? AND ToUserEmail = ?
        RETURNING NotificationId
                            """

accept_notification = """UPDATE S_UserNotifications
                        SET IsAccepted = ?, IsRead = 1, ReadAt = CURRENT_TIMESTAMP,
                            NotificationParams = json_set(COALESCE(NotificationParams, '{}'), '$.AcceptParams', ?)
                        WHERE NotificationId = ? AND ToUserEmail = ?"""

get_notification_params = """SELECT FromUserEmail, NotificationParams FROM S_UserNotifications
                                    WHERE NotificationId = ? AND ToUserEmail = ?"""
