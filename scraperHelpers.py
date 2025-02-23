from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
import time
import random
import json

# Stock-checking logic (old main)
def stock_checker(shared_items, stock_check_event, config):
    while True:
        stock_check_event.wait()

        # Her döngüde config'i yeniden yükle
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
            sleep_min_seconds = config.get('sleep_min_seconds', 30)
            sleep_max_seconds = config.get('sleep_max_seconds', 60)
            items = config.get('items', [])
        except Exception as e:
            print(f"Error loading config: {e}")
            time.sleep(60)  # Hata durumunda 1 dakika bekle
            continue

        service = Service(config.get('chrome_driver_path'))
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        )
        driver = webdriver.Chrome(service=service, options=chrome_options)

        notification_message = ""  # Bildirim mesajını toplamak için
        items_to_remove = []  # Silinecek ürünleri toplamak için
        sizes_to_remove = {}  # URL bazında silinecek bedenleri toplamak için

        try:
            for item in items:  # shared_items yerine güncel items'ı kullan
                try:
                    url = item.get("url")
                    store = item.get("store")
                    sizes = item.get("sizes_to_check")
                    driver.get(url)
                    print(f"Checking stock for URL: {url}")
                    
                    if store.lower() == "zara":
                        size_in_stock = check_stock_zara(driver, sizes)
                        if size_in_stock:
                            print(size_in_stock)
                            notification_message += size_in_stock + "\n"
                            # Stokta olan bedenleri kaydet
                            found_sizes = []
                            for line in size_in_stock.split('\n'):
                                if "Bedeninde stok bulundu" in line:
                                    size = line.split("için")[1].split("Bedeninde")[0].strip()
                                    found_sizes.append(size)
                            if url not in sizes_to_remove:
                                sizes_to_remove[url] = found_sizes
                            else:
                                sizes_to_remove[url].extend(found_sizes)
                        else:
                            print(f"{url} linkli {sizes} Beden ürün için stok bulunamadı.")
                    elif store.lower() == "pullandbear":
                        in_stock = check_stock_pull_and_bear(driver, sizes)
                        if in_stock:
                            print(in_stock)
                            notification_message += in_stock + "\n"
                            # Stokta olan bedenleri kaydet
                            found_sizes = []
                            for line in in_stock.split('\n'):
                                if "Bedeninde stok bulundu" in line:
                                    size = line.split("için")[1].split("Bedeninde")[0].strip()
                                    found_sizes.append(size)
                            if url not in sizes_to_remove:
                                sizes_to_remove[url] = found_sizes
                            else:
                                sizes_to_remove[url].extend(found_sizes)
                        else:
                            print(f"{url} linkli ürün için stok bulunamadı.")
                    elif store.lower() == "rossmann":
                        in_stock = rossmannStockCheck(driver)
                        if in_stock:
                            print(in_stock)
                            notification_message += in_stock + "\n"
                            items_to_remove.append(url)  # Rossmann ürünlerini direkt sil
                        else:
                            print(f"{url} linkli ürün için stok bulunamadı.")
                    elif store.lower() == "bershka":
                        size_in_stock = check_stock_bershka(driver, sizes)
                        if size_in_stock:
                            print(size_in_stock)
                            notification_message += size_in_stock + "\n"
                            # Stokta olan bedenleri kaydet
                            found_sizes = []
                            for line in size_in_stock.split('\n'):
                                if "Bedeninde stok bulundu" in line:
                                    size = line.split("için")[1].split("Bedeninde")[0].strip()
                                    found_sizes.append(size)
                            if url not in sizes_to_remove:
                                sizes_to_remove[url] = found_sizes
                            else:
                                sizes_to_remove[url].extend(found_sizes)
                        else:
                            print(f"{url} linkli {sizes} Beden ürün için stok bulunamadı.")
                    else:
                        print(f"Unsupported store: {store}")
                except Exception as e:
                    print(f"Error checking {url}: {e}")

            # Config'i güncelle
            if notification_message:
                with open('config.json', 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # Stokta olan ürünleri ve bedenleri kaldır
                updated_items = []
                for item in config_data['items']:
                    url = item['url']
                    if url in items_to_remove:
                        continue  # Bu ürünü tamamen atla
                    
                    if url in sizes_to_remove:
                        if 'sizes_to_check' in item:
                            # Stokta olan bedenleri kaldır
                            item['sizes_to_check'] = [size for size in item['sizes_to_check'] 
                                                    if size not in sizes_to_remove[url]]
                            # Eğer takip edilecek beden kalmadıysa, ürünü tamamen kaldır
                            if item['sizes_to_check']:
                                updated_items.append(item)
                    else:
                        updated_items.append(item)
                
                config_data['items'] = updated_items
                
                with open('config.json', 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, indent=4)

        finally:
            driver.quit()
            sleep_time = random.randint(sleep_min_seconds, sleep_max_seconds)
            
            # Eğer bildirilecek stok varsa, önce bildirimi gönder
            if notification_message:
                print(f"\nBir sonraki kontrol {sleep_time // 60} dakika ve {sleep_time % 60} saniye sonra yapılacak...")
                return notification_message.strip()
            
            # Stok yoksa normal bekleme mesajını göster
            print(f"Sleeping for {sleep_time // 60} minutes and {sleep_time % 60} seconds...")
            time.sleep(sleep_time)

# Function to check stock availability (For ZARA)
def check_stock_zara(driver, sizes_to_check):
    return_string = ""
    try:
        # Proceed with the stock check
        print("Waiting for the size selector items to appear...")
        wait = WebDriverWait(driver, 40)
        
        # Ürün adını al
        product_name = driver.find_element(By.XPATH, '//h1[@data-qa-qualifier="product-detail-info-name"]').text
        
        # Çanta kontrolü
        if 'BAG' in sizes_to_check:
            try:
                add_button = driver.find_element(By.XPATH, '//button[@data-qa-action="add-to-cart"]')
                if not "disabled" in add_button.get_attribute("class"):
                    return_string += f"{product_name} için stok bulundu, link: {driver.current_url}\n"
            except:
                pass
        else:
            # Normal beden kontrolü
            wait.until(EC.presence_of_element_located((By.XPATH, '//button[@data-qa-action="add-to-cart"]')))
            add_to_cart_button = driver.find_element(By.XPATH, '//button[@data-qa-action="add-to-cart"]')
            add_to_cart_button.click()

            sizes_in_stock = driver.find_elements(By.XPATH, '//button[@data-qa-action="size-in-stock"]')

            for size in sizes_in_stock:
                size_text = size.text.split()[0]
                if size_text in sizes_to_check:
                    return_string += f"{product_name} için {size_text} Bedeninde stok bulundu, link: {driver.current_url}\n"

        if return_string == "":
            return None
        
        return return_string
    except Exception as e:
        print(f"An error occurred during the operation: {e}")
        return None

# Function to check stock availability (For Rossmann)
def rossmannStockCheck(driver):
    return_string = ""
    wait = WebDriverWait(driver, 25)
    try:
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product-add-form")))
    except Exception:
        return None
    
    try:
        product_name = driver.find_element(By.XPATH,'//ul[@class="items"]').find_elements(By.TAG_NAME,'li')[-1].text
    except Exception as e :
        product_name = ""
        print("Product Name scrape error:",e)
    try:
        # Locate the button with the text "Sepete Ekle"
        button = driver.find_element(By.XPATH, "//button[@type='submit' and contains(., 'Sepete Ekle')]")
        if button:
            return_string += f"{product_name} için stok bulundu, link: {driver.current_url}\n"
            return return_string
    except Exception:
        return None

# Function to check stock availability (For Bershka)
def check_stock_bershka(driver, sizes_to_check):
    return_string = ""
    try:
        # Proceed with the stock check
        print("Waiting for the size buttons to appear...")
        wait = WebDriverWait(driver, 40)
        product_name = driver.find_element(By.XPATH, '//h1[@class="product-detail-info-layout__title bds-typography-heading-xs"]').text
        # Çanta kontrolü
        if 'BAG' in sizes_to_check:
            try:
                wait.until(EC.presence_of_element_located((By.XPATH, '//button[@data-qa-anchor="pdpViewSimilarsButton"]')))
                driver.find_element(By.XPATH,'//button[@data-qa-anchor="pdpViewSimilarsButton"]')    
            except:
                add_button = driver.find_element(By.XPATH, "//button[@data-qa-anchor='addToCartSizeBtn' or @data-qa-anchor='addToCartBtn']")
                if not "disabled" in add_button.get_attribute("class"):
                    return_string += f"{product_name} için stok bulundu, link: {driver.current_url}\n"
        else:
            # Normal beden kontrolü
            wait.until(EC.presence_of_element_located((By.XPATH, "//button[@data-qa-anchor='addToCartSizeBtn' or @data-qa-anchor='addToCartBtn']")))
            size_elements = driver.find_elements(By.CSS_SELECTOR, "button[data-qa-anchor='sizeListItem']")

            for button in size_elements:
                try:
                    size_label = button.find_element(By.CSS_SELECTOR, "span.text__label").text.strip()
                    if size_label in sizes_to_check:
                        if not button.get_attribute("class").__contains__("is-disabled"):
                            return_string += f"{product_name} için {size_label} Bedeninde stok bulundu, link: {driver.current_url}\n"
                except Exception as e:
                    print(f"Error processing size element: {e}")
                    continue

        if return_string == "":
            return None
        return return_string
    except Exception as e:
        print(f"An error occurred during the operation: {e}")
        return None

# Function to check stock availability (For Pull&Bear)
def check_stock_pull_and_bear(driver, sizes_to_check):
    return_string = ""
    try:
        # Proceed with the stock check
        print("Waiting for the size buttons to appear...")
        wait = WebDriverWait(driver, 40)
        product_name = driver.find_element(By.XPATH, '//h1[@id="titleProductCard"]').text

        # Normal beden kontrolü
        wait.until(EC.presence_of_element_located((By.XPATH, '//div[@class="c-product-info--buttons-container"]/button')))

        size_selector = driver.find_element(By.CSS_SELECTOR, "size-selector-with-length")
        shadow_root_1 = driver.execute_script("return arguments[0].shadowRoot", size_selector)

        size_select = shadow_root_1.find_element(By.CSS_SELECTOR, "size-selector-select")
        shadow_root_2 = driver.execute_script("return arguments[0].shadowRoot", size_select)

        size_list = shadow_root_2.find_element(By.CSS_SELECTOR, "size-list")
        shadow_root_3 = driver.execute_script("return arguments[0].shadowRoot", size_list)

        size_elements = shadow_root_3.find_elements(By.CSS_SELECTOR, "button")

        for button in size_elements:
            try:
                spans = button.find_elements(By.TAG_NAME,'span')
                size_label = spans[0].text
                if size_label in sizes_to_check:
                    if len(spans) != 2:  # Stokta var
                        return_string += f"{product_name} için {size_label} Bedeninde stok bulundu, link: {driver.current_url}\n"
            except Exception as e:
                print(f"Error processing size element: {e}")
                continue

        if return_string == "":
            return None
        
        return return_string
    except Exception as e:
        print(f"An error occurred during the operation: {e}")
        return None

def watsonsChecker(driver):
    wait = WebDriverWait(driver, 40)
    try:
        element = wait.until(EC.presence_of_all_elements_located(By.CLASS_NAME, "product-grid-manager__view-mount"))
        text = element.text.strip()
        return not ("0 ürün") in text
    except:
        return False