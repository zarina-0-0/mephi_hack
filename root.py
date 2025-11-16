import json
import time
import requests
import base64
from datetime import datetime
from io import BytesIO


def generate_image(api_key, secret_key, prompt, return_type='file'):
    """
    Улучшенная функция для генерации изображения

    Args:
        api_key (str): Ваш API ключ
        secret_key (str): Ваш секретный ключ
        prompt (str): Описание изображения
        return_type (str): 'file' - путь к файлу, 'bytes' - бинарные данные
    """

    URL = 'https://api-key.fusionbrain.ai/'
    headers = {
        'X-Key': f'Key {api_key}',
        'X-Secret': f'Secret {secret_key}',
    }

    try:
        # 1. Получаем доступную модель
        response = requests.get(URL + 'key/api/v1/pipelines', headers=headers)
        pipelines = response.json()
        pipeline_id = pipelines[0]['id']
        print(f"Используется модель: {pipelines[0]['name']}")

        # 2. Отправляем запрос на генерацию
        params = {
            "type": "GENERATE",
            "numImages": 1,
            "width": 1024,
            "height": 1024,
            "generateParams": {"query": prompt}
        }

        data = {
            'pipeline_id': (None, pipeline_id),
            'params': (None, json.dumps(params), 'application/json')
        }

        response = requests.post(URL + 'key/api/v1/pipeline/run', headers=headers, files=data)
        request_data = response.json()
        uuid = request_data['uuid']
        print(f"Задание создано: {uuid}")

        # 3. Ожидаем завершения генерации
        for i in range(20):
            time.sleep(10)
            response = requests.get(URL + 'key/api/v1/pipeline/status/' + uuid, headers=headers)
            status_data = response.json()

            if status_data['status'] == 'DONE':
                # 4. Получаем изображение
                image_base64 = status_data['result']['files'][0]
                image_data = base64.b64decode(image_base64)

                if return_type == 'bytes':
                    return image_data
                else:
                    filename = f"kandinsky_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    with open(filename, 'wb') as f:
                        f.write(image_data)
                    return filename

            elif status_data['status'] == 'FAIL':
                print(f"❌ Ошибка генерации: {status_data.get('errorDescription', 'Неизвестная ошибка')}")
                return None

        print("❌ Превышено время ожидания")
        return None

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None


def generate_and_save_image(api_key, secret_key, prompt):
    return generate_image(api_key, secret_key, prompt, return_type='file')