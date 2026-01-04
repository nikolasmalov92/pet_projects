def welcome_page():
    return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>VPN & Telegram Bot Service</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    margin: 0;
                    padding: 0;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                }
                .container {
                    background: rgba(255, 255, 255, 0.1);
                    backdrop-filter: blur(10px);
                    padding: 40px;
                    border-radius: 20px;
                    text-align: center;
                    max-width: 600px;
                    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
                }
                h1 {
                    font-size: 2.5em;
                    margin-bottom: 10px;
                    text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
                }
                .status {
                    display: inline-block;
                    padding: 8px 20px;
                    background: #10b981;
                    border-radius: 50px;
                    margin: 20px 0;
                    font-weight: bold;
                    animation: pulse 2s infinite;
                }
                @keyframes pulse {
                    0% { opacity: 1; }
                    50% { opacity: 0.8; }
                    100% { opacity: 1; }
                }
                .info {
                    background: rgba(255, 255, 255, 0.15);
                    padding: 20px;
                    border-radius: 10px;
                    margin: 20px 0;
                    text-align: left;
                }
                .bot-link {
                    display: inline-block;
                    margin-top: 20px;
                    padding: 12px 30px;
                    background: #3b82f6;
                    color: white;
                    text-decoration: none;
                    border-radius: 8px;
                    font-weight: bold;
                    transition: transform 0.3s;
                }
                .bot-link:hover {
                    transform: translateY(-2px);
                    background: #2563eb;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 VPN & Telegram Bot Service</h1>
                <div class="status">✅ Сервис работает</div>

                <div class="info">
                    <h3>📊 Статус сервисов:</h3>
                    <p>• 🤖 Telegram Bot: <strong>Работает</strong></p>
                    <p>• 🔒 VPN сервер: <strong>Активен</strong></p>
                    <p>• 🌐 Веб-сервер: <strong>Nginx 1.24.0</strong></p>
                    <p>• 🔄 SSL: <strong>Let's Encrypt</strong></p>
                </div>

                <div class="info">
                    <h3>📈 Мониторинг:</h3>
                    <p>🕒 Время работы: <span id="uptime">Загружается...</span></p>
                </div>

                <a href="https://t.me/WeatheWakeBot" class="bot-link" target="_blank">
                    🤖 Перейти к Telegram боту
                </a>

                <p style="margin-top: 30px; opacity: 0.8; font-size: 0.9em;">
                    © 2024 VPN & Bot Service | Автоматическое обновление
                </p>
            </div>

            <script>
                // Простой скрипт для отображения времени работы
                const startTime = Date.now();
                function updateUptime() {
                    const uptime = Date.now() - startTime;
                    const hours = Math.floor(uptime / (1000 * 60 * 60));
                    const minutes = Math.floor((uptime % (1000 * 60 * 60)) / (1000 * 60));
                    const seconds = Math.floor((uptime % (1000 * 60)) / 1000);
                    document.getElementById('uptime').textContent = 
                        `${hours}ч ${minutes}м ${seconds}с`;
                }
                setInterval(updateUptime, 1000);
                updateUptime();
            </script>
        </body>
        </html>
        """
