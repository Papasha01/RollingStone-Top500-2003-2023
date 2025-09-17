import time
import csv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import os
import unicodedata

def clean_text(text):
    """
    Очищает текст от специальных символов и нормализует его
    """
    if not text:
        return 'N/A'
    
    # Нормализуем юникод
    text = unicodedata.normalize('NFKD', text)
    
    # Удаляем непечатаемые символы, кроме табуляции и новых строк
    text = ''.join(char for char in text if unicodedata.category(char)[0] != 'C' or char in ['\n', '\t'])
    
    # Заменяем множественные переводы строк и пробелы на одинарные
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    text = ' '.join(lines)
    
    # Убираем лишние пробелы
    text = ' '.join(text.split())
    
    return text if text else 'N/A'

def parse_rollingstone_page(driver, url):
    """
    Парсинг одной страницы Rolling Stone
    """
    try:
        print(f"Открываем страницу: {url}")
        driver.get(url)
        
        # Ждем загрузки страницы
        print("Ждем загрузки страницы...")
        wait = WebDriverWait(driver, 20)
        
        # Ищем контейнер с альбомами
        print("Ожидаем появления контейнера с альбомами...")
        try:
            gallery_container = wait.until(
                EC.presence_of_element_located((By.ID, "pmc-gallery-vertical"))
            )
            print("Контейнер с альбомами найден")
        except TimeoutException:
            print("Контейнер не был найден за отведенное время")
            return []
        
        # Ждем, пока загрузятся все элементы с data-slide-id (все карточки)
        print("Ожидаем загрузки всех карточек...")
        try:
            # Ожидаем появления всех карточек (ожидаем минимум 10 карточек)
            wait.until(
                lambda driver: len(driver.find_elements(By.CSS_SELECTOR, "[data-slide-id]")) >= 10
            )
            print("Все карточки загружены")
            
            # Дополнительно ждем загрузки изображений в каждой карточке
            slide_elements = driver.find_elements(By.CSS_SELECTOR, "[data-slide-id]")
            print(f"Найдено {len(slide_elements)} карточек, ожидаем загрузки изображений...")
            
            # Ждем загрузки изображений для каждой карточки
            for i, element in enumerate(slide_elements):
                try:
                    # Ждем появления изображения в карточке
                    img_wait = WebDriverWait(driver, 10)
                    img_wait.until(
                        EC.presence_of_element_located((
                            By.CSS_SELECTOR, 
                            f"[data-slide-id='{element.get_attribute('data-slide-id')}'] .c-gallery-vertical-album__image"
                        ))
                    )
                    # Ждем, пока у изображения появится атрибут src
                    img_wait.until(
                        lambda driver: element.find_element(
                            By.CLASS_NAME, "c-gallery-vertical-album__image"
                        ).get_attribute('src') and 
                        not element.find_element(
                            By.CLASS_NAME, "c-gallery-vertical-album__image"
                        ).get_attribute('src').endswith('loading.gif')
                    )
                    print(f"Изображение для карточки {i+1} загружено")
                except TimeoutException:
                    print(f"Не удалось дождаться загрузки изображения для карточки {i+1}")
                    continue
                    
        except TimeoutException:
            print("Не удалось дождаться загрузки всех карточек")
        
        # Даем немного времени для полной загрузки
        time.sleep(3)
        
        # Перепроверяем контент
        try:
            # Ищем элементы с data-slide-id
            slide_elements = driver.find_elements(By.CSS_SELECTOR, "[data-slide-id]")
            print(f"Найдено элементов с data-slide-id: {len(slide_elements)}")
            
            if len(slide_elements) == 0:
                print("Не найдено элементов с альбомами")
                return []
            
            # Проверяем наличие заглушки
            loader_elements = driver.find_elements(By.CLASS_NAME, "c-gallery-vertical-loader")
            print(f"Элементов заглушки: {len(loader_elements)}")
            
            # Для каждого найденного элемента пробуем получить данные
            albums_data = []
            
            # Обрабатываем все найденные элементы
            for i, element in enumerate(slide_elements):
                try:
                    album_data = {}
                    
                    # Получаем ID слайда
                    slide_id = element.get_attribute('data-slide-id')
                    album_data['slide_id'] = clean_text(slide_id) if slide_id else f'unknown_{i}'
                    
                    # Пытаемся найти номер
                    try:
                        number_element = element.find_element(By.CLASS_NAME, "c-gallery-vertical-album__number")
                        album_data['number'] = clean_text(number_element.text)
                    except NoSuchElementException:
                        album_data['number'] = 'N/A'
                    
                    # Пытаемся найти название
                    try:
                        title_element = element.find_element(By.CLASS_NAME, "c-gallery-vertical-album__title")
                        album_data['title'] = clean_text(title_element.text)
                    except NoSuchElementException:
                        album_data['title'] = 'N/A'
                        
                    # Пытаемся найти подзаголовок
                    try:
                        subtitle_element = element.find_element(By.CLASS_NAME, "c-gallery-vertical-album__subtitle-1")
                        album_data['subtitle'] = clean_text(subtitle_element.text)
                    except NoSuchElementException:
                        album_data['subtitle'] = 'N/A'
                    
                    # Пытаемся найти изображение
                    try:
                        img_element = element.find_element(By.CLASS_NAME, "c-gallery-vertical-album__image")
                        image_src = img_element.get_attribute('src')
                        album_data['image_url'] = clean_text(image_src) if image_src else 'N/A'
                    except NoSuchElementException:
                        album_data['image_url'] = 'N/A'
                    
                    # Пытаемся найти описание
                    try:
                        desc_element = element.find_element(By.CLASS_NAME, "c-gallery-vertical-album__description")
                        desc_text = desc_element.text
                        album_data['description'] = clean_text(desc_text)
                    except NoSuchElementException:
                        album_data['description'] = 'N/A'
                    
                    albums_data.append(album_data)
                    print(f"Обработана карточка {i+1}: {album_data.get('title', 'Unknown')}")
                    
                except Exception as e:
                    print(f"Ошибка обработки карточки {i+1}: {str(e)}")
                    continue
            
            return albums_data
                
        except Exception as e:
            print(f"Ошибка при поиске карточек: {str(e)}")
            return []
            
    except Exception as e:
        print(f"Ошибка при обработке страницы {url}: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def parse_rollingstone_with_selenium(urls):
    """
    Парсинг Rolling Stone с использованием Selenium для динамического контента
    Обрабатывает массив ссылок
    """
    # Настройки Chrome
    chrome_options = Options()
    # chrome_options.add_argument('--headless')  # Уберите комментарий для headless режима
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    chrome_options.add_argument('--ignore-ssl-errors=yes')
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--disable-web-security')
    chrome_options.add_argument('--disable-features=VizDisplayCompositor')
    
    driver = None
    all_albums_data = []
    
    try:
        print("Запускаем браузер...")
        driver = webdriver.Chrome(options=chrome_options)
        
        # Обрабатываем каждую ссылку
        for url in urls:
            print(f"\nОбрабатываем ссылку: {url}")
            albums_data = parse_rollingstone_page(driver, url)
            all_albums_data.extend(albums_data)
            print(f"Добавлено {len(albums_data)} записей")
        
    except Exception as e:
        print(f"Основная ошибка: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            print("Закрываем браузер...")
            driver.quit()
            print("Браузер закрыт")
    
    return all_albums_data

def save_to_csv(data, filename='rollingstone_albums.csv'):
    """Сохраняет данные в CSV файл (добавляет в конец, если файл существует)"""
    if not data:
        print("Нет данных для сохранения")
        return
    
    # Определяем заголовки
    fieldnames = ['slide_id', 'number', 'title', 'subtitle', 'image_url', 'description']
    
    try:
        # Проверяем, существует ли файл
        file_exists = os.path.isfile(filename)
        
        with open(filename, 'a' if file_exists else 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            # Записываем заголовки, если файл новый
            if not file_exists:
                writer.writeheader()
            
            # Записываем данные
            for row in data:
                writer.writerow(row)
        
        print(f"Данные успешно {'добавлены в' if file_exists else 'сохранены в'} файл {filename}")
        
    except Exception as e:
        print(f"Ошибка при сохранении CSV: {str(e)}")

def main():
    """
    Главная функция
    """
    print("Начинаем парсинг Rolling Stone 500 greatest albums с использованием Selenium...")
    
    # Массив ссылок для парсинга
    urls = [
        "https://www.rollingstone.com/music/music-lists/best-albums-of-all-time-1062063/buzzcocks-singles-going-steady-2-1062983/"
    ]
    
    # Парсим данные
    albums_data = parse_rollingstone_with_selenium(urls)
    
    if albums_data:
        print(f"\nНайдено {len(albums_data)} альбомов:")
        
        # Выводим первые несколько записей для проверки
        for i, album in enumerate(albums_data[:3]):
            print(f"\n{i+1}. Slide ID: {album.get('slide_id', 'N/A')}")
            print(f"   Номер: {album.get('number', 'N/A')}")
            print(f"   Название: {album.get('title', 'N/A')}")
            print(f"   Подзаголовок: {album.get('subtitle', 'N/A')}")
            print(f"   Изображение: {album.get('image_url', 'N/A')}")
            print(f"   Описание: {album.get('description', 'N/A')}")
        
        # Сохраняем в CSV
        save_to_csv(albums_data)
        
    else:
        print("\nНе удалось найти данные для парсинга")
        print("Проверьте, установлен ли chromedriver и соответствует ли он версии Chrome")

if __name__ == "__main__":
    main()