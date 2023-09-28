import logging
import os
import time
from http import HTTPStatus
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
    tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    for token in tokens:
        if token is None:
            logger.critical('Отсутствует переменная окружения')
            raise SystemExit(1)


def send_message(bot, message):
    """Функция отправляет сообщение."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug('Сообщение в Telegram отправлено')
    except Exception:
        logger.error('Cбой при отправке сообщения в Telegram')


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
    if response.status_code != HTTPStatus.OK:
        error_message = 'Некорректный статус страницы'
        logger.error(error_message)
        raise requests.HTTPError(error_message)
    return response.json()


def check_response(response):
    """Функция проверяет соответствие ответа API."""
    if not isinstance(response, dict):
        raise TypeError('Некорректный формат ответа API. Ожидается словарь.')
    if 'homeworks' not in response:
        raise ValueError('Домашние работы не найдены')
    if not isinstance(homework_statuses := response.get('homeworks'), list):
        raise TypeError(
            'Данные домашних работ должны быть представлены в виде списка'
        )
    if not homework_statuses:
        logger.error('Отсутствуют ожидаемые ключи в ответе API')
    return homework_statuses


def parse_status(homework):
    """Функция получает статус домашней работы."""
    if (homework_status := homework.get('status')) not in HOMEWORK_VERDICTS:
        raise KeyError('Статус домашней работы не найден')
    if not (homework_name := homework.get('homework_name')):
        raise KeyError('Имя домашней работы не найдено')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    previous_status = None
    timestamp = 0
    while True:
        try:
            response = get_api_answer(timestamp)
            homework_status = check_response(response)
            if len(homework_status) > 0:
                homework = homework_status[0]
                current_status = homework.get('status')
                if current_status == previous_status:
                    logger.debug('Отсутствуют новые статусы домашней работы.')
                    continue
                message = parse_status(homework)
                send_message(bot, message)
                previous_status = current_status
            else:
                logger.debug('Список домашних заданий пуст.')
            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
