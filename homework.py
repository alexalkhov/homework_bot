import logging
import os
import time
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv


load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(
    'my_logger.log',
    maxBytes=50000000,
    backupCount=5
)
logger.addHandler(handler)


def check_tokens():
    """Функция проверяет введенные токены."""
    token_error = 'Отсутствует переменная окружения'
    if PRACTICUM_TOKEN is None:
        logger.critical(token_error)
    if TELEGRAM_TOKEN is None:
        logger.critical(token_error)
    if TELEGRAM_CHAT_ID is None:
        logger.critical(token_error)


def send_message(bot, message):
    """Функция отправляет сообщение."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception:
        logger.error('Cбой при отправке сообщения в Telegram')
    logger.debug(f'Сообщение {message} в Telegram отправлено')


def get_api_answer(timestamp):
    """Функция получает ответ от API."""
    try:
        response = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
    except Exception:
        logger.error('Отсутствуют ожидаемые ключи в ответе API')
    if response.status_code != 200:
        error_message = 'Статус страницы не равен 200'
        logger.error(error_message)
        raise requests.HTTPError(error_message)
    return response.json()


def check_response(response):
    """Функция проверяет соответствие ответа API."""
    if not isinstance(response, dict):
        raise TypeError('Некорректный формат ответа API. Ожидается словарь.')
    if 'homeworks' not in response:
        raise ValueError('Домашние работы не найдены')
    homework_statuses = response['homeworks']
    if not isinstance(homework_statuses, list):
        raise TypeError(
            'Данные домашних работ должны быть представлены в виде списка'
        )
    if not homework_statuses:
        logger.error('Отсутствуют ожидаемые ключи в ответе API')
    return homework_statuses


def parse_status(homework):
    """Функция получает статус домашней работы."""
    homework_status = homework.get('status')
    homework_name = homework.get('homework_name')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError('Статус домашней работы не найден')
    if not homework_name:
        raise KeyError('Имя домашней работы не найдено')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    if not all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        logger.critical('Отсутствуют переменные окружения')
        raise SystemExit(1)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    previous_status = None
    timestamp = 0
    while True:
        try:
            response = get_api_answer(timestamp)
            homework_statuses = check_response(response)
            homework = homework_statuses[0]
            current_status = homework.get('status')
            if current_status != previous_status:
                message = parse_status(homework)
                send_message(bot, message)
                previous_status = current_status
            time.sleep(RETRY_PERIOD)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
